import ast
import sys
from pathlib import Path
NAMESPACE = 'validate_imports'
TASK_ID = 'validate_imports'

def _parse_directives(source_lines):
    directives = {}
    for i, line in enumerate(source_lines, start=1):
        if '# cruel:' in line:
            raw = line.split('# cruel:', 1)[1].strip()
            if raw:
                directives[i] = sorted((name.strip() for name in raw.split(',') if name.strip()))
    return directives

def _module_top_level_import_ids(tree):
    ids = set()

    def walk_body(body):
        for node in body:
            if isinstance(node, ast.ImportFrom):
                ids.add(id(node))
            elif isinstance(node, (ast.If, ast.Try)):
                walk_body(getattr(node, 'body', []))
                walk_body(getattr(node, 'orelse', []))
                walk_body(getattr(node, 'finalbody', []))
                for handler in getattr(node, 'handlers', []):
                    walk_body(handler.body)
    walk_body(tree.body)
    return ids

def _extract_relative_imports(source_path):
    text = source_path.read_text(encoding='utf-8')
    tree = ast.parse(text, filename=str(source_path))
    directives = _parse_directives(text.splitlines())
    top_level_ids = _module_top_level_import_ids(tree)
    imports = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            continue
        names = [[alias.name, alias.asname] for alias in node.names]
        imports.append({'level': node.level, 'module': node.module, 'names': names, 'lineno': node.lineno, 'col': node.col_offset, 'directives': directives.get(node.lineno, []), 'top_level': id(node) in top_level_ids})
    return imports

def _resolve_target_parts(file_path, pysrc_dir, level, module):
    package_parts = list(file_path.relative_to(pysrc_dir).parent.parts)
    climb = level - 1
    if climb > len(package_parts):
        return None
    if climb > 0:
        package_parts = package_parts[:len(package_parts) - climb]
    if module:
        package_parts.extend(module.split('.'))
    return tuple(package_parts)

def _resolve_target(pysrc_dir, parts):
    if not parts:
        init_path = pysrc_dir / '__init__.py'
        if init_path.is_file():
            return ('package', init_path)
        return ('no_init', pysrc_dir)
    module_path = pysrc_dir.joinpath(*parts[:-1], f'{parts[-1]}.py')
    if module_path.is_file():
        return ('module', module_path)
    package_dir = pysrc_dir.joinpath(*parts)
    if package_dir.is_dir():
        init_path = package_dir / '__init__.py'
        if init_path.is_file():
            return ('package', init_path)
        return ('no_init', package_dir)
    return (None, None)

def _rel(path, project_root):
    return path.relative_to(project_root).as_posix()

def _source_line(project_root, rel_path, lineno):
    try:
        lines = (project_root / rel_path).read_text(encoding='utf-8').splitlines()
    except OSError:
        return None
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1]
    return None

def _refresh_cache(sources, pysrc_dir, cruel_bin, project_root, buildlog, cache):
    cached = cache.load_json(project_root, NAMESPACE)
    fresh = {}
    total = len(sources)
    for index, source_path in enumerate(sources, start=1):
        rel_path = _rel(source_path, project_root)
        digest = cache.file_hash(cruel_bin, source_path)
        entry = cached.get(rel_path)
        if entry is not None and entry.get('hash') == digest:
            fresh[rel_path] = entry
            buildlog.task_progress(TASK_ID, index * 100 // total)
            continue
        buildlog.info(f'checking imports {rel_path}')
        try:
            imports = _extract_relative_imports(source_path)
        except SyntaxError:
            imports = []
        fresh[rel_path] = {'hash': digest, 'imports': imports}
        buildlog.task_progress(TASK_ID, index * 100 // total)
    cache.save_json(project_root, NAMESPACE, fresh)
    return fresh

def _check_modules_and_objects(fresh, pysrc_dir, project_root):
    errors = []
    for rel_path, entry in fresh.items():
        source_path = project_root / rel_path
        for imp in entry['imports']:
            directives = set(imp['directives'])
            parts = _resolve_target_parts(source_path, pysrc_dir, imp['level'], imp['module'])
            if parts is None:
                if 'missing_imports' not in directives:
                    errors.append(_missing_module_error(rel_path, imp))
                continue
            kind, target_path = _resolve_target(pysrc_dir, parts)
            if kind is None:
                if 'missing_imports' not in directives:
                    errors.append(_missing_module_error(rel_path, imp))
                continue
            if kind == 'no_init':
                continue
            if 'missing_import_objects' in directives:
                continue
            if kind == 'package':
                errors.extend(_check_package_names(rel_path, imp, pysrc_dir, parts, target_path, project_root))
                continue
            available = _read_top_level_names(target_path)
            if available is None:
                continue
            for name, _asname in imp['names']:
                if name == '*':
                    continue
                if name not in available:
                    errors.append({'path': rel_path, 'lineno': imp['lineno'], 'col': imp['col'], 'headline': f"unknown object '{name}'", 'help': f"'{name}' is not defined in {_rel(target_path, project_root)}"})
    return errors

def _check_package_names(rel_path, imp, pysrc_dir, parts, init_path, project_root):
    available = _read_top_level_names(init_path)
    errors = []
    for name, _asname in imp['names']:
        if name == '*':
            continue
        sub_kind, _sub_path = _resolve_target(pysrc_dir, parts + (name,))
        if sub_kind is not None:
            continue
        if available is None:
            continue
        if name not in available:
            errors.append({'path': rel_path, 'lineno': imp['lineno'], 'col': imp['col'], 'headline': f"unknown object '{name}'", 'help': f"'{name}' is not defined in {_rel(init_path, project_root)}"})
    return errors

def _missing_module_error(rel_path, imp):
    dots = '.' * imp['level']
    spec = f"{dots}{imp['module'] or ''}"
    return {'path': rel_path, 'lineno': imp['lineno'], 'col': imp['col'], 'headline': f"unresolved import '{spec}'", 'help': 'target module not found'}

def _read_top_level_names(module_path):
    try:
        text = module_path.read_text(encoding='utf-8')
        tree = ast.parse(text, filename=str(module_path))
    except (OSError, SyntaxError):
        return None
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    return None
                names.add(alias.asname or alias.name)
    return names

def _check_init_files(fresh, pysrc_dir, project_root):
    errors = []
    reported = set()
    for rel_path, entry in fresh.items():
        source_path = project_root / rel_path
        for imp in entry['imports']:
            parts = _resolve_target_parts(source_path, pysrc_dir, imp['level'], imp['module'])
            if parts is None:
                continue
            kind, missing_dir = _resolve_target(pysrc_dir, parts)
            missing_dirs = [missing_dir] if kind == 'no_init' else []
            if kind == 'package':
                for name, _asname in imp['names']:
                    if name == '*':
                        continue
                    sub_kind, sub_missing_dir = _resolve_target(pysrc_dir, parts + (name,))
                    if sub_kind == 'no_init':
                        missing_dirs.append(sub_missing_dir)
            for missing_dir in missing_dirs:
                if missing_dir in reported:
                    continue
                reported.add(missing_dir)
                rel_dir = missing_dir.relative_to(project_root).as_posix()
                errors.append({'path': rel_path, 'lineno': imp['lineno'], 'col': imp['col'], 'headline': f"missing package init '{rel_dir}'", 'help': f'add {rel_dir}/__init__.py'})
    return errors

def _import_targets(source_path, pysrc_dir, imp):
    parts = _resolve_target_parts(source_path, pysrc_dir, imp['level'], imp['module'])
    if parts is None:
        return []
    kind, target_path = _resolve_target(pysrc_dir, parts)
    if kind not in ('module', 'package'):
        return []
    if kind == 'package':
        submodules = []
        for name, _asname in imp['names']:
            sub_kind, sub_path = _resolve_target(pysrc_dir, parts + (name,))
            if sub_kind in ('module', 'package'):
                submodules.append(sub_path)
        if submodules:
            return submodules
    return [target_path]

def _check_cycles(fresh, pysrc_dir, project_root):
    errors = []
    edges = {}
    for rel_path, entry in fresh.items():
        source_path = project_root / rel_path
        targets = set()
        for imp in entry['imports']:
            if not imp.get('top_level', True):
                continue
            for target_path in _import_targets(source_path, pysrc_dir, imp):
                targets.add(target_path.relative_to(project_root).as_posix())
        edges[rel_path] = targets
    reported = set()
    for rel_path, targets in edges.items():
        for target in targets:
            if target == rel_path:
                continue
            if rel_path in edges.get(target, ()):
                pair = frozenset((rel_path, target))
                if pair in reported:
                    continue
                reported.add(pair)
                errors.append({'path': rel_path, 'lineno': 1, 'col': 0, 'headline': f"circular import with '{target}'", 'help': 'split one of the two modules to break the cycle'})
    return errors

def run(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    pysrc_dir = Path(pysrc_dir)
    project_root = Path(project_root)
    buildlog.task_start(TASK_ID, 'validate_imports')
    sources = sorted((p for p in pysrc_dir.rglob('*.py') if '__pycache__' not in p.parts))
    if not sources:
        buildlog.task_done(TASK_ID)
        return {}
    fresh = _refresh_cache(sources, pysrc_dir, cruel_bin, project_root, buildlog, cache)
    errors = []
    errors.extend(_check_modules_and_objects(fresh, pysrc_dir, project_root))
    errors.extend(_check_init_files(fresh, pysrc_dir, project_root))
    errors.extend(_check_cycles(fresh, pysrc_dir, project_root))
    if errors:
        for err in errors:
            source_line = _source_line(project_root, err['path'], err['lineno'])
            length = len(source_line) - err['col'] if source_line else 1
            buildlog.error(err['headline'])
            buildlog.frame(err['path'], err['lineno'], err['col'], length, source_line=source_line, help=err['help'])
        buildlog.task_fail(TASK_ID, f'{len(errors)} import error(s) found')
        sys.exit(1)
    buildlog.task_done(TASK_ID)
    return fresh

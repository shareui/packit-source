import ast
import json
import sys
from pathlib import Path
import yaml
try:
    import tomllib
except ImportError:
    import tomli as tomllib
NAMESPACE = 'validate_strings'
LOCALE_SUFFIXES = ('.yml', '.yaml', '.json', '.py')
LOCALE_CONFIG_NAME = 'config.toml'
GET_METHODS = ('get', 'get_with_locale')

def _locale_candidates(strings_ref):
    strings_ref = Path(strings_ref)
    if strings_ref.is_dir():
        return sorted((p for p in strings_ref.iterdir() if p.suffix in LOCALE_SUFFIXES and p.is_file()))
    if strings_ref.is_file():
        return [strings_ref]
    return []

def _check_syntax_one(path):
    text = path.read_text(encoding='utf-8')
    if path.suffix == '.json':
        json.loads(text)
    elif path.suffix == '.py':
        ast.parse(text, filename=str(path))
    else:
        yaml.safe_load(text)

def _validate_syntax(strings_ref, buildlog):
    failures = []
    for path in _locale_candidates(strings_ref):
        try:
            _check_syntax_one(path)
        except (json.JSONDecodeError, SyntaxError, yaml.YAMLError) as e:
            buildlog.error(f"syntax error in strings file '{path.name}': {e}")
            failures.append(path.name)
    if failures:
        sys.exit(1)

def _load_locale_file(path):
    if path.suffix == '.json':
        with open(path, 'rb') as f:
            return json.load(f) or {}
    if path.suffix == '.py':
        namespace = {}
        exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), namespace)
        return {k: v for k, v in namespace.items() if not k.startswith('_') and (not callable(v))}
    with open(path, 'rb') as f:
        return yaml.safe_load(f) or {}

def _collect_locales(strings_ref, buildlog):
    strings_ref = Path(strings_ref)
    base_dir = strings_ref if strings_ref.is_dir() else strings_ref.parent
    config_path = base_dir / LOCALE_CONFIG_NAME
    if not config_path.is_file():
        buildlog.error(f"missing '{LOCALE_CONFIG_NAME}' next to strings, expected a [map] locale -> filename table")
        return {}
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    locale_map = config.get('map')
    if not isinstance(locale_map, dict) or not locale_map:
        buildlog.error(f"'{LOCALE_CONFIG_NAME}' is missing a non empty [map] table")
        return {}
    locales = {}
    for locale, file_name in locale_map.items():
        path = base_dir / file_name
        if not path.is_file():
            buildlog.error(f"strings file '{file_name}' mapped to locale '{locale}' does not exist")
            continue
        locales[locale] = _load_locale_file(path)
    return locales

def _check_key(key, locales, buildlog, has_default=False, path=None, lineno=None, col=None, source_line=None):
    present_in = {locale for locale, table in locales.items() if key in table}
    if not present_in:
        if has_default:
            buildlog.warn(f"missing string key '{key}'")
            buildlog.frame(path, lineno, col, len(key), source_line=source_line, help='falling back to the provided default', level='warn')
            return True
        buildlog.error(f"missing string key '{key}'")
        buildlog.frame(path, lineno, col, len(key), source_line=source_line, help='add it to every locale file')
        return False
    for locale in locales:
        if locale not in present_in:
            buildlog.warn(f"missing string key '{key}' in '{locale}'")
    return True

def _description_placeholder_keys(template):
    keys = []
    i = 0
    length = len(template)
    while i < length:
        if template[i] == '{':
            close = template.find('}', i + 1)
            if close == -1:
                break
            keys.append(template[i + 1:close])
            i = close + 1
            continue
        i += 1
    return keys

def _check_description_placeholders(metadata, locales, buildlog):
    description = metadata.get('description', '')
    ok = True
    for key in sorted(set(_description_placeholder_keys(description))):
        ok = _check_key(key, locales, buildlog, path='cruel.toml [metadata] description') and ok
    if not ok:
        sys.exit(1)

def _bound_names_and_module_import(tree):
    names = set()
    imports_elyx_module = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'elyx':
            for alias in node.names:
                if alias.name == 'strings':
                    names.add(alias.asname or alias.name)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'elyx' and alias.asname is None:
                    imports_elyx_module = True
    return (names, imports_elyx_module)

def _shadow_ranges(tree, name):
    ranges = []

    class Visitor(ast.NodeVisitor):

        def _params(self, node):
            args = node.args
            params = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
            if args.vararg:
                params.append(args.vararg.arg)
            if args.kwarg:
                params.append(args.kwarg.arg)
            return params

        def _visit_scope(self, node):
            if name in self._params(node):
                ranges.append((node.lineno, node.end_lineno))
            else:
                self.generic_visit(node)
        visit_FunctionDef = _visit_scope
        visit_AsyncFunctionDef = _visit_scope
        visit_Lambda = _visit_scope
    Visitor().visit(tree)
    return ranges

class _KeyVisitor(ast.NodeVisitor):

    def __init__(self, bound_names, shadow_ranges, imports_elyx_module):
        self.bound_names = bound_names
        self.shadow_ranges = shadow_ranges
        self.imports_elyx_module = imports_elyx_module
        self.keys = []

    def _is_strings_name(self, expr, lineno):
        if not (isinstance(expr, ast.Name) and expr.id in self.bound_names):
            return False
        return not any((start <= lineno <= end for start, end in self.shadow_ranges.get(expr.id, ())))

    def _is_strings_module_attr(self, expr):
        return self.imports_elyx_module and isinstance(expr, ast.Attribute) and (expr.attr == 'strings') and isinstance(expr.value, ast.Name) and (expr.value.id == 'elyx')

    def _strings_root(self, expr, lineno):
        return self._is_strings_name(expr, lineno) or self._is_strings_module_attr(expr)

    def visit_Attribute(self, node):
        if self._strings_root(node.value, node.lineno) and node.attr not in GET_METHODS + ('pluralize',):
            self.keys.append((node.attr, node.lineno, node.col_offset, False))
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if self._strings_root(node.value, node.lineno):
            key_node = node.slice
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                self.keys.append((key_node.value, node.lineno, node.col_offset, False))
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if self._strings_root(func, node.lineno):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.keys.append((node.args[0].value, node.lineno, node.col_offset, False))
        elif isinstance(func, ast.Attribute) and func.attr in GET_METHODS and self._strings_root(func.value, node.lineno):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                has_default = len(node.args) > 1 or any((kw.arg == 'default' for kw in node.keywords))
                self.keys.append((node.args[0].value, node.lineno, node.col_offset, has_default))
        self.generic_visit(node)

def _keys_used_in(source_path):
    text = source_path.read_text(encoding='utf-8')
    tree = ast.parse(text, filename=str(source_path))
    bound_names, imports_elyx_module = _bound_names_and_module_import(tree)
    if not bound_names and (not imports_elyx_module):
        return []
    shadow_ranges = {name: _shadow_ranges(tree, name) for name in bound_names}
    visitor = _KeyVisitor(bound_names, shadow_ranges, imports_elyx_module)
    visitor.visit(tree)
    return visitor.keys

def _check_pysrc(pysrc_dir, project_root, locales, cruel_bin, buildlog, cache):
    pysrc_dir = Path(pysrc_dir)
    sources = sorted((p for p in pysrc_dir.rglob('*.py') if '__pycache__' not in p.parts))
    ok = True
    for source_path in sources:
        if not cache.is_changed(cruel_bin, project_root, NAMESPACE, source_path):
            continue
        rel_path = source_path.relative_to(project_root)
        lines = source_path.read_text(encoding='utf-8').splitlines()
        for key, lineno, col, has_default in _keys_used_in(source_path):
            source_line = lines[lineno - 1] if 1 <= lineno <= len(lines) else None
            ok = _check_key(key, locales, buildlog, has_default, path=rel_path, lineno=lineno, col=col, source_line=source_line) and ok
        cache.mark(cruel_bin, project_root, NAMESPACE, source_path)
    if not ok:
        sys.exit(1)

def run(cfg_path, cruel_bin, buildlog, cache):
    cfg_path = Path(cfg_path)
    project_root = cfg_path.parent
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    metadata = cfg.get('metadata', {})
    references = cfg.get('references', {})
    locales = {}
    if 'strings' in references:
        strings_ref = project_root / references['strings']
        _validate_syntax(strings_ref, buildlog)
        locales = _collect_locales(strings_ref, buildlog)
    _check_description_placeholders(metadata, locales, buildlog)
    if 'pysrc' in references:
        _check_pysrc(project_root / references['pysrc'], project_root, locales, cruel_bin, buildlog, cache)
    return locales

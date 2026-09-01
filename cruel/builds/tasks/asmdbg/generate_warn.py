import ast
from pathlib import Path
NAMESPACE = 'generate_warn'
TERMINATORS = (ast.Return, ast.Raise, ast.Break, ast.Continue)

def _dump(node):
    return ast.dump(node, annotate_fields=False)

class Finding:

    def __init__(self, kind, message, node):
        self.kind = kind
        self.message = message
        self.node = node
        self.lineno = node.lineno
        self.col = node.col_offset

def _parse_directives(source_lines):
    directives = {}
    for i, line in enumerate(source_lines, start=1):
        if '# cruel:' in line:
            name = line.split('# cruel:', 1)[1].strip()
            if name:
                directives[i] = name
    return directives

def _build_suppression_map(tree, directives):
    node_suppress = {}

    def visit(node, inherited):
        current = inherited
        start = getattr(node, 'lineno', None)
        end = getattr(node, 'end_lineno', start)
        if start is not None:
            hit = {name for line, name in directives.items() if start <= line <= (end or start)}
            if hit:
                current = inherited | hit
        node_suppress[node] = current
        for child in ast.iter_child_nodes(node):
            visit(child, current)
    visit(tree, frozenset())
    return node_suppress

def _check_unused_variable(tree):
    findings = []

    class Scope(ast.NodeVisitor):

        def __init__(self):
            self.assigned = {}
            self.used = set()

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                if not node.id.startswith('_'):
                    self.assigned.setdefault(node.id, node)
            elif isinstance(node.ctx, ast.Load):
                self.used.add(node.id)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            pass

        def visit_AsyncFunctionDef(self, node):
            pass

        def visit_Lambda(self, node):
            pass
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = Scope()
            for stmt in func.body:
                scope.visit(stmt)
            for name, node in scope.assigned.items():
                if name not in scope.used:
                    findings.append(Finding('unused_variable', f"'{name}' is never used", node))
    return findings

def _resolve_relative_module(importer_path, node):
    if node.level < 1:
        return None
    package_dir = importer_path.parent
    for _ in range(node.level - 1):
        package_dir = package_dir.parent
    if node.module:
        target = package_dir.joinpath(*node.module.split('.'))
    else:
        target = package_dir
    module_file = target.with_suffix('.py')
    if module_file.is_file():
        return module_file
    init_file = target / '__init__.py'
    if init_file.is_file():
        return init_file
    return None

def _build_cross_file_usage(trees):
    used_from = {}
    for importer_path, tree in trees.items():
        all_loads = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module_path = _resolve_relative_module(importer_path, node)
            if module_path is None:
                continue
            for alias in node.names:
                if alias.name == '*':
                    continue
                bound = alias.asname or alias.name
                if bound in all_loads:
                    used_from.setdefault(module_path, set()).add(alias.name)
    return used_from

def _check_unused_function(tree, cross_used=frozenset()):
    findings = []
    all_loads = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith('__') and node.name.endswith('__'):
                continue
            if node.name in all_loads or node.name in cross_used:
                continue
            findings.append(Finding('unused_function', f"'{node.name}' is never used", node))
    return findings

def _check_unused_import(tree):
    findings = []
    all_loads = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split('.')[0]
                if bound not in all_loads:
                    findings.append(Finding('unused_import', f"'{bound}' is never used", node))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    continue
                bound = alias.asname or alias.name
                if bound not in all_loads:
                    findings.append(Finding('unused_import', f"'{bound}' is never used", node))
    return findings

def _check_unreachable_code(tree):
    findings = []
    for node in ast.walk(tree):
        for field in ('body', 'orelse', 'finalbody'):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            terminated = False
            for stmt in block:
                if terminated:
                    findings.append(Finding('unreachable_code', 'unreachable statement', stmt))
                    break
                if isinstance(stmt, TERMINATORS):
                    terminated = True
    return findings

def _check_redefined(tree):
    findings = []

    def bound_name(stmt):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return stmt.name
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            return stmt.targets[0].id
        return None

    def names_loaded(stmt):
        return {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

    def check_body(body):
        last_binding = {}
        for stmt in body:
            used = names_loaded(stmt)
            for name in list(last_binding.keys()):
                if name in used:
                    del last_binding[name]
            name = bound_name(stmt)
            if name:
                if name in last_binding:
                    findings.append(Finding('redefined', f"'{name}' is redefined before use", stmt))
                last_binding[name] = stmt
    for node in ast.walk(tree):
        body = getattr(node, 'body', None)
        if isinstance(body, list):
            check_body(body)
    return findings

def _check_constant_condition(tree):
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            test = node.test
            if isinstance(test, ast.Constant) and isinstance(test.value, bool):
                findings.append(Finding('constant_condition', f'condition is always {test.value}', test))
    return findings

def _collect_if_chain(node):
    chain = [node.test]
    orelse = node.orelse
    while len(orelse) == 1 and isinstance(orelse[0], ast.If):
        chain.append(orelse[0].test)
        orelse = orelse[0].orelse
    return chain

def _check_duplicate_conditions(tree):
    findings = []
    elif_children = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            elif_children.add(id(node.orelse[0]))
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and id(node) not in elif_children:
            chain = _collect_if_chain(node)
            seen = {}
            for test in chain:
                key = _dump(test)
                if key in seen:
                    findings.append(Finding('duplicate_conditions', 'condition duplicates an earlier branch', test))
                else:
                    seen[key] = test
    return findings

def _check_duplicate_branches(tree):
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                continue
            if [_dump(s) for s in node.body] == [_dump(s) for s in node.orelse]:
                findings.append(Finding('duplicate_branches', 'both branches are identical', node))
    return findings

def _check_empty_exception(tree):
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                findings.append(Finding('empty_exception', 'exception is silently ignored', node))
    return findings
CHECKS = (_check_unused_variable, _check_unused_function, _check_unused_import, _check_unreachable_code, _check_redefined, _check_constant_condition, _check_duplicate_conditions, _check_duplicate_branches, _check_empty_exception)

def _analyze(source_path, tree, cross_used):
    text = source_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    directives = _parse_directives(lines)
    suppress = _build_suppression_map(tree, directives)
    findings = []
    for check in CHECKS:
        args = (tree, cross_used) if check is _check_unused_function else (tree,)
        for finding in check(*args):
            if finding.kind in suppress.get(finding.node, frozenset()):
                continue
            findings.append(finding)
    findings.sort(key=lambda w: (w.lineno, w.col))
    return (findings, lines)

def _parse_all(sources):
    trees = {}
    for source_path in sources:
        try:
            text = source_path.read_text(encoding='utf-8')
            trees[source_path] = ast.parse(text, filename=str(source_path))
        except SyntaxError:
            continue
    return trees

def run(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    pysrc_dir = Path(pysrc_dir)
    project_root = Path(project_root)
    sources = sorted((p for p in pysrc_dir.rglob('*.py') if '__pycache__' not in p.parts))
    trees = _parse_all(sources)
    used_from = _build_cross_file_usage(trees)
    total_findings = 0
    files_with_findings = 0
    for source_path in sources:
        if not cache.is_changed(cruel_bin, project_root, NAMESPACE, source_path):
            continue
        tree = trees.get(source_path)
        if tree is None:
            continue
        rel_path = source_path.relative_to(project_root)
        cross_used = used_from.get(source_path, frozenset())
        findings, lines = _analyze(source_path, tree, cross_used)
        for finding in findings:
            source_line = lines[finding.lineno - 1] if 1 <= finding.lineno <= len(lines) else None
            end_col = getattr(finding.node, 'end_col_offset', None)
            length = end_col - finding.col if end_col is not None and getattr(finding.node, 'end_lineno', finding.lineno) == finding.lineno else 1
            buildlog.warn(f'{finding.kind}: {finding.message}')
            buildlog.frame(rel_path, finding.lineno, finding.col, length, source_line=source_line, level='warn')
        total_findings += len(findings)
        if findings:
            files_with_findings += 1
        cache.mark(cruel_bin, project_root, NAMESPACE, source_path)
    return (total_findings, files_with_findings)

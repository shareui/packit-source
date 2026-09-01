import ast
import sys
from pathlib import Path
NAMESPACE = 'validate_syntax'

def run(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    pysrc_dir = Path(pysrc_dir)
    project_root = Path(project_root)
    sources = sorted((p for p in pysrc_dir.rglob('*.py') if '__pycache__' not in p.parts))
    ok = True
    for source_path in sources:
        if not cache.is_changed(cruel_bin, project_root, NAMESPACE, source_path):
            continue
        text = source_path.read_text(encoding='utf-8')
        try:
            ast.parse(text, filename=str(source_path))
        except SyntaxError as e:
            rel_path = source_path.relative_to(project_root)
            lineno = e.lineno or 1
            col = (e.offset or 1) - 1
            length = max((e.end_offset or e.offset or 1) - (e.offset or 1), 1)
            buildlog.error(f'syntax error: {e.msg}')
            buildlog.frame(rel_path, lineno, col, length, source_line=e.text.rstrip('\n') if e.text else None)
            ok = False
            continue
        cache.mark(cruel_bin, project_root, NAMESPACE, source_path)
    if not ok:
        sys.exit(1)
    return sources

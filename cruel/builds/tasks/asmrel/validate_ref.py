import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
DIR_KEYS = ('assets', 'pysrc')
FILE_OR_DIR_KEYS = ('strings',)
FILE_KEYS = ('entry',)
REQUIRED_KEYS = DIR_KEYS + FILE_OR_DIR_KEYS + FILE_KEYS

def run(cfg_path, buildlog):
    cfg_path = Path(cfg_path)
    project_root = cfg_path.parent
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    references = cfg.get('references', {})
    ok = True
    for key in REQUIRED_KEYS:
        if key not in references:
            buildlog.error(f'cruel.toml [references] is missing required field: {key}')
            ok = False
    for key in DIR_KEYS:
        if key not in references:
            continue
        target = project_root / references[key]
        if not target.is_dir():
            buildlog.error(f"cruel.toml [references] field '{key}' points to a missing directory: {target}")
            ok = False
    for key in FILE_OR_DIR_KEYS:
        if key not in references:
            continue
        target = project_root / references[key]
        if not target.is_file() and (not target.is_dir()):
            buildlog.error(f"cruel.toml [references] field '{key}' points to a missing path: {target}")
            ok = False
    for key in FILE_KEYS:
        if key not in references:
            continue
        target = project_root / references[key]
        if not target.is_file():
            buildlog.error(f"cruel.toml [references] field '{key}' points to a missing file: {target}")
            ok = False
    if not ok:
        sys.exit(1)
    return references

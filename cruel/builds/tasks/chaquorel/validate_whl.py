import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib

def run(cfg_path, buildlog):
    cfg_path = Path(cfg_path)
    project_root = cfg_path.parent
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    local = cfg.get('requirements', {}).get('local', {})
    ok = True
    for name, rel_path in local.items():
        if not rel_path:
            continue
        target = project_root / rel_path
        if not target.is_file():
            buildlog.error(f"cruel.toml [requirements.local] entry '{name}' points to a missing file: {target}")
            ok = False
    if not ok:
        sys.exit(1)
    return local

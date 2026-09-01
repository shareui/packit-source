import shutil
import subprocess
import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
NAMESPACE = 'pack_assets'
TASK_ID = 'pack_assets'
TEMP_SUBDIR = Path('cruel') / 'local' / 'temp' / 'assets'
CACHE_SUBDIR = Path('cruel') / 'local' / 'cache' / 'zstd'
DEFAULT_ZSTD_LEVEL = 22
ZSTD_LEVEL_RANGE = (1, 22)

def _find_cruel_bin():
    return shutil.which('cruel') or 'cruel'

def _load_assets_config(assets_dir, buildlog):
    cfg_path = assets_dir / 'config.toml'
    if not cfg_path.is_file():
        return {'structured': True, 'zstd': DEFAULT_ZSTD_LEVEL}
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    config = cfg.get('config', {})
    zstd_level = int(config.get('zstd', DEFAULT_ZSTD_LEVEL))
    low, high = ZSTD_LEVEL_RANGE
    if not low <= zstd_level <= high:
        buildlog.error(f"res/assets/config.toml field 'zstd' must be between {low} and {high}, got {zstd_level}")
        sys.exit(1)
    return {'structured': bool(config.get('structured', True)), 'zstd': zstd_level}

def _collect_files(assets_dir):
    return sorted((p for p in assets_dir.rglob('*') if p.is_file() and p.name != 'config.toml'))

def _pack_one(cruel_bin, source_path, dest_path, zstd_level):
    args = [cruel_bin, '__packassets', str(source_path), str(zstd_level)]
    result = subprocess.run(args, capture_output=True)
    if result.returncode != 0:
        return result.stderr.decode('utf-8', errors='replace').strip()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(result.stdout)
    return None

def _cache_entry(cached_path, digest, zstd_level, project_root):
    return {'hash': digest, 'zstd': zstd_level, 'path': str(cached_path.relative_to(project_root / CACHE_SUBDIR).as_posix())}

def _cache_hit(entry, cached_path, digest, zstd_level):
    if entry is None:
        return False
    return entry.get('hash') == digest and entry.get('zstd') == zstd_level and cached_path.is_file()

def run(cfg_path, project_root, buildlog, cache, cruel_bin=None):
    cfg_path = Path(cfg_path)
    project_root = Path(project_root)
    cruel_bin = cruel_bin or _find_cruel_bin()
    with open(cfg_path, 'rb') as f:
        cruel_cfg = tomllib.load(f)
    references = cruel_cfg.get('references', {})
    if 'assets' not in references:
        buildlog.error('assets field not found in [references]')
        sys.exit(1)
    assets_dir = project_root / references['assets']
    if not assets_dir.is_dir():
        buildlog.error(f"cruel.toml [references] field 'assets' points to a missing directory: {assets_dir}")
        sys.exit(1)
    asset_config = _load_assets_config(assets_dir, buildlog)
    structured = asset_config['structured']
    zstd_level = asset_config['zstd']
    temp_dir = project_root / TEMP_SUBDIR
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = project_root / CACHE_SUBDIR
    files = _collect_files(assets_dir)
    if not files:
        buildlog.info('no assets to pack, skipping')
        return temp_dir
    buildlog.task_start(TASK_ID, 'pack_assets')
    manifest = cache.load_json(project_root, NAMESPACE)
    failures = []
    total = len(files)
    for index, source_path in enumerate(files, start=1):
        rel_path = source_path.relative_to(assets_dir)
        rel_key = str(rel_path.as_posix())
        dest_name = source_path.name + '.zst'
        dest_path = (temp_dir / rel_path).with_name(dest_name) if structured else temp_dir / dest_name
        cached_path = (cache_dir / rel_path).with_name(dest_name)
        digest = cache.file_hash(cruel_bin, source_path)
        entry = manifest.get(rel_key)
        if _cache_hit(entry, cached_path, digest, zstd_level):
            buildlog.info(f'  = {rel_path}')
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached_path, dest_path)
            buildlog.task_progress(TASK_ID, index * 100 // total)
            continue
        buildlog.info(f'packing {rel_path}')
        error = _pack_one(cruel_bin, source_path, cached_path, zstd_level)
        if error is not None:
            buildlog.error(f'failed to pack {rel_path}: {error}')
            failures.append(str(rel_path.as_posix()))
            buildlog.task_progress(TASK_ID, index * 100 // total)
            continue
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached_path, dest_path)
        manifest[rel_key] = _cache_entry(cached_path, digest, zstd_level, project_root)
        buildlog.info(f'packed {rel_path}')
        buildlog.task_progress(TASK_ID, index * 100 // total)
    cache.save_json(project_root, NAMESPACE, manifest)
    if failures:
        shutil.rmtree(temp_dir, ignore_errors=True)
        buildlog.task_fail(TASK_ID, f'{len(failures)} of {total} asset(s) failed to pack')
        sys.exit(1)
    buildlog.task_done(TASK_ID)
    return temp_dir

import shutil
import subprocess
import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
TASK_ID = 'adb_push'
LOCAL_CONFIG_PATH = Path('cruel') / 'local' / 'config.toml'

def _find_adb_bin():
    return shutil.which('adb') or 'adb'

def _load_adb_path(project_root, buildlog):
    cfg_path = project_root / LOCAL_CONFIG_PATH
    if not cfg_path.is_file():
        buildlog.error(f'missing {LOCAL_CONFIG_PATH}')
        buildlog.info(f'create it with:\n[config]\nadb_path = "/sdcard/your/folder"')
        return None
    with open(cfg_path, 'rb') as f:
        try:
            cfg = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            buildlog.error(f'{LOCAL_CONFIG_PATH} syntax error: {e}')
            return None
    config = cfg.get('config')
    if not isinstance(config, dict):
        buildlog.error(f'{LOCAL_CONFIG_PATH} is missing [config] section')
        buildlog.info(f'add:\n[config]\nadb_path = "/sdcard/your/folder"')
        return None
    adb_path = config.get('adb_path')
    if not isinstance(adb_path, str) or not adb_path.strip():
        buildlog.error(f"{LOCAL_CONFIG_PATH} [config] field 'adb_path' is missing or empty")
        buildlog.info(f'set:\n[config]\nadb_path = "/sdcard/your/folder"')
        return None
    return adb_path

def _remote_dir_exists(adb_bin, remote_dir, buildlog):
    result = subprocess.run([adb_bin, 'shell', f"test -d '{remote_dir}' && echo exists"], capture_output=True, text=True)
    if result.returncode != 0:
        error = result.stderr.strip()
        buildlog.error(f'adb shell failed: {error}')
        return None
    return result.stdout.strip() == 'exists'

def _create_remote_dir(adb_bin, remote_dir, buildlog):
    result = subprocess.run([adb_bin, 'shell', f"mkdir -p '{remote_dir}'"], capture_output=True, text=True)
    if result.returncode != 0:
        error = result.stderr.strip()
        buildlog.error(f'failed to create remote folder: {error}')
        return False
    return True

def _push_file(adb_bin, local_path, remote_path, buildlog):
    result = subprocess.run([adb_bin, 'push', str(local_path), remote_path], capture_output=True, text=True)
    if result.returncode != 0:
        error = result.stderr.strip()
        buildlog.error(f'adb push failed: {error}')
        return False
    return True

def run(out_path, metadata, build_name, project_root, buildlog):
    out_path = Path(out_path)
    project_root = Path(project_root)
    adb_bin = _find_adb_bin()
    buildlog.task_start(TASK_ID, 'adb_push')
    adb_dir = _load_adb_path(project_root, buildlog)
    if adb_dir is None:
        buildlog.task_fail(TASK_ID, 'adb_path not configured')
        sys.exit(1)
    buildlog.task_progress(TASK_ID, 20)
    exists = _remote_dir_exists(adb_bin, adb_dir, buildlog)
    if exists is None:
        buildlog.task_fail(TASK_ID, 'failed to check remote folder')
        sys.exit(1)
    buildlog.task_progress(TASK_ID, 40)
    if not exists:
        buildlog.info(f'remote folder not found, creating {adb_dir}')
        if not _create_remote_dir(adb_bin, adb_dir, buildlog):
            buildlog.task_fail(TASK_ID, 'failed to create remote folder')
            sys.exit(1)
    buildlog.task_progress(TASK_ID, 60)
    plugin_id = metadata['id']
    remote_name = f'{plugin_id}-{build_name}.crul'
    remote_dir = adb_dir.rstrip('/')
    remote_path = f'{remote_dir}/{remote_name}'
    buildlog.info(f'pushing {out_path.name} to {remote_path}')
    if not _push_file(adb_bin, out_path, remote_path, buildlog):
        buildlog.task_fail(TASK_ID, 'failed to push file')
        sys.exit(1)
    buildlog.task_progress(TASK_ID, 100)
    buildlog.task_done(TASK_ID)
    buildlog.info(f'pushed to device: {remote_path}')

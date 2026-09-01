import importlib.util
import shutil
import sys
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_DIR = SCRIPT_DIR / 'tasks'
BUILD_TASKS_DIR = TASKS_DIR / 'check'
HOOKS_DIR = SCRIPT_DIR / 'hooks'
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CFG_PATH = PROJECT_ROOT / 'cruel.toml'
BUILD_NAME = 'check'
LIBRARIES = {'tomllib (or tomli on python < 3.11)': ('tomllib', 'tomli'), 'pyyaml': ('yaml',)}

def load_module(dir_path, name):
    spec = importlib.util.spec_from_file_location(name, dir_path / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_shared(name):
    return load_module(TASKS_DIR, name)

def load_task(task_name):
    return load_module(BUILD_TASKS_DIR, task_name)

def load_hooks():
    return load_module(HOOKS_DIR, BUILD_NAME)

def check_dependencies(buildlog):
    for libname, module_names in LIBRARIES.items():
        if not any((importlib.util.find_spec(name) is not None for name in module_names)):
            buildlog.error(f'missing library: {libname}')
            buildlog.info('please, install it with pip 3.11')
            sys.exit(1)

def find_cruel_bin():
    return shutil.which('cruel') or 'cruel'

def run_hook(hooks, hook_name, buildlog, *args):
    hook = getattr(hooks, hook_name, None)
    if hook is None:
        return True
    if not hook(*args):
        buildlog.error(f'{hook_name} failed, aborting build')
        sys.exit(1)
    return True

def main():
    buildlog = load_shared('buildlog')
    check_dependencies(buildlog)
    cache = load_shared('cruel_cache')
    validate_cruel = load_task('validate_cruel')
    validate_ref = load_task('validate_ref')
    validate_pypi = load_task('validate_pypi')
    validate_whl = load_task('validate_whl')
    validate_syntax = load_task('validate_syntax')
    validate_imports = load_task('validate_imports')
    validate_strings = load_task('validate_strings')
    hooks = load_hooks()
    cruel_bin = find_cruel_bin()
    run_hook(hooks, 'before_validate_cruel', buildlog, CFG_PATH, buildlog)
    validate_cruel.run(CFG_PATH, buildlog)
    run_hook(hooks, 'after_validate_cruel', buildlog, CFG_PATH, buildlog)
    run_hook(hooks, 'before_validate_ref', buildlog, CFG_PATH, buildlog)
    references = validate_ref.run(CFG_PATH, buildlog)
    run_hook(hooks, 'after_validate_ref', buildlog, CFG_PATH, buildlog, references)
    run_hook(hooks, 'before_validate_whl', buildlog, CFG_PATH, buildlog)
    validate_whl.run(CFG_PATH, buildlog)
    run_hook(hooks, 'after_validate_whl', buildlog, CFG_PATH, buildlog)
    run_hook(hooks, 'before_validate_pypi', buildlog, CFG_PATH, cruel_bin, buildlog, cache)
    validate_pypi.run(CFG_PATH, cruel_bin, buildlog, cache)
    run_hook(hooks, 'after_validate_pypi', buildlog, CFG_PATH, cruel_bin, buildlog, cache)
    pysrc_dir = PROJECT_ROOT / references['pysrc']
    run_hook(hooks, 'before_validate_syntax', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    validate_syntax.run(pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'after_validate_syntax', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'before_validate_imports', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    validate_imports.run(pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'after_validate_imports', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'before_validate_strings', buildlog, CFG_PATH, cruel_bin, buildlog, cache)
    validate_strings.run(CFG_PATH, cruel_bin, buildlog, cache)
    run_hook(hooks, 'after_validate_strings', buildlog, CFG_PATH, cruel_bin, buildlog, cache)
    buildlog.info('check build finished successfully')
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        buildlog = load_shared('buildlog')
        hooks = load_hooks()
        run_hook(hooks, 'on_sigkill', buildlog)
        sys.exit(130)

def on_sigkill(buildlog):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

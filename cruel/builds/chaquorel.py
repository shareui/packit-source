import importlib.util
import shutil
import sys
from pathlib import Path
import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_DIR = SCRIPT_DIR / 'tasks'
BUILD_TASKS_DIR = TASKS_DIR / 'chaquorel'
HOOKS_DIR = SCRIPT_DIR / 'hooks'
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CFG_PATH = PROJECT_ROOT / 'cruel.toml'
BUILD_NAME = 'chaquorel'
BUILD_TYPE = 'release'
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
    res = hook(*args)
    if res is False:
        buildlog.error(f'{hook_name} failed, aborting build')
        sys.exit(1)
    return res

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f'{size_bytes:.2f} {unit}'
        size_bytes /= 1024.0
    return f'{size_bytes:.2f} TB'

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
    generate_warn = load_task('generate_warn')
    compile_chaquo_arm7 = load_task('compile_chaquo_arm7')
    compile_chaquo_arm8 = load_task('compile_chaquo_arm8')
    pack_assets = load_task('pack_assets')
    pack_cruel = load_task('pack_cruel')
    link_sections = load_task('link_sections')
    adb_push = load_task('adb_push')
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
    entry_path = PROJECT_ROOT / references['entry']
    run_hook(hooks, 'before_validate_syntax', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    validate_syntax.run(pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'after_validate_syntax', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'before_validate_imports', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    validate_imports.run(pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'after_validate_imports', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'before_validate_strings', buildlog, CFG_PATH, cruel_bin, buildlog, cache)
    validate_strings.run(CFG_PATH, cruel_bin, buildlog, cache)
    run_hook(hooks, 'after_validate_strings', buildlog, CFG_PATH, cruel_bin, buildlog, cache)
    run_hook(hooks, 'before_generate_warn', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    total_warns, warn_files = generate_warn.run(pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache)
    run_hook(hooks, 'after_generate_warn', buildlog, pysrc_dir, cruel_bin, PROJECT_ROOT, buildlog, cache, total_warns, warn_files)
    with open(CFG_PATH, 'rb') as f:
        cruel_cfg = tomllib.load(f)
    build_section = cruel_cfg['build'][BUILD_NAME]
    opt = build_section.get('opt', 0)
    pycompile = build_section.get('pycompile', False)
    remove_pymeta = build_section.get('remove_pymeta', False)
    archs = []
    if buildlog.flag('v8'):
        archs.append('arm64-v8a')
    if buildlog.flag('v7'):
        archs.append('armeabi-v7a')
    if not archs:
        archs = ['arm64-v8a', 'armeabi-v7a']
    run_hook(hooks, 'before_pack_assets', buildlog, CFG_PATH, PROJECT_ROOT, buildlog, cache, cruel_bin)
    pack_assets.run(CFG_PATH, PROJECT_ROOT, buildlog, cache, cruel_bin=cruel_bin)
    run_hook(hooks, 'after_pack_assets', buildlog, CFG_PATH, PROJECT_ROOT, buildlog, cache, cruel_bin)
    metadata = cruel_cfg.get('metadata', {})
    results = {}
    if 'armeabi-v7a' in archs:
        buildlog.info('== Building for architecture: armeabi-v7a ==')
        run_hook(hooks, 'before_compile_chaquo_arm7', buildlog, pysrc_dir, PROJECT_ROOT, opt, pycompile, remove_pymeta, buildlog, cache, entry_path, cruel_bin)
        compiled_paths = compile_chaquo_arm7.run(pysrc_dir, PROJECT_ROOT, opt, pycompile, remove_pymeta, buildlog, cache, entry_path=entry_path, cruel_bin=cruel_bin)
        run_hook(hooks, 'after_compile_chaquo_arm7', buildlog, pysrc_dir, PROJECT_ROOT, opt, pycompile, remove_pymeta, buildlog, cache, entry_path, cruel_bin, compiled_paths)
        run_hook(hooks, 'before_pack_cruel_arm7', buildlog, CFG_PATH, PROJECT_ROOT, references, build_section, BUILD_TYPE, buildlog, cruel_bin)
        temp_dir = pack_cruel.run(CFG_PATH, PROJECT_ROOT, references, build_section, BUILD_TYPE, buildlog, cruel_bin=cruel_bin, arch='armeabi-v7a')
        run_hook(hooks, 'after_pack_cruel_arm7', buildlog, CFG_PATH, PROJECT_ROOT, references, build_section, BUILD_TYPE, buildlog, cruel_bin, temp_dir)
        run_hook(hooks, 'before_link_sections_arm7', buildlog, temp_dir, metadata, BUILD_NAME, buildlog, cruel_bin)
        out_path = link_sections.run(temp_dir, metadata, BUILD_NAME, buildlog, cruel_bin=cruel_bin)
        run_hook(hooks, 'after_link_sections_arm7', buildlog, temp_dir, metadata, BUILD_NAME, buildlog, cruel_bin)
        arch_out_path = out_path.with_name(f'{out_path.stem}-armeabi-v7a{out_path.suffix}')
        shutil.move(str(out_path), str(arch_out_path))
        hook_res = run_hook(hooks, 'after_file_created', buildlog, arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog, 'armeabi-v7a')
        if isinstance(hook_res, (str, Path)):
            arch_out_path = Path(hook_res)
        results['armeabi-v7a'] = arch_out_path
        if buildlog.flag('adbpush'):
            run_hook(hooks, 'before_adb_push_arm7', buildlog, arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog)
            adb_push.run(arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog)
            run_hook(hooks, 'after_adb_push_arm7', buildlog, arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog)
    if 'arm64-v8a' in archs:
        buildlog.info('== Building for architecture: arm64-v8a ==')
        run_hook(hooks, 'before_compile_chaquo_arm8', buildlog, pysrc_dir, PROJECT_ROOT, opt, pycompile, remove_pymeta, buildlog, cache, entry_path, cruel_bin)
        compiled_paths = compile_chaquo_arm8.run(pysrc_dir, PROJECT_ROOT, opt, pycompile, remove_pymeta, buildlog, cache, entry_path=entry_path, cruel_bin=cruel_bin)
        run_hook(hooks, 'after_compile_chaquo_arm8', buildlog, pysrc_dir, PROJECT_ROOT, opt, pycompile, remove_pymeta, buildlog, cache, entry_path, cruel_bin, compiled_paths)
        run_hook(hooks, 'before_pack_cruel_arm8', buildlog, CFG_PATH, PROJECT_ROOT, references, build_section, BUILD_TYPE, buildlog, cruel_bin)
        temp_dir = pack_cruel.run(CFG_PATH, PROJECT_ROOT, references, build_section, BUILD_TYPE, buildlog, cruel_bin=cruel_bin, arch='arm64-v8a')
        run_hook(hooks, 'after_pack_cruel_arm8', buildlog, CFG_PATH, PROJECT_ROOT, references, build_section, BUILD_TYPE, buildlog, cruel_bin, temp_dir)
        run_hook(hooks, 'before_link_sections_arm8', buildlog, temp_dir, metadata, BUILD_NAME, buildlog, cruel_bin)
        out_path = link_sections.run(temp_dir, metadata, BUILD_NAME, buildlog, cruel_bin=cruel_bin)
        run_hook(hooks, 'after_link_sections_arm8', buildlog, temp_dir, metadata, BUILD_NAME, buildlog, cruel_bin)
        arch_out_path = out_path.with_name(f'{out_path.stem}-arm64-v8a{out_path.suffix}')
        shutil.move(str(out_path), str(arch_out_path))
        hook_res = run_hook(hooks, 'after_file_created', buildlog, arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog, 'arm64-v8a')
        if isinstance(hook_res, (str, Path)):
            arch_out_path = Path(hook_res)
        results['arm64-v8a'] = arch_out_path
        if buildlog.flag('adbpush'):
            run_hook(hooks, 'before_adb_push_arm8', buildlog, arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog)
            adb_push.run(arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog)
            run_hook(hooks, 'after_adb_push_arm8', buildlog, arch_out_path, metadata, BUILD_NAME, PROJECT_ROOT, buildlog)
    buildlog.info('cruel build finished successfully')
    buildlog.info(f'generated {total_warns} warns in {warn_files} files')
    buildlog.info('== Build Outputs ==')
    for arch, path in results.items():
        rel_path = path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path
        size = path.stat().st_size
        buildlog.info(f'build output for {arch}: {rel_path} (size: {format_size(size)})')
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

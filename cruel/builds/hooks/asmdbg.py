import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _b as nb

def before_validate_cruel(cfg_path, buildlog):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_cruel(cfg_path, buildlog):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_validate_ref(cfg_path, buildlog):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_ref(cfg_path, buildlog, references):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_validate_pypi(cfg_path, cruel_bin, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_pypi(cfg_path, cruel_bin, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_validate_whl(cfg_path, buildlog):
    project_root = nb.project_root_from_cfg(cfg_path)
    try:
        cache = nb.load_cache_module()
        cruel_bin = nb.find_cruel_bin()
        ok = nb.build_packutil_wheel(project_root, buildlog, cache, cruel_bin)
        if not ok:
            nb.clean_build_artifacts(project_root, buildlog)
        return ok
    except Exception as e:
        nb.clean_build_artifacts(project_root, buildlog)
        print(f'{e}')
        return False

def after_validate_whl(cfg_path, buildlog):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_validate_syntax(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_syntax(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_validate_imports(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_imports(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_validate_strings(cfg_path, cruel_bin, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_strings(cfg_path, cruel_bin, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_generate_warn(pysrc_dir, cruel_bin, project_root, buildlog, cache):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_generate_warn(pysrc_dir, cruel_bin, project_root, buildlog, cache, total_warns, warn_files):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_compile_src(pysrc_dir, project_root, opt, pycompile, remove_pymeta, buildlog, cache, entry_path, cruel_bin):
    project_root = Path(project_root)
    try:
        deps = nb.check_native_deps(buildlog)
        if deps is None:
            nb.clean_build_artifacts(project_root, buildlog)
            return False
        ok = nb.build_native_libs(project_root, deps, buildlog, cache, cruel_bin)
        if not ok:
            nb.clean_build_artifacts(project_root, buildlog)
        return ok
    except Exception as e:
        nb.clean_build_artifacts(project_root, buildlog)
        print(f'{e}')
        return False

def after_compile_src(pysrc_dir, project_root, opt, pycompile, remove_pymeta, buildlog, cache, entry_path, cruel_bin):
    project_root = Path(project_root)
    try:
        deps = nb.check_kotlin_deps(buildlog)
        if deps is None:
            nb.clean_build_artifacts(project_root, buildlog)
            return False
        ok = nb.build_kotlin_dex(project_root, deps, buildlog, cache, cruel_bin)
        if not ok:
            nb.clean_build_artifacts(project_root, buildlog)
        return ok
    except Exception as e:
        nb.clean_build_artifacts(project_root, buildlog)
        print(f'{e}')
        return False

def before_pack_assets(cfg_path, project_root, buildlog, cache, cruel_bin):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_pack_assets(cfg_path, project_root, buildlog, cache, cruel_bin):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_pack_cruel(cfg_path, project_root, references, build_section, build_type, buildlog, cruel_bin):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_pack_cruel(cfg_path, project_root, references, build_section, build_type, buildlog, cruel_bin, temp_dir):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def before_link_sections(temp_dir, metadata, build_name, buildlog, cruel_bin):
    try:
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_link_sections(temp_dir, metadata, build_name, buildlog, cruel_bin):
    try:
        project_root = nb.project_root_from_temp_dir(temp_dir)
        nb.clean_build_artifacts(project_root, buildlog)
        return True
    except Exception as e:
        print(f'{e}')
        return False

def on_sigkill(buildlog):
    from pathlib import Path
    import _b as nb
    try:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        nb.clean_build_artifacts(project_root, buildlog)
        return True
    except Exception as e:
        print(f'{e}')
        return False

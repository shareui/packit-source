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
    try:
        nb.create_missing_whl_stubs(cfg_path)
        return True
    except Exception as e:
        print(f'{e}')
        return False

def after_validate_whl(cfg_path, buildlog):
    try:
        nb.remove_whl_stubs(cfg_path)
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

import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
METADATA_STRING_FIELDS = ('title', 'description', 'id', 'version', 'author', 'app_version', 'sdk_version', 'icon')
METADATA_INT_FIELDS = ('version_num',)
METADATA_REQUIRED = ('title', 'description', 'id', 'version', 'version_num', 'author', 'app_version', 'sdk_version')
CONFIG_STRING_FIELDS = ('target', 'builder', 'cruel')
CONFIG_REQUIRED = ('target', 'builder', 'cruel')
REFERENCES_STRING_FIELDS = ('assets', 'strings', 'entry', 'pysrc')
BUILD_STRING_FIELDS = ('path', 'ref')
BUILD_INT_FIELDS = ('opt',)
BUILD_BOOL_FIELDS = ('remove_pymeta', 'pycompile')
BUILD_LIST_FIELDS = ('include', 'exclude')
BUILD_REQUIRED = ('path', 'opt', 'remove_pymeta', 'pycompile', 'include')

def run(cfg_path, buildlog):
    cfg_path = Path(cfg_path)
    with open(cfg_path, 'rb') as f:
        try:
            cfg = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            buildlog.error(f'cruel.toml syntax error: {e}')
            sys.exit(1)
    ok = True
    if 'metadata' in cfg:
        ok = check_metadata(cfg['metadata'], buildlog) and ok
    if 'config' in cfg:
        ok = check_config(cfg['config'], buildlog) and ok
    if 'references' in cfg:
        ok = check_references(cfg['references'], buildlog) and ok
    if 'requirements' in cfg:
        ok = check_requirements(cfg['requirements'], buildlog) and ok
    if 'build' in cfg:
        ok = check_build_table(cfg['build'], buildlog) and ok
    if not ok:
        sys.exit(1)
    return cfg_path

def require(table, required, section, buildlog):
    ok = True
    for field in required:
        if field not in table:
            buildlog.error(f'cruel.toml [{section}] is missing required field: {field}')
            ok = False
    return ok

def check_type(table, field, section, expected, type_name, buildlog):
    if field not in table:
        return True
    if not isinstance(table[field], expected):
        buildlog.error(f"cruel.toml [{section}] field '{field}' must be {type_name}")
        return False
    return True

def check_metadata(metadata, buildlog):
    ok = require(metadata, METADATA_REQUIRED, 'metadata', buildlog)
    for field in METADATA_STRING_FIELDS:
        ok = check_type(metadata, field, 'metadata', str, 'a string', buildlog) and ok
    for field in METADATA_INT_FIELDS:
        ok = check_type(metadata, field, 'metadata', int, 'an integer', buildlog) and ok
    return ok

def check_config(config, buildlog):
    ok = require(config, CONFIG_REQUIRED, 'config', buildlog)
    for field in CONFIG_STRING_FIELDS:
        if field == 'cruel':
            if 'cruel' in config:
                val = config['cruel']
                if not isinstance(val, list) or len(val) != 2 or (not all((isinstance(v, str) for v in val))):
                    buildlog.error(f"cruel.toml [config] field 'cruel' must be an array of exactly two strings")
                    ok = False
        else:
            ok = check_type(config, field, 'config', str, 'a string', buildlog) and ok
    return ok

def check_references(references, buildlog):
    ok = True
    for field in REFERENCES_STRING_FIELDS:
        ok = check_type(references, field, 'references', str, 'a string', buildlog) and ok
    return ok

def check_requirements(requirements, buildlog):
    ok = True
    if 'pypi' in requirements:
        ok = check_string_table(requirements['pypi'], 'requirements.pypi', buildlog) and ok
    if 'local' in requirements:
        ok = check_string_table(requirements['local'], 'requirements.local', buildlog) and ok
    if 'plugins' in requirements:
        ok = check_plugin_requirements(requirements['plugins'], buildlog) and ok
    return ok

def check_string_table(table, section, buildlog):
    ok = True
    for name, value in table.items():
        if not isinstance(value, str):
            buildlog.error(f"cruel.toml [{section}] entry '{name}' must be a string")
            ok = False
    return ok

def check_plugin_requirements(table, buildlog):
    ok = True
    for name, value in table.items():
        if not isinstance(value, dict):
            buildlog.error(f"cruel.toml [requirements.plugins] entry '{name}' must be a table")
            ok = False
            continue
        if 'url' in value and (not isinstance(value['url'], str)):
            buildlog.error(f"cruel.toml [requirements.plugins] entry '{name}' field 'url' must be a string")
            ok = False
        if 'version' in value and (not isinstance(value['version'], str)):
            buildlog.error(f"cruel.toml [requirements.plugins] entry '{name}' field 'version' must be a string")
            ok = False
    return ok

def check_build_table(builds, buildlog):
    ok = True
    for build_name, build in builds.items():
        section = f'build.{build_name}'
        ok = require(build, BUILD_REQUIRED, section, buildlog) and ok
        for field in BUILD_STRING_FIELDS:
            ok = check_type(build, field, section, str, 'a string', buildlog) and ok
        for field in BUILD_INT_FIELDS:
            ok = check_type(build, field, section, int, 'an integer', buildlog) and ok
        for field in BUILD_BOOL_FIELDS:
            ok = check_type(build, field, section, bool, 'a boolean', buildlog) and ok
        for field in BUILD_LIST_FIELDS:
            if field not in build:
                continue
            value = build[field]
            if not isinstance(value, list) or not all((isinstance(v, str) for v in value)):
                buildlog.error(f"cruel.toml [{section}] field '{field}' must be an array of strings")
                ok = False
    return ok

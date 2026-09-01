import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
import yaml
TASK_ID = 'pack_cruel'
TEMP_SUBDIR = Path('cruel') / 'local' / 'temp' / 'bin'
ASSETS_TEMP_SUBDIR = Path('cruel') / 'local' / 'temp' / 'assets'
PYTEMP_SUBDIR = Path('cruel') / 'local' / 'temp' / 'pytemp'
LOCALE_CONFIG_NAME = 'config.toml'
DESCRIPTION_KEY = 'plugin_description'
DEFAULT_ZSTD_LEVEL = 22
PYPI_PROJECT_URL = 'https://pypi.org/pypi/{name}/json'
PYPI_VERSION_URL = 'https://pypi.org/pypi/{name}/{version}/json'
PYPI_EXACT_VERSION_PATTERN = re.compile('^==\\s*(.+)$')
PYPI_BARE_VERSION_PATTERN = re.compile('^\\d[\\w.\\-]*$')
REFMAP_KEYS = (('entry', 'entry'), ('strings', 'strings'), ('assets', 'assets'), ('pysrc', 'pysrc'))
BUILD_HASH_SECTIONS = ('description.crulsection', 'refmap.crulsection', 'icon.crulsection', 'fsmeta.crulsection', 'fs.crulsection', 'zstdfsmeta.crulsection', 'zstdfs.crulsection', 'pypimeta.crulsection', 'pypi.crulsection')

def _find_cruel_bin():
    return shutil.which('cruel') or 'cruel'

def _load_locale_file(path):
    if path.suffix == '.json':
        with open(path, 'rb') as f:
            return json.load(f) or {}
    if path.suffix == '.py':
        namespace = {}
        exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), namespace)
        return {k: v for k, v in namespace.items() if not k.startswith('_') and (not callable(v))}
    with open(path, 'rb') as f:
        return yaml.safe_load(f) or {}

def _load_locale_map(strings_ref, buildlog):
    strings_ref = Path(strings_ref)
    config_path = strings_ref / LOCALE_CONFIG_NAME if strings_ref.is_dir() else strings_ref.parent / LOCALE_CONFIG_NAME
    if not config_path.is_file():
        buildlog.error(f"missing '{LOCALE_CONFIG_NAME}' next to strings, expected a [map] locale -> filename table")
        return None
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    locale_map = config.get('map')
    if not isinstance(locale_map, dict) or not locale_map:
        buildlog.error(f"'{LOCALE_CONFIG_NAME}' is missing a non empty [map] table")
        return None
    return locale_map

def _collect_description_tables(strings_ref, buildlog):
    strings_ref = Path(strings_ref)
    base_dir = strings_ref if strings_ref.is_dir() else strings_ref.parent
    locale_map = _load_locale_map(strings_ref, buildlog)
    if locale_map is None:
        return None
    tables = {}
    ok = True
    for locale, file_name in locale_map.items():
        path = base_dir / file_name
        if not path.is_file():
            buildlog.error(f"strings file '{file_name}' mapped to locale '{locale}' does not exist")
            ok = False
            continue
        table = _load_locale_file(path)
        text = table.get(DESCRIPTION_KEY)
        if not isinstance(text, str):
            buildlog.error(f"strings file '{path.name}' is missing string key '{DESCRIPTION_KEY}'")
            ok = False
            continue
        tables[locale] = table
    return tables if ok else None

def _parse_description_template(template):
    parts = []
    buf = []
    i = 0
    length = len(template)
    while i < length:
        ch = template[i]
        if ch == '{':
            close = template.find('}', i + 1)
            if close == -1:
                buf.append(template[i:])
                i = length
                continue
            if buf:
                parts.append(('text', ''.join(buf)))
                buf = []
            parts.append(('key', template[i + 1:close]))
            i = close + 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append(('text', ''.join(buf)))
    return parts

def _render_description_locales(metadata, tables, buildlog):
    template = metadata.get('description', '')
    parts = _parse_description_template(template)

    def substitute(table):
        out = []
        for kind, value in parts:
            if kind == 'text':
                out.append(value)
                continue
            resolved = table.get(value, '')
            out.append(resolved if isinstance(resolved, str) else '')
        return ''.join(out)
    return {locale: substitute(table) for locale, table in tables.items()}

def _collect_refmap_entries(references):
    entries = []
    for toml_key, runtime_key in REFMAP_KEYS:
        if toml_key in references:
            entries.append({'key': runtime_key, 'path': references[toml_key]})
    return entries

def _collect_fs_entries(project_root, include_patterns, exclude_patterns, assets_dir, pysrc_dir, pytemp_dir):
    excluded_dirs = (assets_dir, pysrc_dir, pytemp_dir)
    excluded_matched = set()
    for pattern in exclude_patterns:
        for path in project_root.glob(pattern):
            excluded_matched.add(path)
    matched = set()
    for pattern in include_patterns:
        for path in project_root.glob(pattern):
            matched.add(path)
    dirs = set()
    files = set()
    for path in matched:
        if any((_is_relative_to(path, excluded) for excluded in excluded_dirs)):
            continue
        if any((_is_relative_to(path, excluded) for excluded in excluded_matched)):
            continue
        if path.is_dir():
            dirs.add(path)
        elif path.is_file():
            files.add(path)
        else:
            continue
        parent = path.parent
        while parent != project_root and project_root in parent.parents:
            if any((_is_relative_to(parent, excluded) for excluded in excluded_dirs)):
                break
            dirs.add(parent)
            parent = parent.parent
    entries = {}
    for path in dirs:
        rel_path = path.relative_to(project_root).as_posix()
        entries[rel_path] = {'relative_path': rel_path, 'is_dir': True, 'source_path': None}
    for path in files:
        rel_path = path.relative_to(project_root).as_posix()
        entries[rel_path] = {'relative_path': rel_path, 'is_dir': False, 'source_path': str(path)}
    pysrc_rel_prefix = pysrc_dir.relative_to(project_root)
    for entry in _collect_pytemp_entries(pytemp_dir, pysrc_rel_prefix):
        entries[entry['relative_path']] = entry
    return [entries[key] for key in sorted(entries)]

def _is_relative_to(path, other):
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

def _collect_pytemp_entries(pytemp_dir, pysrc_rel_prefix):
    entries = []
    if not pytemp_dir.is_dir():
        return entries
    dirs = set()
    files = set()
    for path in pytemp_dir.rglob('*'):
        if path.is_dir():
            dirs.add(path)
        elif path.is_file():
            files.add(path)
    for path in dirs:
        rel_path = (pysrc_rel_prefix / path.relative_to(pytemp_dir)).as_posix()
        entries.append({'relative_path': rel_path, 'is_dir': True, 'source_path': None})
    for path in files:
        rel_path = (pysrc_rel_prefix / path.relative_to(pytemp_dir)).as_posix()
        entries.append({'relative_path': rel_path, 'is_dir': False, 'source_path': str(path)})
    return entries

def _load_assets_zstd_level(assets_dir):
    cfg_path = assets_dir / 'config.toml'
    if not cfg_path.is_file():
        return DEFAULT_ZSTD_LEVEL
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    return int(cfg.get('config', {}).get('zstd', DEFAULT_ZSTD_LEVEL))

def _collect_zstdfs_entries(assets_temp_dir):
    entries = []
    for path in sorted(assets_temp_dir.rglob('*.zst')):
        if not path.is_file():
            continue
        rel_path = path.relative_to(assets_temp_dir).as_posix()
        entries.append({'relative_path': rel_path, 'source_path': str(path)})
    return entries

def _run_crulbin(cruel_bin, args, stdin_payload=None):
    result = subprocess.run([cruel_bin, '__crulbin', *args], input=stdin_payload, capture_output=True)
    if result.returncode != 0:
        return (None, result.stderr.decode('utf-8', errors='replace').strip())
    return (result.stdout, None)

def _write_section(dest_path, data):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(data)

def _compute_build_hash(temp_dir):
    digest = hashlib.sha256()
    for name in BUILD_HASH_SECTIONS:
        path = temp_dir / name
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()
PLUGINMETA_OWN_SECTION_FIELDS = ('description', 'icon')

def _pluginmeta_extra_entries(metadata):
    entries = []
    for key, value in metadata.items():
        if key in PLUGINMETA_OWN_SECTION_FIELDS:
            continue
        text = value if isinstance(value, str) else json.dumps(value)
        entries.append({'key': key, 'value': text})
    return entries

def _pypi_exact_version(spec):
    spec = spec.strip()
    if not spec:
        return None
    match = PYPI_EXACT_VERSION_PATTERN.match(spec)
    if match:
        return match.group(1).strip()
    if PYPI_BARE_VERSION_PATTERN.match(spec):
        return spec
    return None

def _fetch_pypi_metadata(name, spec):
    version = _pypi_exact_version(spec)
    url = PYPI_VERSION_URL.format(name=name, version=version) if version else PYPI_PROJECT_URL.format(name=name)
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f'failed to fetch pypi metadata for {name}: http {response.status}')
            body = json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'failed to fetch pypi metadata for {name}: http {e.code}')
    except (urllib.error.URLError, ValueError) as e:
        raise RuntimeError(f'failed to fetch pypi metadata for {name}: {e}')
    return json.dumps(body.get('info', {}))

def _collect_pypi_wheels(requirements, project_root):
    wheels = []
    for name, rel_path in requirements.get('local', {}).items():
        if not rel_path:
            continue
        source_path = project_root / rel_path
        wheels.append({'name': name, 'file_name': Path(rel_path).name, 'source_path': str(source_path)})
    return wheels

def _pluginmeta_requirements_entries(requirements):
    pypi = [{'name': name, 'version': version} for name, version in requirements.get('pypi', {}).items()]
    wheels = [{'name': name, 'path': path} for name, path in requirements.get('local', {}).items()]
    pluginreq = [{'name': name, 'url': spec.get('url', ''), 'version': spec.get('version', '')} for name, spec in requirements.get('plugins', {}).items()]
    entries = []
    if pypi:
        entries.append({'key': 'pypi', 'value': json.dumps(pypi)})
    if wheels:
        entries.append({'key': 'wheels', 'value': json.dumps(wheels)})
    if pluginreq:
        entries.append({'key': 'pluginreq', 'value': json.dumps(pluginreq)})
    return entries

def _pack_pluginmeta(metadata, requirements, build_type, temp_dir, cruel_bin, buildlog, arch='universal'):
    buildlog.info('packing pluginmeta')
    fields = ('title', 'id', 'version', 'version_num', 'author', 'app_version', 'sdk_version')
    body = {field: metadata[field] for field in fields}
    body['is_release'] = build_type == 'release'
    body['extra'] = _pluginmeta_extra_entries(metadata) + _pluginmeta_requirements_entries(requirements) + [{'key': 'build_type', 'value': build_type}, {'key': 'arch', 'value': arch}]
    body['build_hash'] = _compute_build_hash(temp_dir)
    payload = json.dumps(body).encode('utf-8')
    data, error = _run_crulbin(cruel_bin, ['pack-pluginmeta'], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack pluginmeta: {error}')
        return False
    _write_section(temp_dir / 'pluginmeta.crulsection', data)
    buildlog.info('packed pluginmeta')
    return True

def _pack_description(locales, temp_dir, cruel_bin, buildlog):
    buildlog.info('packing description')
    payload = json.dumps({'locales': locales}).encode('utf-8')
    data, error = _run_crulbin(cruel_bin, ['pack-description'], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack description: {error}')
        return False
    _write_section(temp_dir / 'description.crulsection', data)
    buildlog.info('packed description')
    return True

def _pack_icon(icon_path, temp_dir, cruel_bin, buildlog):
    buildlog.info(f'packing icon {icon_path.name}')
    data, error = _run_crulbin(cruel_bin, ['pack-icon', str(icon_path)])
    if error is not None:
        buildlog.error(f'failed to pack icon: {error}')
        return False
    _write_section(temp_dir / 'icon.crulsection', data)
    buildlog.info(f'packed icon {icon_path.name}')
    return True

def _pack_refmap(references, temp_dir, cruel_bin, buildlog):
    buildlog.info('packing refmap')
    entries = _collect_refmap_entries(references)
    payload = json.dumps({'entries': entries}).encode('utf-8')
    data, error = _run_crulbin(cruel_bin, ['pack-refmap'], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack refmap: {error}')
        return False
    _write_section(temp_dir / 'refmap.crulsection', data)
    buildlog.info('packed refmap')
    return True

def _pack_fs(fs_entries, temp_dir, cruel_bin, buildlog):
    buildlog.info(f"packing filesystem tree ({len(fs_entries)} entr{('y' if len(fs_entries) == 1 else 'ies')})")
    fsmeta_path = temp_dir / 'fsmeta.crulsection'
    fs_path = temp_dir / 'fs.crulsection'
    payload = json.dumps({'entries': fs_entries}).encode('utf-8')
    _, error = _run_crulbin(cruel_bin, ['pack-fs', str(fsmeta_path), str(fs_path)], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack filesystem tree: {error}')
        return False
    buildlog.info('packed filesystem tree')
    return True

def _pack_zstdfs(zstdfs_entries, zstd_level, temp_dir, cruel_bin, buildlog):
    buildlog.info(f"packing zstd filesystem tree ({len(zstdfs_entries)} entr{('y' if len(zstdfs_entries) == 1 else 'ies')})")
    zstdfsmeta_path = temp_dir / 'zstdfsmeta.crulsection'
    zstdfs_path = temp_dir / 'zstdfs.crulsection'
    payload = json.dumps({'zstd_level': zstd_level, 'entries': zstdfs_entries}).encode('utf-8')
    _, error = _run_crulbin(cruel_bin, ['pack-zstdfs', str(zstdfsmeta_path), str(zstdfs_path)], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack zstd filesystem tree: {error}')
        return False
    buildlog.info('packed zstd filesystem tree')
    return True

def _pack_pypi(requirements, project_root, temp_dir, cruel_bin, buildlog):
    buildlog.info('packing requirements')
    pypi_specs = requirements.get('pypi', {})
    pypi = []
    for name, version in pypi_specs.items():
        try:
            metadata = _fetch_pypi_metadata(name, version)
        except RuntimeError as e:
            buildlog.error(str(e))
            return False
        pypi.append({'name': name, 'version': version, 'metadata': metadata})
    plugins = [{'name': name, 'url': spec.get('url', ''), 'version': spec.get('version', '')} for name, spec in requirements.get('plugins', {}).items()]
    wheels = _collect_pypi_wheels(requirements, project_root)
    pypimeta_path = temp_dir / 'pypimeta.crulsection'
    pypi_path = temp_dir / 'pypi.crulsection'
    payload = json.dumps({'pypi': pypi, 'plugins': plugins, 'wheels': wheels}).encode('utf-8')
    _, error = _run_crulbin(cruel_bin, ['pack-pypi', str(pypimeta_path), str(pypi_path)], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack pypi: {error}')
        return False
    buildlog.info('packed requirements')
    return True

def _pack_bindata(sign, project_root, temp_dir, cruel_bin, buildlog):
    buildlog.info('packing bindata')
    sections = sorted((p for p in temp_dir.glob('*.crulsection') if p.is_file()))
    entries = [{'name': p.name, 'path': str(p)} for p in sections]
    payload = json.dumps({'entries': entries, 'sign': sign}).encode('utf-8')
    data, error = _run_crulbin(cruel_bin, ['pack-bindata', str(project_root)], stdin_payload=payload)
    if error is not None:
        buildlog.error(f'failed to pack bindata: {error}')
        return False
    _write_section(temp_dir / 'bindata.crulsection', data)
    buildlog.info('packed bindata')
    return True

def run(cfg_path, project_root, references, build_section, build_type, buildlog, cruel_bin=None, arch='universal'):
    cfg_path = Path(cfg_path)
    project_root = Path(project_root)
    cruel_bin = cruel_bin or _find_cruel_bin()
    with open(cfg_path, 'rb') as f:
        cruel_cfg = tomllib.load(f)
    metadata = cruel_cfg.get('metadata', {})
    requirements = cruel_cfg.get('requirements', {})
    if 'strings' not in references:
        buildlog.error('strings field not found in [references]')
        sys.exit(1)
    if 'assets' not in references:
        buildlog.error('assets field not found in [references]')
        sys.exit(1)
    if 'pysrc' not in references:
        buildlog.error('pysrc field not found in [references]')
        sys.exit(1)
    strings_ref = project_root / references['strings']
    metadata = cruel_cfg.get('metadata', {})
    requirements = cruel_cfg.get('requirements', {})
    if 'strings' not in references:
        buildlog.error('strings field not found in [references]')
        sys.exit(1)
    if 'assets' not in references:
        buildlog.error('assets field not found in [references]')
        sys.exit(1)
    if 'pysrc' not in references:
        buildlog.error('pysrc field not found in [references]')
        sys.exit(1)
    strings_ref = project_root / references['strings']
    description_tables = _collect_description_tables(strings_ref, buildlog)
    if description_tables is None:
        sys.exit(1)
    locales = _render_description_locales(metadata, description_tables, buildlog)
    assets_dir = project_root / references['assets']
    pysrc_dir = project_root / references['pysrc']
    if arch == 'universal':
        pytemp_dir = project_root / PYTEMP_SUBDIR
    else:
        pytemp_dir = project_root / 'cruel' / 'local' / 'temp' / f'pytemp_{arch}'
    include_patterns = build_section.get('include', [])
    exclude_patterns = build_section.get('exclude', [])
    fs_entries = _collect_fs_entries(project_root, include_patterns, exclude_patterns, assets_dir, pysrc_dir, pytemp_dir)
    assets_temp_dir = project_root / ASSETS_TEMP_SUBDIR
    zstdfs_entries = _collect_zstdfs_entries(assets_temp_dir)
    zstd_level = _load_assets_zstd_level(assets_dir)
    temp_dir = project_root / TEMP_SUBDIR
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    buildlog.task_start(TASK_ID, 'pack_cruel')
    steps = [lambda: _pack_description(locales, temp_dir, cruel_bin, buildlog), lambda: _pack_refmap(references, temp_dir, cruel_bin, buildlog), lambda: _pack_fs(fs_entries, temp_dir, cruel_bin, buildlog), lambda: _pack_zstdfs(zstdfs_entries, zstd_level, temp_dir, cruel_bin, buildlog), lambda: _pack_pypi(requirements, project_root, temp_dir, cruel_bin, buildlog)]
    icon_ref = metadata.get('icon')
    if icon_ref:
        icon_path = project_root / icon_ref
        if not icon_path.is_file():
            buildlog.error(f"cruel.toml [metadata] field 'icon' points to a missing file: {icon_path}")
            sys.exit(1)
        steps.append(lambda: _pack_icon(icon_path, temp_dir, cruel_bin, buildlog))
    steps.append(lambda: _pack_pluginmeta(metadata, requirements, build_type, temp_dir, cruel_bin, buildlog, arch))
    total = len(steps) + 1
    failed = 0
    for index, step in enumerate(steps, start=1):
        if not step():
            failed += 1
        buildlog.task_progress(TASK_ID, index * 100 // total)
    if failed:
        buildlog.task_fail(TASK_ID, f'{failed} of {total} section(s) failed to pack')
        sys.exit(1)
    if build_type == 'release':
        if not _pack_bindata(True, project_root, temp_dir, cruel_bin, buildlog):
            buildlog.task_fail(TASK_ID, 'bindata section failed to pack')
            sys.exit(1)
    buildlog.task_progress(TASK_ID, 100)
    total_bytes = sum((p.stat().st_size for p in temp_dir.glob('*.crulsection') if p.is_file()))
    buildlog.info(f'written {total_bytes} bytes')
    buildlog.task_done(TASK_ID)
    return temp_dir

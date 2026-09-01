import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib
NAMESPACE = 'validate_pypi'
PROJECT_URL = 'https://pypi.org/pypi/{name}/json'
VERSION_URL = 'https://pypi.org/pypi/{name}/{version}/json'
EXACT_VERSION_PATTERN = re.compile('^==\\s*(.+)$')
BARE_VERSION_PATTERN = re.compile('^\\d[\\w.\\-]*$')

def exact_version(spec):
    spec = spec.strip()
    if not spec:
        return None
    match = EXACT_VERSION_PATTERN.match(spec)
    if match:
        return match.group(1).strip()
    if BARE_VERSION_PATTERN.match(spec):
        return spec
    return None

def url_exists(url):
    request = urllib.request.Request(url, method='HEAD')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    except urllib.error.URLError as e:
        raise RuntimeError(f'failed to reach pypi: {e}')

def run(cfg_path, cruel_bin, buildlog, cache):
    cfg_path = Path(cfg_path)
    project_root = cfg_path.parent
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    pypi = cfg.get('requirements', {}).get('pypi', {})
    ok = True
    for name, spec in pypi.items():
        version = exact_version(spec)
        cache_key = f'{name}=={version}' if version else name
        if not cache.is_record_changed(project_root, NAMESPACE, cache_key, 'ok'):
            continue
        url = VERSION_URL.format(name=name, version=version) if version else PROJECT_URL.format(name=name)
        try:
            found = url_exists(url)
        except RuntimeError as e:
            buildlog.error(str(e))
            ok = False
            continue
        if not found:
            label = f'{name}=={version}' if version else name
            buildlog.error(f'pypi package not found: {label}')
            ok = False
            continue
        cache.mark_record(project_root, NAMESPACE, cache_key, 'ok')
    if not ok:
        sys.exit(1)
    return pypi

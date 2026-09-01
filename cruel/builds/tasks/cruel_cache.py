import json
import subprocess
from pathlib import Path
CACHE_DIR = 'cruel/local/cache'
_MEMORY = {}

def _cache_path(project_root, namespace):
    return Path(project_root) / CACHE_DIR / f'{namespace}.json'

def _memory_key(project_root, namespace):
    return (str(Path(project_root).resolve()), namespace)

def _load(project_root, namespace):
    mem_key = _memory_key(project_root, namespace)
    if mem_key in _MEMORY:
        return _MEMORY[mem_key]
    cache_path = _cache_path(project_root, namespace)
    if not cache_path.is_file():
        entries = {}
    else:
        with open(cache_path, 'rb') as f:
            try:
                entries = json.load(f)
            except ValueError:
                entries = {}
    _MEMORY[mem_key] = entries
    return entries

def _save(project_root, namespace, entries):
    _MEMORY[_memory_key(project_root, namespace)] = entries
    cache_path = _cache_path(project_root, namespace)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, sort_keys=True)

def file_hash(cruel_bin, path):
    result = subprocess.run([cruel_bin, '__bithash', str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'failed to hash {path}: {result.stderr.strip()}')
    return result.stdout.strip()

def is_changed(cruel_bin, project_root, namespace, path):
    key = str(Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix())
    entries = _load(project_root, namespace)
    return entries.get(key) != file_hash(cruel_bin, path)

def mark(cruel_bin, project_root, namespace, path):
    key = str(Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix())
    entries = _load(project_root, namespace)
    entries[key] = file_hash(cruel_bin, path)
    _save(project_root, namespace, entries)

def is_record_changed(project_root, namespace, key, value):
    entries = _load(project_root, namespace)
    return entries.get(key) != value

def mark_record(project_root, namespace, key, value):
    entries = _load(project_root, namespace)
    entries[key] = value
    _save(project_root, namespace, entries)

def load_json(project_root, namespace):
    return _load(project_root, namespace)

def save_json(project_root, namespace, entries):
    _save(project_root, namespace, entries)

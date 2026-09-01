import shutil
import subprocess
import sys
from pathlib import Path
NAMESPACE = 'compile_src'
ENTRY_NAMESPACE = 'compile_src_entry'
TASK_ID = 'compile_src'
CACHE_SUBDIR = Path('cruel') / 'local' / 'cache' / 'python311'
PYTEMP_SUBDIR = Path('cruel') / 'local' / 'temp' / 'pytemp'
PYTHON311_CANDIDATES = ('python3.11', 'python3', 'python', 'py')
_WORKER_SOURCE = '\nimport importlib.util\nimport marshal\nimport struct\nimport sys\nimport types\n\n\ndef _strip_metadata(co):\n    new_consts = tuple(\n        _strip_metadata(const) if isinstance(const, types.CodeType) else const\n        for const in co.co_consts\n    )\n    kwargs = {\n        "co_consts": new_consts,\n        "co_filename": "<compiled>",\n        "co_name": "<compiled>",\n        "co_firstlineno": 1,\n    }\n    if hasattr(co, "co_qualname"):\n        kwargs["co_qualname"] = "<compiled>"\n    return co.replace(**kwargs)\n\n\nsource_path, pyc_path, dfile, optimize, remove_pymeta = sys.argv[1:6]\noptimize = int(optimize)\nremove_pymeta = remove_pymeta == "1"\n\nwith open(source_path, "rb") as f:\n    source = f.read()\n\ncode = compile(source, dfile, "exec", optimize=optimize, dont_inherit=True)\nif remove_pymeta:\n    code = _strip_metadata(code)\n\ndata = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, 0, 0) + marshal.dumps(code)\nwith open(pyc_path, "wb") as f:\n    f.write(data)\n'

def _find_python311():
    for name in PYTHON311_CANDIDATES:
        try:
            result = subprocess.run([name, '--version'], capture_output=True, text=True)
        except FileNotFoundError:
            continue
        if result.returncode == 0 and '3.11' in result.stdout + result.stderr:
            return name
    return None

def _find_cruel_bin():
    return shutil.which('cruel') or 'cruel'

def _compile_one(source_path, pyc_path, dfile, python311, opt, remove_pymeta):
    pyc_path.parent.mkdir(parents=True, exist_ok=True)
    args = [python311, '-c', _WORKER_SOURCE, str(source_path), str(pyc_path), dfile, str(opt), '1' if remove_pymeta else '0']
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr.strip()
    return None

def _copy_py_sources(sources, pysrc_dir, pytemp_dir, buildlog):
    for source_path in sources:
        rel_path = source_path.relative_to(pysrc_dir)
        dest_path = pytemp_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, dest_path)
        buildlog.info(f'  copied {rel_path}')

def _copy_entry(entry_path, pysrc_dir, project_root, pytemp_dir, cache_dir, buildlog, cache, cruel_bin):
    entry_path = Path(entry_path)
    rel_path = entry_path.relative_to(project_root)
    cached_path = cache_dir / rel_path
    digest = cache.file_hash(cruel_bin, entry_path)
    cache_hit = cached_path.is_file() and (not cache.is_record_changed(project_root, ENTRY_NAMESPACE, str(rel_path.as_posix()), digest))
    if not cache_hit:
        buildlog.info(f'caching entry {rel_path} -> {cached_path.relative_to(project_root)}')
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(entry_path, cached_path)
        cache.mark_record(project_root, ENTRY_NAMESPACE, str(rel_path.as_posix()), digest)
    else:
        buildlog.info(f'  = {rel_path}')
    if _is_relative_to(entry_path, pysrc_dir):
        pysrc_rel_path = entry_path.relative_to(pysrc_dir)
        pytemp_path = pytemp_dir / pysrc_rel_path
        pytemp_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached_path, pytemp_path)
    return cached_path

def _is_relative_to(path, other):
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

def run(pysrc_dir, project_root, opt, pycompile, remove_pymeta, buildlog, cache, entry_path=None, cruel_bin=None):
    pysrc_dir = Path(pysrc_dir)
    project_root = Path(project_root)
    cache_dir = project_root / CACHE_SUBDIR
    pytemp_dir = project_root / PYTEMP_SUBDIR
    cruel_bin = cruel_bin or _find_cruel_bin()
    buildlog.task_start(TASK_ID, 'compile_src')
    if pytemp_dir.exists():
        shutil.rmtree(pytemp_dir)
    pytemp_dir.mkdir(parents=True, exist_ok=True)
    if entry_path is not None:
        _copy_entry(entry_path, pysrc_dir, project_root, pytemp_dir, cache_dir, buildlog, cache, cruel_bin)
    entry_path_resolved = Path(entry_path).resolve() if entry_path is not None else None
    sources = sorted((p for p in pysrc_dir.rglob('*.py') if '__pycache__' not in p.parts and p.resolve() != entry_path_resolved))
    if not pycompile:
        buildlog.info('pycompile disabled, copying sources as-is')
        _copy_py_sources(sources, pysrc_dir, pytemp_dir, buildlog)
        buildlog.task_done(TASK_ID)
        return {}
    if not sources:
        buildlog.task_done(TASK_ID)
        return {}
    python311 = _find_python311()
    if python311 is None:
        buildlog.task_fail(TASK_ID, 'python 3.11 is required to compile this build, none found on PATH')
        sys.exit(1)
    compiled_paths = {}
    failures = []
    total = len(sources)
    for index, source_path in enumerate(sources, start=1):
        rel_path = source_path.relative_to(pysrc_dir)
        pyc_path = cache_dir / rel_path.with_suffix('.pyc')
        pyc_rel_path = pyc_path.relative_to(project_root)
        pytemp_path = pytemp_dir / rel_path.with_suffix('.pyc')
        cache_key = f'{rel_path.as_posix()}::opt{opt}::meta{int(remove_pymeta)}'
        digest = cache.file_hash(cruel_bin, source_path)
        cache_hit = pyc_path.is_file() and (not cache.is_record_changed(project_root, NAMESPACE, cache_key, digest))
        if cache_hit:
            buildlog.info(f'  = {rel_path}')
            compiled_paths[str(rel_path.as_posix())] = pyc_path
            pytemp_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pyc_path, pytemp_path)
            buildlog.task_progress(TASK_ID, index * 100 // total)
            continue
        buildlog.info(f'compiling {rel_path} -> {pyc_rel_path}')
        dfile = str(rel_path.as_posix())
        error = _compile_one(source_path, pyc_path, dfile, python311, opt, remove_pymeta)
        if error is not None:
            buildlog.error(f'failed to compile {rel_path}: {error}')
            failures.append(str(rel_path.as_posix()))
            buildlog.task_progress(TASK_ID, index * 100 // total)
            continue
        buildlog.info(f'compiled {rel_path}')
        compiled_paths[str(rel_path.as_posix())] = pyc_path
        cache.mark_record(project_root, NAMESPACE, cache_key, digest)
        pytemp_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pyc_path, pytemp_path)
        buildlog.task_progress(TASK_ID, index * 100 // total)
    if failures:
        buildlog.task_fail(TASK_ID, f'{len(failures)} of {total} file(s) failed to compile')
        sys.exit(1)
    buildlog.task_done(TASK_ID)
    return compiled_paths

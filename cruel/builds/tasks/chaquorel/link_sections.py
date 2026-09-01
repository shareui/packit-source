import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
TASK_ID = 'link_sections'
OUTPUT_SUBDIR = Path('cruel') / 'local' / 'output'
UNSAFE_FILENAME_CHARS = re.compile('[\\/\\\\:*?\\"<>|]')
SECTION_NAMES = ('pluginmeta', 'description', 'icon', 'refmap', 'fsmeta', 'fs', 'zstdfsmeta', 'zstdfs', 'pypimeta', 'pypi', 'bindata')
OPTIONAL_SECTION_NAMES = ('icon', 'bindata')

def _find_cruel_bin():
    return shutil.which('cruel') or 'cruel'

def _collect_sections(temp_dir, buildlog):
    sections = {}
    ok = True
    for name in SECTION_NAMES:
        path = temp_dir / f'{name}.crulsection'
        if path.is_file():
            sections[name] = str(path)
        elif name not in OPTIONAL_SECTION_NAMES:
            buildlog.error(f'missing built section: {name}.crulsection')
            ok = False
    return sections if ok else None

def _sanitize_filename_part(value):
    return UNSAFE_FILENAME_CHARS.sub('_', str(value))

def _output_path(build_name, metadata):
    if build_name == 'asmrel':
        title = _sanitize_filename_part(metadata['title'])
        version = _sanitize_filename_part(metadata['version'])
        file_name = f'{title}-{version}.crul'
    else:
        id_ = _sanitize_filename_part(metadata['id'])
        version_num = _sanitize_filename_part(metadata['version_num'])
        file_name = f'{id_}-{version_num}.crul'
    return OUTPUT_SUBDIR / build_name / file_name

def run(temp_dir, metadata, build_name, buildlog, cruel_bin=None):
    temp_dir = Path(temp_dir)
    cruel_bin = cruel_bin or _find_cruel_bin()
    buildlog.task_start(TASK_ID, 'link_sections')
    sections = _collect_sections(temp_dir, buildlog)
    if sections is None:
        shutil.rmtree(temp_dir, ignore_errors=True)
        buildlog.task_fail(TASK_ID, 'one or more sections were never built')
        sys.exit(1)
    buildlog.task_progress(TASK_ID, 30)
    out_path = _output_path(build_name, metadata)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buildlog.info(f'linking {len(sections)} section(s) into {out_path.name}')
    payload = json.dumps({'sections': sections}).encode('utf-8')
    result = subprocess.run([cruel_bin, '__crulbin', 'link-sections', str(out_path)], input=payload, capture_output=True)
    buildlog.task_progress(TASK_ID, 80)
    shutil.rmtree(temp_dir, ignore_errors=True)
    if result.returncode != 0:
        error = result.stderr.decode('utf-8', errors='replace').strip()
        buildlog.task_fail(TASK_ID, f'failed to link sections: {error}')
        sys.exit(1)
    buildlog.task_progress(TASK_ID, 100)
    buildlog.task_done(TASK_ID)
    buildlog.info(f'written {out_path.stat().st_size} bytes')
    buildlog.info(f'crul built: {out_path}')
    return out_path

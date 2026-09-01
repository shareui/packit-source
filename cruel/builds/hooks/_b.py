import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

CUSTOM_DIR = Path(__file__).resolve().parent
TASKS_DIR = CUSTOM_DIR.parent / 'tasks'

CXX_SRC_SUBDIR = Path('packit') / 'src' / 'cxx'
KOTLIN_SRC_SUBDIR = Path('packit') / 'src' / 'kotlin'
WHEEL_SRC_SUBDIR = Path('packit') / 'src' / 'wheels' / 'packutil'
JARS_SUBDIR = Path('jars')

NATIVE_OUT_SUBDIR = Path('packit') / 'native'
DEX_OUT_PATH = Path('packit') / 'dex' / 'packit.dex'
WHEEL_OUT_SUBDIR = Path('packit') / 'wheels'

SO_CACHE_SUBDIR = Path('cruel') / 'local' / 'so'
DEX_CACHE_SUBDIR = Path('cruel') / 'local' / 'dex'
WHEEL_CACHE_SUBDIR = Path('cruel') / 'local' / 'wheels'

STALE_SCRIPTS_BUILD_DIR = Path('scripts') / 'kotlin-build'

PACKITKEY_LIB_NAME = 'libpackitkey'
NATIVE_ABIS = ('arm64-v8a', 'armeabi-v7a')
NATIVE_LIBRARIES = ('libachiv', 'libbithash', 'libexport', 'libpackitdb', 'libpacklight', 'libscl', 'libsearch')

NAMESPACE_SO = 'custom_native_so'
NAMESPACE_DEX = 'custom_native_dex'
NAMESPACE_WHL = 'custom_native_whl'

WHEEL_BUILD_ARTIFACT_DIRS = ('build', 'dist', '__pycache__')


def load_cache_module():
    spec = importlib.util.spec_from_file_location('cruel_cache', TASKS_DIR / 'cruel_cache.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_root_from_cfg(cfg_path):
    return Path(cfg_path).resolve().parent


def project_root_from_temp_dir(temp_dir):
    return Path(temp_dir).resolve().parent.parent.parent.parent


def find_cruel_bin():
    return shutil.which('cruel') or 'cruel'


def _hash_tree(cruel_bin, root, is_excluded=None):
    files = sorted(
        p for p in root.rglob('*')
        if p.is_file() and (is_excluded is None or not is_excluded(p.relative_to(root)))
    )
    parts = [f'{p.relative_to(root).as_posix()}:{_file_hash(cruel_bin, p)}' for p in files]
    return '|'.join(parts)


def _file_hash(cruel_bin, path):
    result = subprocess.run([cruel_bin, '__bithash', str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'failed to hash {path}: {result.stderr.strip()}')
    return result.stdout.strip()


def _is_wheel_build_artifact(rel_path):
    return any(part in WHEEL_BUILD_ARTIFACT_DIRS or part.endswith('.egg-info') for part in rel_path.parts)


def clean_build_artifacts(project_root, buildlog):
    native_dir = project_root / NATIVE_OUT_SUBDIR
    removed = 0
    if native_dir.is_dir():
        for so_path in native_dir.rglob('*.so'):
            if so_path.stem == PACKITKEY_LIB_NAME:
                continue
            so_path.unlink()
            removed += 1
    dex_path = project_root / DEX_OUT_PATH
    if dex_path.is_file():
        dex_path.unlink()
        removed += 1
    wheels_dir = project_root / WHEEL_OUT_SUBDIR
    if wheels_dir.is_dir():
        for whl_path in wheels_dir.glob('*.whl'):
            whl_path.unlink()
            removed += 1
    stale_scripts_dir = project_root / STALE_SCRIPTS_BUILD_DIR
    if stale_scripts_dir.is_dir():
        shutil.rmtree(stale_scripts_dir)
        removed += 1
    if removed:
        buildlog.info(f'cleaned {removed} build artifact(s) from source tree')


def _find_android_ndk():
    ndk_home = os.environ.get('ANDROID_NDK_HOME')
    if ndk_home and Path(ndk_home).is_dir():
        return ndk_home
    for sdk_env in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        sdk = os.environ.get(sdk_env)
        if sdk:
            candidates = sorted(Path(sdk, 'ndk').glob('*')) if Path(sdk, 'ndk').is_dir() else []
            if candidates:
                return str(candidates[-1])
            bundle = Path(sdk, 'ndk-bundle')
            if bundle.is_dir():
                return str(bundle)
    home = Path.home()
    for base in (home / 'Android' / 'Sdk', home / 'Library' / 'Android' / 'sdk', Path('/usr/lib/android-sdk'), Path('/opt/android-sdk')):
        ndk_dir = base / 'ndk'
        if ndk_dir.is_dir():
            candidates = sorted(ndk_dir.glob('*'))
            if candidates:
                return str(candidates[-1])
        bundle = base / 'ndk-bundle'
        if bundle.is_dir():
            return str(bundle)
    return None


def _find_android_sdk():
    for sdk_env in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        sdk = os.environ.get(sdk_env)
        if sdk and Path(sdk).is_dir():
            return sdk
    home = Path.home()
    for cand in (home / 'Android' / 'Sdk', home / 'Library' / 'Android' / 'sdk', Path('/usr/lib/android-sdk'), Path('/opt/android-sdk')):
        if cand.is_dir():
            return str(cand)
    return None


def check_native_deps(buildlog):
    ndk_home = _find_android_ndk()
    if ndk_home is None:
        buildlog.error('ANDROID_NDK_HOME is not set and no NDK was found in standard SDK paths')
        buildlog.info('export ANDROID_NDK_HOME=/path/to/Android/Sdk/ndk/<version>')
        return None
    toolchain_file = Path(ndk_home) / 'build' / 'cmake' / 'android.toolchain.cmake'
    if not toolchain_file.is_file():
        buildlog.error(f'android.toolchain.cmake not found at {toolchain_file}')
        return None
    if shutil.which('cmake') is None:
        buildlog.error('cmake not found on PATH')
        return None
    return {'ndk_home': ndk_home, 'toolchain_file': str(toolchain_file)}


def check_kotlin_deps(buildlog):
    android_sdk = _find_android_sdk()
    if android_sdk is None:
        buildlog.error('android SDK not found')
        buildlog.info('export ANDROID_HOME=/path/to/Android/Sdk')
        return None
    build_tools_dir = Path(android_sdk) / 'build-tools'
    if not build_tools_dir.is_dir():
        buildlog.error(f'no build-tools under {android_sdk}')
        return None
    build_tools = sorted(build_tools_dir.glob('*'))
    if not build_tools:
        buildlog.error(f'no build-tools versions installed under {build_tools_dir}')
        return None
    d8_jar = build_tools[-1] / 'lib' / 'd8.jar'
    if not d8_jar.is_file():
        buildlog.error(f'd8.jar not found at {d8_jar} (install build-tools via sdkmanager)')
        return None
    platforms = sorted(Path(android_sdk, 'platforms').glob('android-*')) if Path(android_sdk, 'platforms').is_dir() else []
    if not platforms:
        buildlog.error(f'no android platforms installed under {android_sdk}/platforms')
        return None
    android_jar = platforms[-1] / 'android.jar'
    if not android_jar.is_file():
        buildlog.error(f'android.jar not found at {android_jar}')
        return None
    kotlinc = shutil.which('kotlinc')
    if kotlinc is None:
        buildlog.error('kotlinc not found on PATH')
        return None
    if shutil.which('javac') is None:
        buildlog.error('javac not found on PATH (install a JDK 17+)')
        return None
    return {'android_sdk': android_sdk, 'd8_jar': str(d8_jar), 'android_jar': str(android_jar), 'kotlinc': kotlinc}


def check_wheel_deps(buildlog):
    if shutil.which('python3.11') is None and shutil.which('python3') is None:
        buildlog.error('python 3.11 not found on PATH')
        return None
    try:
        import build  # noqa: F401
    except ImportError:
        buildlog.error("python 'build' package is not installed (pip install build)")
        return None
    return True


def wheel_cache_lookup(project_root, cache, cruel_bin):
    wheel_src_dir = project_root / WHEEL_SRC_SUBDIR
    wheel_cache_dir = project_root / WHEEL_CACHE_SUBDIR
    digest = _hash_tree(cruel_bin, wheel_src_dir, is_excluded=_is_wheel_build_artifact)
    manifest = cache.load_json(project_root, NAMESPACE_WHL)
    cached_name = manifest.get('file_name')
    cache_hit = cached_name and (wheel_cache_dir / cached_name).is_file() and (not cache.is_record_changed(project_root, NAMESPACE_WHL, 'packutil', digest))
    return (cached_name, digest) if cache_hit else (None, digest)


def build_native_libs(project_root, deps, buildlog, cache, cruel_bin, target_abis=None):
    if target_abis is None:
        target_abis = NATIVE_ABIS
    cxx_src_dir = project_root / CXX_SRC_SUBDIR
    so_cache_dir = project_root / SO_CACHE_SUBDIR
    native_out_dir = project_root / NATIVE_OUT_SUBDIR
    toolchain_file = deps['toolchain_file']
    build_dir = project_root / 'cruel' / 'local' / 'temp' / 'cxx-build'
    for abi in target_abis:
        (native_out_dir / abi).mkdir(parents=True, exist_ok=True)
        (so_cache_dir / abi).mkdir(parents=True, exist_ok=True)
    total = len(NATIVE_LIBRARIES) * len(target_abis)
    done = 0
    try:
        with buildlog.task(NAMESPACE_SO, 'build_native_libs') as t:
            for lib in NATIVE_LIBRARIES:
                lib_src = cxx_src_dir / lib
                lib_name = lib[3:]
                digest = _hash_tree(cruel_bin, lib_src)
                for abi in target_abis:
                    cache_key = f'{lib}::{abi}'
                    cached_so = so_cache_dir / abi / f'{lib}.so'
                    cache_hit = cached_so.is_file() and (not cache.is_record_changed(project_root, NAMESPACE_SO, cache_key, digest))
                    if not cache_hit:
                        buildlog.info(f'building {lib} for {abi}')
                        lib_build_dir = build_dir / abi / lib
                        buildlog.info(f'  configuring cmake for {lib} ({abi})')
                        cmake_configure = ['cmake', '-B', str(lib_build_dir), '-S', str(lib_src), f'-DCMAKE_TOOLCHAIN_FILE={toolchain_file}', f'-DANDROID_ABI={abi}', '-DANDROID_PLATFORM=android-21', '-DCMAKE_BUILD_TYPE=Release']
                        result = subprocess.run(cmake_configure, capture_output=True, text=True)
                        if result.returncode != 0:
                            buildlog.error(f'cmake configure failed for {lib} ({abi}): {result.stderr.strip()}')
                            raise RuntimeError(f'cmake configure failed for {lib} ({abi})')
                        buildlog.info(f'  compiling {lib} ({abi})')
                        result = subprocess.run(['cmake', '--build', str(lib_build_dir), '--config', 'Release'], capture_output=True, text=True)
                        if result.returncode != 0:
                            buildlog.error(f'cmake build failed for {lib} ({abi}): {result.stderr.strip()}')
                            raise RuntimeError(f'cmake build failed for {lib} ({abi})')
                        built_so = next(lib_build_dir.rglob(f'lib{lib_name}.so'), None)
                        if built_so is None:
                            buildlog.error(f'build for {lib} ({abi}) did not produce lib{lib_name}.so')
                            raise RuntimeError(f'build for {lib} ({abi}) did not produce lib{lib_name}.so')
                        buildlog.info(f'  caching {lib} ({abi}) -> {cached_so.relative_to(project_root)}')
                        cached_so.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(built_so, cached_so)
                        cache.mark_record(project_root, NAMESPACE_SO, cache_key, digest)
                        buildlog.info(f'built {lib} for {abi}')
                    else:
                        buildlog.info(f'  = {lib} ({abi})')
                    shutil.copyfile(cached_so, native_out_dir / abi / f'{lib}.so')
                    done += 1
                    t.progress(done * 100 // total)
    except RuntimeError:
        return False
    _restore_packitkey(project_root, so_cache_dir, native_out_dir, buildlog, target_abis)
    return True


def _restore_packitkey(project_root, so_cache_dir, native_out_dir, buildlog, target_abis=None):
    if target_abis is None:
        target_abis = NATIVE_ABIS
    for abi in target_abis:
        current = native_out_dir / abi / f'{PACKITKEY_LIB_NAME}.so'
        cached = so_cache_dir / abi / f'{PACKITKEY_LIB_NAME}.so'
        if current.is_file():
            buildlog.info(f'  caching {PACKITKEY_LIB_NAME} ({abi})')
            cached.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(current, cached)
        elif cached.is_file():
            buildlog.info(f'  restoring {PACKITKEY_LIB_NAME} ({abi}) from cache')
            current.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, current)
        else:
            buildlog.error(f'{PACKITKEY_LIB_NAME}.so ({abi}) is missing from both source and cache')


def build_kotlin_dex(project_root, deps, buildlog, cache, cruel_bin):
    kotlin_src_dir = project_root / KOTLIN_SRC_SUBDIR
    src_dir = kotlin_src_dir / 'src'
    stub_dir = kotlin_src_dir / 'stubs'
    dex_cache_dir = project_root / DEX_CACHE_SUBDIR
    dex_out_path = project_root / DEX_OUT_PATH
    cached_dex = dex_cache_dir / 'packit.dex'
    digest = _hash_tree(cruel_bin, src_dir) + '::' + _hash_tree(cruel_bin, stub_dir)
    cache_hit = cached_dex.is_file() and (not cache.is_record_changed(project_root, NAMESPACE_DEX, 'packit', digest))
    if cache_hit:
        buildlog.info('  = packit.dex')
        dex_out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached_dex, dex_out_path)
        return True
    try:
        with buildlog.task(NAMESPACE_DEX, 'build_kotlin_dex') as t:
            buildlog.info('building packit.dex')
            build_dir = project_root / 'cruel' / 'local' / 'temp' / 'kotlin-build'
            if build_dir.exists():
                shutil.rmtree(build_dir)
            stubs_classes_dir = build_dir / 'stubs'
            classes_dir = build_dir / 'classes'
            dex_dir = build_dir / 'dex'
            stubs_classes_dir.mkdir(parents=True)
            classes_dir.mkdir(parents=True)
            stub_sources = [str(p) for p in stub_dir.rglob('*.java')]
            buildlog.info(f'  compiling {len(stub_sources)} xposed stub file(s) with javac')
            result = subprocess.run(['javac', '-d', str(stubs_classes_dir), *stub_sources], capture_output=True, text=True)
            if result.returncode != 0:
                buildlog.error(f'javac failed on xposed stubs: {result.stderr.strip()}')
                raise RuntimeError('javac failed on xposed stubs')
            buildlog.info('  xposed stubs compiled')
            t.progress(25)
            kotlinc_home = Path(deps['kotlinc']).resolve().parent.parent
            kotlin_stdlib = project_root / JARS_SUBDIR / 'kotlin-stdlib.jar'
            if not kotlin_stdlib.is_file():
                buildlog.error(f'kotlin-stdlib.jar not found at {kotlin_stdlib}')
                raise RuntimeError('kotlin-stdlib.jar not found')
            kt_sources = [str(p) for p in src_dir.rglob('*.kt')]
            classpath = f"{deps['android_jar']}:{stubs_classes_dir}:{kotlin_stdlib}"
            buildlog.info(f'  compiling {len(kt_sources)} kotlin source file(s) with kotlinc')
            result = subprocess.run([deps['kotlinc'], '-no-stdlib', '-jvm-target', '1.8', '-classpath', classpath, '-d', str(classes_dir), *kt_sources], capture_output=True, text=True)
            if result.returncode != 0:
                buildlog.error(f'kotlinc failed: {result.stderr.strip()}')
                raise RuntimeError('kotlinc failed')
            buildlog.info('  kotlin sources compiled')
            t.progress(60)
            rules_path = build_dir / 'rules.pro'
            rules_path.write_text('-keep class kawaii.packetik.** { *; }\n-dontobfuscate\n-dontoptimize\n-dontwarn de.robv.android.xposed.**\n-dontwarn org.jetbrains.annotations.**\n-dontwarn kotlin.**\n', encoding='utf-8')
            annotations = sorted(kotlinc_home.glob('lib/annotations-*.jar'))
            r8_classpath_args = ['--classpath', str(stubs_classes_dir)]
            if annotations:
                r8_classpath_args += ['--classpath', str(annotations[-1])]
            java_home_lib = os.environ.get('JAVA_HOME')
            if java_home_lib is None:
                javac_path = Path(shutil.which('javac')).resolve()
                java_home_lib = str(javac_path.parent.parent)
            class_files = [str(p) for p in classes_dir.rglob('*.class')]
            r8_cmd = ['java', '-cp', deps['d8_jar'], 'com.android.tools.r8.R8', '--release', '--min-api', '26', '--lib', deps['android_jar'], '--lib', java_home_lib, *r8_classpath_args, '--pg-conf', str(rules_path), '--output', str(dex_dir), *class_files, str(kotlin_stdlib)]
            dex_dir.mkdir(parents=True, exist_ok=True)
            buildlog.info(f'  dexing {len(class_files)} class file(s) with R8')
            result = subprocess.run(r8_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                buildlog.error(f'R8 dexing failed: {result.stderr.strip()}')
                raise RuntimeError('R8 dexing failed')
            buildlog.info('  R8 dexing finished')
            t.progress(90)
            classes_dex = dex_dir / 'classes.dex'
            if not classes_dex.is_file():
                buildlog.error('R8 produced no classes.dex')
                raise RuntimeError('R8 produced no classes.dex')
            if (dex_dir / 'classes2.dex').is_file():
                buildlog.error('R8 split the output across several dex files, packit.dex must stay a single file')
                raise RuntimeError('R8 split the output across several dex files')
            buildlog.info(f'  caching packit.dex -> {cached_dex.relative_to(project_root)}')
            cached_dex.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(classes_dex, cached_dex)
            cache.mark_record(project_root, NAMESPACE_DEX, 'packit', digest)
            dex_out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached_dex, dex_out_path)
            buildlog.info('built packit.dex')
            t.progress(100)
    except RuntimeError:
        return False
    return True


def build_packutil_wheel(project_root, buildlog, cache, cruel_bin):
    wheel_src_dir = project_root / WHEEL_SRC_SUBDIR
    wheel_cache_dir = project_root / WHEEL_CACHE_SUBDIR
    wheel_out_dir = project_root / WHEEL_OUT_SUBDIR
    cached_name, digest = wheel_cache_lookup(project_root, cache, cruel_bin)
    if cached_name is not None:
        buildlog.info(f'  = {cached_name}')
        wheel_out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wheel_cache_dir / cached_name, wheel_out_dir / cached_name)
        return True
    if check_wheel_deps(buildlog) is None:
        return False
    manifest = cache.load_json(project_root, NAMESPACE_WHL)
    try:
        with buildlog.task(NAMESPACE_WHL, 'build_packutil_wheel') as t:
            buildlog.info('building packutil wheel')
            build_dir = project_root / 'cruel' / 'local' / 'temp' / 'wheel-build'
            if build_dir.exists():
                shutil.rmtree(build_dir)
            build_dir.mkdir(parents=True)
            t.progress(20)
            python_bin = shutil.which('python3.11') or shutil.which('python3')
            result = subprocess.run([python_bin, '-m', 'build', '--wheel', '--outdir', str(build_dir), str(wheel_src_dir)], capture_output=True, text=True)
            if result.returncode != 0:
                buildlog.error(f'wheel build failed: {result.stderr.strip()}')
                raise RuntimeError('wheel build failed')
            t.progress(80)
            built_wheels = list(build_dir.glob('*.whl'))
            if len(built_wheels) != 1:
                buildlog.error(f'expected exactly one built wheel, got {len(built_wheels)}')
                raise RuntimeError('expected exactly one built wheel')
            built_wheel = built_wheels[0]
            file_name = _packit_wheel_name(built_wheel.name)
            wheel_cache_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(built_wheel, wheel_cache_dir / file_name)
            manifest['file_name'] = file_name
            manifest['packutil'] = digest
            cache.save_json(project_root, NAMESPACE_WHL, manifest)
            wheel_out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wheel_cache_dir / file_name, wheel_out_dir / file_name)
            _clean_wheel_src_artifacts(wheel_src_dir)
            buildlog.info(f'built {file_name}')
            t.progress(100)
    except RuntimeError:
        return False
    return True


WHL_STUB_MARKER_SUBDIR = Path('cruel') / 'local' / 'temp' / 'whl-stubs.txt'


def create_missing_whl_stubs(cfg_path):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    project_root = project_root_from_cfg(cfg_path)
    with open(cfg_path, 'rb') as f:
        cfg = tomllib.load(f)
    local = cfg.get('requirements', {}).get('local', {})
    created = []
    for rel_path in local.values():
        if not rel_path:
            continue
        target = project_root / rel_path
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            created.append(str(target))
    marker_path = project_root / WHL_STUB_MARKER_SUBDIR
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text('\n'.join(created), encoding='utf-8')


def remove_whl_stubs(cfg_path):
    project_root = project_root_from_cfg(cfg_path)
    marker_path = project_root / WHL_STUB_MARKER_SUBDIR
    if not marker_path.is_file():
        return
    for line in marker_path.read_text(encoding='utf-8').splitlines():
        if line:
            stub_path = Path(line)
            if stub_path.is_file():
                stub_path.unlink()
    marker_path.unlink()


def _clean_wheel_src_artifacts(wheel_src_dir):
    for entry in wheel_src_dir.iterdir():
        if entry.is_dir() and (entry.name in WHEEL_BUILD_ARTIFACT_DIRS or entry.name.endswith('.egg-info')):
            shutil.rmtree(entry)


def _packit_wheel_name(standard_wheel_name):
    name, version = standard_wheel_name.split('-')[:2]
    return f'{name}-({version}).whl'
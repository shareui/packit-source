
import os
import sys
import shutil
import subprocess
from pathlib import Path
import urllib.request
import zipfile

def load_shared(name):
    import importlib.util
    script_dir = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(name, script_dir.parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

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

def _get_chaquo_sysroot(project_root, arch, buildlog):
    version = "3.11.14-0"
    maven_url = f"https://repo.maven.apache.org/maven2/com/chaquo/python/target/{version}/target-{version}-{arch}.zip"
    cache_dir = project_root / "cruel" / "local" / "cache" / "chaquo-sysroot" / version / arch
    
    if (cache_dir / "include" / "python3.11").exists() and (cache_dir / "jniLibs" / arch / "libpython3.11.so").exists():
        return cache_dir
    
    buildlog.info(f"Downloading Chaquopy sysroot for {arch} from Maven...")
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "target.zip"
    
    try:
        req = urllib.request.Request(maven_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(cache_dir)
        zip_path.unlink()
    except Exception as e:
        buildlog.error(f"Failed to download or extract Chaquopy sysroot: {e}")
        shutil.rmtree(cache_dir, ignore_errors=True)
        sys.exit(1)
        
    return cache_dir


def _rewrite_java_imports(content, project_root):
    import ast
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    from pathlib import Path
    
    try:
        tree = ast.parse(content)
    except Exception:
        return content

    include_patterns = {"android", "androidx", "com", "java", "kotlin", "org", "de"}
    exclude_patterns = set()
    
    config_path = Path(project_root) / "cruel" / "configs" / "chaquo.toml"
    if config_path.is_file():
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            jclass = data.get("convert_to_jclass", {})
            if "include" in jclass:
                include_patterns = set(jclass["include"])
            if "exclude" in jclass:
                exclude_patterns = set(jclass["exclude"])
        except Exception:
            pass

    class Transformer(ast.NodeTransformer):
        def __init__(self):
            self.did_change = False
            
        def visit_ImportFrom(self, node):
            if getattr(node, 'level', 0) != 0 or not getattr(node, 'module', None):
                return node
            
            def matches(module_name, patterns):
                root = module_name.split('.')[0]
                for pat in patterns:
                    if module_name == pat or module_name.startswith(pat + ".") or root == pat:
                        return True
                return False

            is_included = matches(node.module, include_patterns)
            is_excluded = matches(node.module, exclude_patterns)
                    
            if is_included and not is_excluded and all(alias.name != "*" for alias in node.names):
                self.did_change = True
                new_nodes = []
                for alias in node.names:
                    target = alias.asname or alias.name
                    assign_str = f"{target} = __import__('java').jclass('{node.module}.{alias.name}')"
                    new_nodes.extend(ast.parse(assign_str).body)
                return new_nodes
            return node

    t = Transformer()
    new_tree = t.visit(tree)
    if t.did_change:
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    return content

    JAVA_PACKAGE_ROOTS = {"android", "androidx", "com", "java", "kotlin", "org", "de"}
    
    class Transformer(ast.NodeTransformer):
        def __init__(self):
            self.did_change = False
            
        def visit_ImportFrom(self, node):
            if getattr(node, 'level', 0) != 0 or not getattr(node, 'module', None):
                return node
            root = node.module.split('.')[0]
            if root in JAVA_PACKAGE_ROOTS and all(alias.name != "*" for alias in node.names):
                self.did_change = True
                new_nodes = []
                for alias in node.names:
                    target = alias.asname or alias.name
                    assign_str = f"{target} = __import__('java').jclass('{node.module}.{alias.name}')"
                    new_nodes.extend(ast.parse(assign_str).body)
                return new_nodes
            return node

    t = Transformer()
    new_tree = t.visit(tree)
    if t.did_change:
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    return content

def _compile_one(source_path, so_path, pytemp_dir, project_root, arch, buildlog):
    ndk_home = _find_android_ndk()
    if not ndk_home:
        buildlog.error("ANDROID_NDK_HOME is not set and no NDK was found in standard SDK paths")
        buildlog.info("export ANDROID_NDK_HOME=/path/to/Android/Sdk/ndk/<version>")
        sys.exit(1)
        
    sysroot_dir = _get_chaquo_sysroot(project_root, arch, buildlog)
    
    so_path.parent.mkdir(parents=True, exist_ok=True)
    
    chaquo_build = pytemp_dir.parent / "chaquo_build"
    shutil.rmtree(chaquo_build, ignore_errors=True)
    chaquo_build.mkdir(parents=True, exist_ok=True)
    
    c_file = chaquo_build / f"{source_path.stem}.c"
    
        # -- INJECTED: Rewrite Java Imports before Cython --
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            source_content = f.read()
    except Exception:
        source_content = ""
        
    morphed_content = _rewrite_java_imports(source_content, project_root)
    
    temp_py_file = chaquo_build / f"{source_path.name}"
    with open(temp_py_file, "w", encoding="utf-8") as f:
        f.write(morphed_content)
    
    cython_cmd = [sys.executable, "-m", "cython", "-3", str(temp_py_file), "-o", str(c_file)]
    # --------------------------------------------------
    res = subprocess.run(cython_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return res.stderr.strip() or res.stdout.strip()
    
    ndk_bin = Path(ndk_home) / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    target_api = "24"
    
    if arch == "arm64-v8a":
        target = f"aarch64-linux-android{target_api}"
        cc = ndk_bin / f"{target}-clang"
        strip = ndk_bin / "llvm-strip"
    elif arch == "armeabi-v7a":
        target = f"armv7a-linux-androideabi{target_api}"
        cc = ndk_bin / f"{target}-clang"
        strip = ndk_bin / "llvm-strip"
    else:
        buildlog.error(f"Unsupported arch: {arch}")
        sys.exit(1)
        
    inc_python = sysroot_dir / "include" / "python3.11"
    inc_other = sysroot_dir / "include"
    lib_dir = sysroot_dir / "jniLibs" / arch
    
    clang_cmd = [
        str(cc), "-shared", "-fPIC", "-Os", "-Wno-unused-result", "-Wno-unreachable-code",
        f"-I{inc_python}", f"-I{inc_other}", str(c_file), "-o", str(so_path),
        f"-L{lib_dir}", "-lpython3.11"
    ]
    
    res = subprocess.run(clang_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return res.stderr.strip() or res.stdout.strip()
        
    subprocess.run([str(strip), str(so_path)], check=False)
    shutil.rmtree(chaquo_build, ignore_errors=True)
    return None

def run(pysrc_dir, project_root, opt, pycompile, remove_pymeta, buildlog, cache, entry_path=None, cruel_bin=None):
    arch = "arm64-v8a"
    buildlog.info(f"compilation started for {arch}")
    
    pytemp_dir = project_root / "cruel" / "local" / "temp" / f"pytemp_{arch}"
    if pytemp_dir.exists():
        shutil.rmtree(pytemp_dir)
    pytemp_dir.mkdir(parents=True)
    
    cache_dir = project_root / "cruel" / "local" / "cache" / "chaquorel" / arch
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    sources = sorted(p for p in pysrc_dir.rglob("*.py") if p.is_file())
    if entry_path and entry_path in sources:
        sources.remove(entry_path)
        

    config_state = "default"
    config_path = project_root / "cruel" / "configs" / "chaquo.toml"
    if config_path.is_file():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            jclass = data.get("convert_to_jclass", {})
            config_state = str(sorted(jclass.get("include", []))) + "|" + str(sorted(jclass.get("exclude", [])))
        except Exception:
            pass
            
    import hashlib
    config_hash = hashlib.md5(config_state.encode()).hexdigest()[:8]
    
    compiled_files = []
    
    with buildlog.task("compile_chaquo_arm8", "compile_chaquo_arm8") as t:
        total = len(sources)
        for i, source_path in enumerate(sources):
            rel_path = source_path.relative_to(pysrc_dir)
            digest = cache.file_hash(cruel_bin, source_path) + "-" + config_hash
            
            so_path = cache_dir / rel_path.with_suffix(".so")
            
            cache_hit = False
            if so_path.is_file():
                if not cache.is_record_changed(project_root, f"compile_chaquo_{arch}", str(rel_path), digest):
                    cache_hit = True
                    
            if cache_hit:
                buildlog.info(f"  = {rel_path.with_suffix('.so')}")
            else:
                buildlog.info(f"  ~ {rel_path.with_suffix('.so')}")
                err = _compile_one(source_path, so_path, pytemp_dir, project_root, arch, buildlog)
                if err:
                    buildlog.error(f"failed to compile {rel_path}:\n{err}")
                    sys.exit(1)
                cache.mark_record(project_root, f"compile_chaquo_{arch}", str(rel_path), digest)
                
            dest_path = pytemp_dir / rel_path.with_suffix(".so")
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(so_path, dest_path)
            compiled_files.append(dest_path)
            
            t.progress(int((i + 1) / total * 100))
            
    if entry_path and entry_path.is_file():
        rel_entry = entry_path.relative_to(pysrc_dir)
        dest_entry = pytemp_dir / rel_entry
        dest_entry.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(entry_path, dest_entry)
        compiled_files.append(dest_entry)
        
    return compiled_files

# PackIt

The largest plugin for exteraGram and AyuGram — a full resource catalog built entirely as a plugin. Install other plugins, icon packs, and fonts without leaving PackIt. Everything you need in one place, all inside a single plugin.

---

## Features

- Install and update plugins from multiple repositories
- Instant plugin installation via URL with automatic dependency resolution
- Icon pack distribution and installation via URL
- Plugin version history
- Export and import plugins between clients
- Multi-repository support
- Local achievements system
- AI-powered plugin search
- Native UI built entirely on `android.view`: the best interface among all exteraGram/AyuGram plugins
- A large ecosystem is planned

## Building

PackIt is not pure Python. Besides the `packit/src/python` plugin code, the build
also compiles native C++ libraries, a Kotlin/dex module, and a Python wheel, then
packs everything into the final plugin file. See [CONTRIBUTING.md](CONTRIBUTING.md#build-system)
for how these steps are wired into the `cruel` build system.

### Requirements

**Python**
- Python 3.11
- [cruel-wrapper](https://pypi.org/project/cruel-wrapper/) main building tool
- [build](https://pypi.org/project/build/) used to build the wheels
- [tomllib](https://docs.python.org/ru/3/library/tomllib.html) configs

**Native libraries (.so) — CMake + Android NDK**
- `cmake` available on `PATH`
- Android NDK. Resolved in this order, first match wins:
  1. `$ANDROID_NDK_HOME`, if it points at an existing directory
  2. `$ANDROID_HOME/ndk/<highest version>` or `$ANDROID_SDK_ROOT/ndk/<highest version>`
  3. `$ANDROID_HOME/ndk-bundle` or `$ANDROID_SDK_ROOT/ndk-bundle`
  4. `~/Android/Sdk/ndk/<highest version>` or `~/Library/Android/sdk/ndk/<highest version>` (or their `ndk-bundle`)
  5. `/usr/lib/android-sdk/ndk/<highest version>` or `/opt/android-sdk/ndk/<highest version>` (or their `ndk-bundle`)
  - if none of these resolve, the build fails with `ANDROID_NDK_HOME is not set and no NDK was found in standard SDK paths`: fix it by exporting `ANDROID_NDK_HOME` yourself:
    ```sh
    export ANDROID_NDK_HOME=/path/to/Android/Sdk/ndk/<version>
    ```
  - if a candidate is found but is missing `build/cmake/android.toolchain.cmake`, the build fails with `android.toolchain.cmake not found at <path>` — install a valid NDK
  - if `cmake` isn't on `PATH`, the build fails with `cmake not found on PATH`
- Compiles `arm64-v8a` and `armeabi-v7a` for: `libachiv`, `libbithash`, `libexport`, `libpackitdb`, `libpacklight`, `libscl`, `libsearch`
- `libpackitkey.so` is prebuilt and checked into `packit/native/<abi>/` — it is never compiled, only cached and restored

**Kotlin / dex (.dex): kotlinc + R8**
- Android SDK. Resolved in this order, first match wins:
  1. `$ANDROID_HOME`, if it points at an existing directory
  2. `$ANDROID_SDK_ROOT`, if it points at an existing directory
  3. `~/Android/Sdk`, `~/Library/Android/sdk`, `/usr/lib/android-sdk`, `/opt/android-sdk`
  - if none resolve, the build fails with `android SDK not found`, fix it with:
    ```sh
    export ANDROID_HOME=/path/to/Android/Sdk
    ```
- Once an SDK is found, all of the following must also be true, checked in order:
  - `<sdk>/build-tools/` must exist and contain at least one version, else `no build-tools under <sdk>` / `no build-tools versions installed under <sdk>/build-tools`
  - the highest installed build-tools version must contain `lib/d8.jar`, else `d8.jar not found at <path> (install build-tools via sdkmanager)`
  - `<sdk>/platforms/android-*` must contain at least one platform, else `no android platforms installed under <sdk>/platforms`
  - the highest installed platform must contain `android.jar`, else `android.jar not found at <path>`
  - `kotlinc` must be on `PATH`, else `kotlinc not found on PATH`
  - `javac` must be on `PATH` (JDK 17+), else `javac not found on PATH (install a JDK 17+)` — used to compile the Xposed stub sources before the Kotlin sources
- `jars/kotlin-stdlib.jar` must be present in the repo (already included); if missing, `kotlin-stdlib.jar not found at <path>`

**Python wheel (.whl)**
- needs the same `python3.11`/`python3` and `build` package as above — checked
  separately, fails with `python 3.11 not found on PATH` or `python 'build' package
  is not installed (pip install build)`
- `packit/src/wheels/packutil` is built with `python -m build --wheel` and renamed to
  the `packutil-(x.y.z).whl` format expected by `[requirements.local]` in `cruel.toml`

Every check above runs before the corresponding step starts, so a missing tool
fails fast with the exact message and, where relevant, the exact command to fix it —
you don't get a build partway through and then a cryptic compiler error.

### Debug build

Install the cruel wrapper package: [crulw-releases](https://github.com/exteraSquad/crulw-releases/releases)

Make sure the requirements above (NDK, Android SDK, kotlinc, JDK, build) are
installed and discoverable, then run:

```sh
crulw make asmdbg
```

### Release build

First go to the @{palceholder} bot and get your developer key.

Setup
```sh
crulw key-gen {key}
```

Then run the release build:
```sh
crulw make asmrel
```

## Community

Central channel: [@packitX](https://t.me/packitX)  
RU channel: [@packitapp](https://t.me/packitapp)  
EN channel: [@packitappen](https://t.me/packitappen)  
Forum: [@packitGround](https://t.me/packitGround)  

## License

[GPL v3.0](https://github.com/shareui/packit-source/blob/main/LICENSE) 2026
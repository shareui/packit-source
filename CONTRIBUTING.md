# Contributing

## Where things located

```
packit/
  locales/          strings_{en,ru,de,be}.yml — the only place UI text belongs
  res/              fonts, sounds, videos, drawables shipped with the plugin
  dex/              packit.dex — all of kawaii.packetik, built from src/kotlin
  native/           .so files per ABI
  wheels/           built packutil wheel
  src/
    python/         the plugin itself, everything below — the package root
    kotlin/         src/ and the compile-only Xposed stubs
    cxx/            native libraries, one folder per lib, built via CMake
    wheels/         python packages built into wheels, e.g. packutil

jars/               prebuilt .jar stubs (kotlin-stdlib, etc)
```

`jars/` is for stub jars under 15mb only. Above that, hand-write a stub instead
— a jar that size bloats the repo more than a stub costs to write.

`src/` holds one folder per language; `src/python` is the package root the
builder's `source:` points at, so moving it means moving the builder config too.

### `src/` layout by language

- **`src/python`** — the plugin itself. Core source.
- **`src/kotlin`** — the dex part. `src/kotlin/src` compiles into
  `packit/dex/packit.dex`; `src/kotlin/stubs` are compile-only Xposed stubs.
  Kotlin only, except stubs where Java is fine (nothing substantial goes there).
- **`src/cxx`** — C/C++, one folder per library (`libachiv`, `libscl`, ...),
  each with its own `CMakeLists.txt`. Builds go through CMake, not ad-hoc
  compiler invocations.
- **`src/wheels`** — Python packages built into `.whl` and installed for
  import anywhere in the project, e.g. `packutil`.
- **any other language** (Rust, Go, etc.) — `src/{lang}/{projectname}`, create
  the folder if needed. File placement follows the entry point/config file,
  or the language governing the surrounding code; with no config file, wherever
  that language has the most code.

Every native library except `libpackitkey` is built from its sources in this
repo — no other checked-in prebuilt binaries. `libpackitkey` is closed-source,
restored only from cache or from what's already in `packit/native/`; see
`packit/src/cxx/libpackitkey/info.txt` for why.

A library's upstream source location (if pulled in rather than written here)
is tracked in `curl.toml`, not in code. Update that entry if the upstream moves.

There is one dex, not one per Kotlin package — R8 emits a single `classes.dex`,
so splitting by name just shipped the same bytes repeatedly. Add a class under
`kawaii.packetik.*`, rebuild (see Build system), reach it from
`core/DexLoader.py` by fully qualified name — nothing else changes.

`src/python` is laid out by what a module *is*, not which client screen it touches:

```
src/python/
  BasePlugin.py     the entry point — the class the loader looks for
  Main.py           startup, hooks, lifecycle

  core/             installing and removing plugins, loading dexes and native libraries, the repository list itself
  network/          everything that goes over the wire to a repository
  utils/            helpers with no UI of their own, including where files live on disk
  scl/              the TOML parser (native-backed) used for .afp files and plugin export
  ui/               the plugin's own screens
    MainActivity.py   builds the plugin's settings root
    components/       pieces screens are assembled from — never a screen
    dialogs/          sheets and dialogs that belong to no single screen
    settings/         the plugin's settings pages
    plugins/ plugin/ icons/ repos/ updates/ files/
    achievements/ contributors/ suggest/
  integrations/     code that reaches into a screen the *client* owns
    chat/             the chat screen: import sheets, inline mode, security
    chatlist/         the dialogs list: buttons, widgets, update sheet
    hooks/            hooks into the client's own settings and fragments
    decorations/      badges and title icons drawn into client UI
  deeplinks/        one module per tg://packit?… route, dispatched by
                    DeepHandler
```

### Where do I put a new file?

| What you are adding | Where it goes |
|---|---|
| A screen of the plugin's own | `ui/<screen>/Fragment.py`, with its sheets and helpers beside it |
| A dialog or sheet used by one screen | that screen's package |
| A dialog or sheet used by several | `ui/dialogs/` |
| A reusable widget, or a view helper | `ui/components/` |
| A page in the plugin's settings | `ui/settings/subsettings/` and register it in `ui/settings/Settings.py` |
| Something drawn into the client's chat, chat list or profile | `integrations/<area>/` |
| A hook into a client class | `integrations/hooks/` |
| A new `tg://packit?…` route | `deeplinks/<Route>.py`, registered in `deeplinks/DeepHandler.py` |
| A pure helper — parsing, hashing, paths, formatting | `utils/` |
| Anything that downloads from a repository | `network/Storage.py` — do not add a second one |
| Anything that reads `reposCache/{rm_rid}.json` | `utils/CachedRepos.py` — same rule |
| User-visible text | `packit/locales/strings_*.yml`, all four in lockstep |

A file with no obvious home is usually doing two things — split it before inventing a folder.

### Naming

- **Folders are lowercase**, no separators: `ui/plugins`, `integrations/chatlist`.
- **Modules are PascalCase**: `CachedRepos.py`, `AddSheet.py`, `EnterView.py`.
- Fixed, never renamed: `BasePlugin.py` (builder's `compilationIgnore` points
  to it by path) and `__init__.py` (Python's).

### Imports

All imports inside `src/python` are relative — `from ..utils import Paths`,
never absolute from the package root. Moving a file changes the dot count.

Two modules are the only way to reach a repository, and which one you want is
readable from the call:

```python
from ..utils import CachedRepos    # off disk, no network, safe anywhere
from ..network import Storage      # over the network, never on the UI thread

url = CachedRepos.plugins_url(repo)
plugins, error = Storage.fetch_plugins(url)
```

---

## Logging

**Always use `logx` from `packutil` for all logs. Never use `log` from `android_utils` directly.**

Full reference and docs: `docs/packutil.md` file.

## Build system

See [README.md](README.md#building) for what to install. This section covers
how the pieces are wired — useful if touching the build itself.

`asmdbg`/`asmrel` (`cruel/builds/asmdbg.py`, `cruel/builds/asmrel.py`) are
`cruel`'s own pipelines: validate config, validate references, validate
pypi/whl requirements, validate python syntax/imports/strings, generate warns,
compile python source, pack assets, pack into the cruel container, link
sections, optionally adb-push. Each step has a `before_<step>`/`after_<step>`
hook `cruel` calls if defined.

PackIt's hooks live in `cruel/builds/custom/asmdbg.py` and `asmrel.py`, both
importing shared helpers from `cruel/builds/custom/_b.py` (`import _b as nb`)
to build the non-python parts at the right pipeline point:

| Hook | Does |
|---|---|
| `before_validate_whl` | builds the `packutil` wheel (`nb.build_packutil_wheel`) |
| `before_compile_src` | checks NDK/cmake (`nb.check_native_deps`), then builds the native `.so` libs (`nb.build_native_libs`) |
| `after_compile_src` | checks Android SDK/kotlinc/javac (`nb.check_kotlin_deps`), then builds `packit.dex` (`nb.build_kotlin_dex`) |
| `after_link_sections` | removes generated build artifacts from the source tree (`nb.clean_build_artifacts`) |

All other hooks in `asmdbg.py`/`asmrel.py` are no-ops (`return True`) —
extension points, nothing runs there today.

If a `before_*`/`after_*` hook returns `False`, `cruel` aborts immediately;
`clean_build_artifacts` still runs, so a failed build never leaves half-built
`.so`/`.dex`/`.whl` files in `packit/`.

**Caching.** `_b.py` hashes each library's/module's source tree (`cruel
__bithash`) against the last recorded hash. Unchanged sources are restored
from `cruel/local/{so,dex,wheels}` instead of rebuilt. `libpackitkey.so` is the
exception — never compiled here, only carried forward from cache (or from
`packit/native/`) so it survives `clean_build_artifacts`.

**`asmdbg` vs `asmrel`.** Same native/kotlin/wheel steps. Differences live in
`cruel.toml`: `asmrel` compiles with `opt = 2` and strips `pymeta`, `asmdbg`
doesn't; only `asmrel` is signed with the developer key from `crulw key-gen`.

Document new hooks/build steps here as the build system grows.

---

## Pull requests

- **No hardcoded UI strings.** Everything user-visible goes through
  `packit/locales/strings_*.yml`, at minimum in English (see [Where do I put a
  new file?](#where-do-i-put-a-new-file)). Exceptions: log messages (plain
  English, not localized) and names (plugins, classes, identifiers).
- **No empty excepts.** Every `except` needs at least `logx(f"...{e}", False)`
  — see [Logging](#logging). Never swallow silently.
- **AI-written code must be tested, at minimum, before opening a PR.** Human
  review is better than testing alone; testing alone is the floor, not untested.
- **New dependency, or anything that changes what gets built?** Update the
  custom build scripts to match (see [Build system](#build-system)). A PR
  adding a library the build doesn't know about isn't done.
- **In `cruel/builds/`, only touch `cruel/builds/custom/` and `_b.py`**, or add
  your own alongside them. Don't edit `cruel`'s own pipeline files
  (`asmdbg.py`/`asmrel.py` at top level, `tasks/`).
- **Architecture changes get discussed first.** New layers, new patterns, or
  moves across the language/module boundaries above — raise it at
  [shareui](https://t.me/shareui) before writing the code, not after.
- **Follow the naming rules and existing structure** (see
  [Naming](#naming), [Where things located](#where-things-located)). No
  parallel conventions for one PR's convenience.
- **No closed-source libraries.** `libpackitkey` is the sole exception to
  [every native library builds from its own sources here](#src-layout-by-language) —
  a PR doesn't add a second one.
- **Use `logx` correctly.** Not `log` from `android_utils`, and not with
  `isDebug` backwards — see [Logging](#logging) and [packutil.md](packutil.md).
- **Non-plugin-specific helpers belong in `packutil`**, not scattered through
  `src/python/utils/` — see [`src/wheels`](#src-layout-by-language).
- **Think before you write.** No sloppy code shipped just because it ran once.
  Unsure of the approach? Ask at [shareui](https://t.me/shareui) before
  writing, not instead of writing it properly.
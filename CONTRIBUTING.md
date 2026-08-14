# Contributing

## Where things live

```
packit/
  meta.yml          plugin name, id, version, minimum client and SDK
  locales/          strings_{en,ru,de,be}.json — the only place UI text belongs
  res/              fonts, sounds, drawables shipped with the plugin
  dex/              compiled Kotlin, built from kotlin/
  native/           .so files per ABI
  src/
    python/         everything below — the plugin itself

kotlin/             Kotlin sources for the dexes in packit/dex
scripts/            one-off tooling; yours goes in scripts/{username}/
```

`src/` holds one folder per language the plugin is written in, and `src/python`
is the package root — the path `refmap.yml` and the builder's `source:` both
point at. Move it and those two have to move with it.

It is laid out by what a module *is*, not by which client screen it happens to
touch:

```
src/python/
  BasePlugin.py     the entry point — the class the loader looks for
  Main.py           startup, hooks, lifecycle

  core/             installing and removing plugins, loading dexes and native
                    libraries, the repository list itself
  network/          everything that goes over the wire to a repository
  utils/            helpers with no UI of their own, including where files
                    live on disk
  scl/              the TOML parser (native-backed) used for .afp files and
                    plugin export

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
| User-visible text | `packit/locales/strings_*.json`, all four in lockstep |

If a file does not obviously belong anywhere, that is usually a sign it does
two things. Split it before inventing a folder for it.

### Naming

- **Folders are lowercase**, no separators: `ui/plugins`, `integrations/chatlist`.
- **Modules are PascalCase**: `CachedRepos.py`, `AddSheet.py`, `EnterView.py`.
- Two names are fixed and must not be renamed: `BasePlugin.py`, which
  `refmap.yml` and the builder's `compilationIgnore` both point at by path, and
  `__init__.py`, which is Python's.

### Imports

All imports inside `src/python` are relative — `from ..utils import Paths`,
never an absolute path from the package root. When you move a file, remember that
the number of dots changes with its depth.

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

```python
from packutil import logx
```

---

### When to use `isDebug=True` vs `isDebug=False`

The rule is simple: think about who the log is for.

**`isDebug=False` — always shown. Use for errors and unexpected states.**

These are logs that help a user report a bug. Something went wrong, an exception was caught, a critical path failed. The user should be able to open logcat, find this line, and send it in a bug report.

```python
try:
    result = do_something()
except Exception as e:
    logx(f"module: do_something failed: {e}", False)
```

**`isDebug=True` — shown only when Debug Logs switch is enabled. Use for informational flow.**

These are logs that describe what the code is doing: a value was loaded, a step completed, a branch was taken. They are useful during development or when diagnosing a specific issue, but not useful to an average user. They add noise and should be hidden by default.

```python
logx(f"module: loaded config, entries={len(entries)}", True)
logx(f"module: cache hit for key={key}", True)
```

**Quick rule:**

| Log contains `{e}` or describes a failure | `isDebug=False` |
|---|---|
| Log describes normal flow or state | `isDebug=True` |

---

### `logx` reference

```python
from packutil import logx

logx(msg: str, isDebug: bool)
```

| Parameter | Type | Description |
|---|---|---|
| `msg` | `str` | The log message |
| `isDebug` | `bool` | `True` = shown only when Debug Logs is enabled. `False` = always shown. |

Internally `logx` calls `android_utils.log()`. When `isDebug=True` and the Debug Logs switch (Settings → Debug menu → Debug logs) is off, the call is a no-op.

---

### Examples

```python
from packutil import logx

# always shown: exception caught, user may need to report this
try:
    data = fetch_data()
except Exception as e:
    logx(f"repo: fetch_data error: {e}", False)

# debug only: routine info, hidden from normal users
logx(f"repo: fetch_data returned {len(data)} items", True)
logx(f"repo: cache miss, fetching from network", True)
```

---

### Scripts

If you need to use the script for yourself, either create a directory `scripts/{username}/` or add it to `.gitignore`
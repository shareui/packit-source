# Main utils package: packutil

Shared utility wheel, built from `src/wheels/packutil` and installed so it's
importable from anywhere in the project.

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

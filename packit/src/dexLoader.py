# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Loads precompiled Kotlin dexes shipped in packit/dex/<abi>/ and calls their
# entrypoints. Currently used for the badge system (kawaii.packetik.badges),
# ported from packit/src/other/{badges,chatBadge,chatTitleIcon,profileTitleIcon}.py.

from packutil import logx
import os

from .nativeLoader import detectArch

_DEX_BASE = "/plugins/ElyxPlugins/shareui_packit/packit/dex"
_BADGES_CLASS = "kawaii.packetik.badges.BadgesNative"

# loaded entrypoint Class objects, keyed by dex name (kept for later calls)
_loaded = {}


def _dexPath(name: str) -> str:
    from .utils.paths import _filesDir
    return _filesDir() + _DEX_BASE + "/" + detectArch() + "/" + name + ".dex"


def _optDir() -> str:
    from .utils.paths import getCacheRoot
    return getCacheRoot() + "/.cache/dex"


def _loadClass(dexName: str, className: str, context):
    # loads className from packit/dex/<abi>/<dexName>.dex via DexClassLoader
    # whose parent is the host app classloader (so host classes resolve).
    cached = _loaded.get(dexName)
    if cached is not None:
        return cached
    dex_path = _dexPath(dexName)
    if not os.path.exists(dex_path):
        logx(f"dexLoader: {dexName}.dex not found at {dex_path}", False)
        return None
    opt_dir = _optDir()
    os.makedirs(opt_dir, exist_ok=True)
    from dalvik.system import DexClassLoader
    parent_cl = context.getClassLoader()
    loader = DexClassLoader(dex_path, opt_dir, None, parent_cl)
    cls = loader.loadClass(className)
    _loaded[dexName] = cls
    logx(f"dexLoader: loaded {className} from {dexName}.dex", True)
    return cls


def _callStatic(cls, method: str, *args):
    # invoke a static method on a dynamically loaded class via the host's
    # XposedHelpers (best-match resolution, same as elsewhere in the plugin)
    from de.robv.android.xposed import XposedHelpers
    return XposedHelpers.callStaticMethod(cls, method, *args)


def loadBadges(context, enabled: bool) -> bool:
    # loads badges.dex and calls BadgesNative.init(classLoader, context, enabled).
    # returns True on success; caller falls back to the Python impl on False.
    try:
        if context is None:
            from org.telegram.messenger import ApplicationLoader
            context = ApplicationLoader.applicationContext
        cls = _loadClass("badges", _BADGES_CLASS, context)
        if cls is None:
            return False
        _callStatic(cls, "init", context.getClassLoader(), context, bool(enabled))
        logx("dexLoader: badges init ok", True)
        return True
    except Exception as e:
        logx(f"dexLoader: loadBadges error: {e}", False)
        return False


def setBadgesEnabled(enabled: bool):
    try:
        cls = _loaded.get("badges")
        if cls is not None:
            _callStatic(cls, "setEnabled", bool(enabled))
    except Exception as e:
        logx(f"dexLoader: setBadgesEnabled error: {e}", False)


def unloadBadges():
    try:
        cls = _loaded.get("badges")
        if cls is not None:
            _callStatic(cls, "deinit")
    except Exception as e:
        logx(f"dexLoader: unloadBadges error: {e}", False)

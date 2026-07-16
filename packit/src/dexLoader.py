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


def _loadClass(dexName: str, className: str, context):
    # loads className from packit/dex/<abi>/<dexName>.dex whose parent is the
    # host app classloader (so host classes resolve).
    #
    # Uses InMemoryDexClassLoader (API 26+; PackIt requires Android 13+): the
    # plugin dir is writable by the app, and Android's W^X policy refuses to
    # load a writable dex file via DexClassLoader ("Writable dex file ... is not
    # allowed"). Loading from an in-memory ByteBuffer sidesteps that entirely.
    cached = _loaded.get(dexName)
    if cached is not None:
        return cached
    dex_path = _dexPath(dexName)
    if not os.path.exists(dex_path):
        logx(f"dexLoader: {dexName}.dex not found at {dex_path}", False)
        return None
    with open(dex_path, "rb") as f:
        data = f.read()
    from java.nio import ByteBuffer
    from dalvik.system import InMemoryDexClassLoader
    parent_cl = context.getClassLoader()
    loader = InMemoryDexClassLoader(ByteBuffer.wrap(data), parent_cl)
    cls = loader.loadClass(className)
    _loaded[dexName] = cls
    logx(f"dexLoader: loaded {className} from {dexName}.dex ({len(data)} bytes, in-memory)", True)
    return cls


def _callStatic(cls, method: str, *args):
    # invoke a static method on a dynamically loaded class by name via plain
    # java.lang.reflect. We can't `from de.robv... import XposedHelpers` here —
    # chaquopy can't import arbitrary Java packages like `de.*` ("No module
    # named 'de'"), and the loaded class isn't on chaquopy's import path either.
    # Reflection on the Class object we already hold sidesteps both.
    n = len(args)
    _STATIC = 0x8  # java.lang.reflect.Modifier.STATIC (@JvmStatic also emits an
                   # instance method of the same name; we must pick the static one)
    for m in cls.getMethods():
        if (m.getName() == method
                and (m.getModifiers() & _STATIC) != 0
                and len(m.getParameterTypes()) == n):
            return m.invoke(None, *args)
    raise Exception(f"static method {method}({n} args) not found on {cls}")


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


_OPENFILE_CLASS = "kawaii.packetik.openfile.OpenFileNative"


def openFileCreate(context, path, text_size_px, pad_l, pad_t, pad_r, pad_b,
                   bg_color, text_color, token_types, token_starts, token_ends,
                   color_keys, color_vals):
    # builds the virtualized Kotlin code viewer for `path` and returns its root
    # View (or None on failure -> caller falls back to the Python renderer).
    # Args are wrapped in exact Chaquopy types so reflective invoke matches the
    # Kotlin int[]/float parameters.
    try:
        if context is None:
            from org.telegram.messenger import ApplicationLoader
            context = ApplicationLoader.applicationContext
        cls = _loadClass("openfile", _OPENFILE_CLASS, context)
        if cls is None:
            return None
        from java import jint, jfloat, jarray

        def _ia(lst):
            return jarray(jint)([int(x) for x in (lst or [])])

        return _callStatic(
            cls, "create",
            context, str(path), jfloat(float(text_size_px)),
            jint(int(pad_l)), jint(int(pad_t)), jint(int(pad_r)), jint(int(pad_b)),
            jint(int(bg_color)), jint(int(text_color)),
            _ia(token_types), _ia(token_starts), _ia(token_ends),
            _ia(color_keys), _ia(color_vals),
        )
    except Exception as e:
        logx(f"dexLoader: openFileCreate error: {e}", False)
        return None


def openFileCancel(view):
    try:
        cls = _loaded.get("openfile")
        if cls is not None and view is not None:
            _callStatic(cls, "cancel", view)
    except Exception as e:
        logx(f"dexLoader: openFileCancel error: {e}", False)


def openFileGetText(view):
    try:
        cls = _loaded.get("openfile")
        if cls is not None and view is not None:
            return _callStatic(cls, "getText", view)
    except Exception as e:
        logx(f"dexLoader: openFileGetText error: {e}", False)
    return None

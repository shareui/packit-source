# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os


try:
    from elyx import settings, assets
except Exception as e:
    logx(f"FontManager: import elyx failed: {e}", False)
    settings = None
    assets = None

_SETTING_KEY = "custom_font"
_FONTS_DIR_NAME = "fonts"

_current_typeface = None
_initialized = False


def _getFontsDir():
    # assets path is resolved by elyx; we need the actual fs path
    # use asset path_str trick: get any asset, derive parent
    try:
        import os as _os
        # assets root is packit/res; fonts subdir is packit/res/fonts
        # resolve via a dummy asset path or find by walking
        if assets is None:
            return None
        # get path of assets root by checking the module location
        # elyx stores assets relative to the plugin root
        sample = getattr(assets, "achievList", None)
        if sample is not None:
            res_dir = _os.path.dirname(sample.path_str)
            return _os.path.join(res_dir, _FONTS_DIR_NAME)
    except Exception as e:
        logx(f"FontManager: _getFontsDir error: {e}", False)
    return None


def listFontFiles():
    # returns list of .ttf filenames (without path) found in res/fonts
    try:
        fonts_dir = _getFontsDir()
        if not fonts_dir or not os.path.isdir(fonts_dir):
            return []
        files = [f for f in os.listdir(fonts_dir) if f.lower().endswith(".ttf")]
        files.sort()
        return files
    except Exception as e:
        logx(f"FontManager: listFontFiles error: {e}", False)
        return []


def getFontPath(filename):
    # returns absolute path for a font filename, or None
    try:
        fonts_dir = _getFontsDir()
        if not fonts_dir:
            return None
        path = os.path.join(fonts_dir, filename)
        return path if os.path.isfile(path) else None
    except Exception as e:
        logx(f"FontManager: getFontPath error: {e}", False)
        return None


def _loadTypeface(filename):
    # loads android Typeface from file, returns None on failure
    try:
        from android.graphics import Typeface
        path = getFontPath(filename)
        if not path:
            return None
        return Typeface.createFromFile(path)
    except Exception as e:
        logx(f"FontManager: _loadTypeface error: {e}", False)
        return None


def getCurrentTypeface():
    # returns cached Typeface or None if default
    # if saved font file is missing — resets to default automatically
    global _current_typeface, _initialized
    if _initialized:
        return _current_typeface
    _initialized = True
    try:
        if settings is None:
            return None
        filename = settings.get(_SETTING_KEY, "")
        if not filename:
            return None
        path = getFontPath(filename)
        if not path:
            # font file missing (e.g. no-assets build) — reset to default
            logx(f"FontManager: font file missing for '{filename}', resetting to default", True)
            settings.set(_SETTING_KEY, "")
            _current_typeface = None
            return None
        _current_typeface = _loadTypeface(filename)
        if _current_typeface is None:
            # file exists but failed to load — reset
            logx(f"FontManager: failed to load '{filename}', resetting to default", True)
            settings.set(_SETTING_KEY, "")
    except Exception as e:
        logx(f"FontManager: getCurrentTypeface error: {e}", False)
    return _current_typeface


def setFont(filename):
    # saves choice and updates cached typeface; pass "" for default
    global _current_typeface, _initialized
    _initialized = True
    try:
        if settings is None:
            return
        if filename:
            path = getFontPath(filename)
            if not path:
                logx(f"FontManager: setFont — file missing for '{filename}', ignoring", True)
                return
            tf = _loadTypeface(filename)
            if tf is None:
                logx(f"FontManager: setFont — failed to load '{filename}', ignoring", True)
                return
            settings.set(_SETTING_KEY, filename)
            _current_typeface = tf
        else:
            settings.set(_SETTING_KEY, "")
            _current_typeface = None
    except Exception as e:
        logx(f"FontManager: setFont error: {e}", False)


def applyToView(view):
    # applies current typeface to view if it is a TextView
    try:
        from android.widget import TextView
        tf = getCurrentTypeface()
        if tf is None:
            return
        if isinstance(view, TextView):
            view.setTypeface(tf)
    except Exception as e:
        logx(f"FontManager: applyToView error: {e}", False)


def getSelectedFilename():
    # returns currently saved font filename or ""
    try:
        if settings is None:
            return ""
        return settings.get(_SETTING_KEY, "")
    except Exception:
        return ""
# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
DEBUG_LOGS = False

from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import OnClickListener
from android.widget import ImageView
from android.net import Uri
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
    from org.telegram.messenger.browser import Browser
except Exception as _cython_exc_e:
    e = _cython_exc_e
    if DEBUG_LOGS:
        logx(f"linksBottomSheet: import error: {e}", False)
    Browser = None
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as _cython_exc_e:
    e = _cython_exc_e
    if DEBUG_LOGS:
        logx(f"linksBottomSheet: import Theme error: {e}", False)
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as _cython_exc_e:
    e = _cython_exc_e
    if DEBUG_LOGS:
        logx(f"linksBottomSheet: import LayoutHelper error: {e}", False)

# default: LEFT|TOP corner, buttons stack downward
_GRAVITY_DEFAULT = 51  # LEFT|TOP
_TOP_MARGIN_START = 16.0
_TOP_MARGIN_STEP = 44.0
_LEFT_MARGIN_DEFAULT = 16.0
_RIGHT_MARGIN_DEFAULT = 0.0

# human-readable gravity aliases -> android Gravity int
# composed from: LEFT=3, RIGHT=5, TOP=48, BOTTOM=80, CENTER=17,
#                CENTER_HORIZONTAL=1, CENTER_VERTICAL=16
_GRAVITY_MAP = {
    "LEFT":              3,
    "RIGHT":             5,
    "TOP":               48,
    "BOTTOM":            80,
    "CENTER":            17,
    "CENTER_HORIZONTAL": 1,
    "CENTER_VERTICAL":   16,
    "LEFT_TOP":          51,   # LEFT|TOP
    "RIGHT_TOP":         53,   # RIGHT|TOP
    "LEFT_BOTTOM":       83,   # LEFT|BOTTOM
    "RIGHT_BOTTOM":      85,   # RIGHT|BOTTOM
    "CENTER_TOP":        49,   # CENTER_HORIZONTAL|TOP
    "CENTER_BOTTOM":     81,   # CENTER_HORIZONTAL|BOTTOM
}


def _resolveGravity(value) -> int:
    # accepts int or string like "LEFT_TOP", "RIGHT|TOP", "LEFT", etc.
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return _GRAVITY_DEFAULT
    combined = 0
    for part in value.replace("|", " ").split():
        part = part.strip().upper()
        g = _GRAVITY_MAP.get(part)
        if g is None:
            if DEBUG_LOGS:
                logx(f"linksBottomSheet: unknown gravity token '{part}', ignoring", True)
            continue
        combined |= g
    return combined if combined else _GRAVITY_DEFAULT


def _parseLinks(filePath: str) -> list:
    # returns list of {"icon", "url", "gravity", "x", "y"}
    import re

    source = None
    try:
        with open(filePath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return []

    m = re.search(r"__links__\s*=\s*(\[.*?\])", source, re.DOTALL)
    if not m:
        return []

    try:
        import ast
        raw = m.group(1)
        links = ast.literal_eval(raw)
        result = []
        for item in links:
            if isinstance(item, dict) and "url" in item:
                result.append({
                    "icon":    item.get("icon", "msg_link"),
                    "url":     str(item["url"]),
                    "gravity": item.get("gravity", None),
                    "x":       item.get("x", None),
                    "y":       item.get("y", None),
                })
        return result
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        if DEBUG_LOGS:
            logx(f"linksBottomSheet: _parseLinks parse error: {e}", False)
        return []


def _openUrl(act, url: str):
    try:
        if Browser:
            Browser.openUrl(act, Uri.parse(url), True, True, True, None, None, False, False, False)
        else:
            from android.content import Intent
            from org.telegram.messenger import ApplicationLoader
            intent = Intent(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(url))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            ApplicationLoader.applicationContext.startActivity(intent)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        if DEBUG_LOGS:
            logx(f"linksBottomSheet: _openUrl error: {e}", False)


_pending: dict = {}


class ConstructorHook(MethodHook):

    def before_hooked_method(self, param):
        try:
            install_params = param.args[2]
            filePath = str(install_params.filePath)
            sheet = param.thisObject
            _pending[sheet.hashCode()] = (filePath, sheet)
            if DEBUG_LOGS:
                logx(f"linksBottomSheet: stored filePath={filePath}", True)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            if DEBUG_LOGS:
                logx(f"linksBottomSheet: ConstructorHook error: {e}", False)


def _getFilePathFromSheet(sheet) -> str:
    # fallback: walk fields looking for PluginInstallParams or a .plugin/.eaf string
    try:
        cls = sheet.getClass()
        while cls is not None:
            for field in cls.getDeclaredFields():
                field.setAccessible(True)
                val = field.get(sheet)
                if val is None:
                    continue
                fieldClass = val.getClass().getName()
                if "PluginInstallParams" in fieldClass:
                    return str(val.filePath)
                if fieldClass == "java.lang.String":
                    s = str(val)
                    if s.endswith(".plugin") or s.endswith(".eaf"):
                        return s
            cls = cls.getSuperclass()
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        if DEBUG_LOGS:
            logx(f"linksBottomSheet: _getFilePathFromSheet error: {e}", False)
    return ""


class SetCustomViewHook(MethodHook):

    def after_hooked_method(self, param):
        try:
            from elyx import settings
            if not settings.get("install_sheet_links", True):
                return
            sheet = param.thisObject
            if "InstallPluginBottomSheet" not in str(sheet.getClass().getName()):
                return

            view = param.args[0]
            if not view:
                return

            frame = view.getChildAt(0)
            if not frame:
                if DEBUG_LOGS:
                    logx("linksBottomSheet: frame not found", True)
                return

            stored = _pending.pop(sheet.hashCode(), ("", None))
            filePath, _sheet = stored
            if not filePath:
                filePath = _getFilePathFromSheet(sheet)
                _sheet = sheet
                if DEBUG_LOGS:
                    logx(f"linksBottomSheet: fallback filePath={filePath}", True)
            if not filePath:
                return

            links = _parseLinks(filePath)
            if not links:
                return

            act = sheet.getContext()

            for i, link in enumerate(links):
                iconName = link["icon"]
                url = link["url"]

                gravity = _resolveGravity(link["gravity"]) if link["gravity"] is not None else _GRAVITY_DEFAULT
                isRight = bool(gravity & 5 == 5)
                defaultX = _RIGHT_MARGIN_DEFAULT if isRight else _LEFT_MARGIN_DEFAULT
                x = float(link["x"]) if link["x"] is not None else defaultX
                y = float(link["y"]) if link["y"] is not None else (_TOP_MARGIN_START + i * _TOP_MARGIN_STEP)
                leftMargin  = 0.0 if isRight else x
                rightMargin = x   if isRight else 0.0

                btn = ImageView(act)
                iconRes = None
                try:
                    iconRes = getattr(R_tg.drawable, iconName)
                except Exception:
                    pass
                if iconRes is None:
                    try:
                        iconRes = getattr(R_tg.drawable, "msg_link")
                    except Exception:
                        pass
                if iconRes is not None:
                    try:
                        btn.setImageResource(iconRes)
                    except Exception:
                        pass

                try:
                    btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
                except Exception:
                    pass

                btn.setScaleType(ImageView.ScaleType.CENTER)
                btn.setClickable(True)
                btn.setFocusable(True)

                def makeOnClick(u, s):
                    def onClick(v):
                        try:
                            if s:
                                s.dismiss()
                        except Exception:
                            pass
                        _openUrl(act, u)
                    return onClick
                btn.setOnClickListener(OnClickListener(makeOnClick(url, _sheet)))

                try:
                    from org.telegram.ui.Components import ScaleStateListAnimator
                    ScaleStateListAnimator.apply(btn, 0.15, 1.5)
                except Exception:
                    pass

                try:
                    selector_color = Theme.getColor(Theme.key_dialogButtonSelector)
                    bg = Theme.createSelectorDrawable(selector_color, 1, AndroidUtilities.dp(20))
                    btn.setBackground(bg)
                except Exception:
                    pass

                lp = LayoutHelper.createFrame(40, 40.0, gravity, leftMargin, y, rightMargin, 0.0)
                frame.addView(btn, lp)
                if DEBUG_LOGS:
                    logx(f"linksBottomSheet: added button icon={iconName} gravity={gravity} x={x} y={y}", True)

        except Exception as _cython_exc_e:
            e = _cython_exc_e
            if DEBUG_LOGS:
                logx(f"linksBottomSheet: SetCustomViewHook error: {e}", False)


def setup_links_buttons_hook(plugin):
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
            if DEBUG_LOGS:
                logx("linksBottomSheet: InstallPluginBottomSheet not found", True)
            return None

        BaseFragment = find_class("org.telegram.ui.ActionBar.BaseFragment")
        ValidationResult = find_class(
            "com.exteragram.messenger.plugins.PluginsController$PluginValidationResult"
        )
        InstallParams = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet$PluginInstallParams"
        )
        if ValidationResult and InstallParams:
            constructor = InstallSheet.getClass().getDeclaredConstructor(
                BaseFragment, ValidationResult, InstallParams
            )
            constructor.setAccessible(True)
            hooks.append(plugin.hook_method(constructor, ConstructorHook()))

        BottomSheet = find_class("org.telegram.ui.ActionBar.BottomSheet")
        ViewClass = find_class("android.view.View")
        if BottomSheet and ViewClass:
            method = BottomSheet.getClass().getDeclaredMethod("setCustomView", ViewClass)
            method.setAccessible(True)
            hooks.append(plugin.hook_method(method, SetCustomViewHook()))

        if DEBUG_LOGS:
            logx(f"linksBottomSheet: setup done, hooks={len(hooks)}", True)
        return hooks
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        if DEBUG_LOGS:
            logx(f"linksBottomSheet: setup error: {e}", False)
        return None
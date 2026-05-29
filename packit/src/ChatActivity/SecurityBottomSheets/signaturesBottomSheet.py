# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

DEBUG_LOGS = False
TEST_UI = False
TEST_WARNING = False

from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, OnClickListener
from client_utils import get_last_fragment
from android.widget import ImageView
from elyx import strings
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    if DEBUG_LOGS:
        log(f"securityUi: import error: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    if DEBUG_LOGS:
        log(f"securityUi: import Theme error: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    if DEBUG_LOGS:
        log(f"securityUi: import LayoutHelper error: {e}")
try:
    from android.view import View
except Exception as e:
    View = find_class("android.view.View")

SIGNATURES_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/signatures.json"

# level -> (icon_name, theme_color_key, fallback_color_argb)
_LEVEL_STYLE = {
    "Critical": ("msg_report_fake",    "key_text_RedBold",                  0xFFE53935),
    "High":     ("msg_report_other",   "key_color_red",                     0xFFFF7043),
    "Medium":   ("msg_info_filled",    "key_color_orange",                  0xFFFFA726),
    "Low":      ("msg_info",           "key_windowBackgroundWhiteGrayText", 0xFF9E9E9E),
}
_LEVEL_ORDER = ["Critical", "High", "Medium", "Low"]

_PACKITKEY_SIGS = frozenset([
    "libpackitkey", "loadPackitKey(", "packitkey_store(",
    "packitkey_load(", "packitkey_delete(", "packitkey_exists(",
    "packit/.secret/keys", "native/packitkey",
])


def _extractPluginId(filePath: str, source: str) -> str:
    import re as _re
    try:
        m = _re.search(r"\.temp_(.+?)\.plugin$", filePath)
        if m:
            return m.group(1)
    except Exception:
        pass
    try:
        m = _re.search(r'^__id__\s*=\s*[\'"]([^\'"]+)[\'"]', source, _re.MULTILINE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def _fetchSignatures():
    import urllib.request, json
    with urllib.request.urlopen(urllib.request.Request(SIGNATURES_URL, headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"}), timeout=10) as r:
        return json.loads(r.read().decode())["signatures"]


def _scanPlugin(source: str, signatures: list) -> dict:
    results: dict = {}

    clean_lines = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            clean_lines.append(line)
    clean_source = "\n".join(clean_lines)

    for sig in signatures:
        pattern = sig[0]
        level = sig[1]
        whitelist = sig[2]["whitelist"] if len(sig) > 2 and isinstance(sig[2], dict) and "whitelist" in sig[2] else []

        # split detection: sig[0] is a list of parts, all must be present
        if isinstance(pattern, list):
            parts = pattern
            if not all(p in clean_source for p in parts):
                continue
            label = " + ".join(parts)
            if whitelist:
                # flag if any line contains all parts simultaneously
                flagged_lines = [l for l in clean_lines if all(p in l for p in parts)]
                if not flagged_lines:
                    continue
                if all(any(wl in line for wl in whitelist) for line in flagged_lines):
                    continue
            if level not in results:
                results[level] = []
            if label not in results[level]:
                results[level].append(label)
            continue

        if pattern not in clean_source:
            continue

        if whitelist:
            matching_lines = [l for l in clean_lines if pattern in l]
            whitelisted = all(
                any(wl in line for wl in whitelist)
                for line in matching_lines
            )
            if whitelisted:
                continue

        if level not in results:
            results[level] = []
        if pattern not in results[level]:
            results[level].append(pattern)

    return results


def _buildTestResults(signatures: list) -> dict:
    # test mode: treat all config signatures as detected
    results: dict = {}
    for sig in signatures:
        pattern = sig[0]
        level = sig[1]
        label = " + ".join(pattern) if isinstance(pattern, list) else pattern
        if level not in results:
            results[level] = []
        if label not in results[level]:
            results[level].append(label)
    return results


def _resolveColor(colorKey: str, fallback: int) -> int:
    try:
        return Theme.getColor(getattr(Theme, colorKey))
    except Exception:
        return fallback


def _resolveIcon(iconName: str, fallbackIcon: str) -> int:
    try:
        return getattr(R_tg.drawable, iconName)
    except Exception:
        try:
            return getattr(R_tg.drawable, fallbackIcon)
        except Exception:
            return 0


def _buildResultsScrollView(act, results: dict):
    from android.widget import LinearLayout, ScrollView, TextView
    from android.view import View, Gravity
    from android.graphics import Typeface

    dp = AndroidUtilities.dp

    scroll = ScrollView(act)
    scroll.setVerticalScrollBarEnabled(False)

    root = LinearLayout(act)
    root.setOrientation(LinearLayout.VERTICAL)
    root.setPadding(dp(0), dp(8), dp(0), dp(4))

    if not results:
        _appendCleanState(act, root)
    else:
        for level in _LEVEL_ORDER:
            if level not in results:
                continue
            _appendLevelBlock(act, root, level, results[level])

    scroll.addView(root)
    return scroll


def _appendCleanState(act, root):
    from android.widget import LinearLayout, TextView
    from android.view import Gravity
    from org.telegram.ui.Components import RLottieImageView

    dp = AndroidUtilities.dp

    container = LinearLayout(act)
    container.setOrientation(LinearLayout.VERTICAL)
    container.setGravity(Gravity.CENTER_HORIZONTAL)
    container.setPadding(0, dp(8), 0, dp(12))

    try:
        lottie = RLottieImageView(act)
        lottie.setAnimation(R_tg.raw.done, dp(72), dp(72))
        lottie.setAutoRepeat(False)
        lottie.playAnimation()
        lp = LinearLayout.LayoutParams(dp(72), dp(72))
        lp.gravity = Gravity.CENTER_HORIZONTAL
        lp.bottomMargin = dp(10)
        container.addView(lottie, lp)
    except Exception as e:
        if DEBUG_LOGS:
            log(f"securityUi: lottie error: {e}")

    label = TextView(act)
    label.setText(strings["sec_no_signatures"])
    label.setTextSize(15)
    label.setTextColor(_resolveColor("key_windowBackgroundWhiteBlackText", 0xFF212121))
    label.setGravity(Gravity.CENTER_HORIZONTAL)
    container.addView(label, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    ))

    root.addView(container, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    ))


def _formatPattern(p: str) -> str:
    if p.endswith("("):
        return p + ")"
    if p.endswith("["):
        return p + "]"
    return p


def _appendLevelBlock(act, root, level: str, patterns: list):
    from android.widget import LinearLayout, TextView
    from android.view import Gravity
    from android.graphics import Typeface
    from android.graphics.drawable import GradientDrawable

    dp = AndroidUtilities.dp
    iconName, colorKey, colorFallback = _LEVEL_STYLE.get(
        level, ("msg_info", "key_windowBackgroundWhiteGrayText", 0xFF9E9E9E)
    )
    levelColor = _resolveColor(colorKey, colorFallback)

    block = LinearLayout(act)
    block.setOrientation(LinearLayout.VERTICAL)
    block.setPadding(dp(12), dp(10), dp(12), dp(10))

    try:
        r = (levelColor >> 16) & 0xFF
        g = (levelColor >> 8) & 0xFF
        b = levelColor & 0xFF
        gd = GradientDrawable()
        gd.setCornerRadius(dp(12))
        gd.setColor((0x18 << 24) | (r << 16) | (g << 8) | b)
        block.setBackground(gd)
    except Exception as e:
        if DEBUG_LOGS:
            log(f"securityUi: block bg error: {e}")

    # header: icon + level name
    header = LinearLayout(act)
    header.setOrientation(LinearLayout.HORIZONTAL)
    header.setGravity(Gravity.CENTER_VERTICAL)

    iconView = ImageView(act)
    iconRes = _resolveIcon(iconName, "msg_info")
    if iconRes:
        iconView.setImageResource(iconRes)
    iconView.setColorFilter(levelColor)
    iconView.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    lpIcon = LinearLayout.LayoutParams(dp(18), dp(18))
    lpIcon.rightMargin = dp(7)
    header.addView(iconView, lpIcon)

    levelLabel = TextView(act)
    levelLabel.setText(level)
    levelLabel.setTextSize(13)
    levelLabel.setTypeface(Typeface.DEFAULT_BOLD)
    levelLabel.setTextColor(levelColor)
    header.addView(levelLabel, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.WRAP_CONTENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    ))

    lpHeader = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    )
    lpHeader.bottomMargin = dp(6)
    block.addView(header, lpHeader)

    # pattern rows
    subtextColor = _resolveColor("key_windowBackgroundWhiteGrayText", 0xFF9E9E9E)
    for i, p in enumerate(patterns):
        display = _formatPattern(p)
        row = TextView(act)
        row.setText(f"• {display}")
        row.setTextSize(12)
        row.setTextColor(subtextColor)
        lpRow = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        )
        if i > 0:
            lpRow.topMargin = dp(3)
        block.addView(row, lpRow)

    lpBlock = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    )
    lpBlock.bottomMargin = dp(10)
    root.addView(block, lpBlock)


def _applyPressScale(view):
    from android.view import MotionEvent, View
    from java import dynamic_proxy

    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self):
                super().__init__()

            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.95).scaleY(0.95).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(150).start()
                except Exception:
                    pass
                return False

        view.setOnTouchListener(_TouchListener())
    except Exception as e:
        if DEBUG_LOGS:
            log(f"securityUi: _applyPressScale error: {e}")


def _hasPackitkeySignature(results: dict) -> bool:
    if TEST_WARNING:
        return True
    for patterns in results.values():
        for p in patterns:
            if p in _PACKITKEY_SIGS:
                return True
    return False


def _buildPackitkeyWarning(act) -> object:
    from android.widget import LinearLayout, TextView
    from android.graphics import Typeface
    from android.graphics.drawable import GradientDrawable

    dp = AndroidUtilities.dp
    warningColor = _resolveColor("key_text_RedBold", 0xFFE53935)

    container = LinearLayout(act)
    container.setOrientation(LinearLayout.VERTICAL)
    container.setPadding(dp(12), dp(12), dp(12), dp(12))

    try:
        r = (warningColor >> 16) & 0xFF
        g = (warningColor >> 8) & 0xFF
        b = warningColor & 0xFF
        gd = GradientDrawable()
        gd.setCornerRadius(dp(12))
        gd.setColor((0x18 << 24) | (r << 16) | (g << 8) | b)
        container.setBackground(gd)
    except Exception as e:
        if DEBUG_LOGS:
            log(f"securityUi: packitkey warning bg error: {e}")

    title = TextView(act)
    title.setText(strings["sec_packitkey_warning_title"])
    title.setTextSize(13)
    title.setTypeface(Typeface.DEFAULT_BOLD)
    title.setTextColor(warningColor)
    lp_title = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    )
    lp_title.bottomMargin = dp(6)
    container.addView(title, lp_title)

    text = TextView(act)
    text.setText(strings["sec_packitkey_warning_text"])
    text.setTextSize(12)
    text.setTextColor(_resolveColor("key_windowBackgroundWhiteGrayText", 0xFF9E9E9E))
    container.addView(text, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    ))

    return container


def _buildLearnMoreBtn(act, onPress) -> object:
    from android.widget import LinearLayout, FrameLayout, TextView
    from android.view import Gravity
    from android.util import TypedValue

    dp = AndroidUtilities.dp

    wrapper = LinearLayout(act)
    wrapper.setOrientation(LinearLayout.VERTICAL)
    wrapper.setPadding(dp(0), dp(4), dp(0), dp(8))

    btn = FrameLayout(act)
    try:
        base = Theme.getColor(Theme.key_graySection)
        pressed = Theme.getColor(Theme.key_listSelector)
    except Exception:
        base = _resolveColor("key_windowBackgroundWhiteBlueButton", 0xFF1E88E5)
        pressed = base
    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(28), base, pressed))
    btn.setPadding(0, dp(14), 0, dp(14))
    btn.setClickable(True)
    btn.setFocusable(True)

    label = TextView(act)
    label.setText(strings["sec_signatures_btn"])
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    label.setTypeface(AndroidUtilities.bold())
    label.setGravity(Gravity.CENTER)
    try:
        label.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception:
        label.setTextColor(0xFF000000)
    btn.addView(label, FrameLayout.LayoutParams(
        FrameLayout.LayoutParams.MATCH_PARENT,
        FrameLayout.LayoutParams.WRAP_CONTENT
    ))

    btn.setOnClickListener(OnClickListener(onPress))
    _applyPressScale(btn)

    wrapper.addView(btn, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    ))
    return wrapper


def _buildCloseBtn(act, onPress) -> object:
    from android.widget import LinearLayout, FrameLayout, TextView
    from android.view import Gravity
    from android.util import TypedValue

    dp = AndroidUtilities.dp

    wrapper = LinearLayout(act)
    wrapper.setOrientation(LinearLayout.VERTICAL)
    wrapper.setPadding(dp(0), 0, dp(0), dp(0))

    btn = FrameLayout(act)
    try:
        base = Theme.getColor(Theme.key_featuredStickers_addButton)
        pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
    except Exception:
        base = _resolveColor("key_windowBackgroundWhiteBlueButton", 0xFF1E88E5)
        pressed = base
    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(28), base, pressed))
    btn.setPadding(0, dp(14), 0, dp(14))
    btn.setClickable(True)
    btn.setFocusable(True)

    label = TextView(act)
    label.setText(strings["close_button"])
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    label.setTypeface(AndroidUtilities.bold())
    label.setGravity(Gravity.CENTER)
    try:
        label.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    except Exception:
        label.setTextColor(0xFFFFFFFF)
    btn.addView(label, FrameLayout.LayoutParams(
        FrameLayout.LayoutParams.MATCH_PARENT,
        FrameLayout.LayoutParams.WRAP_CONTENT
    ))

    btn.setOnClickListener(OnClickListener(onPress))
    _applyPressScale(btn)

    wrapper.addView(btn, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    ))
    return wrapper


def _showResults(results: dict, act):
    from android.widget import LinearLayout, TextView
    from android.view import Gravity
    from android.util import TypedValue
    from org.telegram.ui.ActionBar import BottomSheet

    try:
        sheetRef = [None]

        def onLearnMore(v):
            try:
                from ...utils.localConfig import LocalConfig
                LocalConfig.set("signatures", True)
            except Exception as ex:
                if DEBUG_LOGS:
                    log(f"securityUi: LocalConfig.set signatures error: {ex}")
            try:
                from android.net import Uri
                from org.telegram.messenger.browser import Browser
                Browser.openUrl(act, Uri.parse("https://t.me/packitGround/13/999"), True, True, True, None, None, False, False, False)
                if sheetRef[0]:
                    sheetRef[0].dismiss()
            except Exception as ex:
                if DEBUG_LOGS:
                    log(f"securityUi: open link error: {ex}")

        wrapper = LinearLayout(act)
        wrapper.setOrientation(LinearLayout.VERTICAL)
        wrapper.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            wrapper.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
        except Exception:
            pass

        title = TextView(act)
        title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
        try:
            title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title.setTypeface(AndroidUtilities.bold())
        title.setText(strings["sec_signature_scan_title"])
        title.setGravity(Gravity.CENTER)
        wrapper.addView(title, LinearLayout.LayoutParams(-1, -2))

        title_margin = View(act)
        wrapper.addView(title_margin, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

        scrollView = _buildResultsScrollView(act, results)
        wrapper.addView(scrollView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ))

        if _hasPackitkeySignature(results):
            warningView = _buildPackitkeyWarning(act)
            lp_warn = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp_warn.bottomMargin = AndroidUtilities.dp(10)
            wrapper.addView(warningView, lp_warn)

        try:
            from ...utils.localConfig import LocalConfig
            showLearnMore = not LocalConfig.get("signatures", False)
        except Exception:
            showLearnMore = True

        if showLearnMore:
            learnMoreRow = _buildLearnMoreBtn(act, onLearnMore)
            wrapper.addView(learnMoreRow, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ))

        closeRow = _buildCloseBtn(act, lambda v: sheetRef[0].dismiss() if sheetRef[0] else None)
        wrapper.addView(closeRow, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ))

        builder = BottomSheet.Builder(act)
        builder.setCustomView(wrapper)
        sheet = builder.create()
        sheetRef[0] = sheet
        sheet.show()

    except Exception as e:
        if DEBUG_LOGS:
            log(f"securityUi: _showResults error: {e}")
        # fallback
        from ui.alert import AlertDialogBuilder
        msg = strings["sec_no_signatures"] if not results else "\n\n".join(
            f"{lvl}: {', '.join(f'[{p}]' for p in results[lvl])}"
            for lvl in _LEVEL_ORDER if lvl in results
        )
        builder = AlertDialogBuilder(act)
        builder.set_title(strings["sec_signature_scan_title"])
        builder.set_message(msg)
        builder.set_positive_button(strings["ok_button"], lambda b, w: b.dismiss())
        builder.show()


def _onPolicyClick(act, filePath: str):
    import threading
    from android_utils import run_on_ui_thread
    from ui.alert import AlertDialogBuilder

    loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
    loading.set_title(strings["sec_scanning"])
    loading.set_cancelable(False)
    dlg = loading.create()
    run_on_ui_thread(lambda: dlg.show())

    def _work():
        try:
            with open(filePath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            plugin_id = _extractPluginId(filePath, source)
            if DEBUG_LOGS:
                log(f"securityUi: plugin_id={plugin_id!r}")

            if not TEST_UI and plugin_id == "shareui_packit":
                run_on_ui_thread(lambda: (dlg.dismiss(), _showResults({}, act)))
                return

            signatures = _fetchSignatures()
            results = _buildTestResults(signatures) if TEST_UI else _scanPlugin(source, signatures)
            run_on_ui_thread(lambda: (dlg.dismiss(), _showResults(results, act)))
        except Exception as e:
            if DEBUG_LOGS:
                log(f"securityUi: scan error: {e}")
            run_on_ui_thread(lambda: (dlg.dismiss(), _showResults({}, act)))

    threading.Thread(target=_work, daemon=True).start()


_pending: dict = {}


class ConstructorHook(MethodHook):

    def before_hooked_method(self, param):
        try:
            install_params = param.args[2]
            filePath = str(install_params.filePath)
            sheet = param.thisObject
            _pending[sheet.hashCode()] = filePath
            if DEBUG_LOGS:
                log(f"securityUi: stored filePath={filePath}")
        except Exception as e:
            if DEBUG_LOGS:
                log(f"securityUi: ConstructorHook error: {e}")


class SetCustomViewHook(MethodHook):

    def after_hooked_method(self, param):
        try:
            from elyx import settings
            if not settings.get("install_sheet_signatures", True):
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
                    log("securityUi: frame not found")
                return

            filePath = _pending.pop(sheet.hashCode(), "")
            if DEBUG_LOGS:
                log(f"securityUi: SetCustomViewHook filePath={filePath}")
            act = sheet.getContext()

            policy_btn = ImageView(act)
            try:
                policy_btn.setImageResource(getattr(R_tg.drawable, "msg_policy"))
            except Exception:
                try:
                    policy_btn.setImageResource(getattr(R_tg.drawable, "msg_secret"))
                except Exception:
                    pass

            try:
                policy_btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
            except Exception:
                pass

            policy_btn.setScaleType(ImageView.ScaleType.CENTER)
            policy_btn.setClickable(True)
            policy_btn.setFocusable(True)
            policy_btn.setOnClickListener(OnClickListener(lambda v: _onPolicyClick(act, filePath)))

            try:
                from org.telegram.ui.Components import ScaleStateListAnimator
                ScaleStateListAnimator.apply(policy_btn, 0.15, 1.5)
            except Exception:
                pass

            try:
                selector_color = Theme.getColor(Theme.key_dialogButtonSelector)
                bg = Theme.createSelectorDrawable(selector_color, 1, AndroidUtilities.dp(20))
                policy_btn.setBackground(bg)
            except Exception:
                pass

            lp = LayoutHelper.createFrame(40, 40.0, 53, 0.0, 60.0, 16.0, 0.0)
            frame.addView(policy_btn, lp)

        except Exception as e:
            if DEBUG_LOGS:
                log(f"securityUi: SetCustomViewHook error: {e}")


def setup_policy_button_hook(plugin):
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
            if DEBUG_LOGS:
                log("securityUi: InstallPluginBottomSheet not found")
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

        return hooks
    except Exception as e:
        if DEBUG_LOGS:
            log(f"securityUi: setup error: {e}")
        return None
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, OnClickListener
from client_utils import get_last_fragment
from android.widget import ImageView
from elyx import strings
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    log(f"securityUi: import error: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"securityUi: import Theme error: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    log(f"securityUi: import LayoutHelper error: {e}")

SIGNATURES_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/signatures.json"


def _fetchSignatures():
    import urllib.request, json
    with urllib.request.urlopen(SIGNATURES_URL, timeout=10) as r:
        return json.loads(r.read().decode())["signatures"]


def _scanPlugin(source: str, signatures: list) -> dict:
    results: dict = {}
    lines = source.splitlines()

    for sig in signatures:
        pattern = sig[0]
        level = sig[1]
        whitelist = sig[2]["whitelist"] if len(sig) > 2 and "whitelist" in sig[2] else []

        if pattern not in source:
            continue

        if whitelist:
            matching_lines = [l for l in lines if pattern in l]
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


def _showResults(results: dict, act):
    from ui.alert import AlertDialogBuilder

    LEVEL_ORDER = ["Critical", "High", "Medium", "Low"]

    if not results:
        msg = strings["sec_no_signatures"]
    else:
        lines = []
        for level in LEVEL_ORDER:
            if level in results:
                patterns = ", ".join(
                    p + ")" if p.endswith("(") else p
                    for p in results[level]
                )
                lines.append(f"{level}: {patterns}")
        msg = "\n\n".join(lines)

    builder = AlertDialogBuilder(act)
    builder.set_title(strings["sec_signature_scan_title"])
    builder.set_message(msg)
    def _openLink(b, w):
        b.dismiss()
        try:
            from android.net import Uri
            from org.telegram.messenger.browser import Browser
            Browser.openUrl(act, Uri.parse("https://t.me/packitGround/13/999"), True, True, True, None, None, False, False, False)
        except Exception as e:
            log(f"securityUi: open link error: {e}")

    builder.set_negative_button(strings["sec_signatures_btn"], _openLink)
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
            signatures = _fetchSignatures()
            with open(filePath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            results = _scanPlugin(source, signatures)
            run_on_ui_thread(lambda: (dlg.dismiss(), _showResults(results, act)))
        except Exception as e:
            log(f"securityUi: scan error: {e}")
            run_on_ui_thread(lambda: (dlg.dismiss(), _showResults({}, act)))

    threading.Thread(target=_work, daemon=True).start()


def _makePolicyBtn(act, frame, filePath: str):
    try:
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
        log(f"securityUi: _makePolicyBtn error: {e}")


_pending: dict = {}


class ConstructorHook(MethodHook):

    def before_hooked_method(self, param):
        try:
            install_params = param.args[2]
            filePath = str(install_params.filePath)
            sheet = param.thisObject
            _pending[sheet.hashCode()] = filePath
            log(f"securityUi: stored filePath={filePath}")
        except Exception as e:
            log(f"securityUi: ConstructorHook error: {e}")


class SetCustomViewHook(MethodHook):

    def after_hooked_method(self, param):
        try:
            sheet = param.thisObject
            if "InstallPluginBottomSheet" not in str(sheet.getClass().getName()):
                return

            view = param.args[0]
            if not view:
                return

            frame = view.getChildAt(0)
            if not frame:
                log("securityUi: frame not found")
                return

            filePath = _pending.pop(sheet.hashCode(), "")
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
            log(f"securityUi: SetCustomViewHook error: {e}")


def setup_policy_button_hook(plugin):
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
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
        log(f"securityUi: setup error: {e}")
        return None

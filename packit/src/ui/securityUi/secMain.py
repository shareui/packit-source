from base_plugin import MethodHook
from hook_utils import find_class, get_private_field
from android_utils import log, OnClickListener
from client_utils import get_last_fragment
from android.widget import ImageView, ScrollView
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    log(f"securityUi: import AndroidUtilities, R failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"securityUi: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    log(f"securityUi: import LayoutHelper failed: {e}")


def _onPolicyClick():
    try:
        from ui.alert import AlertDialogBuilder
        fragment = get_last_fragment()
        act = fragment.getParentActivity()
        builder = AlertDialogBuilder(act)
        builder.set_message("Signature checking will be implemented here :3")
        builder.set_positive_button("OK", lambda b, w: b.dismiss())
        builder.show()
    except Exception as e:
        log(f"securityUi: policy click error: {e}")


def _makePolicyBtn(act, frame):
    try:
        policy_btn = ImageView(act)
        try:
            icon_res = getattr(R_tg.drawable, "msg_policy")
            policy_btn.setImageResource(icon_res)
        except Exception:
            try:
                icon_res = getattr(R_tg.drawable, "msg_secret")
                policy_btn.setImageResource(icon_res)
            except Exception:
                pass

        try:
            policy_btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
        except Exception:
            pass

        policy_btn.setScaleType(ImageView.ScaleType.CENTER)
        policy_btn.setClickable(True)
        policy_btn.setFocusable(True)
        policy_btn.setOnClickListener(OnClickListener(lambda v: _onPolicyClick()))

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

        # place below msg_openin: same right=16, top = 16(openin top) + 40(openin height) + 4(gap)
        lp = LayoutHelper.createFrame(40, 40.0, 53, 0.0, 60.0, 16.0, 0.0)
        frame.addView(policy_btn, lp)
    except Exception as e:
        log(f"securityUi: _makePolicyBtn error: {e}")


class SetCustomViewHook(MethodHook):
    """Hook setCustomView to intercept the ScrollView and add button to its child FrameLayout."""

    def after_hooked_method(self, param):
        try:
            sheet = param.thisObject
            view = param.args[0]
            if not view:
                return

            # view is ScrollView — its only child is FrameLayout r7 (r19)
            # which contains LinearLayout r8 + msg_openin button
            frame = view.getChildAt(0)
            if not frame:
                log("securityUi: frame(r7) not found inside ScrollView")
                return

            act = sheet.getContext()
            _makePolicyBtn(act, frame)
        except Exception as e:
            log(f"securityUi: SetCustomViewHook failed: {e}")


def setup_policy_button_hook(plugin):
    try:
        BottomSheet = find_class("org.telegram.ui.ActionBar.BottomSheet")
        if not BottomSheet:
            log("securityUi: BottomSheet class not found")
            return None

        ViewClass = find_class("android.view.View")

        method = BottomSheet.getClass().getDeclaredMethod("setCustomView", ViewClass)
        method.setAccessible(True)

        # wrap hook so it only fires for InstallPluginBottomSheet instances
        class FilteredHook(MethodHook):
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
                    act = sheet.getContext()
                    _makePolicyBtn(act, frame)
                except Exception as e:
                    log(f"securityUi: FilteredHook failed: {e}")

        return plugin.hook_method(method, FilteredHook())
    except Exception as e:
        log(f"securityUi: setup_policy_button_hook error: {e}")
        return None

from android.widget import LinearLayout, TextView, FrameLayout
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.view import Gravity, MotionEvent, View
from android_utils import run_on_ui_thread, log, OnClickListener
from client_utils import get_last_fragment
try:
    from org.telegram.ui.ActionBar import Theme, BottomSheet
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"isBeta: import tg classes failed: {e}")
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from ..utils.localConfig import LocalConfig

BETA = True
_COUNTDOWN_SEC = 5


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self, fn):
                super().__init__()
                self._fn = fn
            def onTouch(self, v, event):
                return self._fn(v, event)
        def _on_touch(v, event):
            try:
                action = event.getActionMasked()
                if action == MotionEvent.ACTION_DOWN:
                    v.animate().scaleX(0.94).scaleY(0.94).setDuration(100).start()
                elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
            except Exception:
                pass
            return False
        view.setOnTouchListener(_TouchListener(_on_touch))
    except Exception:
        pass


def _show_beta_dialog():
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        sheet = BottomSheet(act, False, frag.getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)
        sheet.setCanDismissWithSwipe(False)
        sheet.setCanDismissWithTouchOutside(False)

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(20),
            AndroidUtilities.dp(20), AndroidUtilities.dp(8)
        )
        try:
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadii([
                AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                0, 0, 0, 0
            ])
            bg.setColor(Theme.getColor(Theme.key_dialogBackground))
            root.setBackground(bg)
        except Exception:
            root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))

        msg_tv = TextView(act)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        msg_tv.setText(strings.beta_dialog_message)
        msg_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        msg_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
        msg_tv.setGravity(Gravity.CENTER)
        root.addView(msg_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        try:
            base_active = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed_active = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            base_active = Theme.getColor(Theme.key_dialogTextBlue)
            pressed_active = base_active
        base_locked = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

        ok_btn = FrameLayout(act)
        ok_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        ok_btn.setClickable(False)
        ok_btn.setFocusable(False)
        ok_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base_locked, base_locked
        ))

        ok_tv = TextView(act)
        ok_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        try:
            ok_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        ok_tv.setGravity(Gravity.CENTER)
        ok_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        ok_btn.addView(ok_tv, FrameLayout.LayoutParams(-1, -2))

        # mutable counter visible to the tick closure
        remaining = [_COUNTDOWN_SEC]

        def update_btn():
            n = remaining[0]
            if n > 0:
                ok_tv.setText(f"{strings.beta_dialog_ok} ({n})")
            else:
                ok_tv.setText(strings.beta_dialog_ok)
                ok_btn.setClickable(True)
                ok_btn.setFocusable(True)
                ok_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(28), base_active, pressed_active
                ))
                sheet.setCanDismissWithSwipe(True)
                sheet.setCanDismissWithTouchOutside(True)

        def tick():
            remaining[0] -= 1
            run_on_ui_thread(update_btn)
            if remaining[0] > 0:
                run_on_ui_thread(tick, 1000)

        def on_ok(v):
            if remaining[0] > 0:
                return
            LocalConfig.set("isBetaShow", True)
            sheet.dismiss()

        ok_btn.setOnClickListener(OnClickListener(on_ok))
        _apply_press_scale(ok_btn)
        root.addView(ok_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

        sheet.setCustomView(root)
        sheet.show()

        # draw initial state then start ticking
        run_on_ui_thread(update_btn)
        run_on_ui_thread(tick, 1000)
    except Exception as e:
        log(f"isBeta._show_beta_dialog: error: {e}")


def _check_beta():
    try:
        if LocalConfig.get("isBetaShow", False):
            return
        run_on_ui_thread(_show_beta_dialog)
    except Exception as e:
        log(f"isBeta._check_beta: error: {e}")


def init():
    if not BETA:
        return
    run_on_ui_thread(_check_beta, 1000)

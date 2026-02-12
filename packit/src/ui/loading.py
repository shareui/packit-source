from android_utils import log
from client_utils import get_last_fragment
from org.telegram.ui.ActionBar import Theme
from org.telegram.ui.Components import LayoutHelper
from org.telegram.messenger import AndroidUtilities
from android.widget import LinearLayout, TextView, ProgressBar
from android.view import Gravity
from android.util import TypedValue
from android.graphics import PorterDuff
from android import R as AndroidR


def show_loading_sheet(install_ui, title: str, message: str = "Loading..."):
    fragment = get_last_fragment()
    if not fragment:
        return None
    act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
    if not act:
        return None
    try:
        from org.telegram.ui.ActionBar import BottomSheet
        sheet = BottomSheet(act, False, fragment.getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)
        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(20), AndroidUtilities.dp(20), AndroidUtilities.dp(20))
        try:
            root.setBackground(install_ui._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass
        title_tv = TextView(act)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title_tv.setTypeface(AndroidUtilities.bold())
        title_tv.setText(title)
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER)
        pb = ProgressBar(act, None, AndroidR.attr.progressBarStyleLarge)
        pb.setScaleX(1.5)
        pb.setScaleY(1.5)
        try:
            pb.setIndeterminateTintList(Theme.getColor(Theme.key_featuredStickers_addButton))
        except Exception:
            try:
                pb.getIndeterminateDrawable().setColorFilter(
                    Theme.getColor(Theme.key_dialogTextBlue), PorterDuff.Mode.MULTIPLY
                )
            except Exception:
                pass
        pb_lp = LinearLayout.LayoutParams(-2, -2)
        pb_lp.gravity = Gravity.CENTER
        pb_lp.topMargin = AndroidUtilities.dp(16)
        pb_lp.bottomMargin = AndroidUtilities.dp(16)
        msg_tv = TextView(act)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        msg_tv.setText(message)
        msg_tv.setGravity(Gravity.CENTER)
        msg_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        root.addView(title_tv, LayoutHelper.createLinear(-1, -2))
        root.addView(pb, pb_lp)
        root.addView(msg_tv, LayoutHelper.createLinear(-1, -2))
        sheet.setCustomView(root)
        sheet.setCanDismissWithSwipe(False)
        try:
            sheet.setAllowNestedScroll(True)
        except Exception:
            pass
        sheet.show()
        return sheet
    except Exception as e:
        log(f"loading: failed to show loading sheet: {e}")
        return None
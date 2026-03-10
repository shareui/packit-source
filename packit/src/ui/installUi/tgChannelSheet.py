import traceback
from android_utils import log
from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, ScrollView, TextView
from java import dynamic_proxy
from org.telegram.messenger import AndroidUtilities, R
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper
from org.telegram.ui.Stories.recorder import ButtonWithCounterView
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser
except Exception:
    Browser = None


def show_tg_channel_sheet(activity, resource_provider):
    try:
        from elyx import strings
        from ...other.localConfig import LocalConfig

        sheet = BottomSheet(activity, False, resource_provider)
        sheet.fixNavigationBar()

        frame = FrameLayout(activity)
        linear = LinearLayout(activity)
        linear.setOrientation(LinearLayout.VERTICAL)
        frame.addView(linear)

        from org.telegram.messenger import R as R_tg
        from org.telegram.ui.Components import RLottieImageView
        anim = RLottieImageView(activity)
        anim.setAutoRepeat(True)
        anim.setAnimation(R_tg.raw.utyan_gigagroup, 120, 120)
        anim.playAnimation()
        linear.addView(anim, LayoutHelper.createLinear(120, 120, Gravity.CENTER_HORIZONTAL, 0, 20, 0, 0))

        title = TextView(activity)
        title.setGravity(Gravity.CENTER_HORIZONTAL)
        title.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
        title.setTextSize(1, 20.0)
        title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        title.setText(strings["tg_channel_title"])
        linear.addView(title, LayoutHelper.createFrame(-1, -2.0, 0, 40.0, 16.0, 40.0, 0.0))

        subtitle = TextView(activity)
        subtitle.setGravity(Gravity.CENTER_HORIZONTAL)
        subtitle.setTextSize(1, 14.0)
        subtitle.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteGrayText))
        subtitle.setText(strings["tg_channel_subtitle"])
        linear.addView(subtitle, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 10.0, 24.0, 8.0))

        joinBtn = ButtonWithCounterView(activity, True, resource_provider)
        joinBtn.setRound()
        joinBtn.setText(strings["tg_channel_join"], False)

        class _JoinClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                LocalConfig.set("showTgc", True)
                try:
                    from ...other.achievements import unlock_secret
                    unlock_secret("subscriber")
                except Exception as e:
                    log(f"tgChannelSheet: achievement unlock error: {e}")
                try:
                    url = strings["tg_channel_url"]
                    uri = Uri.parse(url)
                    Browser.openUrl(activity, uri, True, True, True, None, None, False, False, False)
                except Exception:
                    log(f"tgChannelSheet: failed to open url: {traceback.format_exc()}")

        joinBtn.setOnClickListener(_JoinClick())
        linear.addView(joinBtn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 12.0, 16.0, 8.0))

        dismissBtn = ButtonWithCounterView(activity, False, resource_provider)
        dismissBtn.setRound()
        dismissBtn.setNeutral()
        dismissBtn.setText(strings["tg_channel_dismiss"], False)

        class _DismissClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                LocalConfig.set("showTgc", True)

        dismissBtn.setOnClickListener(_DismissClick())
        linear.addView(dismissBtn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 0.0, 16.0, 0.0))

        scroll = ScrollView(activity)
        scroll.addView(frame)
        sheet.setCustomView(scroll)
        sheet.show()
    except Exception:
        log(f"tgChannelSheet: show error: {traceback.format_exc()}")

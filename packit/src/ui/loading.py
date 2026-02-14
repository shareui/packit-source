from android_utils import log
from client_utils import get_last_fragment
from org.telegram.ui.ActionBar import Theme
from org.telegram.ui.Components import LayoutHelper
from org.telegram.messenger import AndroidUtilities
from android.widget import LinearLayout, TextView, VideoView
from android.view import Gravity
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.media import MediaPlayer
from java import dynamic_proxy
import os
from org.telegram.ui.ActionBar import BottomSheet


def show_loading_sheet(install_ui, title: str, message: str = "Loading..."):
    fragment = get_last_fragment()
    if not fragment:
        return None

    act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
    if not act:
        return None

    try:
        sheet = BottomSheet(act, False, fragment.getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(20),
            AndroidUtilities.dp(20),
            AndroidUtilities.dp(20),
            AndroidUtilities.dp(20)
        )

        try:
            root.setBackground(
                install_ui._create_rounded_bg(
                    Theme.getColor(Theme.key_dialogBackground)
                )
            )
        except Exception:
            try:
                root.setBackgroundColor(
                    Theme.getColor(Theme.key_dialogBackground)
                )
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

        pb = VideoView(act)

        video_path = os.path.join(
            os.path.dirname(__file__),
            "../../res/anim.mp4"
        )

        pb.setVideoPath(video_path)

        try:
            audio_manager = act.getSystemService(act.AUDIO_SERVICE)
            if audio_manager:
                pb.setAudioFocusRequest(0)
        except Exception:
            pass

        size = AndroidUtilities.dp(120)
        pb_lp = LinearLayout.LayoutParams(size, size)
        pb_lp.gravity = Gravity.CENTER
        pb_lp.topMargin = AndroidUtilities.dp(16)
        pb_lp.bottomMargin = AndroidUtilities.dp(16)

        container = LinearLayout(act)
        container.setOrientation(LinearLayout.VERTICAL)

        container_lp = LinearLayout.LayoutParams(size, size)
        container_lp.gravity = Gravity.CENTER
        container_lp.topMargin = AndroidUtilities.dp(16)
        container_lp.bottomMargin = AndroidUtilities.dp(16)

        circle = GradientDrawable()
        circle.setShape(GradientDrawable.OVAL)
        circle.setColor(0x00000000)

        container.setBackground(circle)
        container.setClipToOutline(True)

        video_lp = LinearLayout.LayoutParams(-1, -1)
        pb.setLayoutParams(video_lp)

        if pb.getParent() is not None:
            try:
                pb.getParent().removeView(pb)
            except Exception:
                pass

        container.addView(pb, video_lp)

        class CompletionListener(dynamic_proxy(MediaPlayer.OnCompletionListener)):
            def __init__(self, vv):
                super().__init__()
                self.vv = vv

            def onCompletion(self, mp):
                self.vv.start()

        pb.setOnCompletionListener(CompletionListener(pb))
        pb.start()

        try:
            media_player = pb.getMediaPlayer()
            if media_player:
                media_player.setVolume(0, 0)
        except Exception:
            pass

        msg_tv = TextView(act)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        msg_tv.setText(message)
        msg_tv.setGravity(Gravity.CENTER)
        msg_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))

        root.addView(title_tv, LayoutHelper.createLinear(-1, -2))
        root.addView(container, container_lp)
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
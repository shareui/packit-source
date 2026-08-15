# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Text, Divider, Custom
from ui.bulletin import BulletinHelper
from android.net import Uri
from android.os import Process
from client_utils import get_last_fragment, run_on_queue, GLOBAL_QUEUE
try:
    from android.widget import LinearLayout, TextView, ImageView, FrameLayout
except Exception as e:
    import android_utils as _au; _au.log(f"import android.widget failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.graphics.drawable import GradientDrawable
except Exception as e:
    import android_utils as _au; _au.log(f"import android.graphics.drawable import GradientDrawable failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.view import Gravity
except Exception as e:
    import android_utils as _au; _au.log(f"import android.view import Gravity failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.util import TypedValue
except Exception as e:
    import android_utils as _au; _au.log(f"import android.util import TypedValue failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from androidx.core.content import ContextCompat
except Exception as e:
    import android_utils as _au; _au.log(f"import androidx.core.content import ContextCompat failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger.browser import Browser
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger.browser import Browser failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


def _makeBanner(context, icon_name, title_text, subtitle_text):
    dp = AndroidUtilities.dp

    container = LinearLayout(context)
    container.setOrientation(LinearLayout.VERTICAL)
    container.setGravity(Gravity.CENTER)
    container.setPadding(dp(16), dp(24), dp(16), dp(16))

    # circular accent background for icon
    circle_size = dp(64)
    icon_container = FrameLayout(context)
    circle_bg = GradientDrawable()
    circle_bg.setShape(GradientDrawable.OVAL)
    circle_bg.setColor(Theme.getColor(Theme.key_dialogLinkSelection))
    icon_container.setBackground(circle_bg)

    icon_view = ImageView(context)
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    try:
        res_id = getattr(R_tg.drawable, icon_name)
        drawable = ContextCompat.getDrawable(context, res_id)
        if drawable is not None:
            drawable.setTint(Theme.getColor(Theme.key_avatar_text))
            icon_view.setImageDrawable(drawable)
    except Exception:
        pass
    icon_container.addView(icon_view, LayoutHelper.createFrame(36, 36, Gravity.CENTER))
    container.addView(icon_container, LayoutHelper.createLinear(64, 64, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 14))

    title = TextView(context)
    title.setGravity(Gravity.CENTER)
    title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
    title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
    try:
        title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
    except Exception:
        pass
    title.setText(title_text)
    container.addView(title, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 4))

    subtitle = TextView(context)
    subtitle.setGravity(Gravity.CENTER)
    subtitle.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    subtitle.setText(subtitle_text)
    container.addView(subtitle, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL))

    return container


class DocumentationSettings:
    def __init__(self):
        pass

    def _openUrl(self, url):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                Browser.openUrl(act, Uri.parse(url), True, True, True, None, None, False, False, False)
            else:
                raise Exception("no activity")
        except Exception:
            BulletinHelper.show_error(strings.failed_to_open_link)

    def _openFaq(self, view, *_):
        self._openUrl("https://t.me/packitGround/13")

    def _openRepoGuide(self, view, *_):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/packitAPI.md")

    def _openBugReport(self, view, *_):
        self._openUrl("https://t.me/packitGround/85")

    def _openDeeplinks(self, view, *_):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/deeplinks.md")

    def _openMetainfoDocs(self, view, *_):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/devdocs.md")

    def _openPublishPlugin(self, view, *_):
        self._openUrl(strings.publish_plugin_guide_url)

    def _openEnlightenment(self, view, *_):
        
        try:
            clicks = settings.get("enlighten_clicks", 0) + 1
            logx(f"docs._openEnlightenment: clicks={clicks}", True)
            settings.set_setting("enlighten_clicks", clicks)
            fragment = get_last_fragment()
            logx(f"docs._openEnlightenment: fragment={fragment}", True)

            if clicks <= 9:
                logx(f"docs._openEnlightenment: showing enlighten_{clicks}", True)
                BulletinHelper.show_info(getattr(strings, f"enlighten_{clicks}"), fragment)
            elif clicks == 10:
                logx(f"docs._openEnlightenment: showing enlighten_10, scheduling kill", True)
                BulletinHelper.show_info(strings.enlighten_10, fragment)
                run_on_queue(lambda *_: Process.killProcess(Process.myPid()), GLOBAL_QUEUE, 1000)
            elif clicks >= 11:
                logx(f"docs._openEnlightenment: showing enlighten_11, resetting clicks, unlocking achievement", True)
                BulletinHelper.show_info(strings.enlighten_11, fragment)
                settings.set_setting("enlighten_clicks", 0)
                try:
                    from ..achievements.service.AchivementsEngine import unlock_secret
                    logx(f"docs._openEnlightenment: calling unlock_secret enlightened", True)
                    unlock_secret("enlightened")
                    logx(f"docs._openEnlightenment: unlock_secret done", True)
                except Exception as e:
                    logx(f"docs._openEnlightenment: unlock_secret failed: {e}", False)
                run_on_queue(lambda *_: Process.killProcess(Process.myPid()), GLOBAL_QUEUE, 1000)
        except Exception as e:
            logx(f"docs._openEnlightenment: error: {e}", False)

    def _openSecretVideo(self, view, *_):
        self._openUrl("https://youtu.be/xMHJGd3wwZk?si=ZpXaKUV-bpq_Fcob")

    def _makeBannerItem(self, icon_name, title_text, subtitle_text):
        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if not ctx:
                return None
            view = _makeBanner(ctx, icon_name, title_text, subtitle_text)
            return Custom(view=view)
        except Exception:
            return None

    def build(self):
        items = []

        banner = self._makeBannerItem(
            "msg_help",
            str(strings.links_docs),
            str(strings.links_docs_desc)
        )
        if banner is not None:
            items.append(banner)

        items += [
            Text(
                text=strings.faq,
                subtext=strings.faq_desc,
                icon="msg_help",
                on_click=self._openFaq,
                link_alias="faq"
            ),
            Text(
                text=strings.report_bug,
                subtext=strings.report_bug_desc,
                icon="msg_report",
                on_click=self._openBugReport,
                link_alias="report_bug"
            ),
            Text(
                text=strings.how_to_enlighten,
                subtext=strings.how_to_enlighten_desc,
                icon="msg_info",
                on_click=self._openEnlightenment,
                link_alias="how_to_enlighten"
            ),
            Text(
                text=strings.secret_video,
                subtext=strings.secret_video_desc,
                icon="msg_videocall",
                on_click=self._openSecretVideo,
                link_alias="secret_video"
            ),

            Divider(),

            Divider(text=strings.docs_suggest_review),

            Header(text=strings.for_devs),

            Text(
                text=strings.publish_ur_plugin,
                subtext=strings.publish_ur_plugin_desc,
                icon="filled_add_album",
                accent=True,
                on_click=self._openPublishPlugin,
                link_alias="publish_ur_plugin"
            ),
            Text(
                text=strings.creating_own_repo,
                subtext=strings.creating_own_repo_desc,
                icon="msg_edit",
                on_click=self._openRepoGuide,
                link_alias="creating_own_repo"
            ),
            Text(
                text=strings.deeplinks,
                subtext=strings.deeplinks_desc,
                icon="msg_link",
                on_click=self._openDeeplinks,
                link_alias="deeplinks"
            ),
            Text(
                text=strings.devdocs,
                subtext=strings.devdocs_desc,
                icon="menu_intro",
                on_click=self._openMetainfoDocs,
                link_alias="devdocs"
            ),

            Divider()
        ]

        return items
        # mr. penis
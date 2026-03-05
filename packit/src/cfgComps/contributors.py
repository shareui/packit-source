from ui.settings import Header, Text, Divider, Custom
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
try:
    from android.widget import FrameLayout, LinearLayout, TextView
except Exception as e:
    import android_utils as _au; _au.log(f"import android.widget import FrameLayout, LinearLayout, TextView failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.view import Gravity
except Exception as e:
    import android_utils as _au; _au.log(f"import android.view import Gravity failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.util import TypedValue
except Exception as e:
    import android_utils as _au; _au.log(f"import android.util import TypedValue failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.graphics import BitmapFactory
except Exception as e:
    import android_utils as _au; _au.log(f"import android.graphics import BitmapFactory failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.widget import ImageView
except Exception as e:
    import android_utils as _au; _au.log(f"import android.widget import ImageView failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"import android.net import Uri failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.content import Intent
except Exception as e:
    import android_utils as _au; _au.log(f"import android.content import Intent failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import BackupImageView, LayoutHelper, UItem
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import BackupImageView, LayoutHelper, UItem failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities, ImageLocation, UserConfig
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, ImageLocation, UserConfig failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger.browser import Browser
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger.browser import Browser failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui import LaunchActivity
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui import LaunchActivity failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Gifts import GiftSheet
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Gifts import GiftSheet failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android_utils import OnClickListener, run_on_ui_thread
except Exception as e:
    import android_utils as _au; _au.log(f"import android_utils import OnClickListener, run_on_ui_thread failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
import urllib.request
import android_utils as _au

def _make_avatar_view(context, image_url, title_text, subtitle_text, username_url=None):
    try:

        dp = AndroidUtilities.dp

        container = FrameLayout(context)
        try:
            container.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
        except Exception:
            try:
                container.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
            except Exception:
                pass

        main_layout = LinearLayout(context)
        main_layout.setOrientation(LinearLayout.HORIZONTAL)
        main_layout.setGravity(Gravity.CENTER_VERTICAL)
        main_layout.setPadding(dp(20), dp(20), dp(20), dp(20))

        img = BackupImageView(context)
        img.setRoundRadius(dp(50))

        try:
            img.setImage(ImageLocation.getForPath(image_url), "100_100", None, None, None, 0)
        except Exception:
            try:
                data = urllib.request.urlopen(image_url, timeout=8).read()
                bmp = BitmapFactory.decodeByteArray(data, 0, len(data))
                img.setImageBitmap(bmp)
                img.setScaleType(ImageView.ScaleType.CENTER_CROP)
            except Exception:
                pass

        main_layout.addView(img, LayoutHelper.createLinear(60, 60, Gravity.CENTER_VERTICAL, 0, 0, 16, 0))

        text_container = LinearLayout(context)
        text_container.setOrientation(LinearLayout.VERTICAL)
        text_container.setGravity(Gravity.CENTER_VERTICAL)

        title = TextView(context)
        title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        try:
            title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        title.setText(title_text)
        title.setSingleLine(True)
        text_container.addView(title, LayoutHelper.createLinear(-1, -2, 0, 0, 4, 0))

        if subtitle_text:
            subtitle = TextView(context)
            subtitle.setTextColor(Theme.getColor(Theme.key_dialogTextBlue))
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            subtitle.setText(subtitle_text)
            
            if username_url:
                try:
                    subtitle.setOnClickListener(OnClickListener(lambda v: _open_username_url(username_url)))
                    try:
                        subtitle.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
                    except Exception:
                        pass
                except Exception:
                    pass
            
            text_container.addView(subtitle, LayoutHelper.createLinear(-1, -2))

        main_layout.addView(text_container, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))
        container.addView(main_layout, LayoutHelper.createFrame(-1, -2, Gravity.CENTER))

        return container
    except Exception:
        return None

def _open_username_url(url):
    try:
        if url.startswith("https://t.me/"):
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                uri = Uri.parse(url)
                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        else:
            from org.telegram.messenger import ApplicationLoader
            context = ApplicationLoader.applicationContext
            intent = Intent(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(url))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
    except Exception:
        try:
            BulletinHelper.show_error(strings.failed_to_open_link)
        except Exception:
            pass


class ContributorsSettings:
    def __init__(self):
        pass

    def _open_gift_sheet_vestr(self):
        try:
            if not hasattr(LaunchActivity, 'instance') or LaunchActivity.instance is None:
                return
            launch_activity = LaunchActivity.instance
            getSafeLastFragment_method = launch_activity.getClass().getDeclaredMethod("getSafeLastFragment")
            getSafeLastFragment_method.setAccessible(True)
            last_fragment = getSafeLastFragment_method.invoke(launch_activity)
            if last_fragment is None or last_fragment.getContext() is None:
                return
            target_user_id = 2037728749
            current_account = UserConfig.selectedAccount
            gift_sheet = GiftSheet(
                last_fragment.getContext(),
                current_account,
                target_user_id,
                None,
                None
            )
            gift_sheet.show()
        except Exception:
            pass

    def _open_url(self, url):
        try:
            if url.startswith("https://t.me/"):
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if act:
                    uri = Uri.parse(url)
                    Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
            else:
                from org.telegram.messenger import ApplicationLoader
                context = ApplicationLoader.applicationContext
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse(url))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
        except Exception:
            BulletinHelper.show_error(strings.failed_to_open_link)

    def _make_avatar_item(self, image_url, title_text="", subtitle_text="", username_url=None):
        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if not ctx:
                return None
            context = ctx
        except Exception:
            return None

        view = _make_avatar_view(context, image_url, title_text, subtitle_text, username_url)
        if view is None:
            return None

        try:
            return Custom(view=view)
        except Exception:
            pass

        try:
            item = UItem.asCustom(view)
            try:
                item.setTransparent(True)
            except Exception:
                pass
            return item
        except Exception:
            return None

    def build(self):
        def support_via_send(view):
            try:
                BulletinHelper.show_success(strings.donate_easter_egg)
            except Exception:
                pass

            run_on_ui_thread(
                lambda: self._open_url("https://t.me/send?start=IV7kTHbP2iXp"),
                1000
            )

        def support_via_ton(view):
            tonAddress = "UQADRm0R1HNgMYuTfbHB3kdENuWt_Et5dFlEtrILK3LQ-KKL"
            try:
                if AndroidUtilities.addToClipboard(tonAddress):
                    BulletinHelper.show_success(strings.copied_to_clipboard)
                else:
                    BulletinHelper.show_error(strings.failed_to_copy)
            except Exception:
                BulletinHelper.show_error(strings.failed_to_copy)

        items = []

        avatar_shareui = self._make_avatar_item(
            "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/assets/shareui.jpg",
            title_text=str(strings.founder_shareui),
            subtitle_text="@shareui",
            username_url="https://t.me/shareui"
        )
        if avatar_shareui is not None:
            items.append(avatar_shareui)
        else:
            items.append(Header(text=strings.founder_shareui))

        items += [
            Text(
                text=strings.github,
                icon="msg_link",
                link_alias="github_s",
                on_click=lambda v: self._open_url("https://github.com/shareui")
            ),
            Text(
                text=strings.direct_message,
                icon="msg_message",
                link_alias="direct_s",
                on_click=lambda v: self._open_url("https://t.me/shareui")
            ),
            Text(
                text=strings.personal_channel,
                icon="msg_channel",
                link_alias="tgc_s",
                on_click=lambda v: self._open_url("https://t.me/shuiilog")
            ),
            Text(
                text=strings.support_via_send,
                icon="filled_paid_suggest_24",
                accent=True,
                link_alias="support_send_s",
                on_click=support_via_send
            ),
            Text(
                text=strings.support_via_ton,
                icon="menu_my_ton",
                accent=True,
                link_alias="support_ton_s",
                on_click=support_via_ton
            ),

            Divider(),
        ]

        avatar_vestr = self._make_avatar_item(
            "https://avatars.githubusercontent.com/u/184731661?v=4",
            title_text=str(strings.lead_developer_vestr),
            subtitle_text="@mr_Vestr",
            username_url="https://t.me/mr_Vestr"
        )
        if avatar_vestr is not None:
            items.append(avatar_vestr)
        else:
            items.append(Header(text=strings.lead_developer_vestr))

        items += [
            Text(
                text=strings.github,
                icon="msg_link",
                link_alias="github_v",
                on_click=lambda v: self._open_url("https://github.com/mr-vestr")
            ),
            Text(
                text=strings.direct_message,
                icon="msg_message",
                link_alias="direct_v",
                on_click=lambda v: self._open_url("https://t.me/mr_Vestr")
            ),
            Text(
                text=strings.personal_channel,
                icon="msg_channel",
                link_alias="tgc_v",
                on_click=lambda v: self._open_url("https://t.me/I_am_Vestr")
            ),
            Text(
                text="Support with Stars",
                icon="menu_feature_reactions",
                accent=True,
                link_alias="support_stars_v",
                on_click=lambda v: self._open_gift_sheet_vestr()
            ),

            Divider(),

            Divider(text=strings.special_thanks)
        ]

        return items
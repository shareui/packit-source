# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.settings import Header, Text, Divider, Custom
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
try:
    from android.widget import FrameLayout, LinearLayout, TextView
except Exception as e:
    import android_utils as _au; _au.log(f"import android.widget import FrameLayout, LinearLayout, TextView failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.view import Gravity
except Exception as e:
    import android_utils as _au; _au.log(f"import android.view import Gravity failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.util import TypedValue
except Exception as e:
    import android_utils as _au; _au.log(f"import android.util import TypedValue failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.graphics import BitmapFactory
except Exception as e:
    import android_utils as _au; _au.log(f"import android.graphics import BitmapFactory failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.widget import ImageView
except Exception as e:
    import android_utils as _au; _au.log(f"import android.widget import ImageView failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"import android.net import Uri failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.content import Intent
except Exception as e:
    import android_utils as _au; _au.log(f"import android.content import Intent failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import BackupImageView, LayoutHelper, UItem
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import BackupImageView, LayoutHelper, UItem failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities, ImageLocation, UserConfig
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, ImageLocation, UserConfig failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger.browser import Browser
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger.browser import Browser failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui import LaunchActivity
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui import LaunchActivity failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Gifts import GiftSheet
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Gifts import GiftSheet failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android_utils import OnClickListener, run_on_ui_thread
except Exception as e:
    import android_utils as _au; _au.log(f"import android_utils import OnClickListener, run_on_ui_thread failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
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
        title.setHorizontalFadingEdgeEnabled(True)
        title.setFadingEdgeLength(AndroidUtilities.dp(24))
        text_container.addView(title, LayoutHelper.createLinear(-1, -2, 0, 0, 4, 0))

        if subtitle_text:
            subtitle = TextView(context)
            subtitle.setTextColor(Theme.getColor(Theme.key_dialogTextBlue))
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            subtitle.setText(subtitle_text)
            subtitle.setSingleLine(True)
            subtitle.setHorizontalFadingEdgeEnabled(True)
            subtitle.setFadingEdgeLength(AndroidUtilities.dp(24))
            
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

def _make_link_row(context, icon_name, label_text, link_text, on_click):
    # row: icon | label (fill) | accent link text
    try:
        from org.telegram.messenger import R as R_tg
        from androidx.core.content import ContextCompat
        dp = AndroidUtilities.dp

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        row.setPadding(dp(20), dp(10), dp(16), dp(10))
        row.setMinimumHeight(dp(50))
        row.setClickable(True)
        row.setOnClickListener(OnClickListener(on_click))

        try:
            selector = Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2)
            row.setBackground(selector)
        except Exception:
            pass

        icon_view = ImageView(context)
        icon_view.setScaleType(ImageView.ScaleType.CENTER)
        try:
            res_id = getattr(R_tg.drawable, icon_name)
            drawable = ContextCompat.getDrawable(context, res_id)
            if drawable is not None:
                drawable.setTint(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
                icon_view.setImageDrawable(drawable)
        except Exception:
            pass
        row.addView(icon_view, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 0, 0, 24, 0))

        label = TextView(context)
        label.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        label.setText(label_text)
        label.setSingleLine(True)
        row.addView(label, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        link = TextView(context)
        link.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteValueText))
        link.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        link.setText(link_text)
        link.setSingleLine(True)
        try:
            link.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        row.addView(link, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

        return row
    except Exception as e:
        _au.log(f"contributors._make_link_row error: {e}")
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

    def _open_vestr_direct_message(self):
        try:
            from java.util import Locale
            current_lang = Locale.getDefault().getLanguage()
            if current_lang == "ru":
                url = "https://t.me/mr_vestr/?text=%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82%21+%D0%9F%D0%B8%D1%88%D1%83+%D0%BF%D0%BE+%D0%BF%D0%BE%D0%B2%D0%BE%D0%B4%D1%83+%D0%BF%D0%BB%D0%B0%D0%B3%D0%B8%D0%BD%D0%B0+%C2%ABPackit%C2%BB%3A%0D%0A"
            else:
                url = "https://t.me/mr_vestr/?text=Hello%21+I%27m+writing+regarding+the+%22Packit%22+plugin%3A%0D%0A"
            self._open_url(url)
        except Exception:
            self._open_url("https://t.me/mr_Vestr")

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

    def _make_small_divider(self):
        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if not ctx:
                return None
            
            from android.view import View
            
            divider = View(ctx)
            divider.setMinimumHeight(AndroidUtilities.dp(1))
            divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
            container = FrameLayout(ctx)
            params = FrameLayout.LayoutParams(-1, AndroidUtilities.dp(1))
            params.setMargins(AndroidUtilities.dp(68), AndroidUtilities.dp(4), AndroidUtilities.dp(16), 0)
            container.addView(divider, params)
            
            return Custom(view=container)
        except Exception:
            return None

    def _make_link_item(self, icon_name, label_text, link_text, on_click):
        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if not ctx:
                return None
            view = _make_link_row(ctx, icon_name, label_text, link_text, on_click)
            if view is None:
                return None
            return Custom(view=view)
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
            "https://avatars.githubusercontent.com/u/244288900?s=400&u=e0771909fd592fb2263932a6922dc4e7e5de5a81&v=4",
            title_text=str(strings.founder_shareui),
            subtitle_text="@shareui",
            username_url="https://t.me/shareui"
        )
        if avatar_shareui is not None:
            items.append(avatar_shareui)
        else:
            items.append(Header(text=strings.founder_shareui))

        item = self._make_link_item("msg_link", str(strings.github), "github.com/shareui", lambda v: self._open_url("https://github.com/shareui"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_message", str(strings.direct_message), "t.me/shareui", lambda v: self._open_url("https://t.me/shareui"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_channel", str(strings.plugins_channel), "t.me/doctashare", lambda v: self._open_url("https://t.me/doctashare"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        items += [
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
        ]

        items.append(Divider())

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

        item = self._make_link_item("msg_link", str(strings.github), "github.com/mr-vestr", lambda v: self._open_url("https://github.com/mr-vestr"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_message", str(strings.direct_message), "t.me/mr_Vestr", lambda v: self._open_vestr_direct_message())
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_channel", str(strings.plugins_channel), "t.me/I_am_Vestr", lambda v: self._open_url("https://t.me/I_am_Vestr"))
        if item is not None:
            items.append(item)
            
        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        items += [
            Text(
                text=strings.support_with_stars,
                icon="menu_feature_reactions",
                accent=True,
                link_alias="support_stars_v",
                on_click=lambda v: self._open_gift_sheet_vestr()
            ),

            Divider(),
        ]

        def support_via_send_pixwet(view):
            try:
                BulletinHelper.show_success(strings.donate_easter_egg)
            except Exception:
                pass
            run_on_ui_thread(
                lambda: self._open_url("https://t.me/send?start=IVwvWMdWfPCE"),
                1000
            )

        def support_via_ton_pixwet(view):
            tonAddress = "UQBZCTLurgR5KiyvV5o8AchUQSsz-5o_mvehtuf08c8DuDMI"
            try:
                if AndroidUtilities.addToClipboard(tonAddress):
                    BulletinHelper.show_success(strings.copied_to_clipboard)
                else:
                    BulletinHelper.show_error(strings.failed_to_copy)
            except Exception:
                BulletinHelper.show_error(strings.failed_to_copy)

        avatar_pixwet = self._make_avatar_item(
            "https://avatars.githubusercontent.com/u/102206474?v=4",
            title_text=str(strings.mentor),
            subtitle_text="@pixwet",
            username_url="https://t.me/pixwet"
        )
        if avatar_pixwet is not None:
            items.append(avatar_pixwet)
        else:
            items.append(Header(text=strings.mentor))

        item = self._make_link_item("msg_link", str(strings.github), "github.com/pixwet", lambda v: self._open_url("https://github.com/pixwet"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_message", str(strings.direct_message), "t.me/pixwet", lambda v: self._open_url("https://t.me/pixwet"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_channel", str(strings.plugins_channel), "t.me/CactusPlugins", lambda v: self._open_url("https://t.me/CactusPlugins"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_channel", str(strings.personal_channel), "t.me/exteraFeatures", lambda v: self._open_url("https://t.me/exteraFeatures"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        items += [
            Text(
                text=strings.support_via_send,
                icon="filled_paid_suggest_24",
                accent=True,
                link_alias="support_send_pw",
                on_click=support_via_send_pixwet
            ),
            Text(
                text=strings.support_via_ton,
                icon="menu_my_ton",
                accent=True,
                link_alias="support_ton_pw",
                on_click=support_via_ton_pixwet
            ),

            Divider(),
        ]

        avatar_watcha = self._make_avatar_item(
            "https://avatars.githubusercontent.com/u/103638465?v=4",
            title_text="Translator",
            subtitle_text="@homewatcha",
            username_url="https://t.me/homewatcha"
        )
        if avatar_watcha is not None:
            items.append(avatar_watcha)
        else:
            items.append(Header(text="watcha"))

        item = self._make_link_item("msg_link", str(strings.github), "github.com/homewatcha", lambda v: self._open_url("https://github.com/homewatcha"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_message", str(strings.direct_message), "t.me/homewatcha", lambda v: self._open_url("https://t.me/homewatcha"))
        if item is not None:
            items.append(item)

        divider = self._make_small_divider()
        if divider is not None:
            items.append(divider)

        item = self._make_link_item("msg_channel", str(strings.personal_channel), "t.me/watchashitposts", lambda v: self._open_url("https://t.me/watchashitposts"))
        if item is not None:
            items.append(item)

        items += [
            Divider(),

            Divider(text=strings.special_thanks)
        ]

        return items
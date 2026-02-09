from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from org.telegram.messenger.browser import Browser
from android.net import Uri
from android.content import Intent
from org.telegram.messenger import ApplicationLoader
from elyx import strings


class ContributorsSettings:
    def __init__(self):
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
                context = ApplicationLoader.applicationContext
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse(url))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
        except Exception:
            BulletinHelper.show_error(strings.failed_to_open_link)

    def build(self):
        def support_via_send(view):
            try:
                BulletinHelper.show_success(strings.donate_easter_egg)
            except Exception:
                pass

            from android_utils import run_on_ui_thread
            run_on_ui_thread(
                lambda: self._open_url("https://t.me/send?start=IV7kTHbP2iXp"),
                1000
            )

        def support_via_ton(view):
            tonAddress = "UQADRm0R1HNgMYuTfbHB3kdENuWt_Et5dFlEtrILK3LQ-KKL"
            try:
                from org.telegram.messenger import AndroidUtilities
                if AndroidUtilities.addToClipboard(tonAddress):
                    BulletinHelper.show_success(strings.copied_to_clipboard)
                else:
                    BulletinHelper.show_error(strings.failed_to_copy)
            except Exception:
                BulletinHelper.show_error(strings.failed_to_copy)

        return [
            Header(text=strings.founder_shareui),

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

            Header(text=strings.lead_developer_vestr),

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

            Divider()
        ]
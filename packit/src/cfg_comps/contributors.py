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
        return [
            Header(text=strings.founder_shareui),
            
            Text(
                text=strings.github,
                icon="msg_link",
                on_click=lambda v: self._open_url("https://github.com/shareui")
            ),
            Text(
                text=strings.direct_message,
                icon="msg_message",
                on_click=lambda v: self._open_url("https://t.me/shareui")
            ),
            Text(
                text=strings.personal_channel,
                icon="msg_channel",
                on_click=lambda v: self._open_url("https://t.me/shuiilog")
            ),
            
            Divider(),
            
            Header(text=strings.lead_developer_vestr),

            Text(
                text=strings.github,
                icon="msg_link",
                on_click=lambda v: self._open_url("https://github.com/mr-vestr")
            ),
            Text(
                text=strings.direct_message,
                icon="msg_message",
                on_click=lambda v: self._open_url("https://t.me/mr_Vestr")
            ),
            Text(
                text=strings.personal_channel,
                icon="msg_channel",
                on_click=lambda v: self._open_url("https://t.me/I_am_Vestr")
            ),
            Divider()
        ]

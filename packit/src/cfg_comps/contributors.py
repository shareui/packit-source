from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log


class ContributorsSettings:
    def __init__(self):
        pass
    
    def _open_url(self, url):
        try:
            if url.startswith("https://t.me/"):
                from org.telegram.messenger.browser import Browser
                from android.net import Uri
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if act:
                    uri = Uri.parse(url)
                    Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
            else:
                from android.content import Intent
                from android.net import Uri
                from org.telegram.messenger import ApplicationLoader
                
                context = ApplicationLoader.applicationContext
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse(url))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
        except Exception as e:
            log(f"failed to open url: {e}")
            BulletinHelper.show_error("Failed to open link")
    
    def build(self):
        return [
            Header(text="Founder: @shareui"),
            
            Text(
                text="GitHub - github.com/shareui",
                icon="msg_link",
                on_click=lambda v: self._open_url("https://github.com/shareui")
            ),
            Text(
                text="Direct message - @shareui",
                icon="msg_message",
                on_click=lambda v: self._open_url("https://t.me/shareui")
            ),
            Text(
                text="Personal channel - @shuiilog",
                icon="msg_channel",
                on_click=lambda v: self._open_url("https://t.me/shuiilog")
            ),
            
            Divider(),
            
            Header(text="Lead Developer: @mr_Vestr"),

            Text(
                text="GitHub - github.com/mr-vestr",
                icon="msg_link",
                on_click=lambda v: self._open_url("https://github.com/mr-vestr")
            ),
            Text(
                text="Direct message - @mr_Vestr",
                icon="msg_message",
                on_click=lambda v: self._open_url("https://t.me/mr_Vestr")
            ),
            Text(
                text="Personal channel - @I_am_Vestr",
                icon="msg_channel",
                on_click=lambda v: self._open_url("https://t.me/I_am_Vestr")
            ),
            
        ]

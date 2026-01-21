from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from android_utils import log


class DocumentationSettings:
    def __init__(self):
        pass
    
    def _openUrl(self, url):
        try:
            if url.startswith("https://t.me/"):
                from client_utils import get_last_fragment
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
    
    def _openFaq(self, view):
        self._openUrl("https://t.me/c/3663388991/13")
    
    def _openRepoGuide(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/ownrepo.md")
    
    def _openBugReport(self, view):
        self._openUrl("https://t.me/c/3663388991/85")
    
    def _openForum(self, view):
        self._openUrl("https://t.me/+MlXY77j5URE2MTU8")
    
    def build(self):
        return [
            Header(text="Documentation"),
            Text(
                text="FAQ",
                icon="msg_help",
                on_click=self._openFaq
            ),
            Text(
                text="Creating your own repo",
                icon="msg_edit",
                on_click=self._openRepoGuide
            ),
            Text(
                text="Report a bug",
                icon="msg_report",
                on_click=self._openBugReport
            ),
            Text(
                text="Official forum",
                icon="msg_info",
                on_click=self._openForum
            ),

        ]
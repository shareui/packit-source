from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from android_utils import log
from android.content import Intent
from android.net import Uri
from org.telegram.messenger import ApplicationLoader
from client_utils import get_last_fragment
from org.telegram.messenger.browser import Browser


class DocumentationSettings:
    def __init__(self):
        pass
    
    def _openUrl(self, url):
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
    
    def _openDeeplinks(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/deeplinks.md")
    
    def build(self):
        return [
            Header(text="For users"),
            Text(
                text="FAQ",
                icon="msg_help",
                on_click=self._openFaq
            ),
            Text(
                text="Report a bug",
                icon="msg_report",
                on_click=self._openBugReport
            ),
            Text(
                text="Official forum",
                icon="filled_folder_existing",
                on_click=self._openForum
            ),
            Header(text="For devs"),
            Text(
                text="Creating your own repo",
                icon="msg_edit",
                on_click=self._openRepoGuide
            ),
            Text(
                text="Deeplinks",
                icon="msg_link",
                on_click=self._openDeeplinks
            ),
            Divider()
        ]

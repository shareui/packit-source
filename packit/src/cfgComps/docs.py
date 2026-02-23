from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from android.content import Intent
from android.net import Uri
from android.os import Process
from org.telegram.messenger import ApplicationLoader
from client_utils import get_last_fragment, run_on_queue, GLOBAL_QUEUE
from org.telegram.messenger.browser import Browser
from elyx import strings, settings

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
        except Exception:
            BulletinHelper.show_error(strings.failed_to_open_link)

    def _openFaq(self, view):
        self._openUrl("https://t.me/packitGround/13")

    def _openRepoGuide(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/ownrepo.md")

    def _openBugReport(self, view):
        self._openUrl("https://t.me/packitGround/85")

    def _openForum(self, view):
        self._openUrl("https://t.me/packitGround")

    def _openDeeplinks(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/deeplinks.md")

    def _openPublishPlugin(self, view):
        self._openUrl("https://t.me/packitGround/13/351")

    def _openEnlightenment(self, view):
        clicks = settings.get("enlighten_clicks", 0) + 1
        settings.set_setting("enlighten_clicks", clicks)
        fragment = get_last_fragment()

        if clicks <= 9:
            BulletinHelper.show_info(getattr(strings, f"enlighten_{clicks}"), fragment)
        elif clicks == 10:
            BulletinHelper.show_info(strings.enlighten_10, fragment)
            run_on_queue(lambda: Process.killProcess(Process.myPid()), GLOBAL_QUEUE, 1000)
        elif clicks >= 11:
            BulletinHelper.show_info(strings.enlighten_11, fragment)
            settings.set_setting("enlighten_clicks", 0)
            run_on_queue(lambda: Process.killProcess(Process.myPid()), GLOBAL_QUEUE, 1000)

    def _openSecretVideo(self, view):
        self._openUrl("https://youtu.be/xMHJGd3wwZk?si=ZpXaKUV-bpq_Fcob")

    def build(self):
      return [
          Header(text=strings.for_users),
  
          Text(
              text=strings.faq,
              icon="msg_help",
              on_click=self._openFaq,
              link_alias="faq"
          ),
          Text(
              text=strings.report_bug,
              icon="msg_report",
              on_click=self._openBugReport,
              link_alias="report_bug"
          ),
          Text(
              text=strings.official_forum,
              icon="filled_folder_existing",
              on_click=self._openForum,
              link_alias="open_forum"
          ),
          Text(
              text=strings.how_to_enlighten,
              icon="msg_info",
              on_click=self._openEnlightenment,
              link_alias="how_to_enlighten"
          ),
          Text(
              text=strings.secret_video,
              icon="msg_info",
              on_click=self._openSecretVideo,
              link_alias="secret_video"
          ),
  
          Divider(),
  
          Header(text=strings.for_devs),
  
          Text(
              text=strings.creating_own_repo,
              icon="msg_edit",
              on_click=self._openRepoGuide,
              link_alias="creating_own_repo"
          ),
          Text(
              text=strings.publish_ur_plugin,
              icon="filled_add_album",
              on_click=self._openPublishPlugin,
              link_alias="publish_ur_plugin"
          ),
          Text(
              text=strings.deeplinks,
              icon="msg_link",
              on_click=self._openDeeplinks,
              link_alias="deeplinks"
          ),
  
          Divider()
      ]

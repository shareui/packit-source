from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from android.net import Uri
from android.os import Process
from client_utils import get_last_fragment, run_on_queue, GLOBAL_QUEUE
try:
    from org.telegram.messenger.browser import Browser
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger.browser import Browser failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

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

    def _openFaq(self, view):
        self._openUrl("https://t.me/packitGround/13")

    def _openRepoGuide(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/ownrepo.md")

    def _openBugReport(self, view):
        self._openUrl("https://t.me/packitGround/85")

    def _openDeeplinks(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/deeplinks.md")

    def _openMetainfoDocs(self, view):
        self._openUrl("https://github.com/shareui/packit/blob/main/docs/devdocs.md")

    def _openPublishPlugin(self, view):
        self._openUrl("https://t.me/packitGround/13/351")

    def _openEnlightenment(self, view):
        from android_utils import log
        try:
            clicks = settings.get("enlighten_clicks", 0) + 1
            log(f"docs._openEnlightenment: clicks={clicks}")
            settings.set_setting("enlighten_clicks", clicks)
            fragment = get_last_fragment()
            log(f"docs._openEnlightenment: fragment={fragment}")

            if clicks <= 9:
                log(f"docs._openEnlightenment: showing enlighten_{clicks}")
                BulletinHelper.show_info(getattr(strings, f"enlighten_{clicks}"), fragment)
            elif clicks == 10:
                log(f"docs._openEnlightenment: showing enlighten_10, scheduling kill")
                BulletinHelper.show_info(strings.enlighten_10, fragment)
                run_on_queue(lambda: Process.killProcess(Process.myPid()), GLOBAL_QUEUE, 1000)
            elif clicks >= 11:
                log(f"docs._openEnlightenment: showing enlighten_11, resetting clicks, unlocking achievement")
                BulletinHelper.show_info(strings.enlighten_11, fragment)
                settings.set_setting("enlighten_clicks", 0)
                try:
                    from ..ui.AchievementsActivity.service.AchivementsEngine import unlock_secret
                    log(f"docs._openEnlightenment: calling unlock_secret enlightened")
                    unlock_secret("enlightened")
                    log(f"docs._openEnlightenment: unlock_secret done")
                except Exception as e:
                    log(f"docs._openEnlightenment: unlock_secret failed: {e}")
                run_on_queue(lambda: Process.killProcess(Process.myPid()), GLOBAL_QUEUE, 1000)
        except Exception as e:
            log(f"docs._openEnlightenment: error: {e}")

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
          Text(
              text=strings.devdocs,
              icon="msg_info",
              on_click=self._openMetainfoDocs,
              link_alias="devdocs"
          ),

          Divider()
      ]

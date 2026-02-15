from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment, run_on_queue
from android_utils import log, run_on_ui_thread
from elyx import strings
from hook_utils import find_class
from org.telegram.messenger import R as R_tg
from com.exteragram.messenger.utils.text import LocaleUtils  # noqa
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


def handle(url, repoManager):
    try:
        if "repo=add" not in url:
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)

        name = query.get("name", [""])[0].strip()
        link = query.get("link", [""])[0].strip()
        icon = query.get("icon", [""])[0].strip()

        if not name or not link:
            BulletinHelper.show_error(strings.repo_add_invalid)
            return

        repos = repoManager.getRepositories()
        if len(repos) >= 10:
            BulletinHelper.show_error(strings.repo_add_limit)
            return

        try:
            frag = get_last_fragment()
            container = frag.getParentActivity().getWindow().getDecorView()
            resourceProvider = frag.getResourceProvider()
            BulletinFactory.of(container, resourceProvider).createSimpleBulletin(
                R_tg.raw.camera_flip,
                strings.repo_add_fetching
            ).show()
        except Exception as e:
            log(f"[PackIt] repo=add bulletin error: {e}")

        def fetch_task():
            repometa = None
            pluginCount = 0
            try:
                response = requests.get(link, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    repometa = data.get("repometa")
                    plugins = data.get("plugins", [])
                    if isinstance(plugins, dict):
                        pluginCount = len(plugins)
                    elif isinstance(plugins, list):
                        pluginCount = len(plugins)
            except Exception as e:
                log(f"[PackIt] repo=add fetch error: {e}")

            run_on_ui_thread(lambda: show_confirm_dialog(repometa, pluginCount))

        def show_confirm_dialog(repometa, pluginCount):
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return

                builder = AlertDialogBuilder(act)
                builder.set_title(strings.repo_add_title)

                if repometa:
                    rm_url = str(repometa.get("rm_url") or link)
                    rm_url = rm_url.removeprefix("https://").removeprefix("http://")
                    rm_maintainer = str(repometa.get("rm_maintainer") or name)
                    text = strings("repo_add_disclaimer", rm_url, rm_maintainer, pluginCount)
                else:
                    text = strings("repo_add_no_repometa", pluginCount)

                builder.set_message(LocaleUtils.fullyFormatText(text))

                def on_confirm(b, w):
                    try:
                        repoId = datetime.now().strftime("%Y.%m.%d %H:%M:%S.%f")
                        newRepo = {
                            "id": repoId,
                            "name": name,
                            "url": link,
                            "enabled": True,
                            "collapsed": False,
                            "icon": icon if icon else "msg_folders"
                        }
                        currentRepos = repoManager.getRepositories()
                        currentRepos.append(newRepo)
                        repoManager.setRepositories(currentRepos)
                        BulletinHelper.show_success(strings.repo_add_success)
                    except Exception as e:
                        log(f"[PackIt] repo=add confirm error: {e}")

                builder.set_positive_button(strings.repo_add_button, on_confirm)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                builder.show()
            except Exception as e:
                log(f"[PackIt] repo=add dialog error: {e}")

        run_on_queue(fetch_task)
    except Exception as e:
        log(f"[PackIt] repo=add error: {e}")

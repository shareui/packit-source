from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment, run_on_queue
from android_utils import log, run_on_ui_thread
from elyx import strings
from hook_utils import find_class
from org.telegram.messenger import R as R_tg, ApplicationLoader
from com.exteragram.messenger.utils.text import LocaleUtils  # noqa
from urllib.parse import urlparse, parse_qs
import requests
import json
import os

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


def _get_cache_dir() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache"


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

                    # Save to cache if repometa has rm_rid
                    if repometa and repometa.get("rm_rid"):
                        try:
                            cache_dir = _get_cache_dir()
                            os.makedirs(cache_dir, exist_ok=True)
                            cache_path = os.path.join(cache_dir, f"{repometa['rm_rid']}.json")
                            with open(cache_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            log(f"[PackIt] repo=add cache error: {e}")

                    # Get plugin count via repomap.plugins URL if available
                    repomap = data.get("repomap", {})
                    plugins_url = repomap.get("plugins") if repomap else None
                    if plugins_url:
                        try:
                            pr = requests.get(plugins_url, timeout=10)
                            if pr.status_code == 200:
                                pdata = pr.json()
                                plugins = pdata.get("plugins", [])
                                pluginCount = len(plugins) if isinstance(plugins, (list, dict)) else 0
                        except Exception as e:
                            log(f"[PackIt] repo=add plugins count error: {e}")
                    else:
                        plugins = data.get("plugins", [])
                        if isinstance(plugins, (list, dict)):
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

                if not repometa or not repometa.get("rm_rid"):
                    BulletinHelper.show_error("Repository has no metadata")
                    return

                builder = AlertDialogBuilder(act)
                builder.set_title(strings.repo_add_title)

                rm_url = str(repometa.get("rm_url") or link)
                rm_url = rm_url.removeprefix("https://").removeprefix("http://")
                rm_maintainer = str(repometa.get("rm_maintainer") or name)
                text = strings("repo_add_disclaimer", rm_url, rm_maintainer, pluginCount)

                builder.set_message(LocaleUtils.fullyFormatText(text))

                def on_confirm(b, w):
                    try:
                        if not repometa or not repometa.get("rm_rid"):
                            BulletinHelper.show_error("Repository has no metadata")
                            return

                        rm_rid = repometa.get("rm_rid")
                        repo_name = repometa.get("rm_name") or name

                        currentRepos = repoManager.getRepositories()
                        for existing in currentRepos:
                            if existing.get("id") == rm_rid or existing.get("url") == link:
                                BulletinHelper.show_error("Repository already added")
                                b.dismiss()
                                return

                        newRepo = {
                            "id": rm_rid,
                            "name": repo_name,
                            "url": link,
                            "enabled": True,
                            "collapsed": False,
                            "icon": icon if icon else "msg_folders"
                        }
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

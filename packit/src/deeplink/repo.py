from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log
from elyx import strings
from urllib.parse import urlparse, parse_qs
from datetime import datetime


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

        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        builder = AlertDialogBuilder(act)
        builder.set_title(strings.repo_add_title)
        builder.set_message(strings("repo_add_message", name, link))

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
                repos = repoManager.getRepositories()
                repos.append(newRepo)
                repoManager.setRepositories(repos)
                BulletinHelper.show_success(strings.repo_add_success)
            except Exception as e:
                log(f"[PackIt] repo=add confirm error: {e}")

        builder.set_positive_button(strings.repo_add_button, on_confirm)
        builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
        builder.show()
    except Exception as e:
        log(f"[PackIt] repo=add error: {e}")

from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from elyx import strings


def handle(url):
    if url == "tg://packit":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success(strings.everything_working, currentFragment)
        except Exception:
            pass

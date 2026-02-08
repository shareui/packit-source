from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log


def handle(url):
    if url == "tg://packit?settings":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success("Settings triggered", currentFragment)
        except Exception as e:
            log(f"[PackIt] Error: {e}")
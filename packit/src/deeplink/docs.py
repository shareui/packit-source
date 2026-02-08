from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log


def handle(url):
    if url == "tg://packit?docs":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success("Docs triggered", currentFragment)
        except Exception as e:
            log(f"[PackIt] Error: {e}")

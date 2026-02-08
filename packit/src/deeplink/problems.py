from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log

# должно открывать ссылку https://t.me/c/3663388991/13/350
def handle(url):
    if url == "tg://packit?problems":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success("Problems link triggered", currentFragment)
        except Exception as e:
            log(f"[PackIt] Error: {e}")
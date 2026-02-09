from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log
from urllib.parse import urlparse, parse_qs


def handle(url):
    try:
        currentFragment = get_last_fragment()
        
        if url == "tg://packit?update":
            BulletinHelper.show_success("Update all triggered", currentFragment)
        elif "update&repo=" in url:
            BulletinHelper.show_success("Update repo triggered", currentFragment)
    except Exception as e:
        log(f"[PackIt] Error: {e}")

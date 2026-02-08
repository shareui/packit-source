from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log
from urllib.parse import urlparse, parse_qs


def handle(url):
    try:
        currentFragment = get_last_fragment()
        
        if url == "tg://packit?repo":
            BulletinHelper.show_success("Repo list triggered", currentFragment)
        elif "repo=all" in url:
            BulletinHelper.show_success("All repos triggered", currentFragment)
        elif "repo=add" in url:
            BulletinHelper.show_success("Repo add triggered", currentFragment)
    except Exception as e:
        log(f"[PackIt] Error: {e}")

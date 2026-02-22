from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log
from urllib.parse import urlparse, parse_qs


def handle(url):
    try:
        currentFragment = get_last_fragment()
        parsed = urlparse(url)
        query = parse_qs(parsed.query) if parsed.query else {}
        
        if url == "tg://packit?install":
            BulletinHelper.show_success("Install menu triggered", currentFragment)
        elif "install&repo=" in url:
            plugin = query.get("plugin", [""])[0]
            mode = query.get("mode", [""])[0]
            
            if plugin and mode == "share":
                BulletinHelper.show_success("Install plugin share triggered", currentFragment)
            elif plugin:
                BulletinHelper.show_success("Install plugin triggered", currentFragment)
            else:
                BulletinHelper.show_success("Install repo triggered", currentFragment)
    except Exception as e:
        log(f"[PackIt] Error: {e}")

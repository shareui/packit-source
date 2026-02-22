from client_utils import get_last_fragment
from android.net import Uri
from org.telegram.messenger.browser import Browser


def handle(url):
    if url == "tg://packit?problems":
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                uri = Uri.parse("https://t.me/packitGround/13/350")
                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        except Exception:
            pass

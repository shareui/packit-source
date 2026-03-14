from android_utils import log
from client_utils import get_last_fragment
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser
except Exception:
    Browser = None

REPORT_URL = "https://t.me/c/packitGround/970"

def report_plugin(plugin_info: dict, activity):
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else activity
        if act and Browser:
            uri = Uri.parse(REPORT_URL)
            Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        else:
            from android.content import Intent
            from org.telegram.messenger import ApplicationLoader
            context = ApplicationLoader.applicationContext
            intent = Intent(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(REPORT_URL))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
    except Exception as e:
        log(f"Error in report_plugin: {e}")

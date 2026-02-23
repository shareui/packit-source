from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()


def handle(url):
    if url == "tg://packit":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success(strings.everything_working, currentFragment)
        except Exception:
            pass

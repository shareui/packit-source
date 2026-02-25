from android_utils import run_on_ui_thread, log
from client_utils import get_last_fragment
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from .localConfig import LocalConfig

BETA = True


def _show_beta_dialog():
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        def on_ok(b, w):
            LocalConfig.set("isBetaShow", True)
            b.dismiss()

        def on_cancel(b, w):
            LocalConfig.set("isBetaShow", True)
            b.dismiss()
            BulletinHelper.show_info(strings.beta_dialog_cancel)

        builder = AlertDialogBuilder(act)
        builder.set_title(strings.beta_dialog_title)
        builder.set_message(strings.beta_dialog_message)
        builder.set_positive_button(strings.beta_dialog_ok, on_ok)
        builder.set_negative_button(strings.cancel_button, on_cancel)
        builder.show()
    except Exception as e:
        log(f"isBeta._show_beta_dialog: error: {e}")


def _check_beta():
    try:
        if LocalConfig.get("isBetaShow", False):
            return
        run_on_ui_thread(_show_beta_dialog)
    except Exception as e:
        log(f"isBeta._check_beta: error: {e}")


def init():
    if not BETA:
        return
    run_on_ui_thread(_check_beta, 1000)

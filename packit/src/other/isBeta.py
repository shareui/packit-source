from android_utils import run_on_ui_thread, log
from client_utils import get_last_fragment
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
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
            BulletinHelper.show_info("Don't joke like that anymore :(")

        builder = AlertDialogBuilder(act)
        builder.set_title("Beta version")
        builder.set_message("This is a BETA version, not all functionality is ready yet. Also, the plugin doesn't have many plugins in the repository at the moment.")
        builder.set_positive_button("OK", on_ok)
        builder.set_negative_button("Cancel", on_cancel)
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

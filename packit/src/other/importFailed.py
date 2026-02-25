from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from ui.alert_dialog import AlertDialogBuilder
from elyx import strings

_alerted = False

def showImportFailedAlert():
    global _alerted
    if _alerted:
        return
    _alerted = True

    def show():
        fragment = get_last_fragment()
        if not fragment:
            return
        builder = AlertDialogBuilder(fragment.getParentActivity())
        builder.set_title("PackIt")
        builder.set_message(strings["import_failed"])
        builder.setPositiveButton("OK", None)
        builder.show()

    run_on_ui_thread(show)

from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from org.telegram.ui.ActionBar import AlertDialog
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
        builder = AlertDialog.Builder(fragment.getParentActivity())
        builder.setTitle("PackIt")
        builder.setMessage(strings["import_failed"])
        builder.setPositiveButton(strings["ok_button"], None)
        builder.show()

    run_on_ui_thread(show)

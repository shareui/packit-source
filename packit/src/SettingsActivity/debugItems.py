from android_utils import log
from client_utils import get_last_fragment
from java import dynamic_proxy
from android.content import DialogInterface


def _test_native_error():
    try:
        _ = 123 / 0
    except Exception as e:
        log(f"debugItems: test native error triggered: {e}")
        from ..nativeLoader import showNativeErrorSheet
        showNativeErrorSheet("libpackitdb.so", str(e))


def show_debug_menu():
    try:
        from org.telegram.ui.ActionBar import AlertDialog
        from java import jarray
        from java.lang import CharSequence as JCharSequence

        frag = get_last_fragment()
        if not frag:
            return
        act = frag.getParentActivity()
        if not act:
            return

        ITEMS = [
            ("Native error", _test_native_error),
        ]

        labels = jarray(JCharSequence)([item[0] for item in ITEMS])

        class _OnClick(dynamic_proxy(DialogInterface.OnClickListener)):
            def onClick(self, dialog, which):
                try:
                    ITEMS[which][1]()
                except Exception as e:
                    log(f"debugItems.on_click: {e}")

        builder = AlertDialog.Builder(act)
        builder.setTitle("Debug")
        builder.setItems(labels, _OnClick())
        builder.setNegativeButton("Cancel", None)
        builder.show()
    except Exception as e:
        log(f"debugItems.show_debug_menu: {e}")

from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import run_on_ui_thread, log

def show_restart_dialog(restart_type: str, fragment=None):
    def _show():
        try:
            log(f"restartDialog: _show called with restart_type={restart_type}")
            curr_frag = fragment or get_last_fragment()
            log(f"restartDialog: curr_frag={curr_frag}")
            if not curr_frag:
                log("restartDialog: curr_frag is None")
                return
            activity = curr_frag.getParentActivity()
            log(f"restartDialog: activity={activity}")
            if not activity:
                log("restartDialog: activity is None")
                return
            
            builder = AlertDialogBuilder(activity)
            builder.set_title("Restart required")
            
            if restart_type == "required":
                builder.set_message("This plugin requires a client restart after installation.")
            elif restart_type == "optional":
                builder.set_message("This plugin optionally requires a client restart after installation. Restart for the best experience.")
            else:
                return
                
            def on_ok(bld, which):
                bld.dismiss()
                from ..deeplinks import pkill
                pkill.handle("tg://packit?pkill")
                
            builder.set_positive_button("OK", on_ok)
            builder.set_negative_button("Cancel", lambda b, w: b.dismiss())
            builder.make_button_red(AlertDialogBuilder.BUTTON_NEGATIVE)
            builder.show()
            log("restartDialog: dialog successfully shown")
        except Exception as e:
            log(f"show_restart_dialog error: {e}")

    import threading
    threading.Timer(0.5, lambda: run_on_ui_thread(_show)).start()

from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, run_on_ui_thread
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment


class PackItDeeplinkHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin
        self.pending_intent = None
        self.pending_param = None
        self.is_processing = False

    def before_hooked_method(self, param):
        try:
            if len(param.args) < 7:
                return
            
            intent = param.args[0]
            if not intent or intent.getAction() != "android.intent.action.VIEW":
                return
            
            data = intent.getData()
            if not data:
                return

            url = str(data)
            if url.startswith("tg://packit"):
                text = url[11:]
                if not text:
                    text = "PackIt - Universal Plugin Manager"
                self.pending_intent = intent
                self.pending_param = param
                param.setResult(None)
                run_on_ui_thread(lambda: self.show_packit_notification(text))
                return
        except Exception as e:
            log(f"[PackIt] Error in deeplink hook: {e}")

    def show_packit_notification(self, text):
        try:
            current_fragment = get_last_fragment()
            BulletinHelper.show_success(text, current_fragment)
        except Exception as e:
            log(f"[PackIt] Error showing notification: {e}")
            try:
                fragment = get_last_fragment()
                activity = fragment.getParentActivity() if fragment else None
                if activity:
                    builder = AlertDialogBuilder(activity)
                    builder.set_title("PackIt")
                    builder.set_message(text)
                    builder.set_positive_button("OK", lambda b, w: self.proceed_deeplink())
                    builder.set_on_cancel_listener(lambda b: self.proceed_deeplink())
                    builder.show()
                else:
                    self.proceed_deeplink()
            except:
                self.proceed_deeplink()

    def proceed_deeplink(self):
        try:
            self.pending_intent = None
            self.pending_param = None
            self.is_processing = False
        except Exception as e:
            log(f"[PackIt] Error proceeding deeplink: {e}")
            self.is_processing = False

def setup_deeplink_hook(plugin):
    try:
        LaunchActivity = find_class("org.telegram.ui.LaunchActivity")
        if LaunchActivity:
            method = LaunchActivity.getClass().getDeclaredMethod(
                "handleIntent", 
                find_class("android.content.Intent").getClass(),
                find_class("java.lang.Boolean").TYPE,
                find_class("java.lang.Boolean").TYPE,
                find_class("java.lang.Boolean").TYPE,
                find_class("org.telegram.messenger.browser.Browser$Progress").getClass(),
                find_class("java.lang.Boolean").TYPE,
                find_class("java.lang.Boolean").TYPE
            )
            method.setAccessible(True)
            return plugin.hook_method(method, PackItDeeplinkHook(plugin))
    except Exception as e:
        log(f"[PackIt] Error setting up deeplink hook: {e}")
    return None

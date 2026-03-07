from android_utils import log, run_on_ui_thread
from base_plugin import MethodHook
from hook_utils import find_class
from java import jclass, dynamic_proxy
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings failed: {e}")

_Runnable = jclass("java.lang.Runnable")
_String = jclass("java.lang.String")


class _OnClick(dynamic_proxy(_Runnable)):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def run(self):
        try:
            self._callback()
        except Exception as e:
            log(f"ChatDialogButton: OnClick.run error: {e}")


class ChatDialogButton:
    def setup_dialogs_menu_hook(self):
        try:
            ApplicationLoader = find_class("org.telegram.messenger.ApplicationLoader")
            if ApplicationLoader is None:
                log("ChatDialogButton: ApplicationLoader not found")
                return None

            target_method = None
            for m in ApplicationLoader.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "addItemOptions" and len(m.getParameterTypes()) == 1:
                        target_method = m
                        break
                except Exception:
                    continue

            if target_method is None:
                log("ChatDialogButton: addItemOptions method not found")
                return None

            target_method.setAccessible(True)

            plugin = self.plugin

            class AddItemOptionsHook(MethodHook):
                def after_hooked_method(self_hook, param):
                    try:
                        if not settings.get("show_dialogs_menu_button", False):
                            return

                        io = param.args[0]
                        if io is None:
                            return

                        R = find_class("org.telegram.messenger.R")
                        try:
                            icon_id = int(getattr(R.drawable, "msg_addbot"))
                        except Exception:
                            icon_id = 0

                        def on_click():
                            from ..ui.installUi.uiMain import InstallUI
                            run_on_ui_thread(lambda: InstallUI(plugin).open())

                        io.add(icon_id, _String(strings["install_plugin_btn"]), _OnClick(on_click))
                    except Exception as e:
                        log(f"ChatDialogButton: after_hooked_method error: {e}")

            hook_ref = self.plugin.hook_method(target_method, AddItemOptionsHook())
            log("ChatDialogButton: hook set up")
            return hook_ref

        except Exception as e:
            log(f"ChatDialogButton: setup_dialogs_menu_hook error: {e}")
            return None

    def on_dialogs_menu_switch(self, val):
        try:
            settings.set("show_dialogs_menu_button", bool(val))
        except Exception as e:
            log(f"ChatDialogButton: on_dialogs_menu_switch error: {e}")



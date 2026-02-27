from android_utils import run_on_ui_thread
from base_plugin import MenuItemData, MenuItemType
try:
    from elyx import settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()


class BtnPluginsMenu:
    def _update_chat_plugins_menu(self):
        try:
            show_chat_plugins = settings.get("show_chat_plugins_menu", False)
            self.plugin.remove_menu_item('packit_chat_plugins')
            if show_chat_plugins:
                try:
                    menu_type = MenuItemType.CHAT_ACTION_MENU
                except Exception:
                    menu_type = None
                if menu_type:
                    self.plugin.add_menu_item(MenuItemData(
                        menu_type=menu_type,
                        text=self.get_text('packit'),
                        icon='msg_plugins',
                        item_id='packit_chat_plugins',
                        on_click=lambda ctx: self.open_packit_settings()
                    ))
        except Exception:
            pass
    
    def on_chat_plugins_switch(self, val):
        try:
            settings.set("show_chat_plugins_menu", bool(val))
            run_on_ui_thread(self._update_chat_plugins_menu)
        except Exception:
            pass

# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android_utils import run_on_ui_thread
from base_plugin import MenuItemData, MenuItemType
try:
    from elyx import settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()

_SETTINGS_LINK = "https://t.me/exteraSettings?s=mainMenuSettings"


def _open_packit_settings(plugin):
    try:
        from android_utils import run_on_ui_thread as _rout
        from client_utils import get_last_fragment
        from com.exteragram.messenger.plugins import PluginsController
        from com.exteragram.messenger.plugins.ui import PluginSettingsActivity
        def _open():
            try:
                frag = get_last_fragment()
                plugin_obj = PluginsController.getInstance().plugins.get(plugin.id)
                if plugin_obj and frag:
                    frag.presentFragment(PluginSettingsActivity(plugin_obj))
            except Exception as e:
                import android_utils as _au; _au.log(f"BtnPluginsMenu: open settings error: {e}")
        _rout(_open)
    except Exception as e:
        import android_utils as _au; _au.log(f"BtnPluginsMenu: _open_packit_settings error: {e}")


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
                        on_click=lambda ctx: _open_packit_settings(self.plugin)
                    ))
        except Exception:
            pass

    def on_chat_plugins_switch(self, val):
        try:
            settings.set("show_chat_plugins_menu", bool(val))
            run_on_ui_thread(self._update_chat_plugins_menu)
        except Exception:
            pass
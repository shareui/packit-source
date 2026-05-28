# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
try:
    from com.exteragram.messenger.plugins import PluginsController
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins import PluginsController failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.plugins.ui import PluginSettingsActivity
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins.ui import PluginSettingsActivity failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

from .btnCAB import BtnCAB
from .btnPluginsMenu import BtnPluginsMenu
from .chatDialogButton import ChatDialogButton


class ChatButton(BtnCAB, BtnPluginsMenu, ChatDialogButton):
    def __init__(self, plugin):
        self.plugin = plugin
        self.packit_menu_id = 880034
    
    def get_text(self, key):
        texts = {
            'packit': strings.packit,
            'packit_settings': strings.packit_settings
        }
        return texts.get(key, key)
    
    def initialize_chat_menu(self):
        try:
            self._update_chat_menu()
            self._update_chat_plugins_menu()
        except Exception:
            pass
    
    def _get_private_field(self, obj, name):
        try:
            cls = obj.getClass()
        except Exception:
            return None
        while cls is not None:
            try:
                field = cls.getDeclaredField(name)
                field.setAccessible(True)
                return field.get(obj)
            except Exception:
                try:
                    cls = cls.getSuperclass()
                except Exception:
                    break
        return None
    
    def open_packit_settings(self):
        try:
            def _open_settings():
                try:
                    fragment = get_last_fragment()
                    plugin = PluginsController.getInstance().plugins.get(self.plugin.id)
                    if plugin:
                        fragment.presentFragment(PluginSettingsActivity(plugin))
                    else:
                        BulletinHelper.show_error(strings.plugin_not_found)
                except Exception as e:
                    BulletinHelper.show_error(strings.error_opening_settings.format(e))
            
            run_on_ui_thread(_open_settings)
        except Exception as e:
            BulletinHelper.show_error(strings.error_generic.format(e))
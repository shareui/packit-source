from client_utils import get_last_fragment
from android_utils import run_on_ui_thread
from com.exteragram.messenger.plugins import PluginsController
from com.exteragram.messenger.plugins.ui import PluginSettingsActivity


def handle(url, plugin):
    if url == "tg://packit?settings":
        try:
            def openSettings():
                try:
                    fragment = get_last_fragment()
                    pluginObj = PluginsController.getInstance().plugins.get(plugin.id)
                    if pluginObj and fragment:
                        fragment.presentFragment(PluginSettingsActivity(pluginObj))
                except Exception:
                    pass
            
            run_on_ui_thread(openSettings)
        except Exception:
            pass

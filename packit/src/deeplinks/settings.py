from client_utils import get_last_fragment
from android_utils import run_on_ui_thread
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

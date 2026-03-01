from android_utils import log
from client_utils import get_last_fragment
from hook_utils import find_class
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, R as R_tg failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.widget import Toast


BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")

def report_plugin(plugin_info: dict, activity):
    try:
        plugin_name = plugin_info.get("name") or plugin_info.get("id") or "Unknown"
        fragment = get_last_fragment()
        if fragment and activity:
            container = activity.getWindow().getDecorView()
            resource_provider = fragment.getResourceProvider()
            try:
                BulletinFactory.of(container, resource_provider).createSimpleBulletin(
                    R_tg.raw.info, 
                    f"Report for {plugin_name} will be implemented later"
                ).show()
            except Exception:
                try:
                    toast = Toast.makeText(activity, f"Report feature coming soon for {plugin_name}", Toast.LENGTH_SHORT)
                    toast.show()
                except Exception:
                    log(f"Could not show report notification for {plugin_name}")
        
        log(f"Report requested for plugin: {plugin_name}")
        
    except Exception as e:
        log(f"Error in report_plugin: {e}")
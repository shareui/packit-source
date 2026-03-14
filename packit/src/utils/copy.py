from android_utils import log
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, R as R_tg failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from client_utils import get_last_fragment
from hook_utils import find_class
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


def copy_share_link(plugin_info: dict, repo_title: str):
    try:
        plugin_id = plugin_info.get("id")
        fragment = get_last_fragment()
        if not fragment:
            return
        container = fragment.getParentActivity().getWindow().getDecorView()
        resource_provider = fragment.getResourceProvider()
        if not plugin_id:
            BulletinFactory.of(container, resource_provider).createErrorBulletin(strings["plugin_no_id"]).show()
            return
        share_link = f"tg://packit?install&repo={repo_title}&plugin={plugin_id}"
        AndroidUtilities.addToClipboard(share_link)
        plugin_name = plugin_info.get("name") or plugin_info.get("id") or "Unknown"
        BulletinFactory.of(container, resource_provider).createSimpleBulletin(R_tg.raw.voip_invite, strings("plugin_link_copied", plugin_name)).show()
    except Exception as e:
        log(f"copy: failed to copy link: {e}")
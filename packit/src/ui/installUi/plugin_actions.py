from android_utils import log
from client_utils import get_last_fragment
from hook_utils import find_class
from .report import report_plugin
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, R as R_tg failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser
except Exception:
    Browser = None

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


def copy_plugin_link(plugin_info: dict, repo_title: str, sound_path: str = None):
    try:
        if sound_path:
            from ...other.media import playSound
            playSound(sound_path)
    except Exception:
        pass
    
    try:
        plugin_id = plugin_info.get("id")
        fragment = get_last_fragment()
        if not fragment:
            return
        container = fragment.getParentActivity().getWindow().getDecorView()
        resource_provider = fragment.getResourceProvider()
        if not plugin_id:
            BulletinFactory.of(container, resource_provider).createErrorBulletin("Plugin has no id").show()
            return
        share_link = f"tg://packit?install&repo={repo_title}&plugin={plugin_id}"
        AndroidUtilities.addToClipboard(share_link)
        plugin_name = plugin_info.get("name") or plugin_info.get("id") or "Unknown"
        BulletinFactory.of(container, resource_provider).createSimpleBulletin(R_tg.raw.voip_invite, strings("plugin_link_copied", plugin_name)).show()
    except Exception as e:
        log(f"copy: failed to copy link: {e}")


def share_plugin_file(plugin_info: dict, display_name: str, activity):
    try:
        from ...other.share import share_plugin_file as _share_plugin_file
        _share_plugin_file(plugin_info, display_name, activity)
    except Exception as e:
        log(f"Error sharing plugin: {e}")


def _convert_raw_github_url(url: str) -> str:
    """Convert raw.githubusercontent.com URL to github.com for browser viewing."""
    try:
        import re
        m = re.match(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.*)', url)
        if m:
            owner, repo, branch, path = m.group(1), m.group(2), m.group(3), m.group(4)
            return f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    except Exception:
        pass
    return url


def view_plugin_code(plugin_info: dict, activity):
    try:
        plugin_url = plugin_info.get("link") or plugin_info.get("raw")
        if not plugin_url:
            BulletinFactory.of(activity.getWindow().getDecorView(), None).createErrorBulletin("Plugin has no link").show()
            return

        plugin_url = _convert_raw_github_url(plugin_url)

        if activity and Browser:
            uri = Uri.parse(plugin_url)
            Browser.openUrl(activity, uri, True, True, True, None, None, False, False, False)
            log(f"Opening plugin URL: {plugin_url}")
        else:
            try:
                from android.content import Intent
                from org.telegram.messenger import ApplicationLoader
                context = ApplicationLoader.applicationContext
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse(plugin_url))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                log(f"Opening plugin URL via Intent: {plugin_url}")
            except Exception as e:
                log(f"Failed to open URL via Intent: {e}")
                BulletinFactory.of(activity.getWindow().getDecorView(), None).createErrorBulletin("Failed to open URL").show()
                
    except Exception as e:
        log(f"Error opening plugin URL: {e}")
        try:
            BulletinFactory.of(activity.getWindow().getDecorView(), None).createErrorBulletin("Failed to open plugin URL").show()
        except Exception:
            pass
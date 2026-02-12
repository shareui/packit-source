from android_utils import log
from ui.bulletin import BulletinHelper
from org.telegram.messenger import AndroidUtilities


def copy_share_link(plugin_info: dict, repo_title: str):
    try:
        plugin_id = plugin_info.get("id")
        if not plugin_id:
            BulletinHelper.show_error("Plugin has no id")
            return
        share_link = f"tg://packit?install={repo_title}&{plugin_id}"
        AndroidUtilities.addToClipboard(share_link)
        try:
            BulletinHelper.show_copied_to_clipboard()
        except Exception:
            BulletinHelper.show_info("Copied")
    except Exception as e:
        log(f"copy: failed to copy link: {e}")
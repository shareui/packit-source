import os
import tempfile
import requests
from android_utils import log
from ui.bulletin import BulletinHelper
from android.content import Intent
from android.net import Uri
from java.io import File
from android.os import Build
from androidx.core.content import FileProvider


def share_plugin_file(plugin_info: dict, display_name: str, activity):
    try:
        plugin_id = plugin_info.get("id")
        if not plugin_id:
            BulletinHelper.show_error("Plugin has no id")
            return
        link = plugin_info.get("link") or plugin_info.get("raw")
        if not link:
            BulletinHelper.show_error("Plugin has no download link")
            return
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"{plugin_id}.plugin")
        try:
            r = requests.get(link, timeout=30)
            if r.status_code != 200:
                BulletinHelper.show_error("Failed to download plugin for sharing")
                return
            with open(temp_path, "wb") as f:
                f.write(r.content)
            file_obj = File(temp_path)
            if activity:
                if Build.VERSION.SDK_INT >= 24:
                    try:
                        uri = FileProvider.getUriForFile(
                            activity, activity.getPackageName() + ".fileprovider", file_obj
                        )
                        activity.grantUriPermission("", uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    except Exception:
                        try:
                            uri = Uri.parse(
                                "content://" + activity.getPackageName()
                                + ".fileprovider/" + file_obj.getName()
                            )
                        except Exception:
                            uri = Uri.fromFile(file_obj)
                else:
                    uri = Uri.fromFile(file_obj)
                intent = Intent(Intent.ACTION_SEND)
                intent.setType("application/octet-stream")
                intent.putExtra(Intent.EXTRA_STREAM, uri)
                intent.putExtra(Intent.EXTRA_SUBJECT, f"{display_name} Plugin")
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                chooser = Intent.createChooser(intent, "Share Plugin")
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                activity.startActivity(chooser)
                BulletinHelper.show_info("Plugin shared successfully")
        except Exception as e:
            log(f"share: failed to prepare file for sharing: {e}")
            BulletinHelper.show_error("Failed to prepare file for sharing")
    except Exception as e:
        log(f"share: failed to open share: {e}")
        BulletinHelper.show_error("Failed to share")
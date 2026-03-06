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


def download_plugin_file(plugin_info: dict):
    try:
        from elyx import settings
        import requests as _req
        from android_utils import run_on_ui_thread as _run
        from client_utils import get_last_fragment as _get_frag
        from ui.alert import AlertDialogBuilder
        import threading
        import os

        plugin_id = plugin_info.get("id")
        link = plugin_info.get("link") or plugin_info.get("raw")
        if not plugin_id or not link:
            fragment = _get_frag()
            if fragment:
                BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                BulletinFactory.of(fragment.getParentActivity().getWindow().getDecorView(), fragment.getResourceProvider()).createErrorBulletin("Plugin has no download link").show()
            return

        dest_dir = settings.get("download_path", "/storage/emulated/0/Download")
        url_filename = link.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        _, url_ext = os.path.splitext(url_filename)
        if url_ext.lower() == ".py":
            filename = f"{plugin_id}.plugin"
        elif url_ext:
            filename = f"{plugin_id}{url_ext}"
        else:
            filename = f"{plugin_id}.plugin"
        dest_path = os.path.join(str(dest_dir), filename)

        fragment = _get_frag()
        if not fragment:
            return
        ctx = fragment.getContext()
        builder = AlertDialogBuilder(ctx, AlertDialogBuilder.ALERT_TYPE_LOADING)
        builder.set_title("Downloading...")
        builder.set_cancelable(False)
        dlg = builder.show()
        dlg.set_progress(0)

        def _set_progress(value):
            def action():
                try:
                    dlg.set_progress(value)
                except Exception:
                    pass
            _run(action)

        def _dismiss():
            def action():
                try:
                    real = dlg.get_dialog() if hasattr(dlg, "get_dialog") else dlg
                    if real and real.isShowing():
                        real.dismiss()
                except Exception:
                    pass
            _run(action)

        def _do_download():
            try:
                r = _req.get(link, stream=True, timeout=30)
                if r.status_code != 200:
                    _dismiss()
                    _run(lambda: _show_download_error("Server returned " + str(r.status_code)))
                    return
                os.makedirs(str(dest_dir), exist_ok=True)
                content_length = r.headers.get("content-length")
                total = int(content_length) if content_length else 0
                downloaded = 0
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            _set_progress(min(99, int(downloaded * 100 / total)))
                _set_progress(100)
                _dismiss()
                _run(lambda: _show_download_ok(dest_path))
            except Exception as e:
                log(f"download: failed: {e}")
                _dismiss()
                _run(lambda: _show_download_error(str(e)))

        def _show_download_ok(path):
            try:
                fragment = get_last_fragment()
                if not fragment:
                    return
                container = fragment.getParentActivity().getWindow().getDecorView()
                rp = fragment.getResourceProvider()
                BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                folder = str(dest_dir).rstrip("/").rsplit("/", 1)[-1]
                BulletinFactory.of(container, rp).createSimpleBulletin(
                    find_class("org.telegram.messenger.R").raw.ic_download,
                    f"Saved in .../{folder}."
                ).show()
            except Exception as e:
                log(f"download: show ok error: {e}")

        def _show_download_error(msg):
            try:
                fragment = get_last_fragment()
                if not fragment:
                    return
                container = fragment.getParentActivity().getWindow().getDecorView()
                rp = fragment.getResourceProvider()
                BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                BulletinFactory.of(container, rp).createErrorBulletin(f"Download failed: {msg}").show()
            except Exception as e:
                log(f"download: show error error: {e}")

        threading.Thread(target=_do_download, daemon=True).start()
    except Exception as e:
        log(f"download: outer error: {e}")


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
# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from .Bulletins import factory as _pbf
import os
import requests
import threading

from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from java.io import File, FileOutputStream

try:
    from elyx import strings as _share_strings
except Exception:
    _share_strings = None


def _ss(key):
    try:
        return str(_share_strings[key])
    except Exception:
        return key


def share_plugin_file(plugin_info: dict, display_name: str, activity):
    threading.Thread(target=_do_share, args=(plugin_info, display_name), daemon=True).start()


def _do_share(plugin_info: dict, display_name: str):
    try:
        from android_utils import run_on_ui_thread
        from java import jclass, dynamic_proxy
        from ui.alert import AlertDialogBuilder

        plugin_id = plugin_info.get("id")
        if not plugin_id:
            run_on_ui_thread(lambda: BulletinHelper.show_error(_ss("share_plugin_no_id")))
            return
        link = plugin_info.get("link") or plugin_info.get("raw")
        if not link:
            run_on_ui_thread(lambda: BulletinHelper.show_error(_ss("share_plugin_no_link")))
            return

        fragment = get_last_fragment()
        act = fragment.getParentActivity() if fragment else None

        dlg_ref = [None]

        def show_spinner():
            try:
                if not act:
                    return
                loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
                loading.set_cancelable(False)
                dlg_ref[0] = loading.create()
                dlg_ref[0].show()
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"share: show_spinner error: {e}", False)

        def dismiss_spinner():
            try:
                if dlg_ref[0]:
                    dlg_ref[0].dismiss()
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"share: dismiss_spinner error: {e}", False)

        run_on_ui_thread(show_spinner)

        url_filename = link.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        _, url_ext = os.path.splitext(url_filename)
        filename = f"{plugin_id}{url_ext}" if url_ext else f"{plugin_id}.plugin"

        # stage in EXTERNAL app cache — Telegram's isInternalUri() refuses to
        # send files from internal storage (getCacheDir -> /data/user/0/...),
        # which surfaced as "attachment not supported" or a silent no-op
        from .Paths import getShareCachePath
        file_path = getShareCachePath(filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        logx(f"share: downloading {link} -> {file_path}", True)

        r = requests.get(link, timeout=30)
        if r.status_code != 200:
            run_on_ui_thread(dismiss_spinner)
            run_on_ui_thread(lambda: BulletinHelper.show_error(_ss("share_failed")))
            return
        temp_file = File(file_path)
        if temp_file.exists():
            temp_file.delete()
        fos = FileOutputStream(temp_file)
        fos.write(r.content)
        fos.close()
        logx(f"share: written {temp_file.length()} bytes", True)

        def open_share():
            try:
                dismiss_spinner()
                from hook_utils import find_class
                ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                frag = get_last_fragment()
                if not frag:
                    return

                ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")

                _frag = frag

                class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                    def __init__(self):
                        super().__init__()

                    def didShare(self):
                        # didShare is called before dismiss() - post to UI thread so bulletin shows after dialog closes
                        def _show_bulletin():
                            try:
                                from hook_utils import find_class as _fc
                                from org.telegram.messenger import R as R_tg
                                BulletinFactory = _fc("org.telegram.ui.Components.BulletinFactory")
                                from elyx import strings as _strings
                                container = _frag.getParentActivity().getWindow().getDecorView()
                                rp = _frag.getResourceProvider()
                                _pbf(container, rp).createSimpleBulletin(R_tg.raw.voip_invite, _strings["plugin_install_success"]).show()
                            except Exception as _cython_exc__be:
                                _be = _cython_exc__be
                                logx(f"share.ShareDelegate.didShare: {_be}", True)
                        from android_utils import run_on_ui_thread as _run_ui
                        _run_ui(_show_bulletin)

                    def didCopy(self):
                        return False

                share_alert = ShareAlert(
                    frag.getParentActivity(),
                    None, None,
                    temp_file.getAbsolutePath(),
                    None, None,
                    False, None, None,
                    False, False, False,
                    None, None
                )
                share_alert.setDelegate(ShareDelegate())
                frag.showDialog(share_alert)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"share: open_share error: {e}", False)
                BulletinHelper.show_error(_ss("share_failed"))

        run_on_ui_thread(open_share)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"share: _do_share error: {e}", False)
        from android_utils import run_on_ui_thread
        run_on_ui_thread(lambda: BulletinHelper.show_error(_ss("share_failed")))
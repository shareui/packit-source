# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from ui.settings import Divider, Header, Switch, Text
from elyx import strings
from packutil import logx


def _onWriteLogsChange(enabled):
    try:
        from client_utils import get_last_fragment
        from hook_utils import find_class
        from ui.bulletin import BulletinHelper
        import signal
        frag = get_last_fragment()
        R_tg = find_class("org.telegram.messenger.R")
        BulletinHelper.show_with_button(
            str(strings.bulletin_hook_restart_required),
            int(R_tg.raw.chats_infotip),
            str(strings.bulletin_restart_button),
            lambda *_: os.kill(os.getpid(), signal.SIGKILL),
            frag
        )
    except Exception as e:
        logx(f"write_logs: bulletin error: {e}", False)


def _sendLatestLog(view):
    try:
        from ...utils.paths import getCacheRoot, getLogShareCachePath
        log_path = getCacheRoot() + "/latestlog.txt"
        logx(f"sendLatestLog: log_path={log_path}", True)
        if not os.path.exists(log_path):
            logx("sendLatestLog: log file not found", False)
            return
        logx(f"sendLatestLog: log_path size={os.path.getsize(log_path)}", True)
        from java.io import File, FileOutputStream
        share_path = getLogShareCachePath()
        logx(f"sendLatestLog: share_path={share_path}", True)
        with open(log_path, "rb") as f:
            data = f.read()
        logx(f"sendLatestLog: read {len(data)} bytes", True)
        tmp_file = File(share_path)
        if tmp_file.exists():
            tmp_file.delete()
        fos = FileOutputStream(tmp_file)
        fos.write(data)
        fos.close()
        logx(f"sendLatestLog: written to cache, exists={tmp_file.exists()}, size={tmp_file.length()}", True)
        from client_utils import get_last_fragment
        from hook_utils import find_class
        from java import jclass, dynamic_proxy
        from android_utils import run_on_ui_thread

        def open_share():
            try:
                logx("sendLatestLog: open_share start", True)
                ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                logx(f"sendLatestLog: ShareAlert class={ShareAlert}", True)
                fragment = get_last_fragment()
                logx(f"sendLatestLog: fragment={fragment}", True)
                if not fragment:
                    logx("sendLatestLog: no fragment", False)
                    return
                ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")

                class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                    def __init__(self):
                        super().__init__()

                    def didShare(self):
                        pass

                    def didCopy(self):
                        return False

                logx(f"sendLatestLog: creating ShareAlert with path={share_path}", True)
                share_alert = ShareAlert(
                    fragment.getParentActivity(),
                    None, None,
                    share_path,
                    None, None,
                    False, None, None,
                    False, False, False,
                    None, None
                )
                share_alert.setDelegate(ShareDelegate())
                logx("sendLatestLog: showDialog", True)
                fragment.showDialog(share_alert)
            except Exception as e:
                logx(f"sendLatestLog: open_share error: {e}", False)

        run_on_ui_thread(open_share)
    except Exception as e:
        logx(f"sendLatestLog: error: {e}", False)


def _copyLatestLogPath(view):
    try:
        from org.telegram.messenger import AndroidUtilities
        logPath = _getLatestLogPath()
        if logPath and os.path.exists(logPath):
            AndroidUtilities.addToClipboard(logPath)
            from ui.bulletin import BulletinHelper
            BulletinHelper.show_success(str(strings.copy_latestlog_path_done))
    except Exception as e:
        logx(f"copyLatestLogPath: error: {e}", False)


def _getLatestLogPath():
    try:
        from ...utils.paths import getCacheRoot
        return getCacheRoot() + "/latestlog.txt"
    except Exception:
        return None


def _isWriteLogsEnabled():
    try:
        from elyx import settings as _s
        return bool(_s.get("write_logs", False))
    except Exception:
        return False


def _viewLatestLog(view):
    # opens latestlog.txt in exteraGram's native plugin file viewer.
    # PluginFileViewer.open() forces a ".plugin" suffix onto the title via
    # normalizeFileName; we replicate open() but call the private
    # createMessageObject(File, String) directly so the title stays
    # "latestlog.txt" without a suffix.
    try:
        import threading
        from client_utils import get_last_fragment
        from hook_utils import find_class
        from com.exteragram.messenger.plugins.ui.components import PluginFileViewer
        from java.io import File
        from android_utils import run_on_ui_thread
        logPath = _getLatestLogPath()
        if not logPath or not os.path.exists(logPath):
            return
        frag = get_last_fragment()
        if not frag:
            return
        f = File(logPath)
        if not f.exists() or not f.isFile():
            return
        inst = PluginFileViewer.INSTANCE
        if f.length() > 524288:
            # >512KB: let the host show its standard "file too large" bulletin
            # (open() returns without presenting anything, so no suffix leaks).
            inst.open(frag, f, "latestlog.txt")
            return
        PFVCls = find_class("com.exteragram.messenger.plugins.ui.components.PluginFileViewer")
        FileCls = find_class("java.io.File")
        StringCls = find_class("java.lang.String")
        create_mo = PFVCls.getClass().getDeclaredMethod("createMessageObject", FileCls, StringCls)
        create_mo.setAccessible(True)

        def _build_and_open():
            # read file / build MessageObject off the UI thread (as the host does),
            # then present the article viewer on the UI thread.
            try:
                # "Open in…" runs FileProvider on tL_page.local, and the
                # provider doesn't cover files/packit/ — serve a copy from
                # the host's sharing dir (cache/sharing/), which it does cover
                view_file = f
                try:
                    import shutil
                    from org.telegram.messenger import AndroidUtilities
                    sharing_dir = AndroidUtilities.getSharingDirectory()
                    sharing_dir.mkdirs()
                    share_file = File(sharing_dir, "latestlog.txt")
                    shutil.copyfile(logPath, share_file.getAbsolutePath())
                    view_file = share_file
                except Exception as e:
                    logx(f"viewLatestLog: sharing copy error: {e}", False)
                mo = create_mo.invoke(inst, view_file, "latestlog.txt")
                if mo is None:
                    return
                run_on_ui_thread(lambda: frag.createArticleViewer(False).open(mo))
            except Exception as e:
                logx(f"viewLatestLog: build/open error: {e}", False)

        threading.Thread(target=_build_and_open, daemon=True).start()
    except Exception as e:
        logx(f"viewLatestLog: error: {e}", False)


def _forceCleanLog(view):
    from ui.bulletin import BulletinHelper
    try:
        logPath = _getLatestLogPath()
        if logPath and os.path.exists(logPath):
            os.remove(logPath)
        BulletinHelper.show_success(str(strings.force_clean_log_done))
    except Exception as e:
        logx(f"forceCleanLog: error: {e}", False)
        BulletinHelper.show_error(str(strings.force_clean_log_error))


def build_debug_page():
    logPath = _getLatestLogPath()
    logExists = logPath is not None and os.path.exists(logPath)

    items = [
        Header(text=strings.debug_menu),
        Switch(
            key="debug_logs",
            text=strings.debug_logs,
            subtext=strings.debug_logs_desc,
            default=False,
            icon="msg_log",
            link_alias="debug_logs"
        ),
        Switch(
            key="write_logs",
            text=strings.write_logs,
            subtext=strings.write_logs_desc,
            default=False,
            icon="msg_edit",
            link_alias="write_logs",
            on_change=lambda enabled: _onWriteLogsChange(enabled)
        ),
    ]

    if logExists:
        # native log viewer only when the file exists AND file logging is on
        if _isWriteLogsEnabled():
            items.append(Text(
                text=strings.view_latestlog,
                icon="msg_view_file",
                on_click=_viewLatestLog
            ))
        items.append(Text(
            text=strings.send_latestlog,
            icon="msg_share",
            on_click=_sendLatestLog
        ))
        items.append(Text(
            text=strings.copy_latestlog_path,
            subtext=strings.copy_latestlog_path_desc,
            icon="msg_copy",
            on_click=_copyLatestLogPath
        ))

    items += [
        Divider(text=strings.debug_perf_warning),
        Header(text=strings.debug_clearing_header),
        Switch(
            key="clean_logs",
            text=strings.clean_logs,
            subtext=strings.clean_logs_desc,
            default=True,
            icon="msg_clear",
            link_alias="clean_logs"
        ),
        Text(
            text=strings.force_clean_log,
            subtext=strings.force_clean_log_desc,
            icon="msg_delete",
            red=True,
            on_click=_forceCleanLog
        ),
    ]

    return items

# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from ui.settings import Custom, Divider, Header, Switch, Text
from elyx import strings
from packutil import logx

# common su locations checked for the root-status card
_SU_PATHS = (
    "/system/bin/su", "/system/xbin/su", "/sbin/su", "/su/bin/su",
    "/system/sd/xbin/su", "/system/bin/failsafe/su",
    "/data/local/su", "/data/local/bin/su", "/data/local/xbin/su",
    "/system/app/Superuser.apk",
)


def _isDeviceRooted():
    try:
        for p in _SU_PATHS:
            if os.path.exists(p):
                return True
        try:
            from android.os import Build
            tags = str(Build.TAGS or "")
            if "test-keys" in tags:
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _makeBuildInfoCard(ctx):
    # material-you style info card: circle-icon header + grid of rounded
    # value tiles (big bold value under a small gray label)
    try:
        import ctypes
        from android.view import Gravity
        from android.widget import LinearLayout, TextView, FrameLayout, ImageView
        from android.util import TypedValue
        from android.graphics import PorterDuff
        from android.graphics.drawable import GradientDrawable
        from android.os import Build
        from hook_utils import find_class
        from org.telegram.messenger import AndroidUtilities, R as R_tg
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import LayoutHelper

        dp = AndroidUtilities.dp

        def _c(color):
            return ctypes.c_int32(color).value

        def _alpha(color, a):
            return _c((a << 24) | (color & 0x00FFFFFF))

        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        text_black = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        text_gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

        # ---- collect values (each guarded, "?" on failure)
        def _sget(fn, fallback="?"):
            try:
                v = fn()
                return str(v) if v is not None and str(v) else fallback
            except Exception:
                return fallback

        manufacturer = _sget(lambda: str(Build.MANUFACTURER))
        manufacturer = manufacturer[:1].upper() + manufacturer[1:] if manufacturer else "?"
        model = _sget(lambda: str(Build.MODEL))
        android_ver = _sget(lambda: str(Build.VERSION.RELEASE))
        sdk_ver = _sget(lambda: str(Build.VERSION.SDK_INT))
        abi = _sget(lambda: str(Build.SUPPORTED_ABIS[0]))
        abis_all = _sget(lambda: ", ".join([str(a) for a in Build.SUPPORTED_ABIS]), "")
        rooted = _isDeviceRooted()
        root_str = str(strings.bi_root_yes) if rooted else str(strings.bi_root_no)

        app_ver = "?"
        app_code = ""
        try:
            BuildVars = find_class("org.telegram.messenger.BuildVars")
            app_ver = str(BuildVars.BUILD_VERSION_STRING)
            app_code = str(BuildVars.BUILD_VERSION)
        except Exception:
            pass
        package = "?"
        try:
            from org.telegram.messenger import ApplicationLoader
            package = str(ApplicationLoader.applicationContext.getPackageName())
        except Exception:
            pass

        # ---- card scaffolding
        outer = LinearLayout(ctx)
        outer.setOrientation(LinearLayout.VERTICAL)
        outer.setPadding(dp(16), dp(16), dp(16), dp(16))
        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(float(dp(24)))
        card_bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        outer.setBackground(card_bg)

        header = LinearLayout(ctx)
        header.setOrientation(LinearLayout.HORIZONTAL)
        header.setGravity(Gravity.CENTER_VERTICAL)

        circle = FrameLayout(ctx)
        circle_bg = GradientDrawable()
        circle_bg.setShape(GradientDrawable.OVAL)
        circle_bg.setColor(_alpha(accent, 0x1C))
        circle.setBackground(circle_bg)
        circle_icon = ImageView(ctx)
        try:
            circle_icon.setImageResource(getattr(R_tg.drawable, "msg_info", 0))
            circle_icon.setColorFilter(_c(accent), PorterDuff.Mode.SRC_IN)
        except Exception:
            pass
        circle_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        circle.addView(circle_icon, FrameLayout.LayoutParams(dp(18), dp(18), Gravity.CENTER))
        header.addView(circle, LayoutHelper.createLinear(35, 35, Gravity.CENTER_VERTICAL, 0, 0, 14, 0))

        header_tv = TextView(ctx)
        header_tv.setText(str(strings.bi_header))
        header_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 21)
        try:
            header_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        header_tv.setTextColor(_c(text_black))
        header.addView(header_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        outer.addView(header, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))

        field_color = Theme.getColor(Theme.key_windowBackgroundGray)

        def value_tile(labelText, valueText, subText=None, value_size=21):
            tile = LinearLayout(ctx)
            tile.setOrientation(LinearLayout.VERTICAL)
            tile.setPadding(dp(14), dp(12), dp(14), dp(12))
            tile_bg = GradientDrawable()
            tile_bg.setShape(GradientDrawable.RECTANGLE)
            tile_bg.setCornerRadius(float(dp(18)))
            tile_bg.setColor(_c(field_color))
            tile.setBackground(tile_bg)

            lab = TextView(ctx)
            lab.setText(str(labelText))
            lab.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            lab.setTextColor(_c(text_gray))
            tile.addView(lab, LayoutHelper.createLinear(-2, -2))

            val = TextView(ctx)
            val.setText(str(valueText))
            val.setTextSize(TypedValue.COMPLEX_UNIT_DIP, value_size)
            try:
                val.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                pass
            val.setTextColor(_c(text_black))
            val.setSingleLine(True)
            val.setHorizontalFadingEdgeEnabled(True)
            val.setFadingEdgeLength(dp(24))
            tile.addView(val, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

            if subText:
                sub = TextView(ctx)
                sub.setText(str(subText))
                sub.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
                sub.setTextColor(_c(text_gray))
                sub.setSingleLine(True)
                sub.setHorizontalFadingEdgeEnabled(True)
                sub.setFadingEdgeLength(dp(24))
                tile.addView(sub, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))
            return tile

        def pair_row(left, right):
            row = LinearLayout(ctx)
            row.setOrientation(LinearLayout.HORIZONTAL)
            lp = LinearLayout.LayoutParams(0, -1, 1.0)
            lp.rightMargin = dp(4)
            row.addView(left, lp)
            rp = LinearLayout.LayoutParams(0, -1, 1.0)
            rp.leftMargin = dp(4)
            row.addView(right, rp)
            return row

        rows = [
            pair_row(
                value_tile(strings.bi_manufacturer, manufacturer),
                value_tile(strings.bi_model, model),
            ),
            pair_row(
                value_tile(strings.bi_android_version, android_ver),
                value_tile(strings.bi_sdk_version, sdk_ver),
            ),
            pair_row(
                value_tile(strings.bi_abi, abi, abis_all if abis_all != abi else None, value_size=17),
                value_tile(strings.bi_root_status, root_str),
            ),
        ]
        for i, row in enumerate(rows):
            outer.addView(row, LayoutHelper.createLinear(-1, -2, 0, 0 if i == 0 else 8, 0, 0))

        outer.addView(
            value_tile(strings.bi_app_version, app_ver, app_code or None),
            LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0),
        )
        outer.addView(
            value_tile(strings.bi_app_package, package, value_size=16),
            LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0),
        )

        try:
            from ...ui.ViewUtils import applyFontToTree
            applyFontToTree(outer)
        except Exception:
            pass

        # transparent list row carrying the floating card
        container = FrameLayout(ctx)
        container.setPadding(dp(12), dp(6), dp(12), dp(6))
        container.addView(outer, FrameLayout.LayoutParams(-1, -2))
        return container
    except Exception as e:
        logx(f"debug: _makeBuildInfoCard error: {e}", False)
        return None


def _buildInfoItem():
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        ctx = frag.getParentActivity() if frag else None
        if not ctx:
            return None
        view = _makeBuildInfoCard(ctx)
        if view is None:
            return None
        item = Custom(view=view)
        try:
            item.setTransparent(True)
        except Exception:
            pass
        return item
    except Exception as e:
        logx(f"debug: _buildInfoItem error: {e}", False)
        return None


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
        from ...utils.Paths import getCacheRoot, getLogShareCachePath
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
        from ...utils.Paths import getCacheRoot
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

    try:
        buildInfo = _buildInfoItem()
        if buildInfo is not None:
            items.append(Divider())
            items.append(buildInfo)
    except Exception as e:
        logx(f"debug: build info append error: {e}", False)

    return items

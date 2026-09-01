# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import threading
import requests
import traceback
from android_utils import run_on_ui_thread
from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, TextView
from java import dynamic_proxy
from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper, BackupImageView
from org.telegram.ui.Stories.recorder import ButtonWithCounterView
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"updateSheet: import Browser failed: {e}")
    Browser = None
try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"updateSheet: import strings failed: {e}")

INTERNAL_CFG_URL = "https://raw.githubusercontent.com/shareui/packit/main/configs/internal_cfg.json"
SHOWUPD = True


def _parse_version(ver: str) -> tuple:
    # strips everything except digits and dots, then splits by dot
    # "1.0.0-rel.1" -> "1.0.0.1" -> (1, 0, 0, 1)
    # "1.0.0"       -> (1, 0, 0)
    try:
        import re
        clean = re.sub(r"[^0-9.]", ".", ver)
        # collapse multiple consecutive dots
        clean = re.sub(r"\.{2,}", ".", clean).strip(".")
        parts = [int(x) for x in clean.split(".") if x]
        return tuple(parts)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"updateSheet: _parse_version error for '{ver}': {e}", False)
        return (0,)


def _is_newer(remote: str, current: str) -> bool:
    r = _parse_version(remote)
    c = _parse_version(current)
    logx(f"updateSheet: semver compare remote={r} current={c} is_newer={r > c}", True)
    return r > c


# FIXME
def _get_current_version() -> str:
#    try:
#        from elyx import assets
#        import yaml
#        raw = assets.meta.content_string()
#        logx(f"updateSheet: meta raw={raw[:120]}", True)
#        meta = yaml.safe_load(raw)
#        ver = str(meta.get("version", "0.0.0"))
#        logx(f"updateSheet: current version={ver}", True)
#        return ver
#    except Exception as e:
#        logx(f"updateSheet: _get_current_version error: {e}", False)
#        return "0.0.0"
    return "1.0.0" # latest

def _get_dismissed_ver() -> str:
    try:
        from ...utils.LocalConfig import LocalConfig
        v = LocalConfig.get("update_dismissed_ver", "")
        logx(f"updateSheet: dismissed_ver='{v}'", True)
        return v
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"updateSheet: _get_dismissed_ver error: {e}", False)
        return ""


def _save_dismissed_ver(ver: str):
    try:
        from ...utils.LocalConfig import LocalConfig
        LocalConfig.set("update_dismissed_ver", ver)
        logx(f"updateSheet: saved dismissed_ver='{ver}'", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"updateSheet: _save_dismissed_ver error: {e}", False)


def _show_update_sheet(new_ver: str, changelog: str, sticker: str, download_url: str):
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        logx(f"updateSheet: _show fragment={frag}", True)
        if not frag:
            logx("updateSheet: no fragment, aborting show", True)
            return
        activity = frag.getParentActivity()
        logx(f"updateSheet: activity={activity}", True)
        if not activity:
            logx("updateSheet: no activity, aborting show", True)
            return
        resource_provider = frag.getResourceProvider()

        sheet = BottomSheet(activity, False, resource_provider)
        sheet.fixNavigationBar()

        frame = FrameLayout(activity)
        linear = LinearLayout(activity)
        linear.setOrientation(LinearLayout.VERTICAL)
        frame.addView(linear)

        # title
        title_tv = TextView(activity)
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        title_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
        title_tv.setTextSize(1, 20.0)
        title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        title_tv.setText(strings["update_sheet_title"])
        linear.addView(title_tv, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 20.0, 24.0, 0.0))

        # sticker
        sticker_size_dp = 100
        iv = BackupImageView(activity)
        iv.setRoundRadius(AndroidUtilities.dp(16))
        try:
            iv.getImageReceiver().setCrossfadeWithOldImage(True)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"updateSheet: setCrossfadeWithOldImage error: {e}", False)
        from ...utils.Stickers import load_sticker
        load_sticker(iv, sticker, sticker_size_dp)
        linear.addView(iv, LayoutHelper.createLinear(
            sticker_size_dp, sticker_size_dp, Gravity.CENTER_HORIZONTAL, 0, 16, 0, 0
        ))

        # version label
        ver_tv = TextView(activity)
        ver_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        ver_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
        ver_tv.setTextSize(1, 17.0)
        ver_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        ver_tv.setText(strings.update_sheet_version.format(new_ver))
        linear.addView(ver_tv, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 10.0, 24.0, 0.0))

        # changelog with fullyFormatText
        if changelog:
            changelog_tv = TextView(activity)
            changelog_tv.setGravity(Gravity.CENTER_HORIZONTAL)
            changelog_tv.setTextSize(1, 14.0)
            changelog_tv.setTextColor(sheet.getThemedColor(Theme.key_dialogTextBlack))
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                changelog_tv.setText(LocaleUtils.fullyFormatText(changelog))
                changelog_tv.setLinkTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlueText))
                changelog_tv.setMovementMethod(LinkMovementMethod.getInstance())
                logx("updateSheet: changelog fullyFormatText ok", True)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"updateSheet: fullyFormatText failed, fallback plain text: {e}", False)
                changelog_tv.setText(changelog)
            linear.addView(changelog_tv, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 8.0, 24.0, 0.0))

        # Update button
        update_btn = ButtonWithCounterView(activity, True, resource_provider)
        update_btn.setRound()
        update_btn.setText(strings["update_sheet_update"], False)

        class _UpdateClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                try:
                    uri = Uri.parse(download_url)
                    act_ref = frag.getParentActivity()
                    logx(f"updateSheet: opening url='{download_url}' Browser={Browser} act={act_ref}", True)
                    if act_ref and Browser:
                        Browser.openUrl(act_ref, uri, True, True, True, None, None, False, False, False)
                except Exception:
                    logx(f"updateSheet: open url error: {traceback.format_exc()}", True)

        update_btn.setOnClickListener(_UpdateClick())
        linear.addView(update_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 16.0, 16.0, 8.0))

        # Later button
        later_btn = ButtonWithCounterView(activity, False, resource_provider)
        later_btn.setRound()
        later_btn.setNeutral()
        later_btn.setText(strings["update_sheet_later"], False)

        class _LaterClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                _save_dismissed_ver(new_ver)

        later_btn.setOnClickListener(_LaterClick())
        linear.addView(later_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 0.0, 16.0, 0.0))

        from android.widget import ScrollView
        scroll = ScrollView(activity)
        scroll.addView(frame)
        sheet.setCustomView(scroll)
        sheet.show()
        logx("updateSheet: sheet.show() called", True)
    except Exception:
        logx(f"updateSheet: _show_update_sheet error: {traceback.format_exc()}", True)


def check_and_show():
    def _task():
        try:
            if not SHOWUPD:
                logx("updateSheet: SHOWUPD=False, skipping", True)
                return
            logx(f"updateSheet: fetching {INTERNAL_CFG_URL}", True)
            r = requests.get(INTERNAL_CFG_URL, timeout=10)
            logx(f"updateSheet: fetch status={r.status_code}", True)
            if r.status_code != 200:
                logx(f"updateSheet: bad HTTP {r.status_code}", True)
                return
            data = r.json()
            logx(f"updateSheet: json keys={list(data.keys())}", True)
            latest_ver_arr = data.get("latest_ver")
            if not isinstance(latest_ver_arr, list) or len(latest_ver_arr) < 4:
                logx(f"updateSheet: invalid latest_ver={latest_ver_arr}", True)
                return

            new_ver = str(latest_ver_arr[0])
            changelog = str(latest_ver_arr[1])
            sticker = str(latest_ver_arr[2])
            download_url = str(latest_ver_arr[3])
            logx(f"updateSheet: remote ver='{new_ver}' sticker='{sticker}' url='{download_url}'", True)

            current_ver = _get_current_version()

            if not _is_newer(new_ver, current_ver):
                logx("updateSheet: already up to date", True)
                return

            dismissed = _get_dismissed_ver()
            if dismissed == new_ver:
                logx(f"updateSheet: '{new_ver}' already dismissed", True)
                return

            logx("updateSheet: scheduling sheet show on UI thread", True)
            run_on_ui_thread(lambda: _show_update_sheet(new_ver, changelog, sticker, download_url))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"updateSheet: task error: {e}\n{traceback.format_exc()}", False)

    threading.Thread(target=_task, daemon=True).start()

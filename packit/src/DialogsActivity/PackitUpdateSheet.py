import threading
import requests
import traceback
from android_utils import log, run_on_ui_thread
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
except Exception as e:
    import android_utils as _au; _au.log(f"updateSheet: import Browser failed: {e}")
    Browser = None
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"updateSheet: import strings failed: {e}")

INTERNAL_CFG_URL = "https://raw.githubusercontent.com/shareui/packit/main/configs/internal_cfg.json"
_STICKER_RETRY_DELAY = 2.0
SHOWUPD = False


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
    except Exception as e:
        log(f"updateSheet: _parse_version error for '{ver}': {e}")
        return (0,)


def _is_newer(remote: str, current: str) -> bool:
    r = _parse_version(remote)
    c = _parse_version(current)
    log(f"updateSheet: semver compare remote={r} current={c} is_newer={r > c}")
    return r > c


def _get_current_version() -> str:
    try:
        from elyx import assets
        import yaml
        raw = assets.meta.content_string()
        log(f"updateSheet: meta raw={raw[:120]}")
        meta = yaml.safe_load(raw)
        ver = str(meta.get("version", "0.0.0"))
        log(f"updateSheet: current version={ver}")
        return ver
    except Exception as e:
        log(f"updateSheet: _get_current_version error: {e}")
        return "0.0.0"


def _get_dismissed_ver() -> str:
    try:
        from ..utils.localConfig import LocalConfig
        v = LocalConfig.get("update_dismissed_ver", "")
        log(f"updateSheet: dismissed_ver='{v}'")
        return v
    except Exception as e:
        log(f"updateSheet: _get_dismissed_ver error: {e}")
        return ""


def _save_dismissed_ver(ver: str):
    try:
        from ..utils.localConfig import LocalConfig
        LocalConfig.set("update_dismissed_ver", ver)
        log(f"updateSheet: saved dismissed_ver='{ver}'")
    except Exception as e:
        log(f"updateSheet: _save_dismissed_ver error: {e}")


def _try_load_sticker(iv, icon_str: str, size_dp: int) -> bool:
    try:
        if "/" not in icon_str:
            log(f"updateSheet: sticker bad format '{icon_str}'")
            return False
        pack_name, index_str = icon_str.split("/", 1)
        sticker_index = int(index_str)
        log(f"updateSheet: trying sticker pack='{pack_name}' index={sticker_index}")
        mdc = MediaDataController.getInstance(0)
        ss = None
        try:
            ss = mdc.getStickerSetByName(pack_name)
            log(f"updateSheet: getStickerSetByName -> {ss}")
        except Exception as e:
            log(f"updateSheet: getStickerSetByName error: {e}")
        if not ss:
            try:
                ss = mdc.getStickerSetByEmojiOrName(pack_name)
                log(f"updateSheet: getStickerSetByEmojiOrName -> {ss}")
            except Exception as e:
                log(f"updateSheet: getStickerSetByEmojiOrName error: {e}")
        if not ss:
            log(f"updateSheet: sticker set '{pack_name}' not in cache, triggering load")
            try:
                mdc.loadStickersByEmojiOrName(pack_name, False, False)
            except Exception as e:
                log(f"updateSheet: loadStickersByEmojiOrName error: {e}")
            return False
        docs_count = ss.documents.size() if getattr(ss, "documents", None) else 0
        log(f"updateSheet: sticker set found, docs count={docs_count}")
        if docs_count <= sticker_index:
            log(f"updateSheet: index {sticker_index} out of range ({docs_count})")
            return False
        doc = ss.documents.get(sticker_index)
        log(f"updateSheet: got doc={doc}, calling setImage")
        iv.setImage(
            ImageLocation.getForDocument(doc),
            f"{size_dp}_{size_dp}",
            None, None, 0, 1
        )
        log("updateSheet: sticker loaded ok")
        return True
    except Exception as e:
        log(f"updateSheet: _try_load_sticker error: {e}")
        return False


def _schedule_sticker_retry(iv, icon_str: str, size_dp: int):
    def _retry():
        import time
        time.sleep(_STICKER_RETRY_DELAY)
        log(f"updateSheet: retry sticker load for '{icon_str}'")
        run_on_ui_thread(lambda: _try_load_sticker(iv, icon_str, size_dp))
    threading.Thread(target=_retry, daemon=True).start()


def _show_update_sheet(new_ver: str, changelog: str, sticker: str, download_url: str):
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        log(f"updateSheet: _show fragment={frag}")
        if not frag:
            log("updateSheet: no fragment, aborting show")
            return
        activity = frag.getParentActivity()
        log(f"updateSheet: activity={activity}")
        if not activity:
            log("updateSheet: no activity, aborting show")
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
        except Exception as e:
            log(f"updateSheet: setCrossfadeWithOldImage error: {e}")
        loaded = _try_load_sticker(iv, sticker, sticker_size_dp)
        if not loaded:
            _schedule_sticker_retry(iv, sticker, sticker_size_dp)
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
                log("updateSheet: changelog fullyFormatText ok")
            except Exception as e:
                log(f"updateSheet: fullyFormatText failed, fallback plain text: {e}")
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
                    log(f"updateSheet: opening url='{download_url}' Browser={Browser} act={act_ref}")
                    if act_ref and Browser:
                        Browser.openUrl(act_ref, uri, True, True, True, None, None, False, False, False)
                except Exception:
                    log(f"updateSheet: open url error: {traceback.format_exc()}")

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
        log("updateSheet: sheet.show() called")
    except Exception:
        log(f"updateSheet: _show_update_sheet error: {traceback.format_exc()}")


def check_and_show():
    def _task():
        try:
            if not SHOWUPD:
                log("updateSheet: SHOWUPD=False, skipping")
                return
            log(f"updateSheet: fetching {INTERNAL_CFG_URL}")
            r = requests.get(INTERNAL_CFG_URL, timeout=10)
            log(f"updateSheet: fetch status={r.status_code}")
            if r.status_code != 200:
                log(f"updateSheet: bad HTTP {r.status_code}")
                return
            data = r.json()
            log(f"updateSheet: json keys={list(data.keys())}")
            latest_ver_arr = data.get("latest_ver")
            if not isinstance(latest_ver_arr, list) or len(latest_ver_arr) < 4:
                log(f"updateSheet: invalid latest_ver={latest_ver_arr}")
                return

            new_ver = str(latest_ver_arr[0])
            changelog = str(latest_ver_arr[1])
            sticker = str(latest_ver_arr[2])
            download_url = str(latest_ver_arr[3])
            log(f"updateSheet: remote ver='{new_ver}' sticker='{sticker}' url='{download_url}'")

            current_ver = _get_current_version()

            if not _is_newer(new_ver, current_ver):
                log("updateSheet: already up to date")
                return

            dismissed = _get_dismissed_ver()
            if dismissed == new_ver:
                log(f"updateSheet: '{new_ver}' already dismissed")
                return

            log("updateSheet: scheduling sheet show on UI thread")
            run_on_ui_thread(lambda: _show_update_sheet(new_ver, changelog, sticker, download_url))
        except Exception as e:
            log(f"updateSheet: task error: {e}\n{traceback.format_exc()}")

    threading.Thread(target=_task, daemon=True).start()

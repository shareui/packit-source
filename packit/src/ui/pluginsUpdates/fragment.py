import json
import os
import threading

from android.view import Gravity, MotionEvent, View
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.widget import FrameLayout, LinearLayout, TextView, ProgressBar, ImageView
from java import dynamic_proxy
from android_utils import log, run_on_ui_thread
from client_utils import get_last_fragment, run_on_queue

try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"pluginsUpdates: import Theme failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    log(f"pluginsUpdates: import LayoutHelper failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities, ApplicationLoader
except Exception as e:
    log(f"pluginsUpdates: import AndroidUtilities/ApplicationLoader failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    log(f"pluginsUpdates: import UniversalFragment failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()

from android_utils import OnClickListener

import requests
try:
    from elyx import settings, strings
except Exception as e:
    log(f"pluginsUpdates: import elyx.settings failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()


def _get_index_path(pkg: str, rm_rid: str) -> str:
    from ...utils.paths import getRepoIndexPath
    return getRepoIndexPath(rm_rid)


def _get_repo_cache_path(pkg: str, rm_rid: str) -> str:
    from ...utils.paths import getRepoCachePath
    return getRepoCachePath(rm_rid)


def _get_repos() -> list:
    try:
        raw = settings.get("repositories", "[]")
        repos = json.loads(raw)
        return repos if isinstance(repos, list) else []
    except Exception as e:
        log(f"pluginsUpdates: _get_repos error: {e}")
        return []


def _read_index(pkg: str, rm_rid: str) -> list:
    # returns installed_plugins list from index file, empty if absent
    path = _get_index_path(pkg, rm_rid)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        plugins = data.get("installed_plugins")
        return plugins if isinstance(plugins, list) else []
    except Exception as e:
        log(f"pluginsUpdates: _read_index error for '{rm_rid}': {e}")
        return []


def _get_repo_plugins_url(pkg: str, rm_rid: str, fallback_url: str) -> str:
    # resolves plugins url from cached repomap, falls back to repo url
    cache_path = _get_repo_cache_path(pkg, rm_rid)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            resolved = cached.get("repomap", {}).get("plugins")
            if resolved:
                return resolved
        except Exception as e:
            log(f"pluginsUpdates: _get_repo_plugins_url error for '{rm_rid}': {e}")
    return fallback_url


def _fetch_repo_plugins(url: str) -> dict:
    # returns dict: plugin_id plugin_info
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
        if r.status_code != 200:
            log(f"pluginsUpdates: HTTP {r.status_code} for {url}")
            return {}
        config = r.json()
        raw = config.get("plugins", {})
        result = {}
        if isinstance(raw, dict):
            for pid, info in raw.items():
                if isinstance(info, dict):
                    result[pid] = info
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("id"):
                    result[item["id"]] = item
        return result
    except Exception as e:
        log(f"pluginsUpdates: _fetch_repo_plugins error for '{url}': {e}")
        return {}


def _version_tuple(v: str):
    # parse version string into comparable tuple of ints
    import re
    parts = re.findall(r"\d+", str(v or ""))
    return tuple(int(p) for p in parts) if parts else (0,)


def _check_updates(pkg: str) -> list:
    # returns list of dicts: {id, repo_id, local_version, repo_version, reason}
    # reason: "hash_diff_newer" "state_changed"
    repos = _get_repos()
    updates = []

    for repo in repos:
        rm_rid = str(repo.get("id") or "")
        repo_url = str(repo.get("url") or "").strip()
        repo_name = str(repo.get("name") or rm_rid)
        if not rm_rid or not repo_url:
            continue

        installed = _read_index(pkg, rm_rid)
        if not installed:
            continue

        plugins_url = _get_repo_plugins_url(pkg, rm_rid, repo_url)
        repo_plugins = _fetch_repo_plugins(plugins_url)
        if not repo_plugins:
            log(f"pluginsUpdates: no repo plugins for '{rm_rid}', skipping")
            continue

        for entry in installed:
            pid = str(entry.get("id") or "")
            if not pid:
                continue

            repo_info = repo_plugins.get(pid)
            if not repo_info:
                # plugin not found in repo, skip
                continue

            # skip update if the repo version requires an incompatible app version
            repo_app_ver = str(repo_info.get("app_version") or "")
            if repo_app_ver:
                try:
                    from ...utils.app_version import check_app_version
                    if not check_app_version(repo_app_ver):
                        continue
                except Exception as e:
                    log(f"pluginsUpdates: app_version check error for '{pid}': {e}")

            local_hash = str(entry.get("hash") or "")
            local_bithash = str(entry.get("bithash") or "")
            repo_hash = str(repo_info.get("hash") or "")
            repo_bithash = str(repo_info.get("bithash") or "")

            local_ver = _version_tuple(entry.get("version") or "")
            repo_ver = _version_tuple(repo_info.get("version") or "")

            # version check first: if repo is newer — update regardless of hash
            if repo_ver > local_ver:
                updates.append({
                    "id": pid,
                    "repo_id": rm_rid,
                    "repo_name": repo_name,
                    "plugin_name": str(repo_info.get("name") or pid),
                    "icon": str(repo_info.get("icon") or ""),
                    "local_version": str(entry.get("version") or ""),
                    "repo_version": str(repo_info.get("version") or ""),
                    "state": str(repo_info.get("state") or ""),
                    "reason": "hash_diff_newer",
                })
                continue

            # same or older version: compare hashes to detect silent updates or state changes
            hash_matches = True
            if local_hash and repo_hash:
                hash_matches = local_hash == repo_hash
            elif local_bithash and repo_bithash:
                hash_matches = local_bithash == repo_bithash

            if hash_matches:
                continue

            # hash differs at same/older version, check if state changed
            local_state = str(entry.get("state") or "")
            repo_state = str(repo_info.get("state") or "")
            if local_state != repo_state:
                updates.append({
                    "id": pid,
                    "repo_id": rm_rid,
                    "repo_name": repo_name,
                    "plugin_name": str(repo_info.get("name") or pid),
                    "icon": str(repo_info.get("icon") or ""),
                    "local_version": str(entry.get("version") or ""),
                    "repo_version": str(repo_info.get("version") or ""),
                    "state": str(repo_info.get("state") or ""),
                    "reason": "state_changed",
                })

    return updates


def _get_ignore_list(pkg: str, repo_id: str) -> list:
    # reads ignore_list array from {rm_rid}-index.json
    path = _get_index_path(pkg, repo_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        lst = data.get("ignore_list")
        return lst if isinstance(lst, list) else []
    except Exception as e:
        log(f"pluginsUpdates: _get_ignore_list error for '{repo_id}': {e}")
        return []


def _save_ignore_list(pkg: str, repo_id: str, lst: list):
    # writes ignore_list array back into {rm_rid}-index.json
    path = _get_index_path(pkg, repo_id)
    try:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["ignore_list"] = lst
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"pluginsUpdates: _save_ignore_list error for '{repo_id}': {e}")


def _is_ignored(pkg: str, pid: str, repo_id: str, repo_version: str) -> bool:
    # returns True if plugin should be hidden from updates list
    lst = _get_ignore_list(pkg, repo_id)
    for entry in lst:
        if entry.get("id") != pid:
            continue
        if "version" not in entry:
            # forever ignore
            return True
        # until-next: ignore while repo version <= recorded version
        recorded = entry.get("version", "")
        if _version_tuple(repo_version) <= _version_tuple(recorded):
            return True
    return False


def _ignore_until_next(pkg: str, pid: str, repo_id: str, repo_version: str):
    # records plugin+version so it's ignored until a newer version appears
    lst = _get_ignore_list(pkg, repo_id)
    lst = [e for e in lst if e.get("id") != pid]
    lst.append({"id": pid, "version": repo_version})
    _save_ignore_list(pkg, repo_id, lst)


def _ignore_forever(pkg: str, pid: str, repo_id: str):
    # records plugin without version so it's ignored permanently
    lst = _get_ignore_list(pkg, repo_id)
    lst = [e for e in lst if e.get("id") != pid]
    lst.append({"id": pid})
    _save_ignore_list(pkg, repo_id, lst)


def _filter_ignored(pkg: str, updates: list) -> list:
    result = []
    for item in updates:
        pid = item["id"]
        repo_id = item.get("repo_id", "")
        repo_version = item.get("repo_version", "")
        if not _is_ignored(pkg, pid, repo_id, repo_version):
            result.append(item)
    return result


class UpdatesFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):

    def __init__(self, plugin=None):
        super().__init__()
        self._plugin = plugin
        self._content_view = None
        self._alive = [True]
        self._spinner = None
        self._spinner_container = None
        self._active_listeners = []

    def onFragmentCreate(self, *_):
        pass

    def onFragmentDestroy(self, *_):
        self._alive[0] = False
        try:
            from ...core import remove_install_listener
            for fn in list(self._active_listeners):
                remove_install_listener(fn)
            self._active_listeners.clear()
        except Exception as e:
            log(f"pluginsUpdates: onFragmentDestroy listeners cleanup error: {e}")
        try:
            if self._content_view is not None:
                parent = self._content_view.getParent()
                if parent is not None:
                    parent.removeView(self._content_view)
                self._content_view = None
        except Exception as e:
            log(f"pluginsUpdates: onFragmentDestroy error: {e}")

    def onBackPressed(self):
        return False

    def afterCreateView(self, v):
        return None

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, mid):
        if mid == -1:
            try:
                frag = get_last_fragment()
                if frag:
                    frag.finishFragment()
            except Exception as e:
                log(f"pluginsUpdates: finishFragment error: {e}")
            return True
        return False

    def beforeCreateView(self):
        frag = get_last_fragment()
        if not frag:
            return None
        act = frag.getParentActivity()
        if not act:
            return None

        dp = AndroidUtilities.dp
        bg = Theme.getColor(Theme.key_windowBackgroundGray)
        text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        text_gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

        self._content_view = FrameLayout(act)
        self._content_view.setBackgroundColor(bg)

        self._results_container = LinearLayout(act)
        self._results_container.setOrientation(LinearLayout.VERTICAL)
        self._content_view.addView(
            self._results_container,
            FrameLayout.LayoutParams(-1, -1)
        )

        self._spinner_container = None
        try:
            from org.telegram.ui.Components import CircularProgressDrawable
            size = 122
            color = Theme.getColor(Theme.key_dialogLinkSelection)
            thickness = float(AndroidUtilities.dp(8))
            d = CircularProgressDrawable(float(size), thickness, color)
            d.setBounds(0, 0, size, size)
            spinner_view = ImageView(act)
            spinner_view.setImageDrawable(d)
            spinner_view.setScaleType(ImageView.ScaleType.FIT_CENTER)
            spinner_container = FrameLayout(act)
            spinner_lp = FrameLayout.LayoutParams(size, size)
            spinner_lp.gravity = Gravity.CENTER
            spinner_container.addView(spinner_view, spinner_lp)
            self._content_view.addView(spinner_container, FrameLayout.LayoutParams(-1, -1, Gravity.CENTER))
            self._spinner = spinner_view
            self._spinner_container = spinner_container
        except Exception as e:
            log(f"pluginsUpdates: spinner error: {e}")
            fallback = ProgressBar(act)
            fallback_lp = FrameLayout.LayoutParams(AndroidUtilities.dp(48), AndroidUtilities.dp(48))
            fallback_lp.gravity = Gravity.CENTER
            self._content_view.addView(fallback, fallback_lp)
            self._spinner = fallback
            self._spinner_container = fallback

        self._text_primary = text_primary
        self._text_gray = text_gray
        self._act = act

        self._start_load()
        return self._content_view

    def _start_load(self):
        alive = self._alive

        def task():
            try:
                # purge stale entries first
                try:
                    from ...utils.installIndex import purge_missing
                    purge_missing()
                except Exception as e:
                    log(f"pluginsUpdates: purge_missing error: {e}")

                # collect all index entries across all repos
                repos = _get_repos()
                total_installed = 0
                for repo in repos:
                    rm_rid = str(repo.get("id") or "")
                    if not rm_rid:
                        continue
                    total_installed += len(_read_index(None, rm_rid))

                if total_installed == 0:
                    run_on_ui_thread(lambda: self._show_empty("You have not installed any plugins from PackIt", "utyan_empty") if alive[0] else None)
                    return

                updates = _filter_ignored(None, _check_updates(None))

                def on_done():
                    if not alive[0]:
                        return
                    self._hide_spinner()
                    if not updates:
                        self._show_empty("All plugins of the current version", "done")
                    else:
                        self._show_updates(updates)

                run_on_ui_thread(on_done)
            except Exception as e:
                log(f"pluginsUpdates: task error: {e}")
                run_on_ui_thread(lambda: self._show_empty("Failed to check updates", "error") if alive[0] else None)

        run_on_queue(task)

    def _hide_spinner(self):
        try:
            if self._spinner_container is not None:
                self._spinner_container.setVisibility(4)  # GONE
        except Exception as e:
            log(f"pluginsUpdates: _hide_spinner error: {e}")

    def _show_empty(self, message: str, anim_name: str = "done"):
        try:
            self._hide_spinner()
            act = self._act
            dp = AndroidUtilities.dp

            card = LinearLayout(act)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setGravity(Gravity.CENTER)
            card.setPadding(dp(24), dp(28), dp(24), dp(28))
            try:
                bg = GradientDrawable()
                bg.setCornerRadius(dp(16))
                bg.setColor(Theme.getColor(Theme.key_windowBackgroundGray))
                card.setBackground(bg)
            except Exception:
                pass

            try:
                from org.telegram.ui.Components import RLottieImageView
                from org.telegram.messenger import R as R_tg
                lottie = RLottieImageView(act)
                lottie.setAnimation(getattr(R_tg.raw, anim_name), dp(144), dp(144))
                lottie.setAutoRepeat(False)
                lottie.playAnimation()
                lottie_lp = LinearLayout.LayoutParams(dp(144), dp(144))
                lottie_lp.gravity = Gravity.CENTER_HORIZONTAL
                lottie_lp.bottomMargin = dp(12)
                card.addView(lottie, lottie_lp)
            except Exception as e:
                log(f"pluginsUpdates: _show_empty lottie error: {e}")

            tv = TextView(act)
            tv.setText(message)
            tv.setTextColor(self._text_gray)
            tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            tv.setGravity(Gravity.CENTER)
            card.addView(tv, LinearLayout.LayoutParams(-2, -2))

            card_lp = FrameLayout.LayoutParams(-2, -2)
            card_lp.gravity = Gravity.CENTER
            card_lp.leftMargin = dp(16)
            card_lp.rightMargin = dp(16)
            card_lp.topMargin = dp(-80)
            self._content_view.addView(card, card_lp)
        except Exception as e:
            log(f"pluginsUpdates: _show_empty error: {e}")

    def _make_repo_chip(self, act, repo_name: str):
        import ctypes
        try:
            color = Theme.getColor(Theme.key_avatar_background2Blue)
        except Exception:
            color = 0xFF888888
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
        text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(6))
        bg.setColor(fill)
        tv = TextView(act)
        tv.setText(str(strings("from_repo_chip", repo_name=repo_name)))
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        tv.setTextColor(text_color)
        tv.setBackground(bg)
        tv.setPadding(
            AndroidUtilities.dp(7), AndroidUtilities.dp(2),
            AndroidUtilities.dp(7), AndroidUtilities.dp(2)
        )
        return tv

    def _make_state_chip(self, act, state: str):
        import ctypes
        _STATE_COLOR_KEYS = {
            "release": "key_color_green",
            "beta":    "key_color_orange",
            "alpha":   "key_color_red",
        }
        color_key = _STATE_COLOR_KEYS.get(state.lower(), "key_windowBackgroundWhiteGrayText")
        try:
            color = Theme.getColor(getattr(Theme, color_key))
        except Exception:
            color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
        text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(6))
        bg.setColor(fill)
        tv = TextView(act)
        tv.setText(state)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        tv.setTextColor(text_color)
        tv.setBackground(bg)
        tv.setPadding(
            AndroidUtilities.dp(7), AndroidUtilities.dp(3),
            AndroidUtilities.dp(7), AndroidUtilities.dp(3)
        )
        return tv

    def _make_update_card(self, act, item: dict):
        dp = AndroidUtilities.dp
        pid = item["id"]
        display_name = item.get("plugin_name") or pid
        icon_str = item.get("icon") or ""
        local_v = item["local_version"]
        repo_v = item["repo_version"]
        repo_name = item.get("repo_name") or item.get("repo_id") or ""
        icon_size_dp = 48

        outer = LinearLayout(act)
        outer.setOrientation(LinearLayout.VERTICAL)
        outer_lp = LinearLayout.LayoutParams(-1, -2)
        outer_lp.bottomMargin = dp(10)

        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(12))
        try:
            card_bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        except Exception:
            card_bg.setColor(0xFFFFFFFF)
        outer.setBackground(card_bg)
        outer.setPadding(dp(14), dp(12), dp(14), dp(12))

        top_row = LinearLayout(act)
        top_row.setOrientation(LinearLayout.HORIZONTAL)
        top_row.setGravity(Gravity.CENTER_VERTICAL)

        show_icon = bool(icon_str and icon_str != "Unknown" and "/" in icon_str)
        icon_view = None
        if show_icon:
            try:
                from org.telegram.ui.Components import BackupImageView
                from org.telegram.messenger import MediaDataController, ImageLocation
                icon_view = BackupImageView(act)
                icon_view.setRoundRadius(dp(12))
                try:
                    icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
                except Exception:
                    pass
                icon_lp = LinearLayout.LayoutParams(dp(icon_size_dp), dp(icon_size_dp))
                icon_lp.rightMargin = dp(12)
                top_row.addView(icon_view, icon_lp)

                pack_name, index_str = icon_str.split("/", 1)
                sticker_index = int(index_str)
                mdc = MediaDataController.getInstance(0)
                ss = None
                try:
                    ss = mdc.getStickerSetByName(pack_name)
                except Exception:
                    pass
                if not ss:
                    try:
                        ss = mdc.getStickerSetByEmojiOrName(pack_name)
                    except Exception:
                        pass
                if ss and getattr(ss, "documents", None) and ss.documents.size() > sticker_index:
                    doc = ss.documents.get(sticker_index)
                    icon_view.setImage(
                        ImageLocation.getForDocument(doc),
                        f"{icon_size_dp}_{icon_size_dp}",
                        None, None, 0, 1
                    )
                else:
                    try:
                        mdc.loadStickersByEmojiOrName(pack_name, False, False)
                    except Exception:
                        pass
            except Exception as e:
                log(f"pluginsUpdates: icon init error for '{pid}': {e}")

        col = LinearLayout(act)
        col.setOrientation(LinearLayout.VERTICAL)
        col.setGravity(Gravity.CENTER_VERTICAL)

        name_tv = TextView(act)
        name_tv.setText(display_name)
        name_tv.setTextColor(self._text_primary)
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        name_tv.setSingleLine(True)
        col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

        ver_row = LinearLayout(act)
        ver_row.setOrientation(LinearLayout.HORIZONTAL)
        ver_row.setGravity(Gravity.CENTER_VERTICAL)
        ver_row_lp = LinearLayout.LayoutParams(-1, -2)
        ver_row_lp.topMargin = dp(2)

        ver_tv = TextView(act)
        ver_tv.setText(f"{local_v} → {repo_v}")
        ver_tv.setTextColor(self._text_gray)
        ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        ver_row.addView(ver_tv, LinearLayout.LayoutParams(-2, -2))

        state = item.get("state", "").strip()
        if state:
            state_chip = self._make_state_chip(act, state)
            state_chip_lp = LinearLayout.LayoutParams(-2, -2)
            state_chip_lp.leftMargin = dp(6)
            ver_row.addView(state_chip, state_chip_lp)

        col.addView(ver_row, ver_row_lp)

        from android.widget import ImageView as _ImageView
        from hook_utils import find_class as _find_class

        try:
            R_tg = _find_class("org.telegram.messenger.R")
            ignore_icon_id = getattr(R_tg.drawable, "menu_hide_gift", 0)
            download_icon_id = getattr(R_tg.drawable, "msg_download", 0)
        except Exception:
            ignore_icon_id = 0
            download_icon_id = 0

        ignore_btn = _ImageView(act)
        if ignore_icon_id:
            ignore_btn.setImageResource(ignore_icon_id)
        ignore_btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
        ignore_btn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
        ignore_btn.setPadding(dp(6), dp(6), dp(6), dp(6))
        ignore_btn.setOnClickListener(OnClickListener(lambda v: self._show_ignore_dialog(pid, item.get("repo_id", ""), repo_v, outer)))
        ignore_btn_lp = LinearLayout.LayoutParams(dp(32), dp(32))
        ignore_btn_lp.leftMargin = dp(4)

        btn_size = dp(32)
        download_btn = FrameLayout(act)
        download_btn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))

        download_icon_view = _ImageView(act)
        if download_icon_id:
            download_icon_view.setImageResource(download_icon_id)
        try:
            download_icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
        except Exception:
            download_icon_view.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
        download_icon_view.setScaleType(_ImageView.ScaleType.CENTER_INSIDE)
        download_icon_view.setPadding(dp(6), dp(6), dp(6), dp(6))
        icon_lp = FrameLayout.LayoutParams(btn_size, btn_size)
        icon_lp.gravity = Gravity.CENTER
        download_btn.addView(download_icon_view, icon_lp)

        download_btn.setOnClickListener(OnClickListener(lambda v: self._install_update(item, download_btn, download_icon_view, act)))
        download_btn_lp = LinearLayout.LayoutParams(btn_size, btn_size)
        download_btn_lp.leftMargin = dp(4)

        # col takes remaining space, buttons sit at center-right of top_row
        top_row.addView(col, LayoutHelper.createLinear(0, -2, 1.0))
        top_row.addView(ignore_btn, ignore_btn_lp)
        top_row.addView(download_btn, download_btn_lp)
        outer.addView(top_row, LayoutHelper.createLinear(-1, -2))

        show_repo_chip = bool(settings.get("show_from_repo", False))
        if show_repo_chip and repo_name:
            chip_row = LinearLayout(act)
            chip_row.setOrientation(LinearLayout.HORIZONTAL)
            chip_row_lp = LinearLayout.LayoutParams(-2, -2)
            chip_row_lp.topMargin = dp(8)
            chip_row.addView(self._make_repo_chip(act, repo_name))
            outer.addView(chip_row, chip_row_lp)

        outer.setBackground(card_bg)
        outer.setClickable(True)
        outer.setFocusable(True)
        outer.setOnClickListener(OnClickListener(lambda v: self._open_plugin_profile(item)))

        class _CardTouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self): super().__init__()
            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.97).scaleY(0.97).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                except Exception:
                    pass
                return False

        outer.setOnTouchListener(_CardTouchListener())

        return outer, outer_lp

    def _open_plugin_profile(self, item: dict):
        try:
            if not self._plugin:
                log("pluginsUpdates: _open_plugin_profile no plugin ref")
                return
            pid = item["id"]
            repo_id = item.get("repo_id", "")

            repos = _get_repos()
            repo = None
            for r in repos:
                if str(r.get("id") or "") == repo_id:
                    repo = r
                    break

            if not repo:
                log(f"pluginsUpdates: _open_plugin_profile repo '{repo_id}' not found")
                return

            repo_url = str(repo.get("url") or "").strip()
            plugin = self._plugin

            def task():
                try:
                    plugins_url = _get_repo_plugins_url(None, repo_id, repo_url)
                    repo_plugins = _fetch_repo_plugins(plugins_url)
                    full_data = repo_plugins.get(pid)
                    if not full_data:
                        log(f"pluginsUpdates: _open_plugin_profile plugin '{pid}' not in repo data")
                        return
                    plugin_data = {"id": pid, **full_data}

                    def on_ui():
                        try:
                            from ..PluginListActivity.fragment import InstallUI
                            from ..PluginActivity.fragment import show_plugin_profile
                            install_ui = InstallUI(plugin)
                            all_plugins = [{"id": k, **v} for k, v in repo_plugins.items() if isinstance(v, dict)]
                            show_plugin_profile(plugin_data, install_ui, all_plugins=all_plugins, repo_id=repo_id)
                        except Exception as e:
                            log(f"pluginsUpdates: _open_plugin_profile on_ui error: {e}")

                    run_on_ui_thread(on_ui)
                except Exception as e:
                    log(f"pluginsUpdates: _open_plugin_profile task error: {e}")

            run_on_queue(task)
        except Exception as e:
            log(f"pluginsUpdates: _open_plugin_profile error: {e}")

    def _show_ignore_dialog(self, pid: str, repo_id: str, repo_version: str, card_view):
        try:
            from .hideDialog import show_hide_dialog

            def on_apply(forever: bool):
                self._apply_ignore(pid, repo_id, repo_version, forever, card_view)

            show_hide_dialog(self._act, pid, repo_id, repo_version, on_apply)
        except Exception as e:
            log(f"pluginsUpdates: _show_ignore_dialog error: {e}")

    def _apply_ignore(self, pid: str, repo_id: str, repo_version: str, forever: bool, card_view):
        try:
            if forever:
                _ignore_forever(None, pid, repo_id)
            else:
                _ignore_until_next(None, pid, repo_id, repo_version)
            run_on_ui_thread(lambda: self._remove_card(card_view))
        except Exception as e:
            log(f"pluginsUpdates: _apply_ignore error: {e}")

    def _install_update(self, item: dict, download_btn=None, download_icon_view=None, act=None):
        pid = item["id"]
        repo_id = item.get("repo_id", "")
        repos = _get_repos()
        repo = None
        for r in repos:
            if str(r.get("id") or "") == repo_id:
                repo = r
                break
        if not repo:
            log(f"pluginsUpdates: _install_update repo '{repo_id}' not found")
            return

        def set_btn_state(state: str):
            # state: "loading" | "done" | "idle"
            if download_btn is None:
                return
            try:
                download_btn.setEnabled(state != "loading")
                download_btn.removeAllViews()
                btn_lp = FrameLayout.LayoutParams(AndroidUtilities.dp(32), AndroidUtilities.dp(32))
                btn_lp.gravity = Gravity.CENTER
                if state == "loading":
                    try:
                        from org.telegram.ui.Components import CircularProgressDrawable
                        spin_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon)
                        d = CircularProgressDrawable(spin_color)
                        try:
                            d.size = float(AndroidUtilities.dp(20))
                            d.thickness = float(AndroidUtilities.dp(2))
                        except Exception:
                            pass
                        spin_iv = ImageView(act)
                        spin_iv.setImageDrawable(d)
                        spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                        download_btn.addView(spin_iv, btn_lp)
                    except Exception as e:
                        log(f"pluginsUpdates: spinner create error: {e}")
                        if download_icon_view is not None:
                            download_btn.addView(download_icon_view, btn_lp)
                elif state == "done":
                    download_btn.setEnabled(False)
                    download_btn.setClickable(False)
                    download_btn.setBackground(None)
                    try:
                        from hook_utils import find_class as _fc
                        R_tg = _fc("org.telegram.messenger.R")
                        check_icon_id = getattr(R_tg.drawable, "msg_select", 0)
                    except Exception:
                        check_icon_id = 0
                    check_iv = ImageView(act)
                    check_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    check_iv.setPadding(AndroidUtilities.dp(6), AndroidUtilities.dp(6), AndroidUtilities.dp(6), AndroidUtilities.dp(6))
                    if check_icon_id:
                        check_iv.setImageResource(check_icon_id)
                    try:
                        green = Theme.getColor(Theme.key_avatar_backgroundGreen)
                    except Exception:
                        green = 0xFF4CAF50
                    check_iv.setColorFilter(green)
                    download_btn.addView(check_iv, btn_lp)
                else:
                    if download_icon_view is not None:
                        download_btn.addView(download_icon_view, btn_lp)
            except Exception as e:
                log(f"pluginsUpdates: set_btn_state error: {e}")

        run_on_ui_thread(lambda: set_btn_state("loading"))

        def task():
            try:
                from ...deeplinks.install import _resolvePluginsUrl
                from ...core import install_plugin
                import requests as _requests

                plugins_url = _resolvePluginsUrl(repo)
                if not plugins_url:
                    log(f"pluginsUpdates: _install_update no plugins url for '{repo_id}'")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    return

                r = _requests.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
                if r.status_code != 200:
                    log(f"pluginsUpdates: _install_update HTTP {r.status_code}")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    return

                data = r.json()
                plugins_raw = data.get("plugins", {})

                plugin = None
                all_plugins = []
                if isinstance(plugins_raw, dict):
                    for _pid, info in plugins_raw.items():
                        if isinstance(info, dict):
                            all_plugins.append({"id": _pid, **info})
                    info = plugins_raw.get(pid)
                    if isinstance(info, dict):
                        plugin = {"id": pid, **info}
                elif isinstance(plugins_raw, list):
                    all_plugins = [p for p in plugins_raw if isinstance(p, dict)]
                    for p in plugins_raw:
                        if isinstance(p, dict) and p.get("id") == pid:
                            plugin = p
                            break

                if not plugin:
                    log(f"pluginsUpdates: _install_update plugin '{pid}' not found in repo")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    return

                def on_finish(ok):
                    # ok=False means deps cancelled or dialog error, not install cancel
                    # actual success comes via add_install_listener
                    if not ok:
                        run_on_ui_thread(lambda: set_btn_state("idle"))

                from ...core import add_install_listener, remove_install_listener

                listener_ref = [None]

                def on_installed(installed_pid):
                    if installed_pid != pid:
                        return
                    remove_install_listener(listener_ref[0])
                    listener_ref[0] = None
                    set_btn_state("done")

                listener_ref[0] = on_installed
                add_install_listener(on_installed)
                self._active_listeners.append(on_installed)

                run_on_ui_thread(lambda: install_plugin(plugin, all_plugins=all_plugins, rm_rid=repo_id, on_finish=on_finish))
            except Exception as e:
                log(f"pluginsUpdates: _install_update task error: {e}")
                run_on_ui_thread(lambda: set_btn_state("idle"))

        run_on_queue(task)

    def _remove_card(self, card_view):
        try:
            from android.animation import ObjectAnimator, AnimatorSet, ValueAnimator, Animator
            from android.view import ViewGroup

            fade = ObjectAnimator.ofFloat(card_view, "alpha", 1.0, 0.0)
            slide = ObjectAnimator.ofFloat(card_view, "translationX", 0.0, float(AndroidUtilities.dp(40)))

            exit_anim = AnimatorSet()
            exit_anim.playTogether(fade, slide)
            exit_anim.setDuration(200)

            measured_height = [card_view.getHeight()]

            class _ExitListener(dynamic_proxy(Animator.AnimatorListener)):
                def onAnimationEnd(self, *args):
                    try:
                        h = measured_height[0]
                        if h <= 0:
                            parent = card_view.getParent()
                            if parent is not None:
                                parent.removeView(card_view)
                            return

                        lp = card_view.getLayoutParams()

                        collapse = ValueAnimator.ofInt(h, 0)
                        collapse.setDuration(180)

                        class _UpdateListener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                            def onAnimationUpdate(self, anim):
                                try:
                                    lp.height = int(anim.getAnimatedValue())
                                    card_view.setLayoutParams(lp)
                                except Exception:
                                    pass

                        class _CollapseEndListener(dynamic_proxy(Animator.AnimatorListener)):
                            def onAnimationEnd(self, *args):
                                try:
                                    parent = card_view.getParent()
                                    if parent is not None:
                                        parent.removeView(card_view)
                                except Exception:
                                    pass
                            def onAnimationStart(self, *args): pass
                            def onAnimationCancel(self, *args): pass
                            def onAnimationRepeat(self, *args): pass

                        collapse.addUpdateListener(_UpdateListener())
                        collapse.addListener(_CollapseEndListener())
                        collapse.start()
                    except Exception as e:
                        log(f"pluginsUpdates: _remove_card collapse error: {e}")
                        try:
                            parent = card_view.getParent()
                            if parent is not None:
                                parent.removeView(card_view)
                        except Exception:
                            pass

                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            exit_anim.addListener(_ExitListener())
            exit_anim.start()
        except Exception as e:
            log(f"pluginsUpdates: _remove_card error: {e}")
            try:
                parent = card_view.getParent()
                if parent is not None:
                    parent.removeView(card_view)
            except Exception:
                pass

    def _show_updates(self, updates: list):
        try:
            act = self._act
            dp = AndroidUtilities.dp
            container = self._results_container
            container.setPadding(dp(12), dp(12), dp(12), dp(12))

            for item in updates:
                card, lp = self._make_update_card(act, item)
                container.addView(card, lp)
        except Exception as e:
            log(f"pluginsUpdates: _show_updates error: {e}")


def show_updates_fragment(plugin=None):
    try:
        frag = get_last_fragment()
        if not frag:
            log("pluginsUpdates: show_updates_fragment no fragment")
            return
        delegate = UpdatesFragment(plugin)
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        try:
            new_frag.setTitle("Updates", False, 0)
            action_bar = new_frag.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                try:
                    from org.telegram.messenger import R as R_tg
                    back_icon = getattr(R_tg.drawable, "ic_ab_back", 0)
                    if back_icon:
                        action_bar.setBackButtonImage(back_icon)
                        action_bar.setBackButtonContentDescription("Back")
                        try:
                            back_button = action_bar.getBackButton()
                            if back_button:
                                def _on_back(v):
                                    f = get_last_fragment()
                                    if f:
                                        f.finishFragment()
                                back_button.setOnClickListener(OnClickListener(_on_back))
                        except Exception:
                            pass
                except Exception as e:
                    log(f"pluginsUpdates: back button error: {e}")
        except Exception as e:
            log(f"pluginsUpdates: actionBar setup error: {e}")
    except Exception as e:
        log(f"pluginsUpdates: show_updates_fragment error: {e}")

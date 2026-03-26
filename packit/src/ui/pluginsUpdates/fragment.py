import json
import os
import threading

from android.view import Gravity
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
    from elyx import settings
except Exception as e:
    log(f"pluginsUpdates: import elyx.settings failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()


def _get_index_path(pkg: str, rm_rid: str) -> str:
    return f"/data/data/{pkg}/files/packitCache/reposCache/{rm_rid}-index.json"


def _get_repo_cache_path(pkg: str, rm_rid: str) -> str:
    return f"/data/data/{pkg}/files/packitCache/reposCache/{rm_rid}.json"


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

            # skip update if the repo version requires a newer app than installed
            repo_min_ver = str(repo_info.get("min_version") or "")
            if repo_min_ver:
                try:
                    from ..PluginListActivity.fragment import _is_min_version_satisfied
                    if not _is_min_version_satisfied(repo_min_ver):
                        continue
                except Exception as e:
                    log(f"pluginsUpdates: min_version check error for '{pid}': {e}")

            local_hash = str(entry.get("hash") or "")
            local_bithash = str(entry.get("bithash") or "")
            repo_hash = str(repo_info.get("hash") or "")
            repo_bithash = str(repo_info.get("bithash") or "")

            local_ver = _version_tuple(entry.get("version") or "")
            repo_ver = _version_tuple(repo_info.get("version") or "")

            # Outdated means a non-latest version was installed, no hash available for it,
            # so skip hash comparison and check purely by version
            is_outdated_marker = local_hash == "Outdated" or local_bithash == "Outdated"
            if is_outdated_marker:
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

            # compare hashes, pick matching type
            hash_matches = True
            if local_hash and repo_hash:
                hash_matches = local_hash == repo_hash
            elif local_bithash and repo_bithash:
                hash_matches = local_bithash == repo_bithash

            if hash_matches:
                continue

            # hash differs, determine reason
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
            else:
                # same or older version, check if state changed
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


class UpdatesFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):

    def __init__(self):
        super().__init__()
        self._content_view = None
        self._alive = [True]
        self._spinner = None
        self._spinner_container = None

    def onFragmentCreate(self, *_):
        pass

    def onFragmentDestroy(self, *_):
        self._alive[0] = False
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
                pkg = ApplicationLoader.applicationContext.getPackageName()

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
                    total_installed += len(_read_index(pkg, rm_rid))

                if total_installed == 0:
                    run_on_ui_thread(lambda: self._show_empty("You have not installed any plugins from PackIt") if alive[0] else None)
                    return

                updates = _check_updates(pkg)

                def on_done():
                    if not alive[0]:
                        return
                    self._hide_spinner()
                    if not updates:
                        self._show_empty("All plugins of the current version")
                    else:
                        self._show_updates(updates)

                run_on_ui_thread(on_done)
            except Exception as e:
                log(f"pluginsUpdates: task error: {e}")
                run_on_ui_thread(lambda: self._show_empty("Failed to check updates") if alive[0] else None)

        run_on_queue(task)

    def _hide_spinner(self):
        try:
            if self._spinner_container is not None:
                self._spinner_container.setVisibility(4)  # GONE
        except Exception as e:
            log(f"pluginsUpdates: _hide_spinner error: {e}")

    def _show_empty(self, message: str):
        try:
            self._hide_spinner()
            act = self._act
            dp = AndroidUtilities.dp

            tv = TextView(act)
            tv.setText(message)
            tv.setTextColor(self._text_gray)
            tv.setTextSize(1, 15)
            tv.setPadding(dp(24), dp(24), dp(24), dp(24))

            lp = FrameLayout.LayoutParams(-2, -2)
            lp.gravity = Gravity.CENTER
            self._content_view.addView(tv, lp)
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
        tv.setText(f"From {repo_name} repository")
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

        top_row.addView(col, LayoutHelper.createLinear(0, -2, 1.0))
        outer.addView(top_row, LayoutHelper.createLinear(-1, -2))

        chip_row = LinearLayout(act)
        chip_row.setOrientation(LinearLayout.HORIZONTAL)
        chip_lp = LinearLayout.LayoutParams(-2, -2)
        chip_lp.topMargin = dp(8)
        chip_row.addView(self._make_repo_chip(act, repo_name))
        outer.addView(chip_row, chip_lp)

        return outer, outer_lp

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


def show_updates_fragment():
    try:
        frag = get_last_fragment()
        if not frag:
            log("pluginsUpdates: show_updates_fragment no fragment")
            return
        delegate = UpdatesFragment()
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

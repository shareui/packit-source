import json
import os
import threading
# lazy to fix allupdate state
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


def _extract_diff(repo_info: dict, local_version: str):
    # accumulates numeric diff from changelogs of all versions strictly newer than local_version
    # changelog format: [title, "+N", "-M"] — numbers are extracted and summed across versions
    if not local_version:
        return None
    versions = repo_info.get("versions")
    if not isinstance(versions, dict):
        return None

    import re as _re

    local_t = _version_tuple(local_version)

    newer = sorted(
        [(k, v) for k, v in versions.items() if isinstance(v, dict) and _version_tuple(k) >= local_t],
        key=lambda x: _version_tuple(x[0])
    )
    if not newer:
        return None

    total_add = 0
    total_rem = 0
    has_data = False
    for _, vdata in newer:
        cl = vdata.get("changelog")
        if not isinstance(cl, list) or len(cl) < 3:
            continue
        add_nums = _re.findall(r"\d+", str(cl[1]))
        rem_nums = _re.findall(r"\d+", str(cl[2]))
        if add_nums:
            total_add += int(add_nums[0])
            has_data = True
        if rem_nums:
            total_rem += int(rem_nums[0])
            has_data = True

    if not has_data:
        return None
    add_result = f"+{total_add}" if total_add else ""
    rem_result = f"-{total_rem}" if total_rem else ""
    return (add_result, rem_result)


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
                    "diff": _extract_diff(repo_info, str(entry.get("version") or "")),
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
                    "diff": _extract_diff(repo_info, str(entry.get("version") or "")),
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
        self._scroll_view = None
        self._active_listeners = []
        self._card_count = [0]
        self._done_count = [0]
        self._current_updates = []
        self._is_loading = False

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

        from android.widget import ScrollView
        scroll = ScrollView(act)
        scroll.setFillViewport(True)

        self._results_container = LinearLayout(act)
        self._results_container.setOrientation(LinearLayout.VERTICAL)
        scroll.addView(self._results_container, FrameLayout.LayoutParams(-1, -2))
        # bottom padding reserves space for the floating button bar (~120dp)
        scroll.setPadding(0, 0, 0, dp(120))
        self._scroll_view = scroll
        self._content_view.addView(scroll, FrameLayout.LayoutParams(-1, -1))

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

        self._add_button_bar(act, dp)

        self._start_load()
        return self._content_view

    def _add_button_bar(self, act, dp):
        # layout: two floating elements bottom-center
        #   left_island  - pill with icon-only buttons: [Refresh] [Ignore] (full) | [Refresh] [Ignore list] (empty)
        #   right_btn    - square button: [Update all icon] (full mode only)
        #
        # both animate in/out together via _bar_island (left) and _bar_right_btn
        # _bar_island is the primary animation target; right_btn mirrors it

        try:
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception as e:
            log(f"pluginsUpdates: _add_button_bar accent color error: {e}")
            accent = 0xFF2196F3

        try:
            accent_text = Theme.getColor(Theme.key_featuredStickers_buttonText)
        except Exception as e:
            log(f"pluginsUpdates: _add_button_bar accent_text color error: {e}")
            accent_text = 0xFFFFFFFF

        island_r = dp(32)
        btn_r = dp(22)
        island_pad = dp(10)
        btn_gap = dp(6)
        self._bar_btn_gap = btn_gap
        icon_size = dp(22)
        icon_pad = dp(14)   # padding around icon inside each icon button

        def _make_island_bg():
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadius(float(island_r))
            try:
                bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
            except Exception:
                bg.setColor(0xFFFFFFFF)
            return bg

        def _make_icon_btn(res_name: str):
            # square icon-only button with accent background
            btn = TextView(act)
            btn.setGravity(Gravity.CENTER)
            btn.setPadding(icon_pad, icon_pad, icon_pad, icon_pad)
            btn.setClickable(True)
            btn.setFocusable(True)
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadius(float(btn_r))
            bg.setColor(accent)
            btn.setBackground(bg)
            # icon centered via compound drawable with no text
            try:
                from org.telegram.messenger import R as R_tg
                from android.graphics import PorterDuff
                from androidx.core.content import ContextCompat
                res_id = getattr(R_tg.drawable, res_name, 0)
                if res_id:
                    d = ContextCompat.getDrawable(act, res_id).mutate()
                    d.setBounds(0, 0, icon_size, icon_size)
                    d.setColorFilter(accent_text, PorterDuff.Mode.SRC_IN)
                    btn.setCompoundDrawablesRelative(d, None, None, None)
            except Exception as e:
                log(f"pluginsUpdates: _make_icon_btn '{res_name}' error: {e}")
            return btn

        # two separate islands: full_row (refresh+ignore+download) and empty_row (refresh+ignore_list)
        # switching between them is done by GONE/VISIBLE on the whole island — no layout jump
        # because only one island is VISIBLE at a time, bar_frame wraps exactly to the visible one

        # --- full island: [refresh] [ignore] ---
        full_island = LinearLayout(act)
        full_island.setOrientation(LinearLayout.HORIZONTAL)
        full_island.setPadding(island_pad, island_pad, island_pad, island_pad)
        full_island.setElevation(float(dp(10)))
        full_island.setBackground(_make_island_bg())

        refresh_btn = _make_icon_btn("msg_reset")
        ignore_btn = _make_icon_btn("msg_mute")

        r_lp = LinearLayout.LayoutParams(-2, -2)
        r_lp.rightMargin = btn_gap
        full_island.addView(refresh_btn, r_lp)
        full_island.addView(ignore_btn, LinearLayout.LayoutParams(-2, -2))

        # --- empty island: [refresh with text] [ignore_list] ---
        empty_island = LinearLayout(act)
        empty_island.setOrientation(LinearLayout.HORIZONTAL)
        empty_island.setPadding(island_pad, island_pad, island_pad, island_pad)
        empty_island.setElevation(float(dp(10)))
        empty_island.setBackground(_make_island_bg())

        empty_refresh_btn = TextView(act)
        empty_refresh_btn.setGravity(Gravity.CENTER)
        empty_refresh_btn.setPadding(icon_pad, icon_pad, icon_pad, icon_pad)
        empty_refresh_btn.setClickable(True)
        empty_refresh_btn.setFocusable(True)
        empty_refresh_btn.setText(str(strings["updates_btn_refresh"]))
        empty_refresh_btn.setTextColor(accent_text)
        empty_refresh_btn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        try:
            empty_refresh_btn.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        try:
            from org.telegram.messenger import R as R_tg
            from android.graphics import PorterDuff
            from androidx.core.content import ContextCompat
            res_id = getattr(R_tg.drawable, "msg_reset", 0)
            if res_id:
                d = ContextCompat.getDrawable(act, res_id).mutate()
                d.setBounds(0, 0, icon_size, icon_size)
                d.setColorFilter(accent_text, PorterDuff.Mode.SRC_IN)
                empty_refresh_btn.setCompoundDrawablesRelative(d, None, None, None)
                empty_refresh_btn.setCompoundDrawablePadding(dp(6))
        except Exception as e:
            log(f"pluginsUpdates: empty_refresh_btn icon error: {e}")
        er_bg = GradientDrawable()
        er_bg.setShape(GradientDrawable.RECTANGLE)
        er_bg.setCornerRadius(float(btn_r))
        er_bg.setColor(accent)
        empty_refresh_btn.setBackground(er_bg)

        ignore_list_btn = _make_icon_btn("list_mute")

        er_lp = LinearLayout.LayoutParams(-2, -2)
        er_lp.rightMargin = btn_gap
        empty_island.addView(empty_refresh_btn, er_lp)
        empty_island.addView(ignore_list_btn, LinearLayout.LayoutParams(-2, -2))

        # start hidden — shown after load
        empty_island.setVisibility(8)

        # --- right button (Update all) ---
        btn_square = icon_pad * 2 + icon_size

        right_btn = _make_icon_btn("msg_download")
        right_btn_bg = GradientDrawable()
        right_btn_bg.setShape(GradientDrawable.RECTANGLE)
        right_btn_bg.setCornerRadius(float(btn_square // 2))
        right_btn_bg.setColor(accent)
        right_btn.setBackground(right_btn_bg)
        right_btn.setPadding(icon_pad, icon_pad, icon_pad, icon_pad)
        right_btn.setElevation(float(dp(10)))

        bottom_margin = dp(20)
        island_gap = dp(10)

        # bar_frame holds both islands stacked; only one visible at a time so wrap_content is correct
        from android.widget import FrameLayout as _FrameLayout
        bar_frame = _FrameLayout(act)
        bar_frame.addView(full_island, _FrameLayout.LayoutParams(-2, -2))
        bar_frame.addView(empty_island, _FrameLayout.LayoutParams(-2, -2))

        bar_row = LinearLayout(act)
        bar_row.setOrientation(LinearLayout.HORIZONTAL)
        bar_row.setGravity(Gravity.CENTER_VERTICAL)

        left_lp = LinearLayout.LayoutParams(-2, -2)
        left_lp.rightMargin = island_gap
        bar_row.addView(bar_frame, left_lp)

        right_lp = LinearLayout.LayoutParams(btn_square, btn_square)
        bar_row.addView(right_btn, right_lp)

        row_lp = FrameLayout.LayoutParams(-2, -2)
        row_lp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL
        row_lp.bottomMargin = bottom_margin
        self._content_view.addView(bar_row, row_lp)

        # allow right_btn to animate beyond bar_row bounds without being clipped
        bar_row.setClipChildren(False)
        self._content_view.setClipChildren(False)

        self._bar_row = bar_row

        bar_row.setAlpha(0.0)
        bar_row.setScaleX(0.85)
        bar_row.setScaleY(0.85)
        bar_row.setTranslationY(float(dp(16)))

        self._bar_refresh_btn = refresh_btn
        self._bar_ignore_btn = ignore_btn
        self._bar_update_all_btn = right_btn
        self._bar_update_all_btn_animated = False
        self._bar_empty_refresh_btn = empty_refresh_btn
        self._bar_ignore_list_btn = ignore_list_btn
        self._bar_full_island = full_island
        self._bar_empty_island = empty_island
        self._bar_island = bar_row
        self._bar_left_island = full_island
        self._bar_right_btn = right_btn
        self._bar_top_row = full_island
        self._bar_btn_gap = btn_gap
        self._bar_island_bottom_margin = bottom_margin
        self._bar_btn_square = btn_square
        self._bar_island_gap = island_gap

        ignore_list_btn.setOnClickListener(OnClickListener(lambda v: self._open_ignore_list_dialog()))
        empty_refresh_btn.setOnClickListener(OnClickListener(lambda v: self._on_refresh_click()))
        refresh_btn.setOnClickListener(OnClickListener(lambda v: self._on_refresh_click()))
        ignore_btn.setOnClickListener(OnClickListener(lambda v: self._on_ignore_all_click()))

    def _open_ignore_list_dialog(self):
        try:
            from .clearIgnoreListDialog import show_clear_ignore_list_dialog
            show_clear_ignore_list_dialog(self._act, on_close=self._on_refresh_click)
        except Exception as e:
            log(f"pluginsUpdates: _open_ignore_list_dialog error: {e}")

    def _on_ignore_all_click(self):
        updates = getattr(self, "_current_updates", [])
        if not updates:
            return

        def on_confirm():
            def task():
                try:
                    for item in updates:
                        _ignore_until_next(None, item["id"], item.get("repo_id", ""), item.get("repo_version", ""))
                except Exception as e:
                    log(f"pluginsUpdates: _on_ignore_all_click task error: {e}")
                run_on_ui_thread(self._on_refresh_click)

            run_on_queue(task)

        try:
            from .hideAllDialog import show_hide_all_dialog
            show_hide_all_dialog(self._act, on_confirm)
        except Exception as e:
            log(f"pluginsUpdates: _on_ignore_all_click error: {e}")

    def _on_refresh_click(self):
        if self._is_loading:
            return
        try:
            from android.animation import AnimatorSet, ObjectAnimator, Animator
            from android.view.animation import AccelerateInterpolator
            from java import dynamic_proxy

            island = self._bar_island
            dp = AndroidUtilities.dp

            try:
                display = self._act.getWindowManager().getDefaultDisplay()
                from android.graphics import Point
                pt = Point()
                display.getSize(pt)
                screen_h = float(pt.y)
            except Exception:
                screen_h = float(dp(800))

            fly_out = ObjectAnimator.ofFloat(island, "translationY", 0.0, screen_h * 0.4)
            fly_out.setDuration(260)
            fly_out.setInterpolator(AccelerateInterpolator(1.8))

            fade_out = ObjectAnimator.ofFloat(island, "alpha", 1.0, 0.0)
            fade_out.setDuration(180)
            fade_out.setInterpolator(AccelerateInterpolator())

            out_set = AnimatorSet()
            out_set.playTogether(fly_out, fade_out)

            fragment_ref = self
            fragment_ref._is_loading = True

            class _OutDone(dynamic_proxy(Animator.AnimatorListener)):
                def __init__(self): super().__init__()
                def onAnimationEnd(self, *args):
                    try:
                        # reset bar_row to pre-show state
                        island.setTranslationY(float(dp(16)))
                        island.setScaleX(0.85)
                        island.setScaleY(0.85)
                        island.setAlpha(0.0)

                        # clear results and any empty/up-to-date cards
                        fragment_ref._results_container.removeAllViews()
                        content = fragment_ref._content_view
                        sc = fragment_ref._spinner_container
                        # remove only ephemeral cards (empty/up-to-date), keep scroll/spinner/island
                        keep = {fragment_ref._scroll_view, sc, fragment_ref._bar_island}
                        i = content.getChildCount() - 1
                        while i >= 0:
                            child = content.getChildAt(i)
                            if child not in keep:
                                content.removeViewAt(i)
                            i -= 1

                        # show spinner again
                        if sc is not None:
                            sc.setVisibility(0)
                            try:
                                drawable = fragment_ref._spinner.getDrawable()
                                from org.telegram.ui.Components import CircularProgressDrawable
                                if isinstance(drawable, CircularProgressDrawable):
                                    drawable.start()
                            except Exception:
                                pass

                        fragment_ref._card_count[0] = 0
                        fragment_ref._done_count[0] = 0
                        fragment_ref._start_load()
                    except Exception as e:
                        log(f"pluginsUpdates: _on_refresh_click reset error: {e}")
                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            out_set.addListener(_OutDone())
            out_set.start()
        except Exception as e:
            log(f"pluginsUpdates: _on_refresh_click error: {e}")

    def _has_any_ignored(self) -> bool:
        # returns True if at least one plugin is in any repo ignore list
        try:
            repos = _get_repos()
            for repo in repos:
                rm_rid = str(repo.get("id") or "")
                if not rm_rid:
                    continue
                if _get_ignore_list(None, rm_rid):
                    return True
        except Exception as e:
            log(f"pluginsUpdates: _has_any_ignored error: {e}")
        return False

    def _show_bar(self):
        # animates the whole bar row (contains left island + right btn) in from hidden state
        try:
            from android.animation import AnimatorSet, ObjectAnimator
            from android.view.animation import DecelerateInterpolator, OvershootInterpolator

            row = self._bar_island  # bar_row is the animation target

            fade = ObjectAnimator.ofFloat(row, "alpha", 0.0, 1.0)
            fade.setDuration(220)
            fade.setInterpolator(DecelerateInterpolator())

            sx = ObjectAnimator.ofFloat(row, "scaleX", row.getScaleX(), 1.0)
            sx.setDuration(320)
            sx.setInterpolator(OvershootInterpolator(1.4))

            sy = ObjectAnimator.ofFloat(row, "scaleY", row.getScaleY(), 1.0)
            sy.setDuration(320)
            sy.setInterpolator(OvershootInterpolator(1.4))

            tr = ObjectAnimator.ofFloat(row, "translationY", row.getTranslationY(), 0.0)
            tr.setDuration(300)
            tr.setInterpolator(OvershootInterpolator(1.2))

            s = AnimatorSet()
            s.playTogether(fade, sx, sy, tr)
            s.start()
        except Exception as e:
            log(f"pluginsUpdates: _show_bar error: {e}")
            try:
                row = self._bar_island
                row.setAlpha(1.0)
                row.setScaleX(1.0)
                row.setScaleY(1.0)
                row.setTranslationY(0.0)
            except Exception:
                pass

    def _apply_bar_empty_mode(self, empty: bool):
        # switches between two separate islands via GONE/VISIBLE on the whole island view
        # this avoids layout jump because bar_frame wraps to whichever island is visible
        try:
            gone = 8
            visible = 0
            if empty:
                self._bar_full_island.setVisibility(gone)
                self._bar_right_btn.setVisibility(gone)
                has_ignored = self._has_any_ignored()
                self._bar_empty_island.setVisibility(visible)
                self._bar_ignore_list_btn.setVisibility(visible if has_ignored else gone)
                # when ignore list not empty: icon-only (no text, no drawable padding)
                # when ignore list empty: icon + text, stretched to two-button width
                dp = AndroidUtilities.dp
                btn_square = self._bar_btn_square
                btn = self._bar_empty_refresh_btn
                if has_ignored:
                    btn.setText("")
                    btn.setCompoundDrawablePadding(0)
                    btn.setMinWidth(0)
                    lp = LinearLayout.LayoutParams(-2, -2)
                    lp.rightMargin = self._bar_btn_gap
                else:
                    from elyx import strings as _strings
                    btn.setText(str(_strings["updates_btn_refresh"]))
                    btn.setCompoundDrawablePadding(dp(6))
                    two_btn_w = btn_square * 2 + self._bar_btn_gap
                    btn.setMinWidth(two_btn_w)
                    lp = LinearLayout.LayoutParams(-2, -2)
                btn.setLayoutParams(lp)
            else:
                self._bar_empty_island.setVisibility(gone)
                self._bar_full_island.setVisibility(visible)
                self._bar_right_btn.setVisibility(visible)
        except Exception as e:
            log(f"pluginsUpdates: _apply_bar_empty_mode error: {e}")

    def _set_bar_empty_mode(self, empty: bool):
        # island flies down off screen, inner buttons swapped while invisible, slides back up
        # visibility is swapped before out-anim to avoid layout jump in onAnimationEnd
        try:
            from android.animation import AnimatorSet, ObjectAnimator, Animator
            from android.view.animation import AccelerateInterpolator, DecelerateInterpolator
            from java import dynamic_proxy

            island = self._bar_island
            dp = AndroidUtilities.dp

            try:
                display = self._act.getWindowManager().getDefaultDisplay()
                from android.graphics import Point
                pt = Point()
                display.getSize(pt)
                screen_h = float(pt.y)
            except Exception:
                screen_h = float(dp(800))

            drop = screen_h - island.getY() + float(dp(20))

            fly_out = ObjectAnimator.ofFloat(island, "translationY", 0.0, drop)
            fly_out.setDuration(320)
            fly_out.setInterpolator(AccelerateInterpolator(2.0))

            fade_out = ObjectAnimator.ofFloat(island, "alpha", 1.0, 0.0)
            fade_out.setDuration(200)
            fade_out.setInterpolator(AccelerateInterpolator(1.2))

            out_set = AnimatorSet()
            out_set.playTogether(fly_out, fade_out)

            fragment_ref = self

            class _OutListener(dynamic_proxy(Animator.AnimatorListener)):
                def __init__(self): super().__init__()

                def onAnimationEnd(self, *args):
                    try:
                        # swap inner buttons while island is already invisible and off-screen
                        fragment_ref._apply_bar_empty_mode(empty)

                        # reset position below screen, then animate back up — no layout pass, no jump
                        island.setTranslationY(drop)
                        island.setTranslationX(0.0)

                        fly_in = ObjectAnimator.ofFloat(island, "translationY", drop, 0.0)
                        fly_in.setDuration(400)
                        fly_in.setInterpolator(DecelerateInterpolator(2.5))

                        fade_in = ObjectAnimator.ofFloat(island, "alpha", 0.0, 1.0)
                        fade_in.setDuration(250)
                        fade_in.setInterpolator(DecelerateInterpolator())

                        in_set = AnimatorSet()
                        in_set.playTogether(fly_in, fade_in)
                        in_set.start()
                    except Exception as e:
                        log(f"pluginsUpdates: bar anim in error: {e}")

                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            out_set.addListener(_OutListener())
            out_set.start()
        except Exception as e:
            log(f"pluginsUpdates: _set_bar_empty_mode error: {e}")
            self._apply_bar_empty_mode(empty)

    def _start_load(self):
        self._is_loading = True
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
                    self._is_loading = False
                    total_available = 0
                    for repo in repos:
                        rm_rid = str(repo.get("id") or "")
                        repo_url = str(repo.get("url") or "").strip()
                        if not rm_rid or not repo_url:
                            continue
                        try:
                            plugins_url = _get_repo_plugins_url(None, rm_rid, repo_url)
                            total_available += len(_fetch_repo_plugins(plugins_url))
                        except Exception:
                            pass
                    def _open_catalog():
                        try:
                            from ..PluginListActivity.fragment import InstallUI
                            InstallUI(self._plugin).open()
                        except Exception as e:
                            log(f"pluginsUpdates: _open_catalog error: {e}")
                    chip = str(strings("updates_empty_available_chip", count=total_available)) if total_available > 0 else None
                    run_on_ui_thread(lambda: self._show_empty(
                        str(strings["updates_no_plugins_installed"]),
                        "utyan_empty",
                        action_label=str(strings["install_plugin"]),
                        action_icon="menu_shop",
                        on_action=_open_catalog,
                        title=str(strings["updates_empty_title"]),
                        chip_text=chip,
                    ) if alive[0] else None)
                    return

                updates = _filter_ignored(None, _check_updates(None))

                def on_done():
                    if not alive[0]:
                        return
                    self._is_loading = False
                    self._hide_spinner()
                    if not updates:
                        self._show_all_up_to_date()
                    else:
                        self._show_updates(updates)

                run_on_ui_thread(on_done)
            except Exception as e:
                log(f"pluginsUpdates: task error: {e}")
                run_on_ui_thread(lambda: (setattr(self, '_is_loading', False), self._show_empty(str(strings["updates_failed_to_check"]), "error", title=str(strings["updates_error_title"]))) if alive[0] else None)

        run_on_queue(task)

    def _hide_spinner(self):
        try:
            if self._spinner_container is not None:
                self._spinner_container.setVisibility(4)  # GONE
        except Exception as e:
            log(f"pluginsUpdates: _hide_spinner error: {e}")

    def _show_empty(self, message: str, anim_name: str = "done", action_label: str = None, action_icon: str = None, on_action=None, title: str = None, chip_text: str = None):
        try:
            self._hide_spinner()
            self._apply_bar_empty_mode(True)
            self._show_bar()
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

            if title:
                title_tv = TextView(act)
                title_tv.setText(title)
                title_tv.setTextColor(self._text_primary)
                title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
                title_tv.setGravity(Gravity.CENTER)
                try:
                    title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    pass
                title_lp = LinearLayout.LayoutParams(-2, -2)
                title_lp.gravity = Gravity.CENTER_HORIZONTAL
                title_lp.bottomMargin = dp(4)
                card.addView(title_tv, title_lp)

            card.addView(tv, LinearLayout.LayoutParams(-2, -2))

            if action_label and on_action:
                try:
                    accent = Theme.getColor(Theme.key_featuredStickers_addButton)
                    accent_text = Theme.getColor(Theme.key_featuredStickers_buttonText)
                except Exception:
                    accent = 0xFF2196F3
                    accent_text = 0xFFFFFFFF

                btn = TextView(act)
                btn.setText(action_label)
                btn.setTextColor(accent_text)
                btn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                btn.setGravity(Gravity.CENTER)
                btn_pad_h = dp(20)
                btn_pad_v = dp(10)
                btn.setPadding(btn_pad_h, btn_pad_v, btn_pad_h, btn_pad_v)
                btn.setClickable(True)
                btn.setFocusable(True)
                try:
                    btn.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    pass

                if action_icon:
                    try:
                        from org.telegram.messenger import R as R_tg
                        from android.graphics import PorterDuff
                        from androidx.core.content import ContextCompat
                        icon_size = dp(16)
                        res_id = getattr(R_tg.drawable, action_icon, 0)
                        if res_id:
                            d = ContextCompat.getDrawable(act, res_id).mutate()
                            d.setBounds(0, 0, icon_size, icon_size)
                            d.setColorFilter(accent_text, PorterDuff.Mode.SRC_IN)
                            btn.setCompoundDrawablesRelative(d, None, None, None)
                            btn.setCompoundDrawablePadding(dp(6))
                    except Exception as e:
                        log(f"pluginsUpdates: _show_empty action icon error: {e}")

                btn_bg = GradientDrawable()
                btn_bg.setShape(GradientDrawable.RECTANGLE)
                btn_bg.setCornerRadius(float(dp(22)))
                btn_bg.setColor(accent)
                btn.setBackground(btn_bg)
                btn.setElevation(float(dp(4)))
                btn.setOnClickListener(OnClickListener(lambda v: on_action()))

                btn_lp = LinearLayout.LayoutParams(-2, -2)
                btn_lp.gravity = Gravity.CENTER_HORIZONTAL
                btn_lp.topMargin = dp(18)
                card.addView(btn, btn_lp)

                if chip_text:
                    import ctypes
                    try:
                        chip_color = Theme.getColor(Theme.key_avatar_background2Blue)
                    except Exception:
                        chip_color = 0xFF2196F3
                    r = (chip_color >> 16) & 0xFF
                    g = (chip_color >> 8) & 0xFF
                    b = chip_color & 0xFF
                    chip_fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
                    chip_text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
                    chip_bg = GradientDrawable()
                    chip_bg.setShape(GradientDrawable.RECTANGLE)
                    chip_bg.setCornerRadius(float(dp(6)))
                    chip_bg.setColor(chip_fill)
                    chip_tv = TextView(act)
                    chip_tv.setText(chip_text)
                    chip_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
                    chip_tv.setTextColor(chip_text_color)
                    chip_tv.setBackground(chip_bg)
                    chip_tv.setPadding(dp(7), dp(2), dp(7), dp(2))
                    chip_lp = LinearLayout.LayoutParams(-2, -2)
                    chip_lp.gravity = Gravity.CENTER_HORIZONTAL
                    chip_lp.topMargin = dp(10)
                    card.addView(chip_tv, chip_lp)

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

                def try_load_icon(view=icon_view, istr=icon_str, size=icon_size_dp):
                    try:
                        pack_name, index_str = istr.split("/", 1)
                        sticker_index = int(index_str)
                        mdc = MediaDataController.getInstance(0)
                        ss = None
                        try:
                            ss = mdc.getStickerSetByName(pack_name)
                        except Exception:
                            ss = None
                        if not ss:
                            try:
                                ss = mdc.getStickerSetByEmojiOrName(pack_name)
                            except Exception:
                                ss = None
                        if ss and getattr(ss, "documents", None) and ss.documents.size() > sticker_index:
                            doc = ss.documents.get(sticker_index)
                            view.setImage(
                                ImageLocation.getForDocument(doc),
                                f"{size}_{size}",
                                None, None, 0, 1
                            )
                            return True
                        return False
                    except Exception:
                        return False

                if not try_load_icon():
                    try:
                        pack_name = icon_str.split("/", 1)[0]
                        MediaDataController.getInstance(0).loadStickersByEmojiOrName(pack_name, False, False)
                    except Exception:
                        pass

                    def _retry_load(loader=try_load_icon):
                        import time
                        for delay in (0.5, 1.0, 2.0, 3.0):
                            time.sleep(delay)
                            try:
                                if run_on_ui_thread(loader):
                                    return
                            except Exception:
                                pass

                    threading.Thread(target=_retry_load, daemon=True).start()
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

        diff = item.get("diff")
        if isinstance(diff, tuple) and len(diff) == 2:
            add_str, rem_str = diff
            diff_row = LinearLayout(act)
            diff_row.setOrientation(LinearLayout.HORIZONTAL)
            diff_row.setGravity(Gravity.CENTER_VERTICAL)
            diff_row_lp = LinearLayout.LayoutParams(-2, -2)
            diff_row_lp.topMargin = dp(2)

            if add_str:
                add_tv = TextView(act)
                add_tv.setText(add_str)
                add_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
                try:
                    add_tv.setTextColor(Theme.getColor(Theme.key_avatar_backgroundGreen))
                except Exception:
                    add_tv.setTextColor(0xFF4CAF50)
                diff_row.addView(add_tv, LinearLayout.LayoutParams(-2, -2))

            if rem_str:
                rem_tv = TextView(act)
                rem_tv.setText(f"  {rem_str}" if add_str else rem_str)
                rem_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
                try:
                    rem_tv.setTextColor(Theme.getColor(Theme.key_avatar_backgroundRed))
                except Exception:
                    rem_tv.setTextColor(0xFFF44336)
                diff_row.addView(rem_tv, LinearLayout.LayoutParams(-2, -2))

            col.addView(diff_row, diff_row_lp)

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
                    self._on_plugin_done()

                listener_ref[0] = on_installed
                add_install_listener(on_installed)
                self._active_listeners.append(on_installed)

                run_on_ui_thread(lambda: install_plugin(plugin, all_plugins=all_plugins, rm_rid=repo_id, on_finish=on_finish))
            except Exception as e:
                log(f"pluginsUpdates: _install_update task error: {e}")
                run_on_ui_thread(lambda: set_btn_state("idle"))

        run_on_queue(task)

    def _on_plugin_done(self):
        self._done_count[0] += 1
        if self._done_count[0] >= self._card_count[0] and self._card_count[0] > 0 and self._alive[0]:
            run_on_ui_thread(self._remove_all_cards_then_empty)

    def _remove_all_cards_then_empty(self):
        try:
            from android.animation import ObjectAnimator, AnimatorSet, Animator
            container = self._results_container
            count = container.getChildCount()
            if count == 0:
                self._show_all_up_to_date()
                return

            finished = [0]

            class _FadeListener(dynamic_proxy(Animator.AnimatorListener)):
                def __init__(self, view, fragment, total):
                    super().__init__()
                    self._view = view
                    self._fragment = fragment
                    self._total = total

                def onAnimationEnd(self, *args):
                    try:
                        parent = self._view.getParent()
                        if parent is not None:
                            parent.removeView(self._view)
                    except Exception:
                        pass
                    finished[0] += 1
                    if finished[0] >= self._total and self._fragment._alive[0]:
                        self._fragment._show_all_up_to_date()

                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            for i in range(count):
                child = container.getChildAt(i)
                if child is None:
                    finished[0] += 1
                    continue
                fade = ObjectAnimator.ofFloat(child, "alpha", child.getAlpha(), 0.0)
                slide = ObjectAnimator.ofFloat(child, "translationX", 0.0, float(AndroidUtilities.dp(40)))
                anim = AnimatorSet()
                anim.playTogether(fade, slide)
                anim.setDuration(200)
                anim.setStartDelay(i * 40)
                anim.addListener(_FadeListener(child, self, count))
                anim.start()
        except Exception as e:
            log(f"pluginsUpdates: _remove_all_cards_then_empty error: {e}")
            self._show_all_up_to_date()

    def _on_card_removed(self):
        self._card_count[0] -= 1
        remaining = self._card_count[0]
        if remaining <= 0 and self._alive[0]:
            run_on_ui_thread(self._show_all_up_to_date)
        elif remaining == 1 and self._alive[0]:
            run_on_ui_thread(self._hide_update_all_btn_animated)
        elif remaining > 1 and self._alive[0]:
            run_on_ui_thread(self._update_update_all_btn_text)

    def _update_update_all_btn_text(self):
        # icon-only button — no text to update
        pass

    def _hide_update_all_btn_animated(self):
        # right_btn flies right off screen, fades out before reaching clip boundary
        try:
            from android.animation import AnimatorSet, ObjectAnimator, Animator
            from android.view.animation import AccelerateInterpolator
            from java import dynamic_proxy

            btn = self._bar_right_btn
            dp = AndroidUtilities.dp

            try:
                display = self._act.getWindowManager().getDefaultDisplay()
                from android.graphics import Point
                pt = Point()
                display.getSize(pt)
                screen_w = float(pt.x)
            except Exception:
                screen_w = float(dp(360))

            loc = [0, 0]
            btn.getLocationOnScreen(loc)
            btn_right_on_screen = float(loc[0]) + float(btn.getWidth())
            throw = screen_w - btn_right_on_screen + screen_w + float(dp(20))

            slide = ObjectAnimator.ofFloat(btn, "translationX", 0.0, throw)
            slide.setDuration(320)
            slide.setInterpolator(AccelerateInterpolator(2.2))

            # fade completes well before btn reaches screen edge — seamless disappear
            fade = ObjectAnimator.ofFloat(btn, "alpha", 1.0, 0.0)
            fade.setDuration(160)
            fade.setInterpolator(AccelerateInterpolator(1.8))

            fragment_ref = self

            class _Done(dynamic_proxy(Animator.AnimatorListener)):
                def onAnimationEnd(self, *args):
                    try:
                        btn.setVisibility(4)
                        btn.setTranslationX(0.0)
                        btn.setAlpha(1.0)
                        # shift bar_row to center: half of (btn_square + island_gap)
                        shift = float(fragment_ref._bar_btn_square + fragment_ref._bar_island_gap) / 2.0
                        from android.view.animation import DecelerateInterpolator as _DI
                        center_anim = ObjectAnimator.ofFloat(fragment_ref._bar_island, "translationX", 0.0, shift)
                        center_anim.setDuration(300)
                        center_anim.setInterpolator(_DI(2.0))
                        center_anim.start()
                    except Exception as e:
                        log(f"pluginsUpdates: center shift error: {e}")
                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            s = AnimatorSet()
            s.playTogether(slide, fade)
            s.addListener(_Done())
            s.start()
        except Exception as e:
            log(f"pluginsUpdates: _hide_update_all_btn_animated error: {e}")
            try:
                self._bar_right_btn.setVisibility(4)
            except Exception:
                pass

    def _show_all_up_to_date(self):
        try:
            from android.animation import AnimatorSet, ObjectAnimator, Animator
            from android.view.animation import AccelerateInterpolator
            from java import dynamic_proxy

            island = self._bar_island
            dp = AndroidUtilities.dp

            try:
                display = self._act.getWindowManager().getDefaultDisplay()
                from android.graphics import Point
                pt = Point()
                display.getSize(pt)
                screen_h = float(pt.y)
            except Exception:
                screen_h = float(dp(800))

            # cancel any in-flight right_btn slide before fly-out
            try:
                self._bar_right_btn.animate().cancel()
                self._bar_right_btn.setTranslationX(0.0)
                self._bar_right_btn.setAlpha(1.0)
            except Exception:
                pass

            fly_out = ObjectAnimator.ofFloat(island, "translationY", island.getTranslationY(), screen_h * 0.4)
            fly_out.setDuration(260)
            fly_out.setInterpolator(AccelerateInterpolator(1.8))

            fade_out = ObjectAnimator.ofFloat(island, "alpha", island.getAlpha(), 0.0)
            fade_out.setDuration(180)
            fade_out.setInterpolator(AccelerateInterpolator())

            out_set = AnimatorSet()
            out_set.playTogether(fly_out, fade_out)

            empty_card = self._build_all_up_to_date_card()
            empty_card.setAlpha(0.0)
            lp = FrameLayout.LayoutParams(-2, -2)
            lp.gravity = Gravity.CENTER
            lp.leftMargin = dp(16)
            lp.rightMargin = dp(16)
            lp.topMargin = dp(-80)
            self._content_view.addView(empty_card, lp)

            fragment_ref = self

            class _OutDone(dynamic_proxy(Animator.AnimatorListener)):
                def __init__(self): super().__init__()
                def onAnimationEnd(self, *args):
                    try:
                        fragment_ref._apply_bar_empty_mode(True)
                        island.setTranslationX(0.0)
                        island.setTranslationY(float(dp(16)))
                        island.setScaleX(0.85)
                        island.setScaleY(0.85)
                        island.setAlpha(0.0)
                        fragment_ref._show_bar()
                        fade_in = ObjectAnimator.ofFloat(empty_card, "alpha", 0.0, 1.0)
                        fade_in.setDuration(300)
                        fade_in.start()
                    except Exception as e:
                        log(f"pluginsUpdates: _show_all_up_to_date bar-in error: {e}")
                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            out_set.addListener(_OutDone())
            out_set.start()
        except Exception as e:
            log(f"pluginsUpdates: _show_all_up_to_date error: {e}")

    def _build_all_up_to_date_card(self):
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
        except Exception as e:
            log(f"pluginsUpdates: _build_all_up_to_date_card bg error: {e}")

        try:
            from org.telegram.ui.Components import RLottieImageView
            from org.telegram.messenger import R as R_tg
            lottie = RLottieImageView(act)
            lottie.setAnimation(getattr(R_tg.raw, "done"), dp(144), dp(144))
            lottie.setAutoRepeat(False)
            lottie.playAnimation()
            lottie_lp = LinearLayout.LayoutParams(dp(144), dp(144))
            lottie_lp.gravity = Gravity.CENTER_HORIZONTAL
            lottie_lp.bottomMargin = dp(12)
            card.addView(lottie, lottie_lp)
        except Exception as e:
            log(f"pluginsUpdates: _build_all_up_to_date_card lottie error: {e}")

        title_tv = TextView(act)
        title_tv.setText(str(strings["updates_up_to_date_title"]))
        title_tv.setTextColor(self._text_primary)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        title_tv.setGravity(Gravity.CENTER)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception as e:
            log(f"pluginsUpdates: _build_all_up_to_date_card title typeface error: {e}")
        title_lp = LinearLayout.LayoutParams(-2, -2)
        title_lp.gravity = Gravity.CENTER_HORIZONTAL
        title_lp.bottomMargin = dp(4)
        card.addView(title_tv, title_lp)

        tv = TextView(act)
        tv.setText(str(strings["updates_all_up_to_date"]))
        tv.setTextColor(self._text_gray)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        tv.setGravity(Gravity.CENTER)
        card.addView(tv, LinearLayout.LayoutParams(-2, -2))

        try:
            from com.exteragram.messenger.plugins import PluginsController
            from hook_utils import find_class, get_private_field
            ArrayList = find_class("java.util.ArrayList")
            plugins_map = PluginsController.getInstance().plugins
            plugin_list = ArrayList(plugins_map.values())
            total = plugin_list.size()
            active = 0
            for j in range(total):
                p = plugin_list.get(j)
                try:
                    if get_private_field(p, "isEnabled"):
                        active += 1
                except Exception:
                    pass
            total_packit = sum(len(_read_index(None, str(repo.get("id") or ""))) for repo in _get_repos() if repo.get("id"))

            stat_row = LinearLayout(act)
            stat_row.setOrientation(LinearLayout.HORIZONTAL)
            stat_row.setGravity(Gravity.CENTER)

            rows = [
                (str(strings["updates_stat_installed"]), str(total)),
                (str(strings["updates_stat_active"]),    str(active)),
                (str(strings["updates_stat_packit"]),    str(total_packit)),
            ]
            for i, (label, value) in enumerate(rows):
                cell = LinearLayout(act)
                cell.setOrientation(LinearLayout.VERTICAL)
                cell.setGravity(Gravity.CENTER)

                val_tv = TextView(act)
                val_tv.setText(value)
                val_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
                val_tv.setTextColor(self._text_primary)
                val_tv.setGravity(Gravity.CENTER)
                try:
                    val_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception as e:
                    log(f"pluginsUpdates: stat val typeface error: {e}")

                lbl_tv = TextView(act)
                lbl_tv.setText(label)
                lbl_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
                lbl_tv.setTextColor(self._text_gray)
                lbl_tv.setGravity(Gravity.CENTER)

                cell.addView(val_tv, LinearLayout.LayoutParams(-2, -2))
                cell.addView(lbl_tv, LinearLayout.LayoutParams(-2, -2))

                cell_lp = LinearLayout.LayoutParams(-2, -2)
                if i > 0:
                    cell_lp.leftMargin = dp(28)
                stat_row.addView(cell, cell_lp)

            stat_lp = LinearLayout.LayoutParams(-2, -2)
            stat_lp.gravity = Gravity.CENTER_HORIZONTAL
            stat_lp.topMargin = dp(18)
            card.addView(stat_row, stat_lp)
        except Exception as e:
            log(f"pluginsUpdates: _build_all_up_to_date_card stats error: {e}")

        return card

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

            fragment_ref = self

            class _ExitListener(dynamic_proxy(Animator.AnimatorListener)):
                def onAnimationEnd(self, *args):
                    try:
                        h = measured_height[0]
                        if h <= 0:
                            parent = card_view.getParent()
                            if parent is not None:
                                parent.removeView(card_view)
                            fragment_ref._on_card_removed()
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
                                fragment_ref._on_card_removed()
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
                        fragment_ref._on_card_removed()

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
            self._on_card_removed()

    def _install_update_silent(self, item: dict, download_btn=None, download_icon_view=None, act=None, on_done=None):
        # silent install for non-elyx plugins: download → install_plugin_silent → mark done
        # on_done() is called (on any thread) when install completes or fails
        pid = item["id"]
        repo_id = item.get("repo_id", "")
        repos = _get_repos()
        repo = None
        for r in repos:
            if str(r.get("id") or "") == repo_id:
                repo = r
                break
        if not repo:
            log(f"pluginsUpdates: _install_update_silent repo '{repo_id}' not found")
            if on_done:
                on_done()
            return

        def set_btn_state(state: str):
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
                        log(f"pluginsUpdates: _install_update_silent spinner error: {e}")
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
                log(f"pluginsUpdates: _install_update_silent set_btn_state error: {e}")

        run_on_ui_thread(lambda: set_btn_state("loading"))

        def task():
            try:
                from ...deeplinks.install import _resolvePluginsUrl
                from ...core import install_plugin_silent
                from ...utils.paths import getPluginsDir
                import requests as _requests
                import os as _os

                plugins_url = _resolvePluginsUrl(repo)
                if not plugins_url:
                    log(f"pluginsUpdates: _install_update_silent no plugins url for '{repo_id}'")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    if on_done:
                        on_done()
                    return

                r = _requests.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
                if r.status_code != 200:
                    log(f"pluginsUpdates: _install_update_silent plugins list HTTP {r.status_code} for '{pid}'")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    if on_done:
                        on_done()
                    return

                data = r.json()
                plugins_raw = data.get("plugins", {})
                plugin = None
                if isinstance(plugins_raw, dict):
                    info = plugins_raw.get(pid)
                    if isinstance(info, dict):
                        plugin = {"id": pid, **info}
                elif isinstance(plugins_raw, list):
                    for p in plugins_raw:
                        if isinstance(p, dict) and p.get("id") == pid:
                            plugin = p
                            break

                if not plugin:
                    log(f"pluginsUpdates: _install_update_silent plugin '{pid}' not found in repo")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    if on_done:
                        on_done()
                    return

                url = plugin.get("link") or plugin.get("raw")
                if not url:
                    log(f"pluginsUpdates: _install_update_silent no link for '{pid}'")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    if on_done:
                        on_done()
                    return

                log(f"pluginsUpdates: _install_update_silent downloading '{pid}'")
                plugins_dir = getPluginsDir()
                try:
                    _os.makedirs(plugins_dir, exist_ok=True)
                except Exception:
                    pass
                file_path = _os.path.join(plugins_dir, f".temp_{pid}.plugin")

                dl = _requests.get(url, timeout=30, headers={"User-Agent": "PackIt/1.0"})
                if dl.status_code != 200:
                    log(f"pluginsUpdates: _install_update_silent download HTTP {dl.status_code} for '{pid}'")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    if on_done:
                        on_done()
                    return
                with open(file_path, "wb") as f:
                    f.write(dl.content)
                log(f"pluginsUpdates: _install_update_silent downloaded '{pid}', installing")

                fragment_ref = self

                def on_complete():
                    log(f"pluginsUpdates: _install_update_silent installed '{pid}'")
                    run_on_ui_thread(lambda: set_btn_state("done"))
                    fragment_ref._on_plugin_done()
                    if on_done:
                        on_done()

                def on_error(error):
                    log(f"pluginsUpdates: _install_update_silent install error for '{pid}': {error}")
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                    if on_done:
                        on_done()

                install_plugin_silent(file_path, plugin, repo_id, on_complete=on_complete, on_error=on_error)
            except Exception as e:
                log(f"pluginsUpdates: _install_update_silent task error for '{pid}': {e}")
                run_on_ui_thread(lambda: set_btn_state("idle"))
                if on_done:
                    on_done()

        run_on_queue(task)

    def _on_update_all_click(self):
        if self._is_loading:
            return
        updates = getattr(self, "_current_updates", [])
        if not updates:
            return

        from android.widget import LinearLayout as _LL, FrameLayout as _FL

        # build list of (item, dl_btn, dl_icon) for cards that are still enabled
        container = self._results_container
        pending = []
        for i in range(container.getChildCount()):
            child = container.getChildAt(i)
            if child is None or i >= len(updates):
                continue
            try:
                top_row = child.getChildAt(0)
                if not isinstance(top_row, _LL):
                    continue
                dl_btn = top_row.getChildAt(top_row.getChildCount() - 1)
                dl_icon = dl_btn.getChildAt(0) if isinstance(dl_btn, _FL) else None
                if dl_btn.isEnabled():
                    pending.append((updates[i], dl_btn, dl_icon))
            except Exception as e:
                log(f"pluginsUpdates: _on_update_all_click card {i} error: {e}")

        if not pending:
            return

        # elyx plugins install in parallel via existing _install_update (shows install dialog)
        # non-elyx plugins install sequentially via _install_update_silent: done[i] → start[i+1]
        from ...core import _is_elyx_plugin

        elyx_items = [(item, btn, icon) for item, btn, icon in pending if _is_elyx_plugin(item)]
        silent_items = [(item, btn, icon) for item, btn, icon in pending if not _is_elyx_plugin(item)]

        for item, btn, icon in elyx_items:
            self._install_update(item, btn, icon, self._act)

        if not silent_items:
            return

        # sequential chain: install silent_items[0], on done → install silent_items[1], ...
        def run_chain(idx: int):
            if idx >= len(silent_items):
                return
            item, btn, icon = silent_items[idx]
            log(f"pluginsUpdates: update-all silent chain [{idx+1}/{len(silent_items)}] start '{item['id']}'")
            self._install_update_silent(item, btn, icon, self._act, on_done=lambda: run_chain(idx + 1))

        run_chain(0)

    def _show_updates(self, updates: list):
        try:
            act = self._act
            dp = AndroidUtilities.dp
            container = self._results_container
            container.setPadding(dp(12), dp(12), dp(12), dp(12))

            self._apply_bar_empty_mode(False)
            self._current_updates = list(updates)
            count = len(updates)
            if count == 1:
                # only one update — hide right button (Update all not needed)
                self._bar_right_btn.setVisibility(8)
            else:
                # restore right_btn in case it was hidden or collapsed
                self._bar_right_btn.setVisibility(0)
                self._bar_right_btn.setAlpha(1.0)
                self._bar_right_btn.setTranslationY(0.0)
                # reset bar_row centering shift from previous hide animation
                self._bar_island.setTranslationX(0.0)
                self._bar_right_btn.setOnClickListener(OnClickListener(lambda v: self._on_update_all_click()))
            self._show_bar()
            self._card_count[0] = count
            self._done_count[0] = 0
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
            new_frag.setTitle(str(strings["updates_title"]), False, 0)
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

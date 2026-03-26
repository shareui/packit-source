import json
import os
import threading

from android.view import Gravity
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
    # returns dict: plugin_id -> plugin_info
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
    # reason: "hash_diff_newer" | "state_changed"
    repos = _get_repos()
    updates = []

    for repo in repos:
        rm_rid = str(repo.get("id") or "")
        repo_url = str(repo.get("url") or "").strip()
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

            # Outdated means a non-latest version was installed — no hash available for it,
            # so skip hash comparison and check purely by version
            is_outdated_marker = local_hash == "Outdated" or local_bithash == "Outdated"
            if is_outdated_marker:
                if repo_ver > local_ver:
                    updates.append({
                        "id": pid,
                        "repo_id": rm_rid,
                        "local_version": str(entry.get("version") or ""),
                        "repo_version": str(repo_info.get("version") or ""),
                        "reason": "hash_diff_newer",
                    })
                continue

            # compare hashes — pick matching type
            hash_matches = True
            if local_hash and repo_hash:
                hash_matches = local_hash == repo_hash
            elif local_bithash and repo_bithash:
                hash_matches = local_bithash == repo_bithash

            if hash_matches:
                continue

            # hash differs — determine reason
            if repo_ver > local_ver:
                updates.append({
                    "id": pid,
                    "repo_id": rm_rid,
                    "local_version": str(entry.get("version") or ""),
                    "repo_version": str(repo_info.get("version") or ""),
                    "reason": "hash_diff_newer",
                })
            else:
                # same or older version — check if state changed
                local_state = str(entry.get("state") or "")
                repo_state = str(repo_info.get("state") or "")
                if local_state != repo_state:
                    updates.append({
                        "id": pid,
                        "repo_id": rm_rid,
                        "local_version": str(entry.get("version") or ""),
                        "repo_version": str(repo_info.get("version") or ""),
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

        # centered spinner matching PluginList style
        self._spinner = None
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
                    run_on_ui_thread(lambda: self._show_empty("The index did not produce any results") if alive[0] else None)
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

    def _show_updates(self, updates: list):
        try:
            act = self._act
            dp = AndroidUtilities.dp
            container = self._results_container
            container.setPadding(dp(16), dp(16), dp(16), dp(16))

            for item in updates:
                tv = TextView(act)
                pid = item["id"]
                local_v = item["local_version"]
                repo_v = item["repo_version"]
                reason = item["reason"]

                if reason == "hash_diff_newer":
                    label = f"{pid}  {local_v} → {repo_v}"
                else:
                    label = f"{pid}  {local_v} (state changed)"

                tv.setText(label)
                tv.setTextColor(self._text_primary)
                tv.setTextSize(1, 15)
                tv.setPadding(0, dp(8), 0, dp(8))
                container.addView(tv, LayoutHelper.createLinear(-1, -2))
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

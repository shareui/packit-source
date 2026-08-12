# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ...utils.netQueue import run_io
import re
import json
import threading
from collections import deque
from time import time
from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, VideoView, HorizontalScrollView
from android.util import TypedValue
from android.text import TextWatcher, InputType, TextUtils
from android.view.inputmethod import EditorInfo
from android.graphics.drawable import GradientDrawable
from android.media import MediaPlayer
from java import dynamic_proxy
import os
from hook_utils import find_class
import requests
from android_utils import run_on_ui_thread
from client_utils import get_last_fragment, run_on_queue
from ui.bulletin import BulletinHelper
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView, EditTextBoldCursor
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper, BackupImageView, EditTextBoldCursor failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation, R as R_tg failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from android_utils import OnClickListener
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.utils.text import LocaleUtils
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.utils.text import LocaleUtils failed: {e}")
try:
    from org.telegram.ui.ActionBar import ActionBarPopupWindow
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import ActionBarPopupWindow failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"import android.net import Uri failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger.browser import Browser
except Exception:
    Browser = None
try:
    from androidx.core.content import ContextCompat
except Exception as e:
    import android_utils as _au; _au.log(f"import androidx.core.content import ContextCompat failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.graphics.drawable import GradientDrawable, RippleDrawable
except Exception as e:
    import android_utils as _au; _au.log(f"import android.graphics.drawable import GradientDrawable, RippleDrawable failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.graphics import Color as AColor, PorterDuff
except Exception as e:
    import android_utils as _au; _au.log(f"import android.graphics import Color, PorterDuff failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.content.res import ColorStateList as AColorStateList
except Exception as e:
    import android_utils as _au; _au.log(f"import android.content.res import ColorStateList failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.view import View as AView, Gravity as AGravity
except Exception as e:
    import android_utils as _au; _au.log(f"import android.view import View, Gravity failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from android.widget import FrameLayout as AFrame, LinearLayout as ALinear, TextView as AText, ImageView as AImage
except Exception as e:
    import android_utils as _au; _au.log(f"import android.widget import FrameLayout, LinearLayout, TextView, ImageView failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()

from .helpers import uiHelpers
from .sheets.RepoBottomSheet import show_repo_sheet
from .sheets.SortBottomSheet import show_sort_menu
from .sheets.AISearchSheet import show_ai_search_sheet
from .filter.filterDrawer import show_tag_drawer
from ...utils import search as search_mod
from .filter import filterEngine as tag_mod
from .helpers.PluginActions import copy_plugin_link, share_plugin_file, view_plugin_code, report_plugin, download_plugin_file, translate_plugin
from ...utils.media import playSound
from ...core import install_plugin
from . import card as _card


from .helpers.utils import (
    _count_active_repos, _plural_form, _format_plural, _build_stats_label,
    _build_plugin_count_label, _parse_version, _check_app_version,
    _filter_unavailable,
)

class InstallUI:
    def __init__(self, plugin):
        self.plugin = plugin
        self.repoManager = plugin.repoManager
        self._reload_in_flight = set()
        logx(f"InstallUI: created id={id(self)}", True)

    def _parse_github_url(self, url):
        # returns (owner, repo) for github OR gitlab urls (repo / raw / api
        # forms) so the repo picker shows "<owner> • <repo>" for both. owner is
        # the org/user (top namespace) nickname; gitlab groups/subgroups are
        # supported too.
        try:
            if not url:
                return None, None
            github_patterns = [
                r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
                r'raw\.githubusercontent\.com/([^/]+)/([^/]+)/',
                r'api\.github\.com/repos/([^/]+)/([^/]+)',
            ]
            for pattern in github_patterns:
                match = re.search(pattern, url)
                if match:
                    owner = match.group(1)
                    repo = match.group(2).replace('.git', '')
                    return owner, repo
            # gitlab: the namespace may be nested (groups/subgroups); the ref
            # path is split off by '/-/' (…/-/raw/…, …/-/blob/…, …/-/tree/…)
            gl = re.search(r'gitlab\.com/(.+)', url)
            if gl:
                path = re.split(r'/-/', gl.group(1))[0].strip('/')
                segs = [s for s in path.split('/') if s]
                if len(segs) >= 2 and segs[0] not in (
                    'api', 'dashboard', 'explore', 'groups', 'users', 'projects'
                ):
                    owner = segs[0]
                    repo = segs[-1].replace('.git', '')
                    return owner, repo
            return None, None
        except Exception:
            return None, None

    def _apply_press_scale(self, view):
        uiHelpers.apply_press_scale(view)

    def _apply_press_scale_on_target(self, view, target):
        uiHelpers.apply_press_scale_on_target(view, target)

    def _create_close_button(self, act, text=None):
        return uiHelpers.create_close_button(act, text)

    def _setup_bottom_sheet(self, sheet):
        uiHelpers.setup_bottom_sheet(sheet)

    def _create_rounded_bg(self, color):
        return uiHelpers.create_rounded_bg(color)

    def _format_file_size(self, bytes_val):
        return uiHelpers.format_file_size(bytes_val)

    def _make_info_chip(self, act, text, color_key, size_sp=11):
        return uiHelpers.make_info_chip(act, text, color_key, size_sp)

    def _create_pill(self, act, background, pressed, padding_h=14, padding_v=8):
        return uiHelpers.create_pill(act, background, pressed, padding_h, padding_v)

    def _resolve_icon(self, name):
        return uiHelpers.resolve_icon(name)

    def _get_theme_colors(self):
        return uiHelpers.get_theme_colors()

    def open(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        repos = []
        try:
            for r in (self.plugin.repoManager.getRepositories() or []):
                try:
                    if not r or not r.get("enabled"):
                        continue
                    # the url is what makes a repository usable; the name is a
                    # label, and requiring one meant a source someone had
                    # renamed to nothing dropped out of the catalogue — with
                    # every source nameless, the screen refused to open at all
                    url = str(r.get("url") or "").strip()
                    if url:
                        repos.append(r)
                except Exception:
                    continue
        except Exception:
            pass
        if not repos:
            BulletinHelper.show_error(str(strings["pl_no_repos"]))
            return
        if settings.get("skip_repository_selection", False):
            self._open_all_repos_plugins()
            return
        if len(repos) == 1:
            self._open_repo_plugins(repos[0])
            return
        show_repo_sheet(self, repos)

    def _create_circular_loading(self, act, size_dp=20):
        return uiHelpers.create_circular_loading(act, size_dp)

    def _create_center_loading_animation(self, parent_layout):
        return uiHelpers.create_center_loading_animation(parent_layout)

    def _reload_current_plugins(self, repo_id=None):
        delegate = getattr(self, '_active_delegate', None)
        reload_key = (id(delegate), repo_id)
        logx(f"InstallUI: _reload_current_plugins called id={id(delegate)} repo_id='{repo_id}'", True)
        if reload_key in self._reload_in_flight:
            logx(f"InstallUI: _reload_current_plugins skipped, already in flight for key={reload_key}", True)
            return
        self._reload_in_flight.add(reload_key)

        def load_task():
            try:
                if not repo_id:
                    repos = self.repoManager.getRepositories()
                    all_plugins = []
                    for repo in repos:
                        if not repo.get("enabled"): continue
                        r_id = (repo.get("id") or "").strip()
                        repo_url = (repo.get("url") or "").strip()
                        if not repo_url: continue
                        try:
                            plugins_url = repo_url
                            if r_id:
                                try:
                                    from org.telegram.messenger import ApplicationLoader
                                except Exception as e:
                                    pass
                                import os
                                from ...utils.paths import getRepoCachePath
                                cache_path = getRepoCachePath(r_id)
                                if os.path.exists(cache_path):
                                    with open(cache_path, "r", encoding="utf-8") as f:
                                        cached = json.load(f)
                                    resolved = cached.get("repomap", {}).get("plugins") or repo_url
                                    plugins_url = resolved

                            response = requests.get(plugins_url, timeout=10)
                            if response.status_code != 200: continue
                            config = response.json()
                            plugins = config.get("plugins", {})
                            if isinstance(plugins, dict):
                                for pluginId, info in plugins.items():
                                    if isinstance(info, dict):
                                        all_plugins.append({"id": pluginId, "repo_name": repo.get("name", "Unknown"), "_repo_id": r_id, **info})
                            elif isinstance(plugins, list):
                                for item in plugins:
                                    if isinstance(item, dict) and item.get("id"):
                                        all_plugins.append({"id": item.get("id"), "repo_name": repo.get("name", "Unknown"), "_repo_id": r_id, **item})
                        except Exception as e:
                            pass
                    run_on_ui_thread(lambda: self._update_current_fragment_plugins(all_plugins))
                else:
                    repos = self.repoManager.getRepositories()
                    repo = next((r for r in repos if r.get("id") == repo_id), None)
                    if not repo: return
                    repo_url = (repo.get("url") or "").strip()
                    plugins_url = repo_url
                    try:
                        from org.telegram.messenger import ApplicationLoader
                    except Exception as e:
                        pass
                    import os
                    from ...utils.paths import getRepoCachePath
                    cache_path = getRepoCachePath(repo_id)
                    if os.path.exists(cache_path):
                        with open(cache_path, "r", encoding="utf-8") as f:
                            cached = json.load(f)
                        resolved = cached.get("repomap", {}).get("plugins") or repo_url
                        plugins_url = resolved

                    r = requests.get(plugins_url, timeout=20)
                    if r.status_code != 200:
                        raise Exception(f"HTTP {r.status_code}")
                    config = r.json()
                    plugins_raw = config.get("plugins", [])
                    plugins = []
                    if isinstance(plugins_raw, dict):
                        for pid, info in plugins_raw.items():
                            if isinstance(info, dict):
                                plugins.append({"id": pid, **info})
                    elif isinstance(plugins_raw, list):
                        for item in plugins_raw:
                            if isinstance(item, dict) and item.get("id"):
                                plugins.append(item)
                    # the sources screen has no other way to know how big a
                    # source is: repomap only points at this file by url
                    try:
                        from ...utils import repoStats
                        repoStats.remember(repo_id, plugins=len(plugins))
                    except Exception as e:
                        logx(f"InstallUI: repo stats write failed: {e}", True)
                    run_on_ui_thread(lambda: self._update_current_fragment_plugins(plugins))
            except Exception as e:
                BulletinHelper.show_error(str(strings["pl_load_failed"]))
                run_on_ui_thread(lambda: self._update_current_fragment_plugins([]))
            finally:
                self._reload_in_flight.discard(reload_key)
        run_io(load_task)

    def _open_all_repos_plugins(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        self._show_plugins_universal(strings["all_repositories"], [])
        self._reload_current_plugins(None)

    def _update_plugins_in_fragment(self, plugins):
        try:
            fragment = get_last_fragment()
            if not fragment:
                return
            self._show_plugins_universal(self.title if hasattr(self, 'title') else "Plugins", plugins)
        except Exception as e:
            pass

    def _open_repo_plugins(self, repo):
        repo_name = repo.get("name") or strings["unnamed"]
        repo_url = (repo.get("url") or "").strip()
        if not repo_url:
            BulletinHelper.show_error(str(strings["pl_repo_url_empty"]))
            return
        fragment = get_last_fragment()
        if not fragment:
            return
        repo_id = (repo.get("id") or "").strip()
        self._show_plugins_universal(repo_name, [], repo_id=repo_id)
        self._reload_current_plugins(repo_id)

    def _update_current_fragment_plugins(self, plugins):
        try:
            delegate = getattr(self, '_active_delegate', None)
            if not delegate or not hasattr(delegate, 'plugins'):
                # fallback: try via last fragment
                fragment = get_last_fragment()
                if fragment and hasattr(fragment, 'getDelegate') and fragment.getDelegate():
                    d = fragment.getDelegate()
                    if hasattr(d, 'plugins'):
                        delegate = d
            if not delegate:
                logx(f"InstallUI: _update_current_fragment_plugins no delegate, plugins={len(plugins) if plugins else 0}", True)
                return

            delegate.plugins = _filter_unavailable(plugins)
            delegate.filtered_plugins = []
            delegate.visible_plugins = []
            delegate.search_index = search_mod.build_index(delegate.plugins)

            if hasattr(delegate, 'subtitle'):
                delegate.subtitle.setText(_build_plugin_count_label(len(delegate.plugins)))

            cb = getattr(delegate, '_on_data_ready_cb', None)
            # signal gate that data is ready (fires finish if anim also done)
            if cb:
                logx(f"InstallUI: _update_current_fragment_plugins id={id(delegate)} branch=cb plugins={len(delegate.plugins)}", True)
                delegate._on_data_ready_cb = None
                cb()
            elif hasattr(delegate, 'results_container') and delegate.results_container:
                logx(f"InstallUI: _update_current_fragment_plugins id={id(delegate)} branch=direct_rebuild plugins={len(delegate.plugins)}", True)
                run_on_ui_thread(lambda: delegate.build_list_with_sort("alpha_az"))
            else:
                # data arrived before beforeCreateView, gate does not exist yet, flag it for build_list_view
                logx(f"InstallUI: _update_current_fragment_plugins id={id(delegate)} branch=flag_before_view plugins={len(delegate.plugins)}", True)
                delegate._data_ready_before_view = True
        except Exception as e:
            logx(f"InstallUI: _update_current_fragment_plugins error: {e}", False)

    def _show_plugins_universal(self, repo_name: str, plugins: list, repo_id: str = ""):
        fragment = get_last_fragment()
        if not fragment:
            return
        try:
            delegate = self.PluginListFragment(self, repo_name, plugins, show_loading_initial=True, repo_id=repo_id)
            self._active_delegate = delegate
            new_fragment = UniversalFragment(delegate)
            fragment.presentFragment(new_fragment)
            try:
                new_fragment.setTitle(strings["catalog_title"], False, 0)
                actionBar = new_fragment.getActionBar()
                if actionBar:
                    actionBar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                    try:
                        from org.telegram.messenger import R as R_tg
                        back_icon = getattr(R_tg.drawable, 'ic_ab_back', 0)
                        if back_icon:
                            actionBar.setBackButtonImage(back_icon)
                            actionBar.setBackButtonContentDescription("Back")
                            try:
                                back_button = actionBar.getBackButton()
                                if back_button:
                                    def _on_back_click(v):
                                        f = get_last_fragment()
                                        if f: f.finishFragment()
                                    back_button.setOnClickListener(OnClickListener(_on_back_click))
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception as e:
                pass
        except Exception as e:
            pass

    class PluginListFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
        def __init__(self, install_ui, title, plugins, show_loading_initial=False, repo_id=""):
            super().__init__()
            self.install_ui = install_ui
            self.title = title
            self.repo_id = repo_id
            self.plugins = _filter_unavailable(plugins)
            self.show_loading_initial = show_loading_initial
            # skip the pointless empty-index build (json+dlopen on the click path)
            self.search_index = search_mod.build_index(self.plugins) if self.plugins else None
            self.last_search_query = None
            self.filtered_plugins = []
            self.visible_plugins = []
            self.lazy_load_queue = deque()
            self.is_loading = False
            self.scroll_listener = None
            self.current_sort_type = "alpha_az"
            # None = untouched (no filter). A set is what the drawer applied,
            # and an empty one means "nothing selected" — which shows nothing,
            # not everything.
            self.selected_tags = None
            self.selected_authors = None
            self.selected_app_versions = None
            self.selected_saved = None
            self._active_drawer = None
            self.batch_size = 10
            self._ai_result_active = False
            self._ai_result_plugins = []
            self.loading_container = None
            self.loading_video = None
            self._data_ready_before_view = False
            self._bottom_spinner = None
            self._live_search_spinner = None
            self._live_search_spinner_view = None
            self._load_trigger_y = -1  # scrollY threshold to fire next load_more; -1 = disarmed
            logx(f"InstallUI: PluginListFragment created id={id(self)} title='{title}' repo_id='{repo_id}' install_ui_id={id(install_ui)}", True)

        def onFragmentCreate(self, *_):
            try:
                from ..NoInternetBanner import NoInternetBanner as _NIB
                self._no_internet_banner = _NIB(None)

                def _on_restore():
                    plugin_count = len(self.plugins) if self.plugins else 0
                    logx(f"InstallUI: _on_restore called, plugins={plugin_count}, repo_id='{self.repo_id}'", True)
                    try:
                        lc = getattr(self, 'loading_container', None)
                        rc = getattr(self, 'results_container', None)
                        logx(f"InstallUI: _on_restore loading_container={lc is not None}, results_container={rc is not None}", True)
                        if lc and rc:
                            lc.setVisibility(AView.VISIBLE)
                            rc.setVisibility(AView.GONE)
                            logx("InstallUI: _on_restore visibility set — loading visible, results gone", True)
                    except Exception as ex:
                        logx(f"InstallUI: _on_restore visibility error: {ex}", True)
                    logx("InstallUI: _on_restore triggering _reload_current_plugins", True)
                    self.install_ui._reload_current_plugins(self.repo_id)

                self._no_internet_banner._on_network_restored_callback = _on_restore
                self._no_internet_banner.register()
                logx(f"InstallUI: NoInternetBanner registered for fragment id={id(self)}", True)
            except Exception as e:
                logx(f"InstallUI: NoInternetBanner register error: {e}", False)

        def onFragmentDestroy(self, *_):
            logx(f"InstallUI: PluginListFragment destroyed id={id(self)} title='{getattr(self, 'title', '?')}' repo_id='{getattr(self, 'repo_id', '?')}'", True)
            try:
                banner = getattr(self, '_no_internet_banner', None)
                if banner:
                    banner.unregister()
                    self._no_internet_banner = None
            except Exception as e:
                logx(f"InstallUI: NoInternetBanner unregister error: {e}", False)
            try:
                if hasattr(self, 'content_view') and self.content_view is not None:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import unregister_bulletin_container
                    unregister_bulletin_container(self.content_view)
                    parent = self.content_view.getParent()
                    if parent is not None:
                        parent.removeView(self.content_view)
            except Exception:
                pass
            try:
                if hasattr(self, 'search_hooks'):
                    for hook in self.search_hooks:
                        self.install_ui.plugin.unhook_method(hook)
            except Exception:
                pass
            try:
                from ...utils.localConfig import LocalConfig
                showTgc = LocalConfig.get("showTgc", False)
                if not showTgc:
                    count = LocalConfig.get("installUiOpenCount", 0) + 1
                    LocalConfig.set("installUiOpenCount", count)
                    if count >= 2:
                        from android_utils import run_on_ui_thread

                        def _show():
                            try:
                                from .sheets.tgChannelSheet import show_tg_channel_sheet
                                frag = get_last_fragment()
                                if not frag:
                                    return
                                act = frag.getParentActivity()
                                rp = frag.getResourceProvider()
                                if not act:
                                    return
                                show_tg_channel_sheet(act, rp)
                            except Exception as e:
                                pass

                        run_on_ui_thread(_show, 500)
                    else:
                        pass
                else:
                    pass
            except Exception as e:
                pass

        def _handle_repo_select(self, selected):
            if selected == "all":
                self.install_ui._open_all_repos_plugins()
            elif isinstance(selected, dict):
                self.install_ui._open_repo_plugins(selected)

        def beforeCreateView(self):
            # light shell now, heavy chrome a few frames later: build_list_view
            # makes hundreds of python->java calls and used to block the UI
            # thread, freezing the fragment open animation for ~half a second.
            # Data arriving before the chrome is already handled by the
            # _data_ready_before_view flag consumed inside build_list_view.
            from . import listView as _lv
            from android_utils import run_on_ui_thread
            act = get_last_fragment().getContext()
            try:
                bg = self.install_ui._get_theme_colors()["main_bg_color"]
            except Exception:
                from org.telegram.ui.ActionBar import Theme
                bg = Theme.getColor(Theme.key_windowBackgroundGray)
            shell = FrameLayout(act)
            shell.setBackgroundColor(bg)

            def _deferred():
                try:
                    view = _lv.build_list_view(self)
                    if view is not None:
                        shell.addView(view, FrameLayout.LayoutParams(-1, -1))
                except Exception as e:
                    logx(f"InstallUI: deferred build_list_view error: {e}", False)
            # let the open animation start smoothly before the heavy build
            run_on_ui_thread(_deferred, 30)
            return shell

        def getTitle(self):
            return self.title

        def onBackPressed(self):
            try:
                if self._active_drawer is not None and self._active_drawer._is_open:
                    self._active_drawer.close()
                    self._active_drawer = None
                    return True
            except Exception:
                pass
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
                    fragment = get_last_fragment()
                    if fragment:
                        fragment.finishFragment()
                except Exception as e:
                    pass

        def _get_localized_description(self, plugin):
            about = plugin.get("about", [])
            if isinstance(about, list) and len(about) >= 2:
                try:
                    from java.util import Locale
                    current_lang = Locale.getDefault().getLanguage()
                    if current_lang == "ru":
                        return about[1] if len(about) > 1 else about[0]
                    else:
                        return about[0]
                except Exception:
                    return about[0]
            return str(plugin.get("description") or "")

        def _cache_settings(self):
            # read all card settings once per build; avoid repeated Java round-trips in make_item
            self._s_card_padding = settings.get("card_padding", 12)
            self._s_card_radius = settings.get("card_radius", 18)
            self._s_card_name_size = float(settings.get("card_name_size", 20))
            self._s_card_id_size = float(settings.get("card_id_size", 13))
            self._s_card_desc_size = float(settings.get("card_desc_size", 15))
            self._s_card_show_icon = settings.get("card_show_icon", True)
            self._s_card_show_id = settings.get("card_show_id", True)
            self._s_card_show_desc = settings.get("card_show_desc", True)
            self._s_icon_size_dp = settings.get("card_icon_size", 67)
            self._s_sticker_radius = settings.get("sticker_radius", 18)
            self._s_show_default_sticker = settings.get("show_default_sticker", False)
            self._s_show_plugin_tags = settings.get("show_plugin_tags", True)
            self._s_show_size = settings.get("show_plugin_size", False)
            self._s_show_min_ver = settings.get("show_plugin_min_version", False)
            self._s_show_deps = settings.get("show_plugin_deps_count", False)
            self._s_show_view_button = settings.get("show_view_button", False)
            self._s_show_details_button = settings.get("show_details_button", False)
            self._s_chip_ver_size = float(settings.get("chip_ver_size", 11))
            self._s_chip_deps_size = float(settings.get("chip_deps_size", 11))
            self._s_chip_size_size = float(settings.get("chip_size_size", 11))
            self._s_fuzzy_search = settings.get("fuzzy_search", False)
            self._s_relocate_install = settings.get("relocate_install", False)
            self._s_relocate_copy = settings.get("relocate_copy_link", False)
            self._s_relocate_share = settings.get("relocate_share", False)
            self._s_relocate_code = settings.get("relocate_code", False)
            self._s_relocate_download = settings.get("relocate_download", False)
            self._s_relocate_translate = settings.get("relocate_translate", False)
            self._s_relocate_report = settings.get("relocate_report", False)

        def build_list_with_sort(self, sort_type: str, q=None):
            start_time = time()
            self._cache_settings()
            self.current_sort_type = sort_type
            q = (q or "").strip()
            if q != self.last_search_query:
                self.last_search_query = q
            self.is_loading = True
            self._load_trigger_y = -1
            self._pill_prewarmed = False
            self.results_container.removeAllViews()
            self.visible_plugins = []
            self.lazy_load_queue.clear()
            filtered = []
            if not q:
                filtered = list(self.plugins)
            else:
                isRussian = False
                try:
                    from java.util import Locale
                    isRussian = Locale.getDefault().getLanguage() == "ru"
                except Exception:
                    pass
                fuzzy = self._s_fuzzy_search
                scored = []
                for p in self.plugins:
                    s = search_mod.score(p, q, self.search_index, isRussian, fuzzy)
                    if s[0] < 6:
                        result_plugin = dict(p)
                        result_plugin["_search_similarity"] = search_mod.score_percent(s)
                        scored.append((s, result_plugin))
                scored.sort(key=lambda x: x[0])
                filtered = [p for _, p in scored]

            # None = section never filtered. An empty selection is deliberate
            # and matches nothing — the drawer no longer rewrites it to "all".
            if self.selected_tags is not None:
                filtered = tag_mod.filter_by_tags(filtered, self.selected_tags) if self.selected_tags else []

            if self.selected_authors is not None:
                all_authors = set(
                    str(p.get("author") or "").strip()
                    for p in self.plugins
                    if str(p.get("author") or "").strip() and str(p.get("author") or "").strip().lower() != "unknown"
                )
                # everything selected is the same as no filter; anything less
                # filters (">=" and not "<": a selection holding a stale name
                # is still a filter, a strict-subset test called it none)
                if not self.selected_authors:
                    filtered = []
                elif not (self.selected_authors >= all_authors):
                    filtered = [
                        p for p in filtered
                        if str(p.get("author") or "").strip() in self.selected_authors
                    ]

            if self.selected_app_versions is not None:
                all_versions = set(
                    str(p.get("app_version") or "").strip()
                    for p in self.plugins
                    if str(p.get("app_version") or "").strip() and str(p.get("app_version") or "").strip().lower() != "unknown"
                )
                if not self.selected_app_versions:
                    filtered = []
                elif not (self.selected_app_versions >= all_versions):
                    filtered = [
                        p for p in filtered
                        if str(p.get("app_version") or "").strip() in self.selected_app_versions
                    ]

            if getattr(self, "selected_saved", None) is not None and not self.selected_saved:
                filtered = []
            elif getattr(self, "selected_saved", None) is not None and self.selected_saved != {"saved", "unsaved"}:
                try:
                    from ..PluginActivity.fragment import _read_saved_plugins
                    saved_ids = set(_read_saved_plugins())
                    show_saved = "saved" in self.selected_saved
                    show_unsaved = "unsaved" in self.selected_saved
                    if not (show_saved and show_unsaved):
                        filtered = [
                            p for p in filtered
                            if (str(p.get("id") or "") in saved_ids) == show_saved
                        ]
                except Exception as e:
                    logx(f"pluginList: saved filter error: {e}", False)
            
            if not q:
                if sort_type == "alpha_az":
                    filtered.sort(key=lambda p: (1 if str(p.get("name") or p.get("id") or "")[:1].isdigit() else 0, str(p.get("name") or p.get("id") or "").lower()))
                elif sort_type == "alpha_za":
                    filtered.sort(key=lambda p: (0 if str(p.get("name") or p.get("id") or "")[:1].isdigit() else 1, str(p.get("name") or p.get("id") or "").lower()), reverse=True)
                elif sort_type == "authors":
                    filtered.sort(key=lambda p: str(p.get("author") or "").lower())
            self.filtered_plugins = filtered
            if hasattr(self, 'subtitle'):
                total = len(self.plugins)
                # straight from the two lists. Asking a helper whether a filter
                # "is active" meant the header could disagree with what the list
                # actually holds: its tag universe left out the untagged bucket,
                # so filtering by "Unsorted" (12 of 43) kept the header on 43.
                if len(filtered) != total:
                    self.subtitle.setText(f"{len(filtered)}/{_build_plugin_count_label(total)}")
                else:
                    self.subtitle.setText(_build_plugin_count_label(total))
            fragment = get_last_fragment()
            act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
            if not act:
                act = fragment.getContext() if fragment else None
            if not filtered:
                empty_container = LinearLayout(act)
                empty_container.setOrientation(LinearLayout.VERTICAL)
                empty_container.setGravity(Gravity.CENTER)
                empty_container.setPadding(0, AndroidUtilities.dp(60), 0, AndroidUtilities.dp(60))
                stub_size_dp = self._s_icon_size_dp
                stub_view = ImageView(act)
                try:
                    from android.graphics import PorterDuffColorFilter, PorterDuff
                    stub_view.setScaleType(ImageView.ScaleType.FIT_CENTER)
                    stub_view.setImageResource(R_tg.drawable.plugins_filled)
                    stub_view.setColorFilter(PorterDuffColorFilter(
                        Theme.getColor(Theme.key_featuredStickers_buttonText),
                        PorterDuff.Mode.SRC_IN
                    ))
                    p_stub = AndroidUtilities.dp(16)
                    stub_view.setPadding(p_stub, p_stub, p_stub, p_stub)
                    stub_view.setBackground(Theme.createCircleDrawable(
                        AndroidUtilities.dp(stub_size_dp),
                        Theme.getColor(Theme.key_featuredStickers_addButton)
                    ))
                except Exception:
                    pass
                empty_container.addView(stub_view, LayoutHelper.createLinear(stub_size_dp, stub_size_dp, 0, 0, 0, 16))
                empty = TextView(act)
                empty.setText(strings["no_plugins"])
                empty.setGravity(Gravity.CENTER)
                empty.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                empty.setTextColor(self.secondary_text_color)
                empty_container.addView(empty, LayoutHelper.createLinear(-2, -2))
                self.results_container.addView(empty_container, LayoutHelper.createLinear(-1, -2))
                self.is_loading = False
                # dismiss live spinner if active
                try:
                    spinner = getattr(self, '_live_search_spinner', None)
                    if spinner is not None:
                        spinner.animate().alpha(0.0).setDuration(150).withEndAction(
                            lambda: spinner.setVisibility(View.GONE)
                        ).start()
                    self.results_container.setVisibility(View.VISIBLE)
                except Exception:
                    pass
            else:
                self._load_initial_batch()
            logx(f"Build list took {time() - start_time:.3f}s", True)

        def build_list(self, q):
            self.build_list_with_sort(self.current_sort_type, q)

        def _finish_loading_and_show_plugins(self, content_wrapper):
            logx(f"InstallUI: _finish_loading_and_show_plugins enter id={id(self)} plugins={len(self.plugins) if self.plugins else 0}", True)
            try:
                _banner = getattr(self, '_no_internet_banner', None)
                if _banner:
                    _banner.on_config_loaded()
            except Exception as e:
                logx(f"InstallUI: NoInternetBanner on_config_loaded error: {e}", False)
            try:
                if hasattr(self, 'subtitle'):
                    self.subtitle.setText(_build_plugin_count_label(len(self.plugins)))

                # keep loading_container reference — remove it only after first cards are rendered
                content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))

                if self.plugins and len(self.plugins) > 0:
                    logx(f"InstallUI: _finish_loading_and_show_plugins id={id(self)} branch=build_list_with_sort", True)
                    self._content_wrapper_ref = content_wrapper
                    self.build_list_with_sort("alpha_az")
                else:
                    logx(f"InstallUI: _finish_loading_and_show_plugins id={id(self)} branch=empty_state", True)
                    self._dismiss_loading_container(content_wrapper)
                    self._show_empty_state()
            except Exception as e:
                logx(f"InstallUI: _finish_loading_and_show_plugins error: {e}", False)
                try:
                    self._dismiss_loading_container(content_wrapper)
                    content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))
                    if self.plugins and len(self.plugins) > 0:
                        self.build_list_with_sort("alpha_az")
                    else:
                        self._show_empty_state()
                except Exception as e2:
                    logx(f"InstallUI: _finish_loading_and_show_plugins fallback error: {e2}", False)

        def _dismiss_loading_container(self, content_wrapper=None):
            # fade out then remove the spinner; safe to call multiple times
            lc = self.loading_container
            lv = self.loading_video
            if lc is None:
                logx(f"InstallUI: _dismiss_loading_container id={id(self)} skipped, already None", True)
                return
            logx(f"InstallUI: _dismiss_loading_container enter id={id(self)}", True)
            self.loading_container = None
            self.loading_video = None
            try:
                if lv:
                    d = lv.getDrawable()
                    if d:
                        d.stop()
            except Exception:
                pass
            cw = content_wrapper or getattr(self, '_content_wrapper_ref', None)
            cv = self.content_view

            class _RemoveRunnable(dynamic_proxy(find_class("java.lang.Runnable"))):
                def __init__(self, view, parent_cv, parent_cw):
                    super().__init__()
                    self._view = view
                    self._cv = parent_cv
                    self._cw = parent_cw
                def run(self):
                    for parent in (self._cv, self._cw):
                        try:
                            if parent is not None:
                                parent.removeView(self._view)
                                return
                        except Exception as e:
                            logx(f"InstallUI: _dismiss_loading_container removeView failed: {e}", False)
                    logx("InstallUI: _dismiss_loading_container removeView no parent succeeded", False)

            try:
                lc.animate().alpha(0.0).setDuration(150).withEndAction(_RemoveRunnable(lc, cv, cw)).start()
            except Exception as e:
                logx(f"InstallUI: _dismiss_loading_container animate().start() failed: {e}", False)
                try:
                    cv.removeView(lc)
                except Exception as e2:
                    logx(f"InstallUI: _dismiss_loading_container fallback removeView failed: {e2}", False)

        def _show_empty_state(self):
            try:
                fragment = get_last_fragment()
                act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
                if not act:
                    act = fragment.getContext() if fragment else None
                
                empty_container = LinearLayout(act)
                empty_container.setOrientation(LinearLayout.VERTICAL)
                empty_container.setGravity(Gravity.CENTER)
                empty_container.setPadding(0, AndroidUtilities.dp(60), 0, AndroidUtilities.dp(60))
                
                stub_size_dp = self._s_icon_size_dp
                stub_view = ImageView(act)
                try:
                    from android.graphics import PorterDuffColorFilter, PorterDuff
                    stub_view.setScaleType(ImageView.ScaleType.FIT_CENTER)
                    stub_view.setImageResource(R_tg.drawable.plugins_filled)
                    stub_view.setColorFilter(PorterDuffColorFilter(
                        Theme.getColor(Theme.key_featuredStickers_buttonText),
                        PorterDuff.Mode.SRC_IN
                    ))
                    p_stub = AndroidUtilities.dp(16)
                    stub_view.setPadding(p_stub, p_stub, p_stub, p_stub)
                    stub_view.setBackground(Theme.createCircleDrawable(
                        AndroidUtilities.dp(stub_size_dp),
                        Theme.getColor(Theme.key_featuredStickers_addButton)
                    ))
                except Exception:
                    pass
                empty_container.addView(stub_view, LayoutHelper.createLinear(stub_size_dp, stub_size_dp, 0, 0, 0, 16))
                
                empty = TextView(act)
                empty.setText(strings["no_plugins"])
                empty.setGravity(Gravity.CENTER)
                empty.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                empty.setTextColor(self.secondary_text_color)
                empty_container.addView(empty, LayoutHelper.createLinear(-2, -2))
                
                try:
                    from android.view import View
                    retry = TextView(act)
                    retry.setText(strings.get("retry", "Reload"))
                    retry.setGravity(Gravity.CENTER)
                    retry.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                    retry.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                    retry.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(8), AndroidUtilities.dp(16), AndroidUtilities.dp(8))
                    retry.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(4), 0, Theme.getColor(Theme.key_listSelector)
                    ))
                    
                    class RetryClickListener(dynamic_proxy(find_class("android.view.View$OnClickListener"))):
                        def __init__(self, outer):
                            super().__init__()
                            self.outer = outer
                        def onClick(self, v):
                            logx(f"InstallUI: retry button clicked, repo_id='{self.outer.repo_id}', plugins={len(self.outer.plugins) if self.outer.plugins else 0}", True)
                            try:
                                if hasattr(self.outer, 'loading_container') and self.outer.loading_container:
                                    self.outer.loading_container.setVisibility(View.VISIBLE)
                                    logx("InstallUI: retry — loading_container made visible", True)
                                    if hasattr(self.outer, 'results_container'):
                                        self.outer.results_container.setVisibility(View.GONE)
                                else:
                                    logx(f"InstallUI: retry — no loading_container (is None={self.outer.loading_container is None})", True)
                            except Exception as ex:
                                logx(f"InstallUI: retry visibility error: {ex}", True)
                            logx("InstallUI: retry — calling _reload_current_plugins", True)
                            self.outer.install_ui._reload_current_plugins(self.outer.repo_id)

                    retry.setOnClickListener(RetryClickListener(self))
                    
                    lp_btn = LayoutHelper.createLinear(-2, -2, 0, 16, 0, 0)
                    lp_btn.gravity = Gravity.CENTER_HORIZONTAL
                    empty_container.addView(retry, lp_btn)
                except Exception as e:
                    pass
                
                self.results_container.addView(empty_container, LayoutHelper.createLinear(-1, -2))
                self.is_loading = False
            except Exception as e:
                pass

        def _show_bottom_spinner(self):
            # slide-in from bottom: starts offscreen below, animates up to resting position
            try:
                if getattr(self, '_bottom_spinner', None) is not None:
                    return
                act = get_last_fragment().getContext()
                spinner_frame = FrameLayout(act)
                spinner_frame.setPadding(0, AndroidUtilities.dp(16), 0, AndroidUtilities.dp(16))

                from org.telegram.ui.Components import CircularProgressDrawable
                color = Theme.getColor(Theme.key_dialogLinkSelection)
                size = AndroidUtilities.dp(32)
                thickness = float(AndroidUtilities.dp(3))
                d = CircularProgressDrawable(float(size), thickness, color)
                d.setBounds(0, 0, size, size)

                spinner_img = ImageView(act)
                spinner_img.setImageDrawable(d)
                spinner_img.setScaleType(ImageView.ScaleType.CENTER)
                spinner_frame.addView(spinner_img, FrameLayout.LayoutParams(size, size, Gravity.CENTER))

                slide_offset = float(AndroidUtilities.dp(64))
                spinner_frame.setTranslationY(slide_offset)
                spinner_frame.setAlpha(0.0)
                self.results_container.addView(spinner_frame, LayoutHelper.createLinear(-1, -2))
                spinner_frame.animate().translationY(0.0).alpha(1.0).setDuration(250).start()
                self._bottom_spinner = spinner_frame
            except Exception:
                self._bottom_spinner = None

        def _remove_bottom_spinner(self):
            # slide-out to bottom before removal
            try:
                frame = getattr(self, '_bottom_spinner', None)
                self._bottom_spinner = None
                if frame is None:
                    return
                slide_offset = float(AndroidUtilities.dp(64))
                container_ref = self.results_container

                class RemoveRunnable(dynamic_proxy(find_class("java.lang.Runnable"))):
                    def __init__(self, view, container):
                        super().__init__()
                        self._view = view
                        self._container = container
                    def run(self):
                        try:
                            self._container.removeView(self._view)
                        except Exception:
                            pass

                frame.animate().translationY(slide_offset).alpha(0.0).setDuration(200).withEndAction(
                    RemoveRunnable(frame, container_ref)
                ).start()
            except Exception:
                try:
                    if frame is not None:
                        self.results_container.removeView(frame)
                except Exception:
                    pass

        def _add_items_with_animation(self, items_to_add, animate=True):
            try:
                self._remove_bottom_spinner()
                visible_count = len(self.visible_plugins)
                for idx, item in enumerate(items_to_add):
                    self.results_container.addView(item, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 4))
                    if idx == 0:
                        # first card is in the tree — safe to dismiss the loading spinner now
                        self._dismiss_loading_container()
                        # dismiss live search spinner if active
                        try:
                            spinner = getattr(self, '_live_search_spinner', None)
                            if spinner is not None:
                                spinner.animate().alpha(0.0).setDuration(150).withEndAction(
                                    lambda: spinner.setVisibility(View.GONE)
                                ).start()
                            self.results_container.setVisibility(View.VISIBLE)
                        except Exception:
                            pass
                    if animate:
                        try:
                            item.setAlpha(0.0)
                            delay = idx * 25
                            item.animate().alpha(1.0).setDuration(180).setStartDelay(delay).start()
                        except Exception:
                            pass
                    # when the ~10th card is added, pre-warm the pill GPU texture
                    # so the hardware layer upload happens now, not during user scroll
                    if (visible_count + idx) == 9:
                        self._prewarm_pill()
                self.is_loading = False
                if len(self.visible_plugins) < len(self.filtered_plugins):
                    self._rearm_load_trigger()
            except Exception as e:
                self.is_loading = False

        def _prewarm_pill(self):
            # run a zero-duration alpha cycle so Android uploads the hardware layer texture
            # while the user is still at the top — no visible effect
            pill = getattr(self, '_scroll_top_pill', None)
            if pill is None or getattr(self, '_pill_prewarmed', False):
                return
            self._pill_prewarmed = True
            try:
                pill.animate().alpha(0.01).setDuration(1).withEndAction(
                    lambda: pill.animate().alpha(0.0).setDuration(1).start()
                ).start()
            except Exception:
                pass

        def _rearm_load_trigger(self):
            # posts to UI thread after layout so getHeight() reflects actual sizes
            sv = getattr(self, '_scroll_view', None)
            if sv is None:
                return
            outer = self
            class RearmRunnable(dynamic_proxy(find_class("java.lang.Runnable"))):
                def run(self):
                    try:
                        child = sv.getChildAt(0)
                        if child is None:
                            return
                        content_h = child.getHeight()
                        view_h = sv.getHeight()
                        # trigger when 300dp from bottom
                        trigger = content_h - view_h - AndroidUtilities.dp(300)
                        outer._load_trigger_y = max(0, trigger)
                    except Exception:
                        pass
            try:
                sv.post(RearmRunnable())
            except Exception:
                pass

        def _load_initial_batch(self):
            self.is_loading = True
            batch_size = min(self.batch_size, len(self.filtered_plugins))

            def load_batch():
                try:
                    items_to_add = []
                    for i in range(batch_size):
                        if i < len(self.filtered_plugins):
                            plugin = self.filtered_plugins[i]
                            self.visible_plugins.append(plugin)
                            item = self.make_item(plugin)
                            items_to_add.append(item)

                    run_on_ui_thread(lambda: self._add_items_with_animation(items_to_add))
                except Exception as e:
                    logx(f"InstallUI: _load_initial_batch load_batch error: {e}", False)
                    self.is_loading = False
            threading.Thread(target=load_batch, daemon=True).start()

        def _load_more_items(self):
            if self.is_loading or len(self.visible_plugins) >= len(self.filtered_plugins):
                return
            self.is_loading = True
            start_index = len(self.visible_plugins)
            batch_size = min(self.batch_size, len(self.filtered_plugins) - start_index)
            run_on_ui_thread(self._show_bottom_spinner)

            def load_batch():
                try:
                    items_to_add = []
                    for i in range(batch_size):
                        plugin_index = start_index + i
                        if plugin_index < len(self.filtered_plugins):
                            plugin = self.filtered_plugins[plugin_index]
                            self.visible_plugins.append(plugin)
                            item = self.make_item(plugin)
                            items_to_add.append(item)

                    run_on_ui_thread(lambda: self._add_items_with_animation(items_to_add, animate=False))
                except Exception as e:
                    self.is_loading = False
            threading.Thread(target=load_batch, daemon=True).start()

        def make_item(self, p):
            return _card.make_plugin_card(self, p)

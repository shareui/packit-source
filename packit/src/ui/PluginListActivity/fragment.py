import re
import json
import threading
from collections import deque
from time import time
from android.animation import ObjectAnimator
from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, VideoView, ProgressBar, HorizontalScrollView
from android.util import TypedValue
from android.text import TextWatcher, InputType, TextUtils
from android.view.inputmethod import EditorInfo
from android.graphics.drawable import GradientDrawable
from android.media import MediaPlayer
from java import dynamic_proxy
import os
from hook_utils import find_class
import requests
from android_utils import log, run_on_ui_thread
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

from .RepoBottomSheet import show_repo_sheet
from .SortBottomSheet import show_sort_menu
from .TagsBottomSheet import show_tag_filter_menu
from .service import SearchEngine as search_mod
from .service.PluginActions import copy_plugin_link, share_plugin_file, view_plugin_code, report_plugin, download_plugin_file, translate_plugin
from ...utils.media import playSound
from ...core import install_plugin


def _count_active_repos(repo_manager) -> int:
    try:
        repos = repo_manager.getRepositories() or []
        return sum(1 for r in repos if r and r.get("enabled", True) and str(r.get("url") or "").strip())
    except Exception:
        return 0

def _plural_form(n: int, plural_type: str) -> str:
    # returns "one", "few", or "many" based on count and language plural rule
    if plural_type == "ru":
        # slavic rule: 1→one, 2-4→few, 5+→many (also handles 11-19 edge case)
        mod10 = n % 10
        mod100 = n % 100
        if mod10 == 1 and mod100 != 11:
            return "one"
        if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
            return "few"
        return "many"
    if plural_type == "pl":
        # polish rule
        mod10 = n % 10
        mod100 = n % 100
        if n == 1:
            return "one"
        if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
            return "few"
        return "many"
    # default "en" rule: 1→one, else→many
    return "one" if n == 1 else "many"

def _format_plural(n: int, key_one: str, key_few: str, key_many: str, plural_type: str) -> str:
    form = _plural_form(n, plural_type)
    template = key_many
    if form == "one":
        template = key_one
    elif form == "few":
        template = key_few
    return template.replace("{0}", str(n))

def _build_stats_label(repo_count: int, plugin_count: int) -> str:
    try:
        plural_type = strings["plural_type"]
        repo_str = _format_plural(
            repo_count,
            strings["repo_one"], strings["repo_few"], strings["repo_many"],
            plural_type
        )
        plugin_str = _format_plural(
            plugin_count,
            strings["plugin_one"], strings["plugin_few"], strings["plugin_many"],
            plural_type
        )
        return f"{repo_str} · {plugin_str}"
    except Exception:
        return strings("total_plugins", repo_count, plugin_count)

def _build_plugin_count_label(plugin_count: int) -> str:
    try:
        plural_type = strings["plural_type"]
        plugin_str = _format_plural(
            plugin_count,
            strings["plugin_one"], strings["plugin_few"], strings["plugin_many"],
            plural_type
        )
        return plugin_str
    except Exception:
        return strings("plugin_many", plugin_count)

def _parse_version(v_str):
    try:
        return tuple(int(x) for x in str(v_str).strip().split("."))
    except Exception:
        return (0,)

def _is_min_version_satisfied(plugin_min_ver):
    try:
        from org.telegram.messenger import BuildVars
        app_ver = BuildVars.BUILD_VERSION_STRING
        return _parse_version(app_ver) >= _parse_version(plugin_min_ver)
    except Exception:
        return True

def _filter_unavailable(plugins):
    try:
        from elyx import settings as _s
        if not _s.get("hide_unavailable_plugins", False):
            return plugins
    except Exception:
        return plugins
    result = []
    for p in plugins:
        mv = p.get("min_version")
        if not mv or _is_min_version_satisfied(mv):
            result.append(p)
    return result



class InstallUI:
    def __init__(self, plugin):
        self.plugin = plugin
        self.repoManager = plugin.repoManager
        log(f"InstallUI: created id={id(self)}")

    def _parse_github_url(self, url):
        try:
            if not url:
                return None, None
            patterns = [
                r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
                r'raw\.githubusercontent\.com/([^/]+)/([^/]+)/',
                r'api\.github\.com/repos/([^/]+)/([^/]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    owner = match.group(1)
                    repo = match.group(2).replace('.git', '')
                    return owner, repo
            return None, None
        except Exception:
            return None, None

    def _apply_press_scale(self, view):
        try:
            class _TouchListener(dynamic_proxy(View.OnTouchListener)):
                def __init__(self, fn):
                    super().__init__()
                    self._fn = fn
                def onTouch(self, v, event):
                    return self._fn(v, event)
            def _on_touch(v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.94).scaleY(0.94).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                except Exception:
                    pass
                return False
            view.setOnTouchListener(_TouchListener(_on_touch))
        except Exception:
            pass

    def _create_close_button(self, act, text=None):
        close_btn = FrameLayout(act)
        resolvedText = text if text is not None else strings["close_button"]
        try:
            base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception:
            base_color = Theme.getColor(Theme.key_dialogTextBlue)
        try:
            pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            pressed_color = base_color
        close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base_color, pressed_color
        ))
        close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_text = TextView(act)
        close_text.setText(resolvedText)
        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_text.setTypeface(AndroidUtilities.bold())
        close_text.setGravity(Gravity.CENTER)
        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))
        return close_btn

    def _setup_bottom_sheet(self, sheet):
        for attr in ('setAllowNestedScroll', 'setResizeKeyboardArea', 'setUseSmoothKeyboard',
                     'setUseSmoothKeyboardTransition', 'setAnimateKeyboard'):
            try:
                m = getattr(sheet, attr, None)
                if m and attr in ('setUseSmoothKeyboard', 'setUseSmoothKeyboardTransition', 'setAnimateKeyboard'):
                    if hasattr(sheet, attr):
                        m(True)
                elif m:
                    m(True)
            except Exception:
                pass
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)

    def _create_rounded_bg(self, color):
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadii([
            AndroidUtilities.dp(20), AndroidUtilities.dp(20),
            AndroidUtilities.dp(20), AndroidUtilities.dp(20),
            0, 0, 0, 0
        ])
        bg.setColor(color)
        return bg

    def _format_file_size(self, bytes_val):
        # returns e.g. "123.00 KB" or "1.23 MB"
        if bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.2f} KB"
        return f"{bytes_val / (1024 * 1024):.2f} MB"

    def _make_info_chip(self, act, text, color_key):
        import ctypes
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
        tv.setText(text)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        tv.setTextColor(text_color)
        tv.setBackground(bg)
        tv.setPadding(
            AndroidUtilities.dp(7), AndroidUtilities.dp(2),
            AndroidUtilities.dp(7), AndroidUtilities.dp(2)
        )
        return tv

    def _create_pill(self, act, background, pressed, padding_h=14, padding_v=8):
        pill_btn = LinearLayout(act)
        pill_btn.setOrientation(LinearLayout.HORIZONTAL)
        pill_btn.setGravity(Gravity.CENTER_VERTICAL)
        pill_btn.setPadding(AndroidUtilities.dp(padding_h), AndroidUtilities.dp(padding_v),
                           AndroidUtilities.dp(padding_h), AndroidUtilities.dp(padding_v))
        pill_btn.setClickable(True)
        pill_btn.setFocusable(True)
        pill_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(18), background, pressed
        ))
        return pill_btn

    def _resolve_icon(self, name):
        try:
            R_tg = find_class("org.telegram.messenger.R")
            return getattr(R_tg.drawable, name)
        except Exception:
            return 0

    def _get_theme_colors(self):
        is_dark_theme = False
        try:
            is_dark_theme = Theme.isCurrentThemeDark()
        except Exception:
            try:
                bg_color = Theme.getColor(Theme.key_dialogBackground)
                is_dark_theme = (bg_color & 0x00FFFFFF) < 0x00808080
            except Exception:
                pass
        from android.graphics import Color
        cardBgColor = Theme.getColor(Theme.key_windowBackgroundWhite)
        if is_dark_theme:
            return {
                "main_bg_color": Theme.getColor(Theme.key_windowBackgroundGray),
                "card_bg_color": cardBgColor,
                "card_pressed_color": Color.parseColor("#3C3C3C"),
                "text_color": Color.WHITE,
                "secondary_text_color": Color.parseColor("#CCCCCC"),
                "hint_text_color": Color.parseColor("#999999"),
                "cursor_color": Theme.getColor(Theme.key_chat_messagePanelCursor),
                "search_border_color": Color.parseColor("#3C3C3C"),
                "search_stroke_width": AndroidUtilities.dp(2)
            }
        return {
            "main_bg_color": Theme.getColor(Theme.key_windowBackgroundGray),
            "card_bg_color": cardBgColor,
            "card_pressed_color": Color.parseColor("#f5f5f5"),
            "text_color": Color.BLACK,
            "secondary_text_color": Color.parseColor("#666666"),
            "hint_text_color": Color.parseColor("#999999"),
            "cursor_color": Theme.getColor(Theme.key_chat_messagePanelCursor),
            "search_border_color": Color.parseColor("#e0e0e0"),
            "search_stroke_width": 0
        }

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
                    name = str(r.get("name") or "").strip()
                    url = str(r.get("url") or "").strip()
                    if name and url:
                        repos.append(r)
                except Exception:
                    continue
        except Exception:
            pass
        if not repos:
            BulletinHelper.show_error("No repositories configured")
            return
        if settings.get("skip_repository_selection", False):
            self._open_all_repos_plugins()
            return
        if len(repos) == 1:
            self._open_repo_plugins(repos[0])
            return
        show_repo_sheet(self, repos)

    def _create_circular_loading(self, act, size_dp=20):
        try:
            from org.telegram.ui.Components import CircularProgressDrawable
            color = Theme.getColor(Theme.key_featuredStickers_buttonText)
            d = CircularProgressDrawable(color)
            try:
                d.size = float(AndroidUtilities.dp(size_dp))
                d.thickness = float(AndroidUtilities.dp(2))
            except Exception:
                pass
            v = ImageView(act)
            v.setImageDrawable(d)
            try:
                v.setScaleType(ImageView.ScaleType.CENTER)
            except Exception:
                pass
            return v
        except Exception:
            loading_view = ProgressBar(act)
            try:
                loading_view.setIndeterminate(True)
            except Exception:
                pass
            try:
                from android.content.res import ColorStateList
                color = Theme.getColor(Theme.key_featuredStickers_addButton)
                tint = ColorStateList.valueOf(color)
                try:
                    loading_view.setIndeterminateTintList(tint)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                loading_view.setLayoutParams(FrameLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp), Gravity.CENTER))
            except Exception:
                pass
            return loading_view

    def _create_center_loading_animation(self, parent_layout):
        try:
            act = get_last_fragment().getContext()
            loading_container = FrameLayout(act)
            loading_container.setLayoutParams(FrameLayout.LayoutParams(-1, -1, Gravity.CENTER))

            from org.telegram.ui.Components import CircularProgressDrawable
            size = 122
            color = Theme.getColor(Theme.key_dialogLinkSelection)
            thickness = float(AndroidUtilities.dp(8))
            # use 3-arg ctor: size is set before setStyle, so m3IndicatorView gets correct size
            d = CircularProgressDrawable(float(size), thickness, color)
            d.setBounds(0, 0, size, size)

            spinner = ImageView(act)
            spinner.setImageDrawable(d)
            spinner.setScaleType(ImageView.ScaleType.FIT_CENTER)
            lp = FrameLayout.LayoutParams(size, size, Gravity.CENTER)
            loading_container.addView(spinner, lp)

            return loading_container, spinner
        except Exception as e:
            log(f"Failed to create center loading animation: {e}")
            return None, None

    def _open_all_repos_plugins(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        self._show_plugins_universal(strings["all_repositories"], [])

        def load_task():
            try:
                repos = self.repoManager.getRepositories()
                all_plugins = []
                for repo in repos:
                    if not repo.get("enabled"):
                        continue
                    repo_id = (repo.get("id") or "").strip()
                    repo_url = (repo.get("url") or "").strip()
                    if not repo_url:
                        continue
                    try:
                        plugins_url = repo_url
                        if repo_id:
                            try:
                                from org.telegram.messenger import ApplicationLoader
                            except Exception as e:
                                import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
                                from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
                            import os
                            pkg = ApplicationLoader.applicationContext.getPackageName()
                            cache_path = f"/data/data/{pkg}/files/packitCache/reposCache/{repo_id}.json"
                            log(f"installUI: cache_path={cache_path} exists={os.path.exists(cache_path)}")
                            if os.path.exists(cache_path):
                                with open(cache_path, "r", encoding="utf-8") as f:
                                    cached = json.load(f)
                                resolved = cached.get("repomap", {}).get("plugins") or repo_url
                                log(f"installUI: resolved plugins_url={resolved}")
                                plugins_url = resolved

                        log(f"installUI: GET {plugins_url}")
                        response = requests.get(plugins_url, timeout=10)
                        log(f"installUI: HTTP {response.status_code} for {plugins_url}")
                        if response.status_code != 200:
                            log(f"repo '{repo.get('name')}': HTTP {response.status_code}, skipping")
                            continue
                        config = response.json()
                        plugins = config.get("plugins", {})
                        log(f"installUI: plugins type={type(plugins).__name__} len={len(plugins)}")
                        if isinstance(plugins, dict):
                            for pluginId, info in plugins.items():
                                if isinstance(info, dict):
                                    all_plugins.append({"id": pluginId, "repo_name": repo.get("name", "Unknown"), **info})
                        elif isinstance(plugins, list):
                            for item in plugins:
                                if isinstance(item, dict) and item.get("id"):
                                    all_plugins.append({"id": item.get("id"), "repo_name": repo.get("name", "Unknown"), **item})
                        log(f"installUI: all_plugins so far={len(all_plugins)}")
                    except Exception as e:
                        log(f"failed to load repo {repo.get('name')}: {e}")

                run_on_ui_thread(lambda: self._update_current_fragment_plugins(all_plugins))
            except Exception as e:
                BulletinHelper.show_error("Failed to load plugins")
                log(f"failed to load all repos: {e}")
        run_on_queue(load_task)

    def _update_plugins_in_fragment(self, plugins):
        try:
            fragment = get_last_fragment()
            if not fragment:
                return
            self._show_plugins_universal(self.title if hasattr(self, 'title') else "Plugins", plugins)
        except Exception as e:
            log(f"Failed to update plugins in fragment: {e}")

    def _open_repo_plugins(self, repo):
        repo_name = repo.get("name") or strings["unnamed"]
        repo_url = (repo.get("url") or "").strip()
        if not repo_url:
            BulletinHelper.show_error("Repository URL is empty")
            return
        fragment = get_last_fragment()
        if not fragment:
            return
        repo_id = (repo.get("id") or "").strip()
        self._show_plugins_universal(repo_name, [], repo_id=repo_id)

        def load_task():
            try:
                # Try to resolve plugins URL from cached repomap
                plugins_url = repo_url
                repo_id = (repo.get("id") or "").strip()
                if repo_id:
                    try:
                        from org.telegram.messenger import ApplicationLoader
                    except Exception as e:
                        import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
                        from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
                    import os
                    pkg = ApplicationLoader.applicationContext.getPackageName()
                    cache_path = f"/data/data/{pkg}/files/packitCache/reposCache/{repo_id}.json"
                    log(f"installUI: single cache_path={cache_path} exists={os.path.exists(cache_path)}")
                    if os.path.exists(cache_path):
                        with open(cache_path, "r", encoding="utf-8") as f:
                            cached = json.load(f)
                        resolved = cached.get("repomap", {}).get("plugins") or repo_url
                        log(f"installUI: single resolved plugins_url={resolved}")
                        plugins_url = resolved

                log(f"installUI: single GET {plugins_url}")
                r = requests.get(plugins_url, timeout=20)
                log(f"installUI: single HTTP {r.status_code}")
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

                run_on_ui_thread(lambda: self._update_current_fragment_plugins(plugins))
            except Exception as e:
                BulletinHelper.show_error("An error occurred while downloading")
                log(f"InstallUI: error downloading repository '{repo_url}': {e}")
        run_on_queue(load_task)

    def _update_current_fragment_plugins(self, plugins):
        try:
            delegate = getattr(self, '_active_delegate', None)
            log(f"installUI: _update_current_fragment_plugins plugins={len(plugins)} active_delegate={id(delegate) if delegate else None}")
            if not delegate or not hasattr(delegate, 'plugins'):
                # fallback: try via last fragment
                fragment = get_last_fragment()
                log(f"installUI: fallback fragment={fragment}")
                if fragment and hasattr(fragment, 'getDelegate') and fragment.getDelegate():
                    d = fragment.getDelegate()
                    if hasattr(d, 'plugins'):
                        delegate = d
                        log(f"installUI: fallback delegate found id={id(delegate)}")
            if not delegate:
                log("installUI: no delegate found, aborting")
                return

            delegate.plugins = _filter_unavailable(plugins)
            delegate.filtered_plugins = []
            delegate.visible_plugins = []
            delegate.search_index = search_mod.build_index(delegate.plugins)

            if hasattr(delegate, 'subtitle'):
                delegate.subtitle.setText(_build_plugin_count_label(len(delegate.plugins)))

            cb = getattr(delegate, '_on_data_ready_cb', None)
            log(f"installUI: _on_data_ready_cb={cb} gate={getattr(delegate, '_load_gate', None)}")
            # signal gate that data is ready (fires finish if anim also done)
            if cb:
                delegate._on_data_ready_cb = None
                log("installUI: calling _on_data_ready_cb")
                cb()
            elif hasattr(delegate, 'results_container') and delegate.results_container:
                log("installUI: no gate cb, calling build_list_with_sort directly")
                run_on_ui_thread(lambda: delegate.build_list_with_sort("alpha_az"))
        except Exception as e:
            log(f"Failed to update current fragment plugins: {e}")

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
                new_fragment.setTitle(repo_name, False, 0)
                actionBar = new_fragment.getActionBar()
                if actionBar:
                    actionBar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
            except Exception as e:
                log(f"Failed to setup action bar: {e}")
        except Exception as e:
            log(f"Failed to show plugins universal: {e}")

    class PluginListFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
        def __init__(self, install_ui, title, plugins, show_loading_initial=False, repo_id=""):
            super().__init__()
            self.install_ui = install_ui
            self.title = title
            self.repo_id = repo_id
            self.plugins = _filter_unavailable(plugins)
            self.show_loading_initial = show_loading_initial
            self.search_index = search_mod.build_index(self.plugins)
            self.last_search_query = None
            self.filtered_plugins = []
            self.visible_plugins = []
            self.lazy_load_queue = deque()
            self.is_loading = False
            self.scroll_listener = None
            self.current_sort_type = "alpha_az"
            self.selected_tags = set()
            self.batch_size = 10
            self.loading_container = None
            self.loading_video = None
            log(f"InstallUI: PluginListFragment created id={id(self)} title='{title}' repo_id='{repo_id}' install_ui_id={id(install_ui)}")

        def onFragmentCreate(self, *_):
            pass

        def onFragmentDestroy(self, *_):
            log(f"InstallUI: PluginListFragment destroyed id={id(self)} title='{getattr(self, 'title', '?')}' repo_id='{getattr(self, 'repo_id', '?')}'")
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
                log(f"tgChannel: showTgc={showTgc}")
                if not showTgc:
                    count = LocalConfig.get("installUiOpenCount", 0) + 1
                    LocalConfig.set("installUiOpenCount", count)
                    log(f"tgChannel: installUiOpenCount={count}")
                    if count >= 2:
                        from android_utils import run_on_ui_thread
                        log("tgChannel: scheduling sheet in 500ms")

                        def _show():
                            try:
                                log("tgChannel: _show fired")
                                from .tgChannelSheet import show_tg_channel_sheet
                                frag = get_last_fragment()
                                log(f"tgChannel: frag={frag}")
                                if not frag:
                                    log("tgChannel: no fragment, abort")
                                    return
                                act = frag.getParentActivity()
                                rp = frag.getResourceProvider()
                                log(f"tgChannel: act={act}, rp={rp}")
                                if not act:
                                    log("tgChannel: act is None, abort")
                                    return
                                log("tgChannel: calling show_tg_channel_sheet")
                                show_tg_channel_sheet(act, rp)
                                log("tgChannel: sheet shown")
                            except Exception as e:
                                log(f"tgChannel: _show error: {e}")

                        run_on_ui_thread(_show, 500)
                    else:
                        log("tgChannel: first visit, skip")
                else:
                    log("tgChannel: already shown, skip")
            except Exception as e:
                log(f"tgChannel: check error: {e}")

        def _handle_repo_select(self, selected):
            if selected == "all":
                self.install_ui._open_all_repos_plugins()
            elif isinstance(selected, dict):
                self.install_ui._open_repo_plugins(selected)

        def beforeCreateView(self):
            # save scroll position before rebuilding view
            _saved_scroll_y = 0
            try:
                if hasattr(self, '_scroll_view') and self._scroll_view:
                    _saved_scroll_y = self._scroll_view.getScrollY()
            except Exception:
                pass

            act = get_last_fragment().getContext()
            colors = self.install_ui._get_theme_colors()
            self.main_bg_color = colors["main_bg_color"]
            self.card_bg_color = colors["card_bg_color"]
            self.card_pressed_color = colors["card_pressed_color"]
            self.text_color = colors["text_color"]
            self.secondary_text_color = colors["secondary_text_color"]
            self.hint_text_color = colors["hint_text_color"]
            self.cursor_color = colors["cursor_color"]
            self.search_border_color = colors["search_border_color"]
            self.search_stroke_width = colors["search_stroke_width"]

            self.content_view = FrameLayout(act)
            self.content_view.setBackgroundColor(self.main_bg_color)
            from ...ui.AchievementsActivity.service.AchivementsEngine import register_bulletin_container
            register_bulletin_container(self.content_view)
            main_layout = LinearLayout(act)
            main_layout.setOrientation(LinearLayout.VERTICAL)
            main_layout.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(16), AndroidUtilities.dp(16), AndroidUtilities.dp(14))
            self.content_view.addView(main_layout, FrameLayout.LayoutParams(-1, -1))

            search_container = FrameLayout(act)
            pill = GradientDrawable()
            pill.setShape(GradientDrawable.RECTANGLE)
            pill.setCornerRadius(AndroidUtilities.dp(50))
            try:
                base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                pill.setStroke(AndroidUtilities.dp(2), base_color)
            except Exception:
                try:
                    pill.setStroke(AndroidUtilities.dp(2), Theme.getColor(Theme.key_dialogTextBlue))
                except Exception:
                    pass
            try:
                pill.setColor(self.card_bg_color)
            except Exception:
                pass
            search_container.setBackground(pill)
            search_container.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(8), AndroidUtilities.dp(16), AndroidUtilities.dp(8))
            self.search = EditTextBoldCursor(act)
            self.search.setHint(strings["search_hint"])
            self.search.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            self.search.setSingleLine(True)
            self.search.setInputType(InputType.TYPE_CLASS_TEXT)
            self.search.setBackgroundColor(0)
            self.search.setTextColor(self.text_color)
            try:
                self.search.setHintTextColor(self.hint_text_color)
            except Exception:
                pass
            try:
                self.search.setCursorColor(self.cursor_color)
            except Exception:
                pass
            try:
                self.search.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(10), AndroidUtilities.dp(8))
            except Exception:
                pass

            def perform_search():
                try:
                    query = self.search.getText().toString()
                    if query != self.last_search_query:
                        self.last_search_query = query
                        self.build_list(query)
                    imm = act.getSystemService("input_method")
                    imm.hideSoftInputFromWindow(self.search.getWindowToken(), 0)
                except Exception:
                    pass

            try:
                EditActionListener = find_class("android.widget.TextView$OnEditorActionListener")
                class SearchEditorActionListener(dynamic_proxy(EditActionListener)):
                    def __init__(self, outer):
                        super().__init__()
                        self.outer = outer
                    def onEditorAction(self, v, actionId, event):
                        if actionId == EditorInfo.IME_ACTION_SEARCH or actionId == EditorInfo.IME_ACTION_DONE or actionId == 6 or actionId == 3:
                            perform_search()
                            return True
                        return False
                self.search.setOnEditorActionListener(SearchEditorActionListener(self))
            except Exception as ex:
                log(f"InstallUI: setOnEditorActionListener failed: {ex}")

            class SearchTextWatcherWithClear(dynamic_proxy(TextWatcher)):
                def __init__(self, outer, clear_btn_ref):
                    super().__init__()
                    self.outer = outer
                    self.clear_btn = clear_btn_ref
                def afterTextChanged(self, s):
                    text = s.toString()
                    if text and len(text) > 0:
                        self.clear_btn.setVisibility(View.VISIBLE)
                        try:
                            self.clear_btn.animate().alpha(1.0).setDuration(200).start()
                        except Exception:
                            pass
                    else:
                        try:
                            self.clear_btn.animate().alpha(0.0).setDuration(200).withEndAction(
                                lambda: self.clear_btn.setVisibility(View.GONE)).start()
                        except Exception:
                            self.clear_btn.setVisibility(View.GONE)
                def beforeTextChanged(self, s, start, count, after):
                    pass
                def onTextChanged(self, s, start, before, count):
                    pass

            search_row = LinearLayout(act)
            search_row.setOrientation(LinearLayout.HORIZONTAL)
            search_row.setGravity(Gravity.CENTER_VERTICAL)
            search_row.addView(self.search, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(42), 1.0))
            
            clear_btn = FrameLayout(act)
            clear_btn.setClickable(True)
            clear_btn.setFocusable(True)
            clear_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(25), 0x00000000, 0x00000000
            ))
            clear_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8))
            clear_btn_icon = ImageView(act)
            clear_btn_icon_id = self.install_ui._resolve_icon("input_clear")
            clear_btn_icon.setImageResource(clear_btn_icon_id)
            try:
                clear_btn_icon.setColorFilter(self.text_color)
            except Exception:
                pass
            clear_btn_icon.setScaleType(ImageView.ScaleType.CENTER)
            clear_btn.addView(clear_btn_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
            
            clearSoundPath = os.path.join(os.path.dirname(__file__), "../../../res/sounds/clear-search.mp3")

            def on_clear_click():
                try:
                    playSound(clearSoundPath, "sfx_clear_search")
                except Exception:
                    pass
                try:
                    self.search.setText("")
                    self.last_search_query = ""
                    self.build_list("")
                    imm = act.getSystemService("input_method")
                    imm.hideSoftInputFromWindow(self.search.getWindowToken(), 0)
                except Exception:
                    pass
            
            clear_btn.setOnClickListener(OnClickListener(lambda v: on_clear_click()))
            self.install_ui._apply_press_scale(clear_btn)
            clear_btn.setVisibility(View.GONE)
            clear_btn.setAlpha(0.0)
            search_row.addView(clear_btn, LinearLayout.LayoutParams(AndroidUtilities.dp(52), AndroidUtilities.dp(42), 0))
            
            search_btn = FrameLayout(act)
            search_btn.setClickable(True)
            search_btn.setFocusable(True)
            try:
                base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            except Exception:
                base_color = Theme.getColor(Theme.key_dialogTextBlue)
                pressed_color = base_color
            search_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(25), base_color, pressed_color
            ))
            search_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8))
            search_btn_icon = ImageView(act)
            search_btn_icon_id = self.install_ui._resolve_icon("ic_ab_search")
            search_btn_icon.setImageResource(search_btn_icon_id)
            try:
                search_btn_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            search_btn_icon.setScaleType(ImageView.ScaleType.CENTER)
            search_btn.addView(search_btn_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
            searchBtnSoundPath = os.path.join(os.path.dirname(__file__), "../../../res/sounds/search-btn.mp3")

            def onSearchBtnClick(v):
                try:
                    playSound(searchBtnSoundPath, "sfx_search")
                except Exception:
                    pass
                perform_search()

            search_btn.setOnClickListener(OnClickListener(onSearchBtnClick))
            self.install_ui._apply_press_scale(search_btn)
            search_row.addView(search_btn, LinearLayout.LayoutParams(AndroidUtilities.dp(52), AndroidUtilities.dp(42), 0))
            search_container.addView(search_row, FrameLayout.LayoutParams(-1, -2))
            main_layout.addView(search_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

            # header_row uses FrameLayout so subtitle is always centered
            # regardless of its text length, with equal spacing on both sides
            header_row = FrameLayout(act)
            header_row_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(44))
            header_row_lp.topMargin = AndroidUtilities.dp(4)
            header_row_lp.bottomMargin = AndroidUtilities.dp(12)
            main_layout.addView(header_row, header_row_lp)
            repo_btn = LinearLayout(act)
            repo_btn.setOrientation(LinearLayout.HORIZONTAL)
            repo_btn.setGravity(Gravity.CENTER_VERTICAL)
            repo_btn.setClickable(True)
            repo_btn.setFocusable(True)
            try:
                repo_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(16), self.card_bg_color, self.card_pressed_color
                ))
            except Exception:
                pass
            repo_btn.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(8), AndroidUtilities.dp(12), AndroidUtilities.dp(8))
            
            repo_icon = ImageView(act)
            icon_id = self.install_ui._resolve_icon("msg_media")
            repo_icon.setImageResource(icon_id)
            try:
                repo_icon.setColorFilter(self.text_color)
            except Exception:
                pass
            repo_btn.addView(repo_icon, LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20)))
            
            repo_count_container = FrameLayout(act)
            repo_count_text = TextView(act)
            repo_count = _count_active_repos(self.install_ui.plugin.repoManager)
            repo_count_text.setText(str(repo_count))
            repo_count_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            repo_count_text.setTypeface(AndroidUtilities.bold())
            repo_count_text.setGravity(Gravity.CENTER)
            try:
                repo_count_text.setTextColor(self.text_color)
            except Exception:
                pass

            badge_bg = GradientDrawable()
            badge_bg.setShape(GradientDrawable.OVAL)
            badge_bg.setColor(0x00000000)
            try:
                badge_bg.setStroke(AndroidUtilities.dp(1.5), self.text_color)
            except Exception:
                badge_bg.setStroke(AndroidUtilities.dp(1.5), 0xFFFFFFFF)
            repo_count_text.setBackground(badge_bg)
            
            badge_size = AndroidUtilities.dp(18) if repo_count < 10 else AndroidUtilities.dp(20)
            repo_count_text.setLayoutParams(FrameLayout.LayoutParams(badge_size, badge_size))
            repo_count_container.addView(repo_count_text, FrameLayout.LayoutParams(badge_size, badge_size, Gravity.CENTER))
            
            repo_count_container_lp = LinearLayout.LayoutParams(-2, -2)
            repo_count_container_lp.leftMargin = AndroidUtilities.dp(6)
            repo_count_container_lp.gravity = Gravity.CENTER_VERTICAL
            repo_btn.addView(repo_count_container, repo_count_container_lp)
            
            def show_repo_menu_handler():
                try:
                    imm = act.getSystemService("input_method")
                    imm.hideSoftInputFromWindow(self.search.getWindowToken(), 0)
                except Exception:
                    pass
                fragment = get_last_fragment()
                if fragment:
                    fragment.finishFragment()
                repos = []
                try:
                    for r in (self.install_ui.plugin.repoManager.getRepositories() or []):
                        if not r or not r.get("enabled"):
                            continue
                        name = str(r.get("name") or "").strip()
                        url = str(r.get("url") or "").strip()
                        if name and url:
                            repos.append(r)
                except Exception:
                    pass
                show_repo_sheet(self.install_ui, repos, on_select=self._handle_repo_select)
            repo_btn.setOnClickListener(OnClickListener(lambda v: show_repo_menu_handler()))
            self.install_ui._apply_press_scale(repo_btn)
            repo_btn_lp = FrameLayout.LayoutParams(-2, -2, Gravity.LEFT | Gravity.CENTER_VERTICAL)
            header_row.addView(repo_btn, repo_btn_lp)

            subtitle = TextView(act)
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            subtitle.setText(_build_plugin_count_label(len(self.plugins)) if self.plugins else strings["total_plugins_unknown"])
            subtitle.setGravity(Gravity.CENTER)
            subtitle.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(7), AndroidUtilities.dp(12), AndroidUtilities.dp(7))
            subtitle.setClickable(False)
            subtitle.setFocusable(False)
            try:
                subtitle.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(16), self.card_bg_color, self.card_bg_color
                ))
            except Exception:
                pass
            try:
                subtitle.setTextColor(self.text_color)
            except Exception:
                pass
            # center subtitle absolutely in the header row
            subtitle_lp = FrameLayout.LayoutParams(-2, -2, Gravity.CENTER)
            header_row.addView(subtitle, subtitle_lp)
            self.subtitle = subtitle

            tag_filter_btn = FrameLayout(act)
            tag_filter_btn.setClickable(True)
            tag_filter_btn.setFocusable(True)
            try:
                tag_filter_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(16), self.card_bg_color, self.card_pressed_color
                ))
            except Exception:
                pass
            tag_filter_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8))
            tag_filter_icon = ImageView(act)
            icon_id = self.install_ui._resolve_icon("menu_tag_filter_solar")
            tag_filter_icon.setImageResource(icon_id)
            try:
                tag_filter_icon.setColorFilter(self.text_color)
            except Exception:
                pass
            tag_filter_btn.addView(tag_filter_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
            
            def show_tag_filter_handler():
                try:
                    imm = act.getSystemService("input_method")
                    imm.hideSoftInputFromWindow(self.search.getWindowToken(), 0)
                except Exception:
                    pass
                def on_tags_selected(tags):
                    try:
                        self.selected_tags = tags
                    except Exception:
                        pass
                def on_save():
                    try:
                        current_q = self.search.getText().toString() if self.search else (self.last_search_query or "")
                        self.build_list_with_sort(self.current_sort_type, current_q)
                    except Exception:
                        pass
                show_tag_filter_menu(self.install_ui, act, self.plugins, self.selected_tags, on_tags_selected, on_save)
            
            tag_filter_btn.setOnClickListener(OnClickListener(lambda v: show_tag_filter_handler()))
            self.install_ui._apply_press_scale(tag_filter_btn)
            tag_filter_btn_lp = FrameLayout.LayoutParams(-2, -2, Gravity.RIGHT | Gravity.CENTER_VERTICAL)
            tag_filter_btn_lp.rightMargin = AndroidUtilities.dp(40)
            header_row.addView(tag_filter_btn, tag_filter_btn_lp)
            
            sort_btn = FrameLayout(act)
            sort_btn.setClickable(True)
            sort_btn.setFocusable(True)
            try:
                sort_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(16), self.card_bg_color, self.card_pressed_color
                ))
            except Exception:
                pass
            sort_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8))
            sort_icon = ImageView(act)
            icon_id = self.install_ui._resolve_icon("msg_list")
            sort_icon.setImageResource(icon_id)
            try:
                sort_icon.setColorFilter(self.text_color)
            except Exception:
                pass
            sort_btn.addView(sort_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
            def show_sort_menu_handler():
                try:
                    imm = act.getSystemService("input_method")
                    imm.hideSoftInputFromWindow(self.search.getWindowToken(), 0)
                except Exception:
                    pass
                def on_sort_selected(sort_type):
                    try:
                        current_q = self.search.getText().toString() if self.search else (self.last_search_query or "")
                    except Exception:
                        current_q = self.last_search_query or ""
                    self.build_list_with_sort(sort_type, current_q)
                show_sort_menu(self.install_ui, act, self.current_sort_type, on_sort_selected)
            sort_btn.setOnClickListener(OnClickListener(lambda v: show_sort_menu_handler()))
            self.install_ui._apply_press_scale(sort_btn)
            sort_btn_lp = FrameLayout.LayoutParams(-2, -2, Gravity.RIGHT | Gravity.CENTER_VERTICAL)
            header_row.addView(sort_btn, sort_btn_lp)

            scroll = ScrollView(act)
            self._scroll_view = scroll
            scroll.setFillViewport(True)
            scroll.setVerticalScrollBarEnabled(False)
            scroll.setBackgroundColor(self.main_bg_color)
            scroll.setFadingEdgeLength(AndroidUtilities.dp(24))
            scroll.setVerticalFadingEdgeEnabled(True)
            try:
                scroll.setNestedScrollingEnabled(True)
            except Exception:
                pass

            if self.show_loading_initial:
                content_wrapper = FrameLayout(act)
                content_wrapper.setLayoutParams(ScrollView.LayoutParams(-1, -2))

                # loading already finished on a previous beforeCreateView call — skip animation
                if self.loading_container is None and getattr(self, '_load_gate', None) and self._load_gate[0] and self._load_gate[1]:
                    log(f"installUI: beforeCreateView re-entry after gate done, skipping animation")
                    try:
                        p = self.results_container.getParent()
                        if p is not None:
                            p.removeView(self.results_container)
                    except Exception:
                        pass
                    scroll.addView(self.results_container, ScrollView.LayoutParams(-1, -2))
                else:
                    self.loading_container, self.loading_video = self.install_ui._create_center_loading_animation(content_wrapper)
                    if self.loading_container:
                        # add to content_view (full-screen FrameLayout) for true screen centering
                        self.content_view.addView(self.loading_container, FrameLayout.LayoutParams(-1, -1))
                        # finish only when both: min animation played AND data arrived
                        self._load_gate = [False, False]  # [anim_done, data_ready]

                        def _try_finish():
                            log(f"installUI: _try_finish gate={self._load_gate}")
                            if self._load_gate[0] and self._load_gate[1]:
                                log("installUI: gate passed, calling _finish_loading_and_show_plugins")
                                self._finish_loading_and_show_plugins(content_wrapper)

                        def _on_anim_done():
                            log("installUI: anim timer done")
                            self._load_gate[0] = True
                            _try_finish()

                        def _on_data_ready():
                            log("installUI: data ready callback fired")
                            self._load_gate[1] = True
                            run_on_ui_thread(_try_finish)

                        self._on_data_ready_cb = _on_data_ready
                        log(f"installUI: gate set up, delegate id={id(self)}, _on_data_ready_cb set")
                        threading.Timer(1.0, lambda: run_on_ui_thread(_on_anim_done)).start()
                    else:
                        self._on_data_ready_cb = None
                        self._finish_loading_and_show_plugins(content_wrapper)

                    scroll.addView(content_wrapper, ScrollView.LayoutParams(-1, -2))
            else:
                scroll.addView(self.results_container, ScrollView.LayoutParams(-1, -2))

            class ScrollListener(dynamic_proxy(View.OnScrollChangeListener)):
                def __init__(self, outer):
                    super().__init__()
                    self.outer = outer
                    self.last_scroll_y = 0
                    self.scroll_threshold = AndroidUtilities.dp(50)
                def onScrollChange(self, v, scrollX, scrollY, oldScrollX, oldScrollY):
                    try:
                        if not self.outer.is_loading and len(self.outer.visible_plugins) < len(self.outer.filtered_plugins):
                            height = v.getHeight()
                            content_height = v.getChildAt(0).getHeight()
                            scroll_delta = abs(scrollY - self.last_scroll_y)
                            if scroll_delta > self.scroll_threshold:
                                if scrollY + height >= content_height - AndroidUtilities.dp(300):
                                    self.outer._load_more_items()
                                self.last_scroll_y = scrollY
                    except Exception:
                        pass
            try:
                scroll.setOnScrollChangeListener(ScrollListener(self))
            except Exception:
                pass
            # only create results_container on first call; reuse on re-entry
            if not hasattr(self, 'results_container') or self.results_container is None:
                self.results_container = LinearLayout(act)
                self.results_container.setOrientation(LinearLayout.VERTICAL)
                self.results_container.setPadding(0, 0, 0, AndroidUtilities.dp(10))
            main_layout.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1.0))

            if _saved_scroll_y > 0:
                _y = _saved_scroll_y
                run_on_ui_thread(lambda: scroll.scrollTo(0, _y))

            self.search.addTextChangedListener(SearchTextWatcherWithClear(self, clear_btn))
            try:
                from ..viewUtils import applyFontToTree
                applyFontToTree(self.content_view)
            except Exception:
                pass
            return self.content_view

        def getTitle(self):
            return self.title

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

        def build_list_with_sort(self, sort_type: str, q=None):
            start_time = time()
            self.current_sort_type = sort_type
            q = (q or "").strip()
            if q != self.last_search_query:
                self.last_search_query = q
            self.is_loading = True
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
                fuzzy = settings.get("fuzzy_search", False)
                for p in self.plugins:
                    s = search_mod.score(p, q, self.search_index, isRussian, fuzzy)
                    if s[0] < 6:
                        filtered.append(p)
                filtered.sort(key=lambda p: search_mod.score(p, q, self.search_index, isRussian, fuzzy))

            if self.selected_tags:
                tag_filtered = []
                for p in filtered:
                    plugin_tags = p.get("tags", [])
                    if isinstance(plugin_tags, list):
                        for tag_info in plugin_tags:
                            if isinstance(tag_info, list) and len(tag_info) >= 1:
                                tag_name = tag_info[0]
                                if tag_name in self.selected_tags:
                                    tag_filtered.append(p)
                                    break
                filtered = tag_filtered
            
            if not q:
                if sort_type == "alpha_az":
                    filtered.sort(key=lambda p: (1 if str(p.get("name") or p.get("id") or "")[:1].isdigit() else 0, str(p.get("name") or p.get("id") or "").lower()))
                elif sort_type == "alpha_za":
                    filtered.sort(key=lambda p: (0 if str(p.get("name") or p.get("id") or "")[:1].isdigit() else 1, str(p.get("name") or p.get("id") or "").lower()), reverse=True)
                elif sort_type == "authors":
                    filtered.sort(key=lambda p: str(p.get("author") or "").lower())
            self.filtered_plugins = filtered
            fragment = get_last_fragment()
            act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
            if not act:
                act = fragment.getContext() if fragment else None
            if not filtered:
                empty_container = LinearLayout(act)
                empty_container.setOrientation(LinearLayout.VERTICAL)
                empty_container.setGravity(Gravity.CENTER)
                empty_container.setPadding(0, AndroidUtilities.dp(60), 0, AndroidUtilities.dp(60))
                ghost_icon = ImageView(act)
                try:
                    R_tg = find_class("org.telegram.messenger.R")
                    icon_id = getattr(R_tg.drawable, "ayu_ghost")
                    ghost_icon.setImageResource(icon_id)
                    ghost_icon.setColorFilter(self.secondary_text_color)
                except Exception:
                    pass
                ghost_icon.setLayoutParams(LayoutHelper.createLinear(AndroidUtilities.dp(64), AndroidUtilities.dp(64)))
                empty_container.addView(ghost_icon, LayoutHelper.createLinear(-2, -2, 0, 0, 0, 16))
                empty = TextView(act)
                empty.setText(strings["no_plugins"])
                empty.setGravity(Gravity.CENTER)
                empty.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                empty.setTextColor(self.secondary_text_color)
                empty_container.addView(empty, LayoutHelper.createLinear(-2, -2))
                self.results_container.addView(empty_container, LayoutHelper.createLinear(-1, -2))
                self.is_loading = False
            else:
                self._load_initial_batch()
            log(f"Build list took {time() - start_time:.3f}s")

        def build_list(self, q):
            self.build_list_with_sort(self.current_sort_type, q)

        def _finish_loading_and_show_plugins(self, content_wrapper):
            try:
                log(f"installUI: _finish_loading_and_show_plugins plugins={len(self.plugins)} loading_container={self.loading_container}")
                if hasattr(self, 'subtitle'):
                    self.subtitle.setText(_build_plugin_count_label(len(self.plugins)))

                if self.loading_container:
                    # stop the spinner drawable before removing to avoid background animation leak
                    try:
                        if self.loading_video:
                            d = self.loading_video.getDrawable()
                            if d:
                                d.stop()
                    except Exception:
                        pass
                    # loading_container is in content_view, not content_wrapper
                    try:
                        self.content_view.removeView(self.loading_container)
                    except Exception:
                        content_wrapper.removeView(self.loading_container)
                    self.loading_container = None
                    self.loading_video = None

                content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))

                if self.plugins and len(self.plugins) > 0:
                    self.build_list_with_sort("alpha_az")
                else:
                    self._show_empty_state()
            except Exception as e:
                log(f"Error finishing loading: {e}")
                try:
                    content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))
                    if self.plugins and len(self.plugins) > 0:
                        self.build_list_with_sort("alpha_az")
                    else:
                        self._show_empty_state()
                except Exception:
                    pass

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
                
                ghost_icon = ImageView(act)
                try:
                    R_tg = find_class("org.telegram.messenger.R")
                    icon_id = getattr(R_tg.drawable, "ayu_ghost")
                    ghost_icon.setImageResource(icon_id)
                    ghost_icon.setColorFilter(self.secondary_text_color)
                except Exception:
                    pass
                ghost_icon.setLayoutParams(LayoutHelper.createLinear(AndroidUtilities.dp(64), AndroidUtilities.dp(64)))
                empty_container.addView(ghost_icon, LayoutHelper.createLinear(-2, -2, 0, 0, 0, 16))
                
                empty = TextView(act)
                empty.setText(strings["no_plugins"])
                empty.setGravity(Gravity.CENTER)
                empty.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                empty.setTextColor(self.secondary_text_color)
                empty_container.addView(empty, LayoutHelper.createLinear(-2, -2))
                
                self.results_container.addView(empty_container, LayoutHelper.createLinear(-1, -2))
                self.is_loading = False
            except Exception as e:
                log(f"Error showing empty state: {e}")

        def _add_items_with_animation(self, items_to_add):
            try:
                for idx, item in enumerate(items_to_add):
                    self.results_container.addView(item, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 4))
                    try:
                        item.setAlpha(0.0)
                        item.setScaleX(0.92)
                        item.setScaleY(0.92)
                        delay = idx * 35
                        item.animate().alpha(1.0).scaleX(1.0).scaleY(1.0).setDuration(220).setStartDelay(delay).start()
                    except Exception:
                        pass
                self.is_loading = False
            except Exception as e:
                log(f"Error adding items: {e}")
                self.is_loading = False

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
                    log(f"Error in initial batch loading: {e}")
                    self.is_loading = False
            threading.Thread(target=load_batch, daemon=True).start()

        def _load_more_items(self):
            if self.is_loading or len(self.visible_plugins) >= len(self.filtered_plugins):
                return
            self.is_loading = True
            start_index = len(self.visible_plugins)
            batch_size = min(self.batch_size, len(self.filtered_plugins) - start_index)

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

                    run_on_ui_thread(lambda: self._add_items_with_animation(items_to_add))
                except Exception as e:
                    log(f"Error in batch loading: {e}")
                    self.is_loading = False
            threading.Thread(target=load_batch, daemon=True).start()

        def make_item(self, p):
            act = get_last_fragment().getContext()
            fragment = get_last_fragment()
            row = FrameLayout(act)
            container = LinearLayout(act)
            container.setOrientation(LinearLayout.VERTICAL)
            container.setGravity(Gravity.TOP)
            _card_padding = AndroidUtilities.dp(settings.get("card_padding", 12))
            container.setPadding(_card_padding, _card_padding, _card_padding, _card_padding)
            try:
                container.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(settings.get("card_radius", 18)), self.card_bg_color, self.card_bg_color
                ))
            except Exception:
                pass
            
            def create_icon_pill(icon_name, handler):
                try:
                    surface_color = self.card_bg_color
                    pressed_color = self.card_pressed_color
                except Exception:
                    surface_color = self.card_bg_color
                    pressed_color = self.card_pressed_color
                pill = self.install_ui._create_pill(
                    act,
                    surface_color,
                    pressed_color,
                    padding_h=8,
                    padding_v=8
                )
                icon = ImageView(act)
                icon_id = self.install_ui._resolve_icon(icon_name)
                icon.setImageResource(icon_id)
                try:
                    icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    pass
                pill.addView(icon, LinearLayout.LayoutParams(AndroidUtilities.dp(23), AndroidUtilities.dp(23)))
                pill.setOnClickListener(OnClickListener(lambda v: handler()))
                self.install_ui._apply_press_scale(pill)
                return pill
            
            icon_str = p.get("icon")
            show_default_sticker = settings.get("show_default_sticker", False)
            show_icon = (icon_str and icon_str != "Unknown") and settings.get("card_show_icon", True)
            if not show_icon and show_default_sticker and settings.get("card_show_icon", True):
                icon_str = "Plugins_Stickers/0"
                show_icon = True
            icon_size_dp = settings.get("card_icon_size", 67)
            top_row = LinearLayout(act)
            top_row.setOrientation(LinearLayout.HORIZONTAL)
            top_row.setGravity(Gravity.TOP)
            container.addView(top_row, LayoutHelper.createLinear(-1, -2))
            if show_icon:
                try:
                    icon_view = BackupImageView(act)
                    icon_view.setRoundRadius(AndroidUtilities.dp(12))
                    try:
                        icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
                    except Exception:
                        pass
                    icon_size_px = AndroidUtilities.dp(icon_size_dp)
                    icon_lp = LinearLayout.LayoutParams(icon_size_px, icon_size_px)
                    icon_lp.rightMargin = AndroidUtilities.dp(12)
                    icon_lp.topMargin = AndroidUtilities.dp(5)
                    top_row.addView(icon_view, icon_lp)

                    def onIconClick(v, plugin=p):
                        try:
                            from ..PluginActivity.fragment import show_plugin_profile
                            show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id)
                        except Exception as e:
                            log(f"pluginProfile: open error: {e}")

                    icon_view.setClickable(True)
                    icon_view.setFocusable(True)
                    icon_view.setOnClickListener(OnClickListener(onIconClick))
                    self.install_ui._apply_press_scale(icon_view)

                    def try_load_icon():
                        try:
                            if "/" not in str(icon_str):
                                return False
                            pack_name, index_str = str(icon_str).split("/", 1)
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
                            if ss and getattr(ss, 'documents', None) and ss.documents.size() > sticker_index:
                                doc = ss.documents.get(sticker_index)
                                icon_view.setImage(
                                    ImageLocation.getForDocument(doc),
                                    f"{icon_size_dp}_{icon_size_dp}",
                                    None, None, 0, 1
                                )
                                try:
                                    fade_in = ObjectAnimator.ofFloat(icon_view, "alpha", 0.0, 1.0)
                                    fade_in.setDuration(300)
                                    fade_in.start()
                                except Exception:
                                    pass
                                return True
                            return False
                        except Exception as e:
                            log(f"InstallUI: failed to load icon for '{p.get('id')}' ({icon_str}): {e}")
                            return False
                    if not try_load_icon():
                        try:
                            pack_name = str(icon_str).split("/", 1)[0]
                            MediaDataController.getInstance(0).loadStickersByEmojiOrName(pack_name, False, False)
                        except Exception:
                            pass
                except Exception as e:
                    log(f"InstallUI: icon init error for '{p.get('id')}': {e}")

            col = LinearLayout(act)
            col.setOrientation(LinearLayout.VERTICAL)
            
            name_scroll = HorizontalScrollView(act)
            name_scroll.setHorizontalScrollBarEnabled(False)
            name_scroll.setFillViewport(True)
            name_scroll.setHorizontalFadingEdgeEnabled(True)
            name_scroll.setFadingEdgeLength(AndroidUtilities.dp(24))
            
            name_container = LinearLayout(act)
            name_container.setOrientation(LinearLayout.VERTICAL)
            
            name_tv = TextView(act)
            try:
                name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                name_tv.setTypeface(AndroidUtilities.bold())
            name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(settings.get("card_name_size", 20)))
            display_name = p.get("name") or p.get("id") or "Unknown"
            name_tv.setText(str(display_name))
            name_tv.setTextColor(self.text_color)
            name_tv.setSingleLine(True)
            name_tv.setHorizontalFadingEdgeEnabled(True)
            name_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            id_tv = TextView(act)
            id_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(settings.get("card_id_size", 13)))
            version_text = str(p.get("version") or "").strip()
            author_text = str(p.get("author") or "").strip()
            if version_text and author_text:
                formatted_text = LocaleUtils.fullyFormatText(f"v{version_text} • {author_text}")
                id_tv.setText(formatted_text)
            elif version_text:
                id_tv.setText(f"v{version_text}")
            else:
                formatted_author = LocaleUtils.fullyFormatText(author_text)
                id_tv.setText(formatted_author)
            if not settings.get("card_show_id", True):
                id_tv.setVisibility(View.GONE)
            try:
                id_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                id_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                from android.text.method import LinkMovementMethod
                id_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                pass
            id_tv.setSingleLine(True)
            id_tv.setHorizontalFadingEdgeEnabled(True)
            id_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            
            name_container.addView(name_tv, LayoutHelper.createLinear(-1, -2))
            name_container.addView(id_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))
            
            name_scroll.addView(name_container, FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ))
            col.addView(name_scroll, LayoutHelper.createLinear(-1, -2))
            
            tags = p.get("tags") or []
            if tags and settings.get("show_plugin_tags", True):
                tags_row = LinearLayout(act)
                tags_row.setOrientation(LinearLayout.HORIZONTAL)
                tags_row.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL)
                tags_row.setPadding(0, AndroidUtilities.dp(6), 0, 0)
                for tag in tags:
                    if not isinstance(tag, (list, tuple)) or len(tag) < 2:
                        continue
                    tag_name = str(tag[0])
                    tag_color_key = str(tag[1])
                    tag_url = str(tag[2]) if len(tag) > 2 else None
                    try:
                        tag_color = Theme.getColor(getattr(Theme, tag_color_key))
                    except Exception:
                        continue
                    import ctypes
                    r = (tag_color >> 16) & 0xFF
                    g = (tag_color >> 8) & 0xFF
                    b = tag_color & 0xFF
                    fill_color = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
                    text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
                    tag_bg = GradientDrawable()
                    tag_bg.setShape(GradientDrawable.RECTANGLE)
                    tag_bg.setCornerRadius(AndroidUtilities.dp(6))
                    tag_bg.setColor(fill_color)
                    tag_tv = TextView(act)
                    tag_tv.setText(tag_name)
                    tag_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
                    tag_tv.setTextColor(text_color)
                    tag_tv.setBackground(tag_bg)
                    tag_tv.setPadding(
                        AndroidUtilities.dp(7), AndroidUtilities.dp(2),
                        AndroidUtilities.dp(7), AndroidUtilities.dp(2)
                    )
                    if tag_url:
                        tag_tv.setClickable(True)
                        tag_tv.setFocusable(True)
                        def onTagClick(v, url=tag_url):
                            try:
                                if url.startswith("https://t.me/"):
                                    frag = get_last_fragment()
                                    act2 = frag.getParentActivity() if frag else None
                                    if act2:
                                        Browser.openUrl(act2, Uri.parse(url), True, True, True, None, None, False, False, False)
                                else:
                                    from android.content import Intent
                                    ctx = act
                                    intent = Intent(Intent.ACTION_VIEW)
                                    intent.setData(Uri.parse(url))
                                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                    ctx.startActivity(intent)
                            except Exception as e:
                                log(f"tag url open error: {e}")
                        tag_tv.setOnClickListener(OnClickListener(onTagClick))
                        self.install_ui._apply_press_scale(tag_tv)
                    tag_lp = LinearLayout.LayoutParams(-2, -2)
                    tag_lp.rightMargin = AndroidUtilities.dp(5)
                    tags_row.addView(tag_tv, tag_lp)
                col.addView(tags_row, LayoutHelper.createLinear(-1, -2))
            
            top_row.addView(col, LayoutHelper.createLinear(0, -2, 1.0))

            show_size = settings.get("show_plugin_size", False)
            show_min_ver = settings.get("show_plugin_min_version", False)
            show_deps = settings.get("show_plugin_deps_count", False)

            if show_size or show_min_ver or show_deps:
                chips_col = LinearLayout(act)
                chips_col.setOrientation(LinearLayout.VERTICAL)
                chips_col.setGravity(Gravity.TOP | Gravity.RIGHT)

                if show_min_ver:
                    min_ver = p.get("min_version")
                    if min_ver:
                        chip = self.install_ui._make_info_chip(act, str(min_ver), "key_avatar_background2Blue")
                        chip_lp = LinearLayout.LayoutParams(-2, -2)
                        chip_lp.bottomMargin = AndroidUtilities.dp(4)
                        chips_col.addView(chip, chip_lp)

                if show_deps:
                    deps = p.get("deps") or []
                    dep_count = len(deps)
                    if dep_count > 0:
                        dep_label = "library" if dep_count == 1 else "libraries"
                        chip = self.install_ui._make_info_chip(act, f"{dep_count} {dep_label}", "key_color_purple")
                        chip_lp = LinearLayout.LayoutParams(-2, -2)
                        chip_lp.bottomMargin = AndroidUtilities.dp(4)
                        chips_col.addView(chip, chip_lp)

                if show_size:
                    size_str = p.get("size")
                    if size_str:
                        chip = self.install_ui._make_info_chip(act, str(size_str), "key_color_cyan")
                        chips_col.addView(chip, LinearLayout.LayoutParams(-2, -2))

                chips_lp = LinearLayout.LayoutParams(-2, -2)
                chips_lp.leftMargin = AndroidUtilities.dp(8)
                top_row.addView(chips_col, chips_lp)

            desc_tv = TextView(act)
            desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(settings.get("card_desc_size", 15)))
            description_text = self._get_localized_description(p)
            formatted_description = LocaleUtils.fullyFormatText(description_text)
            desc_tv.setText(formatted_description)
            try:
                desc_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                desc_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                from android.text.method import LinkMovementMethod
                desc_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                pass
            if settings.get("card_show_desc", True):
                container.addView(desc_tv, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

            buttons = LinearLayout(act)
            buttons.setOrientation(LinearLayout.HORIZONTAL)
            buttons.setGravity(Gravity.LEFT)
            buttons.setPadding(0, AndroidUtilities.dp(8), 0, 0)
            base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)

            plugin_min_version = p.get("min_version")
            is_available = (not plugin_min_version) or _is_min_version_satisfied(plugin_min_version)

            install_btn = self.install_ui._create_pill(act, base_color, pressed_color)
            install_icon = ImageView(act)
            icon_id = self.install_ui._resolve_icon("msg_view_file")
            install_icon.setImageResource(icon_id)
            try:
                install_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
            icon_lp.rightMargin = AndroidUtilities.dp(6)
            install_btn.addView(install_icon, icon_lp)
            install_text = TextView(act)
            install_text.setText(strings["plugin_view_button"])
            install_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            install_text.setTypeface(AndroidUtilities.bold())
            install_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            install_btn.addView(install_text)

            current_hint_ref = [None]

            def onViewClick(v, plugin=p, btn=install_btn, row_ref=row, hint_ref=current_hint_ref, available=is_available):
                if not available:
                    try:
                        from org.telegram.ui.Stories.recorder import HintView2
                        from android.text import Layout

                        prev = hint_ref[0]
                        if prev is not None:
                            try:
                                prev.hide()
                            except Exception:
                                pass
                            hint_ref[0] = None

                        hint = (
                            HintView2(row_ref.getContext(), 3)
                            .setMultilineText(True)
                            .setBgColor(Theme.getColor(Theme.key_undo_background))
                            .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                            .setText(strings["plugin_version_below_min"])
                            .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                            .allowBlur(True)
                            .setRounding(AndroidUtilities.dp(12))
                        )
                        try:
                            hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                        except Exception:
                            pass

                        row_ref.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                        hint_ref[0] = hint

                        def _position_and_show():
                            try:
                                btn_loc = [0, 0]
                                btn.getLocationInWindow(btn_loc)
                                row_loc = [0, 0]
                                row_ref.getLocationInWindow(row_loc)
                                rel_x = btn_loc[0] - row_loc[0]
                                rel_y = btn_loc[1] - row_loc[1]
                                center_x = float(rel_x) + float(btn.getMeasuredWidth()) / 2.0
                                hint.setTranslationY(float(rel_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                                hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                                hint.setDuration(5500)
                                hint.show()
                            except Exception as e:
                                log(f"unavailable hint position error: {e}")

                        run_on_ui_thread(_position_and_show)
                    except Exception as e:
                        log(f"unavailable hint error: {e}")

                try:
                    from ..PluginActivity.fragment import show_plugin_profile
                    show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id)
                except Exception as e:
                    log(f"pluginProfile: open error: {e}")

            install_btn.setOnClickListener(OnClickListener(onViewClick))
            self.install_ui._apply_press_scale(install_btn)

            buttons.addView(install_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 8, 0))

            def create_icon_pill(icon_name, handler):
                try:
                    surface_color = self.card_bg_color
                    pressed_color = self.card_pressed_color
                except Exception:
                    surface_color = self.card_bg_color
                    pressed_color = self.card_pressed_color
                pill = self.install_ui._create_pill(
                    act,
                    surface_color,
                    pressed_color,
                    padding_h=8,
                    padding_v=8
                )
                icon = ImageView(act)
                icon_id = self.install_ui._resolve_icon(icon_name)
                icon.setImageResource(icon_id)
                try:
                    icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    pass
                pill.addView(icon, LinearLayout.LayoutParams(AndroidUtilities.dp(23), AndroidUtilities.dp(23)))
                pill.setOnClickListener(OnClickListener(lambda v: handler()))
                self.install_ui._apply_press_scale(pill)
                return pill

            def do_download_relocated():
                download_plugin_file(p)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Downloading")
                except Exception as e:
                    log(f"uiMain: achievements increment error: {e}")

            def do_copy_relocated():
                copy_plugin_link(p, self.repo_id or self.title, copyLinkSoundPath)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Copying links")
                except Exception as e:
                    log(f"uiMain: achievements increment error: {e}")

            def do_share_relocated():
                share_plugin_file(p, str(display_name), act_for_share)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Sharing")
                except Exception as e:
                    log(f"uiMain: achievements increment error: {e}")

            def do_code_relocated():
                view_plugin_code(p, act)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Viewing code")
                except Exception as e:
                    log(f"uiMain: achievements increment error: {e}")

            def do_translate_relocated():
                translate_plugin(p)

            def do_report_relocated():
                report_plugin(p, act)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Reporting")
                except Exception as e:
                    log(f"uiMain: achievements increment error: {e}")

            spacer = View(act)
            buttons.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))

            relocate_actions = [
                ("relocate_copy_link", "msg_copy", do_copy_relocated),
                ("relocate_share", "msg_share", do_share_relocated),
                ("relocate_code", "msg_view_file", do_code_relocated),
                ("relocate_download", "msg_download", do_download_relocated),
                ("relocate_translate", "msg_replace", do_translate_relocated),
                ("relocate_report", "msg_report", do_report_relocated),
            ]
            for setting_key, icon_name, action in relocate_actions:
                if settings.get(setting_key, False):
                    relocated_btn = create_icon_pill(icon_name, action)
                    buttons.addView(relocated_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 4, 0))

            act_for_share = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None

            copyLinkSoundPath = os.path.join(os.path.dirname(__file__), "../../../res/sounds/copy-link.mp3")

            def show_plugin_actions_menu(anchor_view):
                try:
                    popup_layout = ActionBarPopupWindow.ActionBarPopupWindowLayout(act)
                    popup_layout.setBackgroundColor(Theme.getColor(Theme.key_actionBarDefaultSubmenuBackground))
                    popup_layout.setFitItems(True)
                    popup_window_ref = [None]
                    
                    def create_menu_item(icon_res: int, title: str, action, is_red=False):
                        item_frame = AFrame(act)
                        item_frame.setMinimumWidth(AndroidUtilities.dp(160))
                        item_frame.setClickable(True)
                        item_frame.setFocusable(True)
                        try:
                            bg_color = Theme.getColor(Theme.key_dialogBackgroundGray) & 0x20FFFFFF | 0x10000000
                            try:
                                pressed_color = Theme.getColor(Theme.key_listSelector) & 0x40FFFFFF | 0x30000000
                            except Exception:
                                pressed_color = AColor.parseColor("#D0D0D0")
                            btn_bg = GradientDrawable()
                            btn_bg.setCornerRadius(AndroidUtilities.dp(10))
                            btn_bg.setColor(bg_color)
                            try:
                                ripple_color = AColorStateList.valueOf(AColor.parseColor("#40000000"))
                                pressed_bg = GradientDrawable()
                                pressed_bg.setCornerRadius(AndroidUtilities.dp(10))
                                pressed_bg.setColor(pressed_color)
                                ripple_drawable = RippleDrawable(ripple_color, btn_bg, pressed_bg)
                                item_frame.setBackground(ripple_drawable)
                            except Exception:
                                try:
                                    item_frame.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                                        AndroidUtilities.dp(10),
                                        bg_color,
                                        pressed_color
                                    ))
                                except Exception:
                                    item_frame.setBackground(btn_bg)
                        except Exception:
                            item_frame.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))
                        
                        item_content = ALinear(act)
                        item_content.setOrientation(ALinear.HORIZONTAL)
                        item_content.setGravity(AGravity.CENTER_VERTICAL)
                        item_content.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
                        
                        icon = AImage(act)
                        icon.setScaleType(AImage.ScaleType.CENTER)
                        try:
                            icon_drawable = ContextCompat.getDrawable(act, icon_res)
                            if is_red:
                                try:
                                    red_color = Theme.getColor(Theme.key_text_RedRegular)
                                except Exception:
                                    red_color = AColor.parseColor("#FF3B30")
                                icon_drawable.setColorFilter(red_color, PorterDuff.Mode.SRC_IN)
                            else:
                                try:
                                    gray_color = Theme.getColor(Theme.key_dialogTextGray)
                                except Exception:
                                    gray_color = AColor.parseColor("#808080")
                                icon_drawable.setColorFilter(gray_color, PorterDuff.Mode.SRC_IN)
                            icon.setImageDrawable(icon_drawable)
                        except Exception:
                            icon.setImageResource(icon_res)
                        
                        item_content.addView(icon, LayoutHelper.createLinear(24, 24, AGravity.CENTER_VERTICAL, 0, 0, 12, 0))
                        
                        title_tv = AText(act)
                        title_tv.setText(title)
                        title_tv.setTextSize(14)
                        try:
                            if is_red:
                                try:
                                    red_color = Theme.getColor(Theme.key_text_RedRegular)
                                except Exception:
                                    red_color = AColor.parseColor("#FF3B30")
                                title_tv.setTextColor(red_color)
                            else:
                                title_tv.setTextColor(Theme.getColor(Theme.key_actionBarDefaultSubmenuItem))
                        except Exception:
                            pass
                        item_content.addView(title_tv, LayoutHelper.createLinear(-1, -2, 1.0, AGravity.CENTER_VERTICAL))
                        item_frame.addView(item_content)
                        
                        def _on_click(*_):
                            try:
                                if popup_window_ref[0]:
                                    popup_window_ref[0].dismiss()
                            except Exception:
                                pass
                            try:
                                action()
                            except Exception:
                                pass
                        
                        item_frame.setOnClickListener(OnClickListener(_on_click))
                        popup_layout.addView(item_frame, LayoutHelper.createLinear(-1, -2))
                    
                    def do_download():
                        download_plugin_file(p)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Downloading")
                        except Exception as e:
                            log(f"uiMain: achievements increment error: {e}")

                    def do_copy():
                        copy_plugin_link(p, self.repo_id or self.title, copyLinkSoundPath)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Copying links")
                        except Exception as e:
                            log(f"uiMain: achievements increment error: {e}")

                    def do_share():
                        share_plugin_file(p, str(display_name), act_for_share)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Sharing")
                        except Exception as e:
                            log(f"uiMain: achievements increment error: {e}")

                    def do_code():
                        view_plugin_code(p, act)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Viewing code")
                        except Exception as e:
                            log(f"uiMain: achievements increment error: {e}")

                    def do_translate():
                        translate_plugin(p)

                    def do_report():
                        report_plugin(p, act)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Reporting")
                        except Exception as e:
                            log(f"uiMain: achievements increment error: {e}")
                    
                    icon_download = getattr(R_tg.drawable, 'msg_download', 0)
                    icon_copy = getattr(R_tg.drawable, 'msg_copy', getattr(R_tg.drawable, 'msg_copy_filled', 0))
                    icon_share = getattr(R_tg.drawable, 'msg_share', 0)
                    icon_code = getattr(R_tg.drawable, 'msg_view_file', 0)
                    icon_report = getattr(R_tg.drawable, 'msg_report', 0)
                    icon_translate = getattr(R_tg.drawable, 'msg_replace', 0)
                    

                    menu_items = [
                        (icon_copy, strings["copy_link"], do_copy, False, "relocate_copy_link"),
                        (icon_share, strings["share"], do_share, False, "relocate_share"),
                        (icon_code, strings["code"], do_code, False, "relocate_code"),
                        (icon_download, strings["download"], do_download, False, "relocate_download"),
                        (icon_translate, strings["translate"], do_translate, False, "relocate_translate"),
                        (icon_report, strings["report"], do_report, True, "relocate_report"),
                    ]
                    
                    for icon_res, title, action, is_red, setting_key in menu_items:
                        if not settings.get(setting_key, False):
                            create_menu_item(icon_res, title, action, is_red)
                    
                    popup_window = ActionBarPopupWindow(popup_layout, -2, -2)
                    popup_window_ref[0] = popup_window
                    popup_window.setOutsideTouchable(True)
                    popup_window.setClippingEnabled(True)
                    popup_window.setAnimationStyle(R_tg.style.PopupContextAnimation)
                    popup_window.setFocusable(True)
                    popup_layout.measure(
                        AView.MeasureSpec.makeMeasureSpec(AndroidUtilities.dp(1000), AView.MeasureSpec.AT_MOST),
                        AView.MeasureSpec.makeMeasureSpec(AndroidUtilities.dp(1000), AView.MeasureSpec.AT_MOST)
                    )
                    location = [0, 0]
                    anchor_view.getLocationInWindow(location)
                    popup_x = location[0] + anchor_view.getWidth() - popup_layout.getMeasuredWidth()
                    popup_y = location[1] - popup_layout.getMeasuredHeight()
                    popup_window.showAtLocation(anchor_view, AGravity.TOP | AGravity.LEFT, popup_x, popup_y)
                    popup_window.dimBehind()
                except Exception as e:
                    log(f"Error showing plugin actions menu: {e}")

            show_details_button = settings.get("show_details_button", True)
            if show_details_button:
                menu_btn = create_icon_pill("ic_ab_other", lambda: show_plugin_actions_menu(menu_btn))
                buttons.addView(menu_btn, LayoutHelper.createLinear(-2, -2))
            container.addView(buttons, LayoutHelper.createLinear(-1, -2))

            row.addView(container)
            return row
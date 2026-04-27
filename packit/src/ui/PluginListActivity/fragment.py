import re
import json
import threading
from collections import deque
from time import time
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
from .filterDrawer import show_tag_drawer
from .service import SearchEngine as search_mod
from .service import filterEngine as tag_mod
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
        # slavic rule: 1->one, 2-4->few, 5+->many (also handles 11-19 edge case)
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

def _is_filtered(self_obj) -> bool:
    # true if any filter reduces the full plugin set
    all_tags = set()
    all_authors = set()
    all_versions = set()
    for p in self_obj.plugins:
        for t in (p.get("tags") or []):
            if isinstance(t, list) and t:
                all_tags.add(t[0])
        a = str(p.get("author") or "").strip()
        if a and a.lower() != "unknown":
            all_authors.add(a)
        v = str(p.get("app_version") or "").strip()
        if v and v.lower() != "unknown":
            all_versions.add(v)

    tags_filtered = bool(self_obj.selected_tags) and self_obj.selected_tags < all_tags
    authors_filtered = bool(self_obj.selected_authors) and self_obj.selected_authors < all_authors
    versions_filtered = bool(self_obj.selected_app_versions) and self_obj.selected_app_versions < all_versions
    saved_filtered = hasattr(self_obj, 'selected_saved') and self_obj.selected_saved != {"saved", "unsaved"}
    return tags_filtered or authors_filtered or versions_filtered or saved_filtered


def _parse_version(v_str):
    try:
        return tuple(int(x) for x in str(v_str).strip().split("."))
    except Exception:
        return (0,)

def _check_app_version(app_version_expr):
    from ...utils.app_version import check_app_version
    return check_app_version(app_version_expr)

def _filter_unavailable(plugins):
    try:
        from elyx import settings as _s
        if not _s.get("hide_unavailable_plugins", False):
            return plugins
    except Exception:
        return plugins
    result = []
    for p in plugins:
        av = p.get("app_version")
        if not av or _check_app_version(av):
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

    def _apply_press_scale_on_target(self, view, target):
        # touch on view animates target (the card row), not view itself
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
                        target.animate().scaleX(0.97).scaleY(0.97).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        target.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
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
            color = Theme.getColor(Theme.key_featuredStickers_addButton)
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
            color = Theme.getColor(Theme.key_featuredStickers_addButton)
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
                            from ...utils.paths import getRepoCachePath
                            cache_path = getRepoCachePath(repo_id)
                            if os.path.exists(cache_path):
                                with open(cache_path, "r", encoding="utf-8") as f:
                                    cached = json.load(f)
                                resolved = cached.get("repomap", {}).get("plugins") or repo_url
                                plugins_url = resolved

                        response = requests.get(plugins_url, timeout=10)
                        if response.status_code != 200:
                            continue
                        config = response.json()
                        plugins = config.get("plugins", {})
                        if isinstance(plugins, dict):
                            for pluginId, info in plugins.items():
                                if isinstance(info, dict):
                                    all_plugins.append({"id": pluginId, "repo_name": repo.get("name", "Unknown"), **info})
                        elif isinstance(plugins, list):
                            for item in plugins:
                                if isinstance(item, dict) and item.get("id"):
                                    all_plugins.append({"id": item.get("id"), "repo_name": repo.get("name", "Unknown"), **item})
                    except Exception as e:
                        pass

                run_on_ui_thread(lambda: self._update_current_fragment_plugins(all_plugins))
            except Exception as e:
                BulletinHelper.show_error("Failed to load plugins")
        run_on_queue(load_task)

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

                run_on_ui_thread(lambda: self._update_current_fragment_plugins(plugins))
            except Exception as e:
                BulletinHelper.show_error("An error occurred while downloading")
        run_on_queue(load_task)

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
                delegate._on_data_ready_cb = None
                cb()
            elif hasattr(delegate, 'results_container') and delegate.results_container:
                run_on_ui_thread(lambda: delegate.build_list_with_sort("alpha_az"))
        except Exception as e:
            pass

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
            self.search_index = search_mod.build_index(self.plugins)
            self.last_search_query = None
            self.filtered_plugins = []
            self.visible_plugins = []
            self.lazy_load_queue = deque()
            self.is_loading = False
            self.scroll_listener = None
            self.current_sort_type = "alpha_az"
            self.selected_tags = set()
            self.selected_authors = set()
            self.selected_app_versions = set()
            self.selected_saved = {"saved", "unsaved"}
            self._active_drawer = None
            self.batch_size = 10
            self.loading_container = None
            self.loading_video = None
            self._bottom_spinner = None
            self._live_search_spinner = None
            self._live_search_spinner_view = None
            self._load_trigger_y = -1  # scrollY threshold to fire next load_more; -1 = disarmed
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
                if not showTgc:
                    count = LocalConfig.get("installUiOpenCount", 0) + 1
                    LocalConfig.set("installUiOpenCount", count)
                    if count >= 2:
                        from android_utils import run_on_ui_thread

                        def _show():
                            try:
                                from .tgChannelSheet import show_tg_channel_sheet
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
            main_layout.setPadding(AndroidUtilities.dp(16), 0, AndroidUtilities.dp(16), AndroidUtilities.dp(14))
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
            search_container.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(5), AndroidUtilities.dp(8), AndroidUtilities.dp(5))
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
                pass

            class SearchTextWatcherWithClear(dynamic_proxy(TextWatcher)):
                def __init__(self, outer, clear_btn_ref):
                    super().__init__()
                    self.outer = outer
                    self.clear_btn = clear_btn_ref
                    self._live_timer = None

                def _show_live_spinner(self):
                    try:
                        if getattr(self.outer, '_live_search_spinner', None) is None:
                            spinner_container, spinner_view = self.outer.install_ui._create_center_loading_animation(self.outer.content_view)
                            if spinner_container is None:
                                return
                            self.outer._live_search_spinner = spinner_container
                            self.outer._live_search_spinner_view = spinner_view
                            self.outer.content_view.addView(spinner_container, FrameLayout.LayoutParams(-1, -1))
                        else:
                            self.outer._live_search_spinner.setAlpha(1.0)
                            self.outer._live_search_spinner.setVisibility(View.VISIBLE)
                        # hide cards while spinner is shown
                        try:
                            self.outer.results_container.setVisibility(View.INVISIBLE)
                        except Exception:
                            pass
                    except Exception:
                        pass

                def _hide_live_spinner(self):
                    try:
                        spinner = getattr(self.outer, '_live_search_spinner', None)
                        if spinner is None:
                            return
                        spinner.animate().alpha(0.0).setDuration(150).withEndAction(
                            lambda: spinner.setVisibility(View.GONE)
                        ).start()
                    except Exception:
                        pass
                    try:
                        self.outer.results_container.setVisibility(View.VISIBLE)
                    except Exception:
                        pass

                def _schedule_live_search(self, query):
                    # cancel previous pending timer
                    prev = self._live_timer
                    if prev is not None:
                        try:
                            prev.cancel()
                        except Exception:
                            pass
                    outer = self.outer

                    def _do_search():
                        def _ui():
                            try:
                                if query != outer.last_search_query:
                                    outer.last_search_query = query
                                    outer.build_list(query)
                                self._hide_live_spinner()
                            except Exception:
                                pass
                        run_on_ui_thread(_ui)

                    t = threading.Timer(0.3, _do_search)
                    self._live_timer = t
                    t.start()

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
                    try:
                        from elyx import settings as _s
                        if _s.get("live_search", False):
                            self._show_live_spinner()
                            self._schedule_live_search(text)
                    except Exception:
                        pass

                def beforeTextChanged(self, s, start, count, after):
                    pass
                def onTextChanged(self, s, start, before, count):
                    pass

            search_row = LinearLayout(act)
            search_row.setOrientation(LinearLayout.HORIZONTAL)
            search_row.setGravity(Gravity.CENTER_VERTICAL)
            search_row.addView(self.search, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(36), 1.0))
            
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
            search_row.addView(clear_btn, LinearLayout.LayoutParams(AndroidUtilities.dp(52), AndroidUtilities.dp(36), 0))
            
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
            try:
                from elyx import settings as _s
                if _s.get("live_search", False):
                    search_btn.setVisibility(View.GONE)
            except Exception:
                pass
            search_row.addView(search_btn, LinearLayout.LayoutParams(AndroidUtilities.dp(52), AndroidUtilities.dp(36), 0))
            search_container.addView(search_row, FrameLayout.LayoutParams(-1, -2))
            main_layout.addView(search_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))

            # header_row uses FrameLayout so subtitle is always centered
            # regardless of its text length, with equal spacing on both sides
            header_row = FrameLayout(act)
            header_row_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(44))
            header_row_lp.topMargin = AndroidUtilities.dp(2)
            header_row_lp.bottomMargin = AndroidUtilities.dp(6)
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
            icon_id = self.install_ui._resolve_icon("msg_list")
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
                def on_apply(tags, authors, app_versions, saved):
                    try:
                        self.selected_tags = tags
                        self.selected_authors = authors
                        self.selected_app_versions = app_versions
                        self.selected_saved = saved
                        current_q = self.search.getText().toString() if self.search else (self.last_search_query or "")
                        self.build_list_with_sort(self.current_sort_type, current_q)
                    except Exception:
                        pass
                self._active_drawer = show_tag_drawer(act, self.content_view, self.plugins, self.selected_tags, on_apply,
                                                      self.selected_authors, self.selected_app_versions, self.selected_saved)
            
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
            icon_id = self.install_ui._resolve_icon("msg_topics")
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
                            if self._load_gate[0] and self._load_gate[1]:
                                self._finish_loading_and_show_plugins(content_wrapper)

                        def _on_anim_done():
                            self._load_gate[0] = True
                            _try_finish()

                        def _on_data_ready():
                            self._load_gate[1] = True
                            run_on_ui_thread(_try_finish)

                        self._on_data_ready_cb = _on_data_ready
                        threading.Timer(1.0, lambda: run_on_ui_thread(_on_anim_done)).start()
                    else:
                        self._on_data_ready_cb = None
                        self._finish_loading_and_show_plugins(content_wrapper)

                    scroll.addView(content_wrapper, ScrollView.LayoutParams(-1, -2))
            else:
                scroll.addView(self.results_container, ScrollView.LayoutParams(-1, -2))

            scroll_bottom_right = False
            try:
                from elyx import settings as _s
                scroll_bottom_right = _s.get("scroll_button_bottom_right", False)
            except Exception:
                pass

            # pill: "↑ To the beginning" — floats over list, shown after scrolling ~10 plugins
            pill_wrapper = FrameLayout(act)

            if scroll_bottom_right:
                import math
                from android.graphics.drawable import GradientDrawable as _GD
                
                squareFab = True
                try:
                    from hook_utils import find_class as _find_class
                    _ExteraConfig = _find_class("com.exteragram.messenger.ExteraConfig")
                    raw = _ExteraConfig.squareFab
                    squareFab = bool(raw)
                except Exception as e:
                    pass

                def _make_fab_bg(color, size_dp=56, isSquare=False):
                    bg = _GD()
                    if isSquare:
                        bg.setShape(_GD.RECTANGLE)
                        corner = AndroidUtilities.dp(float(math.ceil(size_dp * 16.0 / 56.0)))
                        bg.setCornerRadius(corner)
                    else:
                        bg.setShape(_GD.OVAL)
                    bg.setColor(color)
                    return bg

                scroll_top_pill = FrameLayout(act)
                scroll_top_pill.setClickable(True)
                scroll_top_pill.setFocusable(True)
                try:
                    btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
                    scroll_top_pill.setBackground(_make_fab_bg(btn_base, 56, squareFab))
                except Exception:
                    pass

                fab_size = AndroidUtilities.dp(56)
                fab_margin = AndroidUtilities.dp(16)
                arrow_icon = ImageView(act)
                arrow_icon_id = self.install_ui._resolve_icon("msg_to_beginning")
                arrow_icon.setImageResource(arrow_icon_id)
                try:
                    arrow_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
                except Exception:
                    pass
                arrow_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                scroll_top_pill.addView(arrow_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(26), AndroidUtilities.dp(26), Gravity.CENTER))
                
                pill_wrapper.addView(scroll_top_pill, FrameLayout.LayoutParams(fab_size, fab_size))
                
                pill_lp = FrameLayout.LayoutParams(fab_size, fab_size, Gravity.BOTTOM | Gravity.END)
                pill_lp.rightMargin = fab_margin
                pill_lp.bottomMargin = fab_margin
            else:
                scroll_top_pill = LinearLayout(act)
                scroll_top_pill.setOrientation(LinearLayout.HORIZONTAL)
                scroll_top_pill.setGravity(Gravity.CENTER_VERTICAL)
                scroll_top_pill.setClickable(True)
                scroll_top_pill.setFocusable(True)
                try:
                    pill_bg_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                    pill_pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
                except Exception:
                    pill_bg_color = Theme.getColor(Theme.key_dialogTextBlue)
                    pill_pressed_color = pill_bg_color
                scroll_top_pill.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(20), pill_bg_color, pill_pressed_color
                ))
                scroll_top_pill.setPadding(
                    AndroidUtilities.dp(14), AndroidUtilities.dp(8),
                    AndroidUtilities.dp(14), AndroidUtilities.dp(8)
                )

                arrow_icon = ImageView(act)
                arrow_icon_id = self.install_ui._resolve_icon("msg_to_beginning")
                arrow_icon.setImageResource(arrow_icon_id)
                try:
                    arrow_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
                except Exception:
                    pass
                arrow_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                arrow_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                arrow_lp.rightMargin = AndroidUtilities.dp(6)
                scroll_top_pill.addView(arrow_icon, arrow_lp)

                pill_label = TextView(act)
                pill_label.setText(strings["to_the_beginning"])
                pill_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                pill_label.setTypeface(AndroidUtilities.bold())
                try:
                    pill_label.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
                except Exception:
                    pass
                scroll_top_pill.addView(pill_label, LinearLayout.LayoutParams(-2, -2))

                pill_wrapper.addView(scroll_top_pill, FrameLayout.LayoutParams(-2, -2))
                
                pill_lp = FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.CENTER_HORIZONTAL)
                pill_lp.topMargin = AndroidUtilities.dp(118)
            pill_wrapper.setAlpha(0.0)
            # keep VISIBLE at alpha=0 so GPU texture stays uploaded — avoids upload spike on first show
            pill_wrapper.setVisibility(View.VISIBLE)
            # hardware layer: GPU compositing is cheaper than CPU software raster during scroll
            try:
                from android.view import View as _AView
                pill_wrapper.setLayerType(_AView.LAYER_TYPE_HARDWARE, None)
            except Exception:
                pass
            self.content_view.addView(pill_wrapper, pill_lp)
            self._scroll_top_pill = pill_wrapper
            self._pill_visible = False

            # ~10 plugins * ~88dp per card
            scroll_show_threshold = AndroidUtilities.dp(880)

            _drag_dismissed = [False]
            _drag_start_raw_y = [0.0]
            _is_dragging = [False]
            _DISMISS_THRESHOLD_DY = AndroidUtilities.dp(-40)

            def _set_pill_visible(visible):
                if visible and _drag_dismissed[0]:
                    return
                if self._pill_visible == visible:
                    return
                self._pill_visible = visible
                pill_wrapper.animate().cancel()
                if visible:
                    pill_wrapper.animate().alpha(1.0).setDuration(150).start()
                else:
                    pill_wrapper.animate().alpha(0.0).setDuration(150).start()

            def _scroll_to_top_smooth():
                try:
                    scroll.smoothScrollTo(0, 0)
                except Exception:
                    pass
                _set_pill_visible(False)

            def _animate_dismiss_up():
                try:
                    pill_wrapper.animate().cancel()
                    pill_wrapper.animate().translationY(-AndroidUtilities.dp(80)).alpha(0.0).setDuration(250).start()
                except Exception:
                    pass

            def _animate_snap_back():
                try:
                    pill_wrapper.animate().cancel()
                    pill_wrapper.animate().translationY(0.0).alpha(1.0).setDuration(200).start()
                except Exception:
                    pass

            if not scroll_bottom_right:
                class PillTouchListener(dynamic_proxy(View.OnTouchListener)):
                    def onTouch(self, v, ev):
                        action = ev.getActionMasked()
                        if action == MotionEvent.ACTION_DOWN:
                            _drag_start_raw_y[0] = ev.getRawY()
                            _is_dragging[0] = False
                            pill_wrapper.animate().cancel()
                            return False
                        if action == MotionEvent.ACTION_MOVE:
                            dy = ev.getRawY() - _drag_start_raw_y[0]
                            if not _is_dragging[0]:
                                if abs(dy) > AndroidUtilities.dp(4):
                                    _is_dragging[0] = True
                                    scroll_top_pill.setPressed(False)
                                else:
                                    return False
                            # direct property set — no animator overhead on MOVE
                            translation = dy if dy < 0 else dy * 0.25
                            pill_wrapper.setTranslationY(translation)
                            progress = max(0.0, min(1.0, -translation / AndroidUtilities.dp(80)))
                            pill_wrapper.setAlpha(1.0 - progress * 0.5)
                            return True
                        if action == MotionEvent.ACTION_UP or action == MotionEvent.ACTION_CANCEL:
                            if not _is_dragging[0]:
                                return False
                            _is_dragging[0] = False
                            dy = ev.getRawY() - _drag_start_raw_y[0]
                            if action == MotionEvent.ACTION_UP and dy < _DISMISS_THRESHOLD_DY:
                                _drag_dismissed[0] = True
                                _animate_dismiss_up()
                            else:
                                _animate_snap_back()
                            return True
                        return False

                scroll_top_pill.setOnTouchListener(PillTouchListener())
            scroll_top_pill.setOnClickListener(OnClickListener(lambda v: _scroll_to_top_smooth()))

            class ScrollListener(dynamic_proxy(View.OnScrollChangeListener)):
                def __init__(self, outer):
                    super().__init__()
                    self.outer = outer
                def onScrollChange(self, v, scrollX, scrollY, oldScrollX, oldScrollY):
                    outer = self.outer
                    if scrollY >= scroll_show_threshold:
                        if not outer._pill_visible:
                            _set_pill_visible(True)
                    else:
                        if outer._pill_visible:
                            _set_pill_visible(False)
                    trigger = outer._load_trigger_y
                    if trigger >= 0 and not outer.is_loading and scrollY >= trigger:
                        outer._load_trigger_y = -1
                        outer._load_more_items()
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
            self._s_show_view_button = settings.get("show_view_button", True)
            self._s_show_details_button = settings.get("show_details_button", True)
            self._s_fuzzy_search = settings.get("fuzzy_search", False)
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
                        scored.append((s, p))
                scored.sort(key=lambda x: x[0])
                filtered = [p for _, p in scored]

            if self.selected_tags:
                filtered = tag_mod.filter_by_tags(filtered, self.selected_tags)

            if self.selected_authors:
                all_authors = set(
                    str(p.get("author") or "").strip()
                    for p in self.plugins
                    if str(p.get("author") or "").strip() and str(p.get("author") or "").strip().lower() != "unknown"
                )
                # no filter if all selected
                if self.selected_authors < all_authors:
                    filtered = [
                        p for p in filtered
                        if str(p.get("author") or "").strip() in self.selected_authors
                    ]

            if self.selected_app_versions:
                all_versions = set(
                    str(p.get("app_version") or "").strip()
                    for p in self.plugins
                    if str(p.get("app_version") or "").strip() and str(p.get("app_version") or "").strip().lower() != "unknown"
                )
                if self.selected_app_versions < all_versions:
                    filtered = [
                        p for p in filtered
                        if str(p.get("app_version") or "").strip() in self.selected_app_versions
                    ]

            if hasattr(self, 'selected_saved') and self.selected_saved != {"saved", "unsaved"}:
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
                    log(f"pluginList: saved filter error: {e}")
            
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
                if _is_filtered(self):
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
            log(f"Build list took {time() - start_time:.3f}s")

        def build_list(self, q):
            self.build_list_with_sort(self.current_sort_type, q)

        def _finish_loading_and_show_plugins(self, content_wrapper):
            try:
                if hasattr(self, 'subtitle'):
                    self.subtitle.setText(_build_plugin_count_label(len(self.plugins)))

                # keep loading_container reference — remove it only after first cards are rendered
                content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))

                if self.plugins and len(self.plugins) > 0:
                    self._content_wrapper_ref = content_wrapper
                    self.build_list_with_sort("alpha_az")
                else:
                    self._dismiss_loading_container(content_wrapper)
                    self._show_empty_state()
            except Exception as e:
                try:
                    self._dismiss_loading_container(content_wrapper)
                    content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))
                    if self.plugins and len(self.plugins) > 0:
                        self.build_list_with_sort("alpha_az")
                    else:
                        self._show_empty_state()
                except Exception:
                    pass

        def _dismiss_loading_container(self, content_wrapper=None):
            # fade out then remove the spinner; safe to call multiple times
            lc = self.loading_container
            lv = self.loading_video
            if lc is None:
                return
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
                        except Exception:
                            pass

            try:
                lc.animate().alpha(0.0).setDuration(150).withEndAction(_RemoveRunnable(lc, cv, cw)).start()
            except Exception:
                try:
                    cv.removeView(lc)
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
            act = get_last_fragment().getContext()
            fragment = get_last_fragment()
            row = FrameLayout(act)
            container = LinearLayout(act)
            container.setOrientation(LinearLayout.VERTICAL)
            container.setGravity(Gravity.TOP)
            _card_padding = AndroidUtilities.dp(self._s_card_padding)
            container.setPadding(_card_padding, _card_padding, _card_padding, _card_padding)
            try:
                container.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(self._s_card_radius), self.card_bg_color, self.card_bg_color
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
            show_icon = (icon_str and icon_str != "Unknown") and self._s_card_show_icon
            if not show_icon and self._s_show_default_sticker and self._s_card_show_icon:
                icon_str = "Plugins_Stickers/0"
                show_icon = True
            icon_size_dp = self._s_icon_size_dp
            top_row = LinearLayout(act)
            top_row.setOrientation(LinearLayout.HORIZONTAL)
            top_row.setGravity(Gravity.TOP)
            container.addView(top_row, LayoutHelper.createLinear(-1, -2))
            if show_icon:
                try:
                    icon_view = BackupImageView(act)
                    icon_view.setRoundRadius(AndroidUtilities.dp(self._s_sticker_radius))
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
                            pass

                    icon_view.setClickable(True)
                    icon_view.setFocusable(True)
                    icon_view.setOnClickListener(OnClickListener(onIconClick))
                    if self._s_show_details_button:
                        self.install_ui._apply_press_scale(icon_view)
                    else:
                        self.install_ui._apply_press_scale_on_target(icon_view, row)

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
                                return True
                            return False
                        except Exception as e:
                            return False
                    if not try_load_icon():
                        try:
                            pack_name = str(icon_str).split("/", 1)[0]
                            MediaDataController.getInstance(0).loadStickersByEmojiOrName(pack_name, False, False)
                        except Exception:
                            pass

                        def _retry_load(view=icon_view, loader=try_load_icon):
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
                    pass

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
            name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, self._s_card_name_size)
            display_name = p.get("name") or p.get("id") or "Unknown"
            name_tv.setText(str(display_name))
            name_tv.setTextColor(self.text_color)
            name_tv.setSingleLine(True)
            name_tv.setHorizontalFadingEdgeEnabled(True)
            name_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            id_tv = TextView(act)
            id_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, self._s_card_id_size)
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
            if not self._s_card_show_id:
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
            if tags and self._s_show_plugin_tags:
                tags_row = LinearLayout(act)
                tags_row.setOrientation(LinearLayout.HORIZONTAL)
                tags_row.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL)
                tags_row.setPadding(0, AndroidUtilities.dp(6), 0, 0)
                tags_row.setClipChildren(True)
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
                                pass
                        tag_tv.setOnClickListener(OnClickListener(onTagClick))
                        self.install_ui._apply_press_scale(tag_tv)
                    tag_lp = LinearLayout.LayoutParams(-2, -2)
                    tag_lp.rightMargin = AndroidUtilities.dp(5)
                    tags_row.addView(tag_tv, tag_lp)

                # hide tags that don't fit in a single line — keep only the first visible one
                _tags_row_ref = tags_row
                class _TagsLayoutListener(dynamic_proxy(View.OnLayoutChangeListener)):
                    def __init__(self):
                        super().__init__()
                        self._done = False
                    def onLayoutChange(self, v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom):
                        if self._done:
                            return
                        row_width = v.getWidth()
                        if row_width <= 0:
                            return
                        self._done = True
                        # hide any child whose right edge exceeds row width
                        found_hidden = False
                        for i in range(v.getChildCount()):
                            child = v.getChildAt(i)
                            if child is None:
                                continue
                            if found_hidden or child.getRight() > row_width:
                                child.setVisibility(View.GONE)
                                found_hidden = True
                        v.removeOnLayoutChangeListener(self)
                tags_row.addOnLayoutChangeListener(_TagsLayoutListener())
                col.addView(tags_row, LayoutHelper.createLinear(-1, -2))
            
            top_row.addView(col, LayoutHelper.createLinear(0, -2, 1.0))

            show_size = self._s_show_size
            show_min_ver = self._s_show_min_ver
            show_deps = self._s_show_deps

            if show_size or show_min_ver or show_deps:
                chips_col = LinearLayout(act)
                chips_col.setOrientation(LinearLayout.VERTICAL)
                chips_col.setGravity(Gravity.TOP | Gravity.RIGHT)

                if show_min_ver:
                    min_ver = p.get("app_version")
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
            desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, self._s_card_desc_size)
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
            if self._s_card_show_desc:
                container.addView(desc_tv, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

            buttons = LinearLayout(act)
            buttons.setOrientation(LinearLayout.HORIZONTAL)
            buttons.setGravity(Gravity.LEFT)
            buttons.setPadding(0, AndroidUtilities.dp(8), 0, 0)
            base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)

            plugin_min_version = p.get("app_version")
            is_available = (not plugin_min_version) or _check_app_version(plugin_min_version)

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
                                pass

                        run_on_ui_thread(_position_and_show)
                    except Exception as e:
                        pass

                try:
                    from ..PluginActivity.fragment import show_plugin_profile
                    show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id)
                except Exception as e:
                    pass

            def onCardClick(v, plugin=p, row_ref=row, hint_ref=current_hint_ref, available=is_available):
                if not self._s_show_view_button:
                    try:
                        from ..PluginActivity.fragment import show_plugin_profile
                        show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id)
                    except Exception as e:
                        pass

            install_btn.setOnClickListener(OnClickListener(onViewClick))
            self.install_ui._apply_press_scale(install_btn)

            if not self._s_show_view_button:
                row.setOnClickListener(OnClickListener(onCardClick))
                self.install_ui._apply_press_scale_on_target(row, row)
                name_tv.setClickable(True)
                name_tv.setFocusable(True)
                name_tv.setOnClickListener(OnClickListener(onCardClick))
                self.install_ui._apply_press_scale_on_target(name_tv, row)
                if self._s_card_show_desc:
                    desc_tv.setClickable(True)
                    desc_tv.setFocusable(True)
                    desc_tv.setOnClickListener(OnClickListener(onCardClick))
                    self.install_ui._apply_press_scale_on_target(desc_tv, row)

            if self._s_show_view_button:
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
                    pass

            def do_copy_relocated():
                copy_plugin_link(p, self.repo_id or self.title, copyLinkSoundPath)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Copying links")
                except Exception as e:
                    pass

            def do_share_relocated():
                share_plugin_file(p, str(display_name), act_for_share)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Sharing")
                except Exception as e:
                    pass

            def do_code_relocated():
                view_plugin_code(p, act)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Viewing code")
                except Exception as e:
                    pass

            def do_translate_relocated():
                translate_plugin(p)

            def do_report_relocated():
                report_plugin(p, act)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Reporting")
                except Exception as e:
                    pass

            spacer = View(act)
            buttons.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))

            relocate_actions = [
                ("_s_relocate_copy", "msg_copy", do_copy_relocated),
                ("_s_relocate_share", "msg_share", do_share_relocated),
                ("_s_relocate_code", "msg_view_file", do_code_relocated),
                ("_s_relocate_download", "msg_download", do_download_relocated),
                ("_s_relocate_translate", "msg_replace", do_translate_relocated),
                ("_s_relocate_report", "msg_report", do_report_relocated),
            ]
            for attr_key, icon_name, action in relocate_actions:
                if getattr(self, attr_key, False):
                    relocated_btn = create_icon_pill(icon_name, action)
                    buttons.addView(relocated_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 4, 0))

            act_for_share = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None

            copyLinkSoundPath = os.path.join(os.path.dirname(__file__), "../../../res/sounds/copy-link.mp3")

            def show_plugin_actions_menu(anchor_view):
                try:
                    from ..contextMenu import show_plugin_context_menu

                    def do_download():
                        download_plugin_file(p)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Downloading")
                        except Exception:
                            pass

                    def do_copy():
                        copy_plugin_link(p, self.repo_id or self.title, copyLinkSoundPath)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Copying links")
                        except Exception:
                            pass

                    def do_share():
                        share_plugin_file(p, str(display_name), act_for_share)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Sharing")
                        except Exception:
                            pass

                    def do_code():
                        view_plugin_code(p, act)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Viewing code")
                        except Exception:
                            pass

                    def do_translate():
                        translate_plugin(p)

                    def do_report():
                        report_plugin(p, act)
                        try:
                            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                            increment_category("Reporting")
                        except Exception:
                            pass

                    show_plugin_context_menu(anchor_view.getRootView(), anchor_view, [
                        {"icon": "msg_copy",      "text": str(strings["copy_link"]), "action": do_copy,      "show": not getattr(self, "_s_relocate_copy",      False)},
                        {"icon": "msg_share",     "text": str(strings["share"]),     "action": do_share,     "show": not getattr(self, "_s_relocate_share",     False)},
                        {"icon": "msg_view_file", "text": str(strings["code"]),      "action": do_code,      "show": not getattr(self, "_s_relocate_code",      False)},
                        {"icon": "msg_download",  "text": str(strings["download"]),  "action": do_download,  "show": not getattr(self, "_s_relocate_download",  False)},
                        {"icon": "msg_replace",   "text": str(strings["translate"]), "action": do_translate, "show": not getattr(self, "_s_relocate_translate", False)},
                        {"icon": "msg_report",    "text": str(strings["report"]),    "action": do_report,    "show": not getattr(self, "_s_relocate_report",    False), "red": True},
                    ])
                except Exception as e:
                    pass

            if self._s_show_details_button:
                menu_btn = create_icon_pill("ic_ab_other", lambda: show_plugin_actions_menu(menu_btn))
                buttons.addView(menu_btn, LayoutHelper.createLinear(-2, -2))
            container.addView(buttons, LayoutHelper.createLinear(-1, -2))

            row.addView(container)
            return row
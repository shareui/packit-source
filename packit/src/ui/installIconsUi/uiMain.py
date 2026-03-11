import json
import threading
from collections import deque
from android.animation import ObjectAnimator
from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, ProgressBar
from android.util import TypedValue
from android.text import TextWatcher, InputType, TextUtils
from android.view.inputmethod import EditorInfo
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy
from hook_utils import find_class
import requests
from android_utils import log, run_on_ui_thread
from client_utils import get_last_fragment, run_on_queue
from ui.bulletin import BulletinHelper
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper, EditTextBoldCursor
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper, EditTextBoldCursor failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, R as R_tg failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android_utils import OnClickListener
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()

from .repo import show_icon_repo_sheet
from .sort import show_icon_sort_menu


def _count_active_repos(repoManager) -> int:
    try:
        repos = repoManager.getRepositories() or []
        return sum(1 for r in repos if r and r.get("enabled", True) and str(r.get("url") or "").strip())
    except Exception:
        return 0


class InstallIconsUI:
    def __init__(self, plugin):
        self.plugin = plugin
        self.repoManager = plugin.repoManager
        self._preview_cache = {}
        self._preview_cache_lock = threading.Lock()

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

    def _create_close_button(self, act):
        close_btn = FrameLayout(act)
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
        close_text.setText(strings["close_button"])
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
            R = find_class("org.telegram.messenger.R")
            return getattr(R.drawable, name)
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
            }
        return {
            "main_bg_color": Theme.getColor(Theme.key_windowBackgroundGray),
            "card_bg_color": cardBgColor,
            "card_pressed_color": Color.parseColor("#f5f5f5"),
            "text_color": Color.BLACK,
            "secondary_text_color": Color.parseColor("#666666"),
            "hint_text_color": Color.parseColor("#999999"),
            "cursor_color": Theme.getColor(Theme.key_chat_messagePanelCursor),
        }

    def open(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        repos = []
        try:
            for r in (self.repoManager.getRepositories() or []):
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
            self._open_all_repos_icons()
            return
        if len(repos) == 1:
            self._open_repo_icons(repos[0])
            return
        show_icon_repo_sheet(self, repos)

    def _open_all_repos_icons(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        self._show_icons_universal(strings["all_repositories"], [])

        def load_task():
            try:
                repos = self.repoManager.getRepositories()
                all_icons = []
                for repo in repos:
                    if not repo.get("enabled"):
                        continue
                    repo_id = (repo.get("id") or "").strip()
                    repo_url = (repo.get("url") or "").strip()
                    if not repo_url:
                        continue
                    try:
                        icons_url = repo_url
                        if repo_id:
                            try:
                                from org.telegram.messenger import ApplicationLoader
                            except Exception as e:
                                import android_utils as _au; _au.log(f"import ApplicationLoader failed: {e}")
                                from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
                            import os
                            pkg = ApplicationLoader.applicationContext.getPackageName()
                            cache_path = f"/data/data/{pkg}/files/packitCache/{repo_id}.json"
                            if os.path.exists(cache_path):
                                with open(cache_path, "r", encoding="utf-8") as f:
                                    cached = json.load(f)
                                icons_url = cached.get("repomap", {}).get("icons") or repo_url

                        response = requests.get(icons_url, timeout=10)
                        if response.status_code != 200:
                            log(f"icons repo '{repo.get('name')}': HTTP {response.status_code}, skipping")
                            continue
                        config = response.json()
                        icons = config.get("icons", {})
                        if isinstance(icons, dict):
                            for iconId, info in icons.items():
                                if isinstance(info, dict):
                                    all_icons.append({"id": iconId, "repo_name": repo.get("name", "Unknown"), **info})
                        elif isinstance(icons, list):
                            for item in icons:
                                if isinstance(item, dict) and item.get("id"):
                                    all_icons.append({"id": item.get("id"), "repo_name": repo.get("name", "Unknown"), **item})
                    except Exception as e:
                        log(f"icons: failed to load repo {repo.get('name')}: {e}")

                run_on_ui_thread(lambda: self._update_current_fragment_icons(all_icons))
            except Exception as e:
                BulletinHelper.show_error("Failed to load icons")
                log(f"icons: failed to load all repos: {e}")
        run_on_queue(load_task)

    def _open_repo_icons(self, repo):
        repo_name = repo.get("name") or strings["unnamed"]
        repo_url = (repo.get("url") or "").strip()
        if not repo_url:
            BulletinHelper.show_error("Repository URL is empty")
            return
        fragment = get_last_fragment()
        if not fragment:
            return
        repo_id = (repo.get("id") or "").strip()
        self._show_icons_universal(repo_name, [], repo_id=repo_id)

        def load_task():
            try:
                icons_url = repo_url
                if repo_id:
                    try:
                        from org.telegram.messenger import ApplicationLoader
                    except Exception as e:
                        import android_utils as _au; _au.log(f"import ApplicationLoader failed: {e}")
                        from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
                    import os
                    pkg = ApplicationLoader.applicationContext.getPackageName()
                    cache_path = f"/data/data/{pkg}/files/packitCache/{repo_id}.json"
                    if os.path.exists(cache_path):
                        with open(cache_path, "r", encoding="utf-8") as f:
                            cached = json.load(f)
                        icons_url = cached.get("repomap", {}).get("icons") or repo_url

                r = requests.get(icons_url, timeout=20)
                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}")
                config = r.json()
                icons_raw = config.get("icons", [])
                icons = []
                if isinstance(icons_raw, dict):
                    for iid, info in icons_raw.items():
                        if isinstance(info, dict):
                            icons.append({"id": iid, **info})
                elif isinstance(icons_raw, list):
                    for item in icons_raw:
                        if isinstance(item, dict) and item.get("id"):
                            icons.append(item)

                run_on_ui_thread(lambda: self._update_current_fragment_icons(icons))
            except Exception as e:
                BulletinHelper.show_error("An error occurred while downloading")
                log(f"InstallIconsUI: error downloading repo '{repo_url}': {e}")
        run_on_queue(load_task)

    def _update_current_fragment_icons(self, icons):
        try:
            fragment = get_last_fragment()
            if not fragment:
                return
            if hasattr(fragment, 'getDelegate') and fragment.getDelegate():
                delegate = fragment.getDelegate()
                if hasattr(delegate, 'icons'):
                    delegate.icons = icons
                    delegate.filtered_icons = []
                    delegate.visible_icons = []
                    # if still showing loading placeholder — transition to real list
                    if getattr(delegate, '_loading_started', False) and callable(getattr(delegate, '_finish_loading', None)):
                        delegate._loading_started = False
                        run_on_ui_thread(delegate._finish_loading)
                    elif hasattr(delegate, 'results_container') and delegate.results_container:
                        delegate.build_list_with_sort(delegate.current_sort_type)
        except Exception as e:
            log(f"icons: failed to update fragment: {e}")

    def _show_icons_universal(self, repo_name: str, icons: list, repo_id: str = ""):
        fragment = get_last_fragment()
        if not fragment:
            return
        try:
            delegate = self.IconListFragment(self, repo_name, icons, show_loading_initial=True, repo_id=repo_id)
            new_fragment = UniversalFragment(delegate)
            fragment.presentFragment(new_fragment)
            try:
                new_fragment.setTitle(repo_name, False, 0)
                actionBar = new_fragment.getActionBar()
                if actionBar:
                    actionBar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
            except Exception as e:
                log(f"icons: failed to setup action bar: {e}")
        except Exception as e:
            log(f"icons: failed to show universal: {e}")

    class IconListFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
        def __init__(self, install_ui, title, icons, show_loading_initial=False, repo_id=""):
            super().__init__()
            self.install_ui = install_ui
            self.title = title
            self.repo_id = repo_id
            self.icons = icons
            self.show_loading_initial = show_loading_initial
            self.last_search_query = None
            self.filtered_icons = []
            self.visible_icons = []
            self.lazy_load_queue = deque()
            self.is_loading = False
            self.current_sort_type = "alpha_az"
            self.batch_size = 15
            self.results_container = None
            self._finish_loading = None
            self._loading_started = False
            # registry of (iv, loaded_list) for the global swap ticker
            self._card_registry = []
            self._ticker_started = False

        def onFragmentCreate(self, *_):
            pass

        def onFragmentDestroy(self, *_):
            try:
                if hasattr(self, 'content_view') and self.content_view is not None:
                    parent = self.content_view.getParent()
                    if parent is not None:
                        parent.removeView(self.content_view)
            except Exception:
                pass

        def _handle_repo_select(self, selected):
            if selected == "all":
                self.install_ui._open_all_repos_icons()
            elif isinstance(selected, dict):
                self.install_ui._open_repo_icons(selected)

        def beforeCreateView(self):
            act = get_last_fragment().getContext()
            colors = self.install_ui._get_theme_colors()
            self.main_bg_color = colors["main_bg_color"]
            self.card_bg_color = colors["card_bg_color"]
            self.card_pressed_color = colors["card_pressed_color"]
            self.text_color = colors["text_color"]
            self.secondary_text_color = colors["secondary_text_color"]
            self.hint_text_color = colors["hint_text_color"]
            self.cursor_color = colors["cursor_color"]

            self.content_view = FrameLayout(act)
            self.content_view.setBackgroundColor(self.main_bg_color)

            main_layout = LinearLayout(act)
            main_layout.setOrientation(LinearLayout.VERTICAL)
            main_layout.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(16), AndroidUtilities.dp(16), AndroidUtilities.dp(14))
            self.content_view.addView(main_layout, FrameLayout.LayoutParams(-1, -1))

            # search bar
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
            self.search.setHint(strings["icons_search_hint"])
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
                        if actionId in (EditorInfo.IME_ACTION_SEARCH, EditorInfo.IME_ACTION_DONE, 6, 3):
                            perform_search()
                            return True
                        return False
                self.search.setOnEditorActionListener(SearchEditorActionListener(self))
            except Exception as ex:
                log(f"icons: setOnEditorActionListener failed: {ex}")

            class SearchTextWatcher(dynamic_proxy(TextWatcher)):
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
            clear_btn_icon.setImageResource(self.install_ui._resolve_icon("input_clear"))
            try:
                clear_btn_icon.setColorFilter(self.text_color)
            except Exception:
                pass
            clear_btn_icon.setScaleType(ImageView.ScaleType.CENTER)
            clear_btn.addView(clear_btn_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))

            def on_clear_click():
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
            search_btn_icon.setImageResource(self.install_ui._resolve_icon("ic_ab_search"))
            try:
                search_btn_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            search_btn_icon.setScaleType(ImageView.ScaleType.CENTER)
            search_btn.addView(search_btn_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
            search_btn.setOnClickListener(OnClickListener(lambda v: perform_search()))
            self.install_ui._apply_press_scale(search_btn)
            search_row.addView(search_btn, LinearLayout.LayoutParams(AndroidUtilities.dp(52), AndroidUtilities.dp(42), 0))
            search_container.addView(search_row, FrameLayout.LayoutParams(-1, -2))
            main_layout.addView(search_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

            # header row: repo button | subtitle | sort button
            header_row = FrameLayout(act)
            header_row_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(44))
            header_row_lp.topMargin = AndroidUtilities.dp(4)
            header_row_lp.bottomMargin = AndroidUtilities.dp(12)
            main_layout.addView(header_row, header_row_lp)

            repo_btn = FrameLayout(act)
            repo_btn.setClickable(True)
            repo_btn.setFocusable(True)
            try:
                repo_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(16), self.card_bg_color, self.card_pressed_color
                ))
            except Exception:
                pass
            repo_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8))
            repo_icon = ImageView(act)
            repo_icon.setImageResource(self.install_ui._resolve_icon("msg_smile_status"))
            try:
                repo_icon.setColorFilter(self.text_color)
            except Exception:
                pass
            repo_btn.addView(repo_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))

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
                show_icon_repo_sheet(self.install_ui, repos, on_select=self._handle_repo_select)

            repo_btn.setOnClickListener(OnClickListener(lambda v: show_repo_menu_handler()))
            self.install_ui._apply_press_scale(repo_btn)
            if settings.get("hide_repository_selection_button", False):
                repo_btn.setVisibility(View.GONE)
            header_row.addView(repo_btn, FrameLayout.LayoutParams(-2, -2, Gravity.LEFT | Gravity.CENTER_VERTICAL))

            subtitle = TextView(act)
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            subtitle.setText(strings["total_plugins_unknown"] if not self.icons else strings["icons_count"].format(len(self.icons)))
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
            header_row.addView(subtitle, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
            self.subtitle = subtitle

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
            sort_icon.setImageResource(self.install_ui._resolve_icon("msg_list"))
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
                show_icon_sort_menu(self.install_ui, act, self.current_sort_type, on_sort_selected)

            sort_btn.setOnClickListener(OnClickListener(lambda v: show_sort_menu_handler()))
            self.install_ui._apply_press_scale(sort_btn)
            header_row.addView(sort_btn, FrameLayout.LayoutParams(-2, -2, Gravity.RIGHT | Gravity.CENTER_VERTICAL))

            scroll = ScrollView(act)
            scroll.setFillViewport(True)
            scroll.setVerticalScrollBarEnabled(False)
            try:
                scroll.setNestedScrollingEnabled(True)
            except Exception:
                pass

            self.results_container = LinearLayout(act)
            self.results_container.setOrientation(LinearLayout.VERTICAL)
            self.results_container.setPadding(0, 0, 0, AndroidUtilities.dp(10))

            if self.show_loading_initial:
                content_wrapper = FrameLayout(act)
                content_wrapper.setLayoutParams(ScrollView.LayoutParams(-1, -2))

                loading_tv = TextView(act)
                loading_tv.setText(strings["total_plugins_unknown"])
                loading_tv.setGravity(Gravity.CENTER)
                loading_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                try:
                    loading_tv.setTextColor(self.secondary_text_color)
                except Exception:
                    pass
                loading_tv_lp = FrameLayout.LayoutParams(-2, -2, Gravity.CENTER)
                loading_tv_lp.topMargin = AndroidUtilities.dp(60)
                content_wrapper.addView(loading_tv, loading_tv_lp)

                # store callback so _update_current_fragment_icons can call it after data arrives
                def finish_loading():
                    try:
                        content_wrapper.removeView(loading_tv)
                        content_wrapper.addView(self.results_container, FrameLayout.LayoutParams(-1, -2))
                        if self.icons:
                            self.build_list_with_sort("alpha_az")
                        else:
                            self._show_empty_state()
                        if hasattr(self, 'subtitle'):
                            self.subtitle.setText(strings["icons_count"].format(len(self.icons)))
                    except Exception as e:
                        log(f"icons: finish_loading error: {e}")

                self._finish_loading = finish_loading
                self._loading_started = True
                scroll.addView(content_wrapper, ScrollView.LayoutParams(-1, -2))
            else:
                self._finish_loading = None
                self._loading_started = False
                scroll.addView(self.results_container, ScrollView.LayoutParams(-1, -2))

            class ScrollListener(dynamic_proxy(View.OnScrollChangeListener)):
                def __init__(self, outer):
                    super().__init__()
                    self.outer = outer
                    self.last_scroll_y = 0
                    self.scroll_threshold = AndroidUtilities.dp(50)
                def onScrollChange(self, v, scrollX, scrollY, oldScrollX, oldScrollY):
                    try:
                        if not self.outer.is_loading and len(self.outer.visible_icons) < len(self.outer.filtered_icons):
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

            main_layout.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1.0))
            self.search.addTextChangedListener(SearchTextWatcher(self, clear_btn))
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

        def build_list_with_sort(self, sort_type: str, q=None):
            self.current_sort_type = sort_type
            q = (q or "").strip()
            if q != self.last_search_query:
                self.last_search_query = q
            self.is_loading = True
            self.results_container.removeAllViews()
            self.visible_icons = []
            self.lazy_load_queue.clear()
            self._card_registry = []
            self._ticker_started = False

            if not q:
                filtered = list(self.icons)
            else:
                q_lower = q.lower()
                filtered = [
                    icon for icon in self.icons
                    if q_lower in str(icon.get("id") or "").lower()
                    or q_lower in str(icon.get("name") or "").lower()
                    or q_lower in str(icon.get("author") or "").lower()
                ]

            if not q:
                if sort_type == "alpha_az":
                    filtered.sort(key=lambda i: str(i.get("name") or i.get("id") or "").lower())
                elif sort_type == "alpha_za":
                    filtered.sort(key=lambda i: str(i.get("name") or i.get("id") or "").lower(), reverse=True)
                elif sort_type == "authors":
                    filtered.sort(key=lambda i: str(i.get("author") or "").lower())

            self.filtered_icons = filtered

            fragment = get_last_fragment()
            act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
            if not act:
                act = fragment.getContext() if fragment else None

            if not filtered:
                self._show_empty_state()
            else:
                self._load_initial_batch()

        def build_list(self, q):
            self.build_list_with_sort(self.current_sort_type, q)

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
                    R = find_class("org.telegram.messenger.R")
                    ghost_icon.setImageResource(getattr(R.drawable, "ayu_ghost"))
                    ghost_icon.setColorFilter(self.secondary_text_color)
                except Exception:
                    pass
                empty_container.addView(ghost_icon, LayoutHelper.createLinear(AndroidUtilities.dp(64), AndroidUtilities.dp(64), 0, 0, 0, 16))

                empty = TextView(act)
                empty.setText(strings["no_plugins"])
                empty.setGravity(Gravity.CENTER)
                empty.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                empty.setTextColor(self.secondary_text_color)
                empty_container.addView(empty, LayoutHelper.createLinear(-2, -2))

                self.results_container.addView(empty_container, LayoutHelper.createLinear(-1, -2))
                self.is_loading = False
            except Exception as e:
                log(f"icons: empty state error: {e}")

        def _add_items_with_animation(self, items_to_add):
            try:
                fragment = get_last_fragment()
                act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else fragment.getContext()
                gap = AndroidUtilities.dp(8)
                # pair items into rows of 2
                i = 0
                rows = []
                while i < len(items_to_add):
                    row = LinearLayout(act)
                    row.setOrientation(LinearLayout.HORIZONTAL)
                    left = items_to_add[i]
                    lp = LinearLayout.LayoutParams(0, AndroidUtilities.dp(160), 1.0)
                    lp.rightMargin = gap // 2
                    row.addView(left, lp)
                    if i + 1 < len(items_to_add):
                        right = items_to_add[i + 1]
                        rp = LinearLayout.LayoutParams(0, AndroidUtilities.dp(160), 1.0)
                        rp.leftMargin = gap // 2
                        row.addView(right, rp)
                    else:
                        # odd last item — fill half width with empty space
                        spacer = View(act)
                        sp = LinearLayout.LayoutParams(0, AndroidUtilities.dp(160), 1.0)
                        sp.leftMargin = gap // 2
                        row.addView(spacer, sp)
                    row_lp = LayoutHelper.createLinear(-1, -2, 0, 4, 0, 4)
                    self.results_container.addView(row, row_lp)
                    rows.append(row)
                    i += 2

                delay_step = 40
                for idx, row in enumerate(rows):
                    try:
                        row.setAlpha(0.0)
                        row.setScaleX(0.94)
                        row.setScaleY(0.94)
                        row.animate().alpha(1.0).scaleX(1.0).scaleY(1.0).setDuration(220).setStartDelay(idx * delay_step).start()
                    except Exception:
                        pass
                self.is_loading = False
            except Exception as e:
                log(f"icons: add items error: {e}")
                self.is_loading = False

        def _load_initial_batch(self):
            self.is_loading = True
            batch_size = min(self.batch_size, len(self.filtered_icons))

            def load_batch():
                try:
                    items_to_add = []
                    for i in range(batch_size):
                        if i < len(self.filtered_icons):
                            icon = self.filtered_icons[i]
                            self.visible_icons.append(icon)
                            items_to_add.append(self.make_item(icon))
                    run_on_ui_thread(lambda: self._add_items_with_animation(items_to_add))
                except Exception as e:
                    log(f"icons: initial batch error: {e}")
                    self.is_loading = False
            threading.Thread(target=load_batch, daemon=True).start()

        def _load_more_items(self):
            if self.is_loading or len(self.visible_icons) >= len(self.filtered_icons):
                return
            self.is_loading = True
            start_index = len(self.visible_icons)
            batch_size = min(self.batch_size, len(self.filtered_icons) - start_index)

            def load_batch():
                try:
                    items_to_add = []
                    for i in range(batch_size):
                        idx = start_index + i
                        if idx < len(self.filtered_icons):
                            icon = self.filtered_icons[idx]
                            self.visible_icons.append(icon)
                            items_to_add.append(self.make_item(icon))
                    run_on_ui_thread(lambda: self._add_items_with_animation(items_to_add))
                except Exception as e:
                    log(f"icons: batch load error: {e}")
                    self.is_loading = False
            threading.Thread(target=load_batch, daemon=True).start()

        def _start_ticker_if_needed(self):
            if self._ticker_started:
                return
            self._ticker_started = True
            import random
            Runnable = find_class("java.lang.Runnable")
            registry = self._card_registry
            ticker_runnable = [None]
            # track last swapped card and bitmap to prevent consecutive repeats
            last_iv = [None]
            last_bmp = [None]

            def tick():
                try:
                    candidates = [(iv, bitmaps) for iv, bitmaps in registry if len(bitmaps) >= 1]
                    if candidates:
                        # exclude last card if other options exist
                        filtered = [c for c in candidates if c[0] is not last_iv[0]]
                        if not filtered:
                            filtered = candidates
                        iv, bitmaps = random.choice(filtered)
                        # exclude last shown bitmap on this card if other options exist
                        other_bmps = [b for b in bitmaps if b is not last_bmp[0]]
                        bmp = random.choice(other_bmps if other_bmps else bitmaps)
                        last_iv[0] = iv
                        last_bmp[0] = bmp
                        def do_swap(v=iv, b=bmp):
                            try:
                                fade_out_done = make_end_action(lambda: (
                                    v.setImageBitmap(b),
                                    v.animate().alpha(1.0).setDuration(200).start()
                                ))
                                v.animate().alpha(0.0).setDuration(200).withEndAction(fade_out_done).start()
                            except Exception:
                                try:
                                    v.setImageBitmap(b)
                                except Exception:
                                    pass
                        run_on_ui_thread(do_swap)
                    try:
                        if registry:
                            registry[0][0].postDelayed(ticker_runnable[0], 2000)
                    except Exception:
                        pass
                except Exception as ex:
                    log(f"icons ticker: tick error: {ex}")

            class _TickerRunnable(dynamic_proxy(Runnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    tick()

            # helper: wrap lambda as Runnable for withEndAction
            def make_end_action(fn):
                class _R(dynamic_proxy(Runnable)):
                    def __init__(self):
                        super().__init__()
                    def run(self):
                        fn()
                return _R()

            ticker_runnable[0] = _TickerRunnable()

            def post_start():
                try:
                    if registry:
                        registry[0][0].postDelayed(ticker_runnable[0], 2000)
                except Exception as ex:
                    log(f"icons ticker: post_start error: {ex}")
            run_on_ui_thread(post_start)

        def make_item(self, icon):
            import random
            import ctypes
            act = get_last_fragment().getContext()

            icon_size_dp = 64

            card = FrameLayout(act)
            try:
                card.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(18), self.card_bg_color, self.card_pressed_color
                ))
            except Exception:
                pass

            inner = LinearLayout(act)
            inner.setOrientation(LinearLayout.VERTICAL)
            inner.setGravity(Gravity.CENTER)
            inner.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(10), AndroidUtilities.dp(8), AndroidUtilities.dp(10))
            card.addView(inner, FrameLayout.LayoutParams(-1, -1))

            all_urls = [u for u in (icon.get("preview") or []) if str(u).lower().endswith(".png") or str(u).lower().endswith(".svg")]

            icon_size_px = AndroidUtilities.dp(icon_size_dp)
            iv = ImageView(act)
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER)
            iv_lp = LinearLayout.LayoutParams(icon_size_px, icon_size_px)
            iv_lp.bottomMargin = AndroidUtilities.dp(8)
            inner.addView(iv, iv_lp)

            name_tv = TextView(act)
            try:
                name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                name_tv.setTypeface(AndroidUtilities.bold())
            name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            name_tv.setGravity(Gravity.CENTER)
            name_tv.setText(str(icon.get("name") or icon.get("id") or "Unknown"))
            name_tv.setTextColor(self.text_color)
            name_tv.setSingleLine(True)
            try:
                name_tv.setEllipsize(TextUtils.TruncateAt.END)
            except Exception:
                pass
            inner.addView(name_tv, LinearLayout.LayoutParams(-1, -2))

            icon_count = icon.get("icon_count")
            if icon_count is not None:
                try:
                    base_color = Theme.getColor(Theme.key_avatar_backgroundInProfileBlue)
                    r = (base_color >> 16) & 0xFF
                    g = (base_color >> 8) & 0xFF
                    b = base_color & 0xFF
                    fill_color = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
                    text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
                    count_pill = TextView(act)
                    count_pill.setText(f"{icon_count} icons")
                    count_pill.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 10)
                    count_pill.setGravity(Gravity.CENTER)
                    try:
                        count_pill.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        pass
                    count_pill.setTextColor(text_color)
                    pill_bg = GradientDrawable()
                    pill_bg.setShape(GradientDrawable.RECTANGLE)
                    pill_bg.setCornerRadius(AndroidUtilities.dp(6))
                    pill_bg.setColor(fill_color)
                    count_pill.setBackground(pill_bg)
                    count_pill.setPadding(
                        AndroidUtilities.dp(6), AndroidUtilities.dp(2),
                        AndroidUtilities.dp(6), AndroidUtilities.dp(2)
                    )
                    count_lp = LinearLayout.LayoutParams(-2, -2)
                    count_lp.topMargin = AndroidUtilities.dp(4)
                    inner.addView(count_pill, count_lp)
                except Exception:
                    pass

            cache = self.install_ui._preview_cache
            cache_lock = self.install_ui._preview_cache_lock
            loaded = []
            # register this card so the fragment-level ticker can swap it
            self._card_registry.append((iv, loaded))
            self._start_ticker_if_needed()

            def fetch_all(urls=all_urls, px=icon_size_px):
                for url in urls:
                    try:
                        with cache_lock:
                            bmp = cache.get(url)
                        if bmp is None:
                            r = requests.get(url, timeout=10)
                            if r.status_code != 200:
                                continue
                            data = r.content
                            if url.lower().endswith(".svg"):
                                try:
                                    SVG = find_class("com.caverock.androidsvg.SVG")
                                    ByteArrayInputStream = find_class("java.io.ByteArrayInputStream")
                                    Bitmap = find_class("android.graphics.Bitmap")
                                    Canvas = find_class("android.graphics.Canvas")
                                    stream = ByteArrayInputStream(data)
                                    svg = SVG.getFromInputStream(stream)
                                    # force render at target size, respects viewBox scaling
                                    svg.setDocumentWidth(px)
                                    svg.setDocumentHeight(px)
                                    bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888)
                                    canvas = Canvas(bmp)
                                    svg.renderToCanvas(canvas)
                                except Exception as e:
                                    log(f"icons svg render error: {e}")
                                    continue
                            else:
                                BitmapFactory = find_class("android.graphics.BitmapFactory")
                                opts = BitmapFactory.Options()
                                opts.inJustDecodeBounds = True
                                BitmapFactory.decodeByteArray(data, 0, len(data), opts)
                                scale = max(1, min(opts.outWidth // px, opts.outHeight // px))
                                opts.inSampleSize = scale
                                opts.inJustDecodeBounds = False
                                bmp = BitmapFactory.decodeByteArray(data, 0, len(data), opts)
                            if bmp is None:
                                continue
                            with cache_lock:
                                cache[url] = bmp
                        loaded.append(bmp)
                    except Exception as e:
                        log(f"icons preview load error: {e}")
                # show a random bitmap from all loaded ones
                if loaded:
                    import random
                    b = random.choice(loaded)
                    run_on_ui_thread(lambda b=b: iv.setImageBitmap(b))

            threading.Thread(target=fetch_all, daemon=True).start()
            return card

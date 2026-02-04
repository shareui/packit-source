import os
import tempfile
import requests
import threading
from android_utils import log, run_on_ui_thread
from client_utils import get_last_fragment, run_on_queue
from ui.bulletin import BulletinHelper
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper, BackupImageView, EditTextBoldCursor
from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, ProgressBar
from android.view import Gravity, View, MotionEvent
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.graphics import Color, PorterDuff
from android.text import TextWatcher, InputType
from android.animation import ObjectAnimator
from java import dynamic_proxy, jclass
from android_utils import OnClickListener
from android.content import Intent
from android.net import Uri
from java.io import File
from android.os import Build
from androidx.core.content import FileProvider
from hook_utils import find_class
from android import R as AndroidR
from com.exteragram.messenger.plugins import PluginsController
from org.telegram.messenger import ApplicationLoader


class InstallUI:
    def __init__(self, plugin):
        self.plugin = plugin
        self.repoManager = plugin.repoManager

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

    def _create_close_button(self, act, text="Close"):
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
            AndroidUtilities.dp(28),
            base_color,
            pressed_color
        ))
        close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_text = TextView(act)
        close_text.setText(text)
        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_text.setTypeface(AndroidUtilities.bold())
        close_text.setGravity(Gravity.CENTER)
        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))
        return close_btn

    def _setup_bottom_sheet(self, sheet):
        try:
            sheet.setAllowNestedScroll(True)
        except Exception:
            pass
        try:
            sheet.setResizeKeyboardArea(True)
        except Exception:
            pass
        try:
            if hasattr(sheet, 'setUseSmoothKeyboard'):
                sheet.setUseSmoothKeyboard(True)
        except Exception:
            pass
        try:
            if hasattr(sheet, 'setUseSmoothKeyboardTransition'):
                sheet.setUseSmoothKeyboardTransition(True)
        except Exception:
            pass
        try:
            if hasattr(sheet, 'setAnimateKeyboard'):
                sheet.setAnimateKeyboard(True)
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

    def _set_background_safe(self, view, color_str):
        try:
            view.setBackgroundColor(Color.parseColor(color_str))
        except Exception:
            pass

    def open(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
        if not act:
            return

        repos = []
        try:
            raw = self.plugin.repoManager.getRepositories() or []
            repos = []
            for r in raw:
                try:
                    if not r or not r.get("enabled"):
                        continue
                    name = str(r.get("name") or "").strip()
                    url = str(r.get("url") or "").strip()
                    if not name or not url:
                        continue
                    repos.append(r)
                except Exception:
                    continue
        except Exception:
            repos = []

        if not repos:
            BulletinHelper.show_error("No repositories configured")
            return

        def show_repo_sheet():
            try:
                is_dark_theme = False
                try:
                    is_dark_theme = Theme.isCurrentThemeDark()
                except Exception:
                    try:
                        bg_color = Theme.getColor(Theme.key_dialogBackground)
                        is_dark_theme = (bg_color & 0x00FFFFFF) < 0x00808080
                    except Exception:
                        pass
                
                sheet = BottomSheet(act, False, fragment.getResourceProvider())
                self._setup_bottom_sheet(sheet)
                root = LinearLayout(act)
                root.setOrientation(LinearLayout.VERTICAL)
                root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
                try:
                    root.setBackground(self._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
                except Exception:
                    try:
                        root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                    except Exception:
                        pass
                title = TextView(act)
                title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
                try:
                    title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    title.setTypeface(AndroidUtilities.bold())
                title.setText("Select a repository")
                title.setGravity(Gravity.CENTER)
                root.addView(title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 8))
                content_frame = FrameLayout(act)
                root.addView(content_frame, LayoutHelper.createLinear(-1, 0, 1.0))
                content_layout = LinearLayout(act)
                content_layout.setOrientation(LinearLayout.VERTICAL)
                content_frame.addView(content_layout, FrameLayout.LayoutParams(-1, -1))
                scroll = ScrollView(act)
                scroll.setFillViewport(True)
                scroll.setVerticalScrollBarEnabled(False)
                try:
                    scroll.setNestedScrollingEnabled(True)
                except Exception:
                    pass
                items = LinearLayout(act)
                items.setOrientation(LinearLayout.VERTICAL)
                scroll.addView(items)
                divider_color = Theme.getColor(Theme.key_divider)

                def add_divider():
                    d = View(act)
                    d.setBackgroundColor(divider_color)
                    items.addView(d, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 0, 16, 0))

                def make_repo_button(repo):
                    btn = LinearLayout(act)
                    btn.setOrientation(LinearLayout.HORIZONTAL)
                    btn.setClickable(True)
                    btn.setFocusable(True)
                    btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
                    try:
                        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                            AndroidUtilities.dp(8),
                            Theme.getColor(Theme.key_dialogBackground),
                            Theme.getColor(Theme.key_dialogBackgroundGray)
                        ))
                    except Exception:
                        try:
                            btn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector)))
                        except Exception:
                            pass

                    icon_iv = ImageView(act)
                    icon_name = repo.get('icon', 'msg_folders')
                    try:
                        R_tg = find_class("org.telegram.messenger.R")
                        icon_id = getattr(R_tg.drawable, icon_name)
                        icon_iv.setImageResource(icon_id)
                        if not is_dark_theme:
                            icon_iv.setColorFilter(Color.BLACK)
                        else:
                            icon_iv.setColorFilter(Color.WHITE)
                    except Exception:
                        pass
                    icon_iv.setScaleType(ImageView.ScaleType.CENTER)
                    icon_iv.setLayoutParams(LayoutHelper.createLinear(AndroidUtilities.dp(24), AndroidUtilities.dp(24), Gravity.CENTER_VERTICAL, 0, 0, 16, 0))
                    text_container = LinearLayout(act)
                    text_container.setOrientation(LinearLayout.VERTICAL)
                    text_container.setLayoutParams(LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))
                    name_tv = TextView(act)
                    try:
                        name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        name_tv.setTypeface(AndroidUtilities.bold())
                    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                    name_tv.setText(repo.get("name") or "Unnamed")
                    name_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                    url_tv = TextView(act)
                    url_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    url_tv.setText(repo.get("url") or "")
                    url_tv.setTextColor(Theme.getColor(Theme.key_dialogTextGray2))
                    text_container.addView(name_tv)
                    text_container.addView(url_tv, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))
                    btn.addView(icon_iv)
                    btn.addView(text_container)

                    def on_click(v):
                        try:
                            sheet.dismiss()
                        except Exception:
                            pass
                        self._open_repo_plugins(repo)

                    btn.setOnClickListener(OnClickListener(lambda v: on_click(v)))
                    return btn

                all_repos_btn = LinearLayout(act)
                all_repos_btn.setOrientation(LinearLayout.HORIZONTAL)
                all_repos_btn.setClickable(True)
                all_repos_btn.setFocusable(True)
                all_repos_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
                try:
                    all_repos_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(8),
                        Theme.getColor(Theme.key_dialogBackground),
                        Theme.getColor(Theme.key_dialogBackgroundGray)
                    ))
                except Exception:
                    try:
                        all_repos_btn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector)))
                    except Exception:
                        all_repos_btn.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                all_repos_icon = ImageView(act)
                try:
                    R_tg = find_class("org.telegram.messenger.R")
                    icon_id = getattr(R_tg.drawable, "msg_folders")
                    all_repos_icon.setImageResource(icon_id)
                    all_repos_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                except Exception:
                    pass
                all_repos_icon.setScaleType(ImageView.ScaleType.CENTER)
                all_repos_icon.setLayoutParams(LayoutHelper.createLinear(AndroidUtilities.dp(24), AndroidUtilities.dp(24), Gravity.CENTER_VERTICAL, 0, 0, 16, 0))
                all_repos_name = TextView(act)
                all_repos_name.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                all_repos_name.setText("All repositories")
                all_repos_name.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                all_repos_name.setTypeface(AndroidUtilities.bold())
                all_repos_url = TextView(act)
                all_repos_url.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                all_repos_url.setText("Search across all repositories")
                all_repos_url.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                all_repos_text_container = LinearLayout(act)
                all_repos_text_container.setOrientation(LinearLayout.VERTICAL)
                all_repos_text_container.setLayoutParams(LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))
                all_repos_text_container.addView(all_repos_name)
                all_repos_text_container.addView(all_repos_url, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))
                all_repos_btn.addView(all_repos_icon)
                all_repos_btn.addView(all_repos_text_container)
                
                def on_all_repos_click(v):
                    try:
                        sheet.dismiss()
                    except Exception:
                        pass
                    self._open_all_repos_plugins()
                
                all_repos_btn.setOnClickListener(OnClickListener(lambda v: on_all_repos_click(v)))
                self._apply_press_scale(all_repos_btn)
                items.addView(all_repos_btn, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 16, 4, 16, 4))

                add_divider()

                for idx, repo in enumerate(repos):
                    if idx != 0:
                        add_divider()
                    items.addView(make_repo_button(repo), LayoutHelper.createFrame(-1, -2, Gravity.TOP, 16, 4, 16, 4))

                content_frame.addView(scroll, FrameLayout.LayoutParams(-1, -1))
                close_btn = self._create_close_button(act)

                def on_close(v):
                    try:
                        sheet.dismiss()
                    except Exception:
                        pass

                close_btn.setOnClickListener(OnClickListener(lambda v: on_close(v)))
                self._apply_press_scale(close_btn)
                root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))
                sheet.setCustomView(root)
                sheet.show()
            except Exception as e:
                log(f"InstallUI repo sheet error: {e}")

        run_on_ui_thread(show_repo_sheet)

    def _show_loading_sheet(self, title: str, message: str = "Loading..."):
        fragment = get_last_fragment()
        if not fragment:
            return None
        act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
        if not act:
            return None
        try:
            sheet = BottomSheet(act, False, fragment.getResourceProvider())
            sheet.setApplyBottomPadding(False)
            sheet.setApplyTopPadding(False)
            root = LinearLayout(act)
            root.setOrientation(LinearLayout.VERTICAL)
            root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(20), AndroidUtilities.dp(20), AndroidUtilities.dp(20))
            try:
                root.setBackground(self._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
            except Exception:
                try:
                    root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                except Exception:
                    pass

            title_tv = TextView(act)
            title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
            try:
                title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                title_tv.setTypeface(AndroidUtilities.bold())
            title_tv.setText(title)
            title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            title_tv.setGravity(Gravity.CENTER)
            pb = ProgressBar(act, None, AndroidR.attr.progressBarStyleLarge)
            pb.setScaleX(1.5)
            pb.setScaleY(1.5)
            try:
                pb.setIndeterminateTintList(Theme.getColor(Theme.key_featuredStickers_addButton))
            except Exception:
                try:
                    pb.getIndeterminateDrawable().setColorFilter(Theme.getColor(Theme.key_dialogTextBlue), PorterDuff.Mode.MULTIPLY)
                except Exception:
                    pass
            msg = TextView(act)
            msg.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
            msg.setText(message)
            msg.setGravity(Gravity.CENTER)
            msg.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            root.addView(title_tv, LayoutHelper.createLinear(-1, -2, Gravity.CENTER, 0, 0, 0, 32))
            root.addView(pb, LayoutHelper.createLinear(-2, -2, Gravity.CENTER, 0, 0, 0, 32))
            root.addView(msg, LayoutHelper.createLinear(-1, -2, Gravity.CENTER))
            sheet.setCustomView(root)
            sheet.setCanDismissWithSwipe(False)
            try:
                sheet.setAllowNestedScroll(True)
            except Exception:
                pass
            try:
                sheet.setCanDismissWithSwipe(False)
            except Exception:
                pass
            sheet.show()
            return sheet
        except Exception as e:
            log(f"failed to show loading sheet: {e}")
            return None

    def _open_all_repos_plugins(self):
        fragment = get_last_fragment()
        if not fragment:
            return
        act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
        if not act:
            return

        loading_sheet = [None]

        def load_task():
            try:
                def open_loading():
                    loading_sheet[0] = self._show_loading_sheet("All repositories", "Loading...")

                run_on_ui_thread(open_loading)

                repos = self.repoManager.getRepositories()
                all_plugins = []
                
                for repo in repos:
                    if not repo.get("enabled"):
                        continue
                    
                    repo_url = (repo.get("url") or "").strip()
                    if not repo_url:
                        continue
                    
                    try:
                        response = requests.get(repo_url, timeout=10)
                        if response.status_code != 200:
                            continue
                        
                        config = response.json()
                        plugins = config.get("plugins", {})
                        
                        if isinstance(plugins, dict):
                            for pluginId, info in plugins.items():
                                if isinstance(info, dict):
                                    all_plugins.append({
                                        "id": pluginId,
                                        "repo_name": repo.get("name", "Unknown"),
                                        **info
                                    })
                        elif isinstance(plugins, list):
                            for item in plugins:
                                if isinstance(item, dict) and item.get("id"):
                                    all_plugins.append({
                                        "id": item.get("id"),
                                        "repo_name": repo.get("name", "Unknown"),
                                        **item
                                    })
                    except Exception as e:
                        log(f"failed to load repo {repo.get('name')}: {e}")
                        continue

                def show_plugins():
                    try:
                        def preload_stickers():
                            try:
                                mdc = MediaDataController.getInstance(0)
                                loaded_packs = set()
                                
                                for plugin in all_plugins:
                                    icon_str = plugin.get("icon")
                                    if icon_str and "/" in str(icon_str):
                                        pack_name = str(icon_str).split("/", 1)[0]
                                        if pack_name not in loaded_packs:
                                            try:
                                                mdc.loadStickersByEmojiOrName(pack_name, False, False)
                                                loaded_packs.add(pack_name)
                                            except Exception:
                                                pass
                            except Exception:
                                pass

                        preload_stickers()

                        def show_after_delay():
                            try:
                                if loading_sheet[0]:
                                    loading_sheet[0].dismiss()
                                self._show_plugins_sheet("All repositories", "", all_plugins)
                            except Exception as e:
                                log(f"failed to show plugins: {e}")
                        
                        threading.Timer(0.5, lambda: run_on_ui_thread(show_after_delay)).start()
                        
                    except Exception as e:
                        log(f"failed to show plugins: {e}")

                run_on_ui_thread(show_plugins)

            except Exception as e:
                def show_err():
                    try:
                        if loading_sheet[0]:
                            loading_sheet[0].dismiss()
                        BulletinHelper.show_error("Failed to load plugins")
                    except Exception:
                        pass

                run_on_ui_thread(show_err)
                log(f"failed to load all repos: {e}")

        run_on_queue(load_task)

    def _open_repo_plugins(self, repo):
        repo_name = repo.get("name") or "Unnamed"
        repo_url = (repo.get("url") or "").strip()

        if not repo_url:
            BulletinHelper.show_error("Repository URL is empty")
            return

        fragment = get_last_fragment()
        if not fragment:
            return
        act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
        if not act:
            return

        loading_sheet = [None]

        def load_task():
            try:
                def open_loading():
                    loading_sheet[0] = self._show_loading_sheet(repo_name, "Loading...")

                run_on_ui_thread(open_loading)

                r = requests.get(repo_url, timeout=20)
                if r.status_code != 200:
                    log(f"InstallUI: failed to download repo config '{repo_url}': HTTP {r.status_code}")
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

                def show_plugins():
                    try:
                        def preload_stickers():
                            try:
                                mdc = MediaDataController.getInstance(0)
                                loaded_packs = set()
                                
                                for plugin in plugins:
                                    icon_str = plugin.get("icon")
                                    if icon_str and "/" in str(icon_str):
                                        pack_name = str(icon_str).split("/", 1)[0]
                                        if pack_name not in loaded_packs:
                                            try:
                                                mdc.loadStickersByEmojiOrName(pack_name, False, False)
                                                loaded_packs.add(pack_name)
                                            except Exception:
                                                pass
                            except Exception:
                                pass
                        
                        preload_stickers()
                        
                        def show_after_delay():
                            try:
                                if loading_sheet[0]:
                                    loading_sheet[0].dismiss()
                                self._show_plugins_sheet(repo_name, repo_url, plugins)
                            except Exception:
                                pass
                        
                        threading.Timer(0.5, lambda: run_on_ui_thread(show_after_delay)).start()
                        
                    except Exception:
                        pass

                run_on_ui_thread(show_plugins)

            except Exception as e:
                def show_err():
                    try:
                        if loading_sheet[0]:
                            loading_sheet[0].dismiss()
                    except Exception:
                        pass
                    log(f"InstallUI: error while downloading repository '{repo_url}': {e}")
                    BulletinHelper.show_error("An error occurred while downloading")

                run_on_ui_thread(show_err)

        run_on_queue(load_task)

    def _show_plugins_sheet(self, repo_name: str, repo_url: str, plugins: list[dict]):
        fragment = get_last_fragment()
        if not fragment:
            return
        act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
        if not act:
            return

        def show():
            try:
                is_dark_theme = False
                try:
                    is_dark_theme = Theme.isCurrentThemeDark()
                except Exception:
                    try:
                        bg_color = Theme.getColor(Theme.key_dialogBackground)
                        is_dark_theme = (bg_color & 0x00FFFFFF) < 0x00808080
                    except Exception:
                        pass

                if is_dark_theme:
                    main_bg_color = "#000000"
                    card_bg_color = "#181818"
                    card_pressed_color = "#3C3C3C"
                    text_color = Color.WHITE
                    secondary_text_color = Color.parseColor("#CCCCCC")
                    hint_text_color = Color.parseColor("#999999")
                    cursor_color = Color.parseColor("#4FC3F7")
                    search_border_color = Color.parseColor("#3C3C3C")
                    search_stroke_width = AndroidUtilities.dp(2)
                else:
                    main_bg_color = "#f0f0f0"
                    card_bg_color = "#ffffff"
                    card_pressed_color = "#f5f5f5"
                    text_color = Color.BLACK
                    secondary_text_color = Color.parseColor("#666666")
                    hint_text_color = Color.parseColor("#999999")
                    cursor_color = Color.parseColor("#2196F3")
                    search_border_color = Color.parseColor("#e0e0e0")
                    search_stroke_width = 0

                try:
                    R_tg = find_class("org.telegram.messenger.R")
                except Exception:
                    try:
                        R_tg = jclass("org.telegram.messenger.R")
                    except Exception:
                        R_tg = None

                def resolve_icon(name):
                    if not R_tg:
                        return 0
                    try:
                        return getattr(R_tg.drawable, name)
                    except Exception:
                        return 0

                sheet = BottomSheet(act, False, fragment.getResourceProvider())
                self._setup_bottom_sheet(sheet)
                try:
                    sheet.setCanDismissWithSwipe(False)
                except Exception:
                    pass
                root = LinearLayout(act)
                root.setOrientation(LinearLayout.VERTICAL)
                root.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(8))
                try:
                    root.setBackground(self._create_rounded_bg(Color.parseColor(main_bg_color)))
                except Exception:
                    self._set_background_safe(root, main_bg_color)
                title = TextView(act)
                title.setTextColor(text_color)
                title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
                try:
                    title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    title.setTypeface(AndroidUtilities.bold())
                title.setText(repo_name)
                title.setGravity(Gravity.CENTER)
                root.addView(title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 8))
                content_frame = FrameLayout(act)
                root.addView(content_frame, LayoutHelper.createLinear(-1, 0, 1.0))
                content_layout = LinearLayout(act)
                content_layout.setOrientation(LinearLayout.VERTICAL)
                content_frame.addView(content_layout, FrameLayout.LayoutParams(-1, -1))
                search_container = FrameLayout(act)
                pill = GradientDrawable()
                pill.setShape(GradientDrawable.RECTANGLE)
                pill.setCornerRadius(AndroidUtilities.dp(50))
                try:
                    pill.setStroke(search_stroke_width, search_border_color)
                except Exception:
                    pass
                try:
                    pill.setColor(Color.parseColor(card_bg_color))
                except Exception:
                    pass
                search_container.setBackground(pill)
                search_container.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(3), AndroidUtilities.dp(16), AndroidUtilities.dp(3))
                search = EditTextBoldCursor(act)
                search.setHint("Search plugins...")
                search.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                search.setSingleLine(True)
                search.setInputType(InputType.TYPE_CLASS_TEXT)
                search.setBackgroundColor(0)
                search.setTextColor(text_color)
                try:
                    search.setHintTextColor(hint_text_color)
                except Exception:
                    pass
                try:
                    search.setCursorColor(cursor_color)
                except Exception:
                    pass
                try:
                    pad = AndroidUtilities.dp(16)
                    search.setPadding(pad, pad, pad, pad)
                except Exception:
                    pass
                search_container.addView(search, LayoutHelper.createFrame(-1, -2, Gravity.CENTER_VERTICAL))
                content_layout.addView(search_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))
                header_row = LinearLayout(act)
                header_row.setOrientation(LinearLayout.HORIZONTAL)
                header_row.setGravity(Gravity.CENTER_VERTICAL)
                subtitle = TextView(act)
                subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                subtitle.setText(f"Total plugins: {len(plugins)}")
                subtitle.setGravity(Gravity.CENTER)
                subtitle.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(6), AndroidUtilities.dp(12), AndroidUtilities.dp(6))
                try:
                    subtitle.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(50),
                        Color.parseColor(card_bg_color),
                        Color.parseColor(card_pressed_color)
                    ))
                except Exception:
                    try:
                        subtitle.setBackgroundColor(Color.parseColor(card_bg_color))
                    except Exception:
                        pass
                try:
                    subtitle.setTextColor(secondary_text_color)
                except Exception:
                    pass
                header_row.addView(subtitle, LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0))
                spacer = View(act)
                header_row.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))
                sort_btn = FrameLayout(act)
                sort_btn.setClickable(True)
                sort_btn.setFocusable(True)
                sort_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(16),
                    Color.parseColor(card_bg_color),
                    Color.parseColor(card_pressed_color)
                ))
                sort_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(8))
                sort_icon = ImageView(act)
                icon_id = resolve_icon("msg_list")
                if icon_id:
                    sort_icon.setImageResource(icon_id)
                try:
                    sort_icon.setColorFilter(secondary_text_color)
                except Exception:
                    pass
                sort_btn.addView(sort_icon, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
                
                def show_sort_menu():
                    try:
                        sort_sheet = BottomSheet(act, False, fragment.getResourceProvider())
                        sort_sheet.setApplyBottomPadding(False)
                        sort_sheet.setApplyTopPadding(False)
                        sort_root = LinearLayout(act)
                        sort_root.setOrientation(LinearLayout.VERTICAL)
                        sort_root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
                        try:
                            sort_root.setBackground(self._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
                        except Exception:
                            try:
                                sort_root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                            except Exception:
                                pass
                        
                        sort_title = TextView(act)
                        sort_title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                        sort_title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
                        try:
                            sort_title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                        except Exception:
                            sort_title.setTypeface(AndroidUtilities.bold())
                        sort_title.setText("Sort Plugins")
                        sort_title.setGravity(Gravity.CENTER)
                        sort_root.addView(sort_title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 16))
                        
                        def create_sort_option(text, sort_type):
                            option = LinearLayout(act)
                            option.setOrientation(LinearLayout.HORIZONTAL)
                            option.setGravity(Gravity.CENTER_VERTICAL)
                            option.setClickable(True)
                            option.setFocusable(True)
                            option.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
                            is_current = (sort_type == current_sort_type)
                            
                            try:
                                if is_current:
                                    option.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                                        AndroidUtilities.dp(8),
                                        Theme.getColor(Theme.key_featuredStickers_addButton),
                                        Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
                                    ))
                                else:
                                    option.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                                        AndroidUtilities.dp(8),
                                        Theme.getColor(Theme.key_dialogBackground),
                                        Theme.getColor(Theme.key_dialogBackgroundGray)
                                    ))
                            except Exception:
                                try:
                                    option.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector)))
                                except Exception:
                                    pass
                            
                            option_text = TextView(act)
                            option_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                            option_text.setText(text)
                            if is_current:
                                option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
                            else:
                                option_text.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                            option_layout = LinearLayout(act)
                            option_layout.setOrientation(LinearLayout.HORIZONTAL)
                            option_layout.setGravity(Gravity.CENTER_VERTICAL)
                            icon = ImageView(act)
                            icon_id = None
                            if "A-Z" in text:
                                icon_id = resolve_icon("msg_archive")
                            elif "Z-A" in text:
                                icon_id = resolve_icon("msg_unarchive")
                            elif "Authors" in text:
                                icon_id = resolve_icon("msg_online")
                            elif "Repository" in text:
                                icon_id = resolve_icon("menu_intro_solar")
                                
                            if icon_id:
                                icon.setImageResource(icon_id)
                                try:
                                    icon.setColorFilter(Theme.getColor(Theme.key_dialogTextGray2))
                                except Exception:
                                    pass
                                icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                                icon_lp.rightMargin = AndroidUtilities.dp(16)
                                option_layout.addView(icon, icon_lp)
                            
                            option_layout.addView(option_text, LayoutHelper.createLinear(-1, -2))
                            option.addView(option_layout, LayoutHelper.createLinear(-1, -2))
                            
                            def on_option_click(v):
                                try:
                                    sort_sheet.dismiss()
                                    build_list_with_sort(sort_type)
                                except Exception:
                                    pass
                            
                            option.setOnClickListener(OnClickListener(lambda v: on_option_click(v)))
                            self._apply_press_scale(option)
                            return option
                        
                        sort_root.addView(create_sort_option("As in Repository", "repo_order"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
                        divider = View(act)
                        divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
                        sort_root.addView(divider, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
                        sort_root.addView(create_sort_option("Alphabetically A-Z", "alpha_az"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
                        divider3 = View(act)
                        divider3.setBackgroundColor(Theme.getColor(Theme.key_divider))
                        sort_root.addView(divider3, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
                        sort_root.addView(create_sort_option("Alphabetically Z-A", "alpha_za"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
                        divider2 = View(act)
                        divider2.setBackgroundColor(Theme.getColor(Theme.key_divider))
                        sort_root.addView(divider2, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
                        sort_root.addView(create_sort_option("By Authors", "authors"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
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
                            AndroidUtilities.dp(28),
                            base_color,
                            pressed_color
                        ))
                        close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
                        close_btn.setClickable(True)
                        close_btn.setFocusable(True)
                        close_text = TextView(act)
                        close_text.setText("Close")
                        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                        close_text.setTypeface(AndroidUtilities.bold())
                        close_text.setGravity(Gravity.CENTER)
                        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
                        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))

                        def on_close_sort(v):
                            try:
                                sort_sheet.dismiss()
                            except Exception:
                                pass

                        close_btn.setOnClickListener(OnClickListener(lambda v: on_close_sort(v)))
                        self._apply_press_scale(close_btn)
                        sort_root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))
                        
                        sort_sheet.setCustomView(sort_root)
                        sort_sheet.show()
                    except Exception as e:
                        log(f"InstallUI: sort menu error: {e}")
                
                sort_btn.setOnClickListener(OnClickListener(lambda v: show_sort_menu()))
                self._apply_press_scale(sort_btn)
                header_row.addView(sort_btn, LayoutHelper.createLinear(-2, -2))
                content_layout.addView(header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))
                scroll = ScrollView(act)
                scroll.setFillViewport(True)
                scroll.setVerticalScrollBarEnabled(False)
                try:
                    scroll.setNestedScrollingEnabled(True)
                except Exception:
                    pass
                items = LinearLayout(act)
                items.setOrientation(LinearLayout.VERTICAL)
                scroll.addView(items)

                def score(p, q):
                    if not q:
                        return (0, 0)
                    ql = q.lower()
                    pid = str(p.get("id") or "").lower()
                    name = str(p.get("name") or "").lower()
                    desc = str(p.get("description") or "").lower()
                    if ql in pid:
                        return (0, 0 if pid.startswith(ql) else 1)
                    if ql in name:
                        return (1, 0 if name.startswith(ql) else 1)
                    if ql in desc:
                        return (2, 0)
                    return (3, 0)

                def make_item(p):
                    row = FrameLayout(act)
                    container = LinearLayout(act)
                    container.setOrientation(LinearLayout.VERTICAL)
                    container.setGravity(Gravity.TOP)
                    container.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(12), AndroidUtilities.dp(12), AndroidUtilities.dp(12))
                    try:
                        container.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                            AndroidUtilities.dp(18),
                            Color.parseColor(card_bg_color),
                            Color.parseColor(card_pressed_color)
                        ))
                    except Exception:
                        try:
                            container.setBackgroundColor(Color.parseColor(card_bg_color))
                        except Exception:
                            pass

                    icon_str = p.get("icon")
                    icon_size_dp = 52
                    top_row = LinearLayout(act)
                    top_row.setOrientation(LinearLayout.HORIZONTAL)
                    top_row.setGravity(Gravity.TOP)
                    container.addView(top_row, LayoutHelper.createLinear(-1, -2))
                    if icon_str:
                        try:
                            icon_view = BackupImageView(act)
                            icon_view.setRoundRadius(AndroidUtilities.dp(8))
                            try:
                                icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
                            except Exception:
                                pass

                            icon_size_px = AndroidUtilities.dp(icon_size_dp)
                            icon_lp = LinearLayout.LayoutParams(icon_size_px, icon_size_px)
                            icon_lp.rightMargin = AndroidUtilities.dp(12)
                            icon_lp.topMargin = AndroidUtilities.dp(2)
                            top_row.addView(icon_view, icon_lp)

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
                                            None,
                                            None,
                                            0,
                                            1
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
                                    self._run_delayed(1500, try_load_icon)
                                except Exception:
                                    pass
                        except Exception as e:
                            log(f"InstallUI: icon init error for '{p.get('id')}': {e}")

                    col = LinearLayout(act)
                    col.setOrientation(LinearLayout.VERTICAL)
                    name_tv = TextView(act)
                    try:
                        name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        name_tv.setTypeface(AndroidUtilities.bold())
                    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
                    display_name = p.get("name") or p.get("id") or "Unknown"
                    name_tv.setText(str(display_name))
                    name_tv.setTextColor(text_color)
                    id_tv = TextView(act)
                    id_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                    version_text = str(p.get("version") or "").strip()
                    author_text = str(p.get("author") or "").strip()
                    if version_text and author_text:
                        id_tv.setText(f"v{version_text} • {author_text}")
                    elif version_text:
                        id_tv.setText(f"v{version_text}")
                    else:
                        id_tv.setText(author_text)
                    try:
                        id_tv.setTextColor(secondary_text_color)
                    except Exception:
                        pass
                    desc_tv = TextView(act)
                    desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                    desc_tv.setText(str(p.get("description") or ""))
                    try:
                        desc_tv.setTextColor(secondary_text_color)
                    except Exception:
                        pass
                    col.addView(name_tv, LayoutHelper.createLinear(-1, -2))
                    col.addView(id_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))
                    buttons = LinearLayout(act)
                    buttons.setOrientation(LinearLayout.HORIZONTAL)
                    buttons.setGravity(Gravity.LEFT)
                    buttons.setPadding(0, AndroidUtilities.dp(8), 0, 0)

                    def open_system_share():
                        try:
                            sheet.dismiss()
                            plugin_id = p.get("id")
                            if not plugin_id:
                                BulletinHelper.show_error("Plugin has no id")
                                return
                            link = p.get("link") or p.get("raw")
                            if not link:
                                BulletinHelper.show_error("Plugin has no download link")
                                return
                            temp_dir = tempfile.gettempdir()
                            temp_path = os.path.join(temp_dir, f"{plugin_id}.plugin")
                            try:
                                r = requests.get(link, timeout=30)
                                if r.status_code != 200:
                                    BulletinHelper.show_error("Failed to download plugin for sharing")
                                    return
                                with open(temp_path, "wb") as f:
                                    f.write(r.content)
                                file_obj = File(temp_path)
                                if Build.VERSION.SDK_INT >= 24:
                                    try:
                                        uri = FileProvider.getUriForFile(act, act.getPackageName() + ".fileprovider", file_obj)
                                        act.grantUriPermission("", uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                    except Exception:
                                        try:
                                            if Build.VERSION.SDK_INT >= 24:
                                                uri = Uri.parse("content://" + act.getPackageName() + ".fileprovider/" + file_obj.getName())
                                            else:
                                                uri = Uri.fromFile(file_obj)
                                        except Exception:
                                            uri = Uri.fromFile(file_obj)
                                else:
                                    uri = Uri.fromFile(file_obj)
                                intent = Intent(Intent.ACTION_SEND)
                                intent.setType("application/octet-stream")
                                intent.putExtra(Intent.EXTRA_STREAM, uri)
                                intent.putExtra(Intent.EXTRA_SUBJECT, f"{display_name} Plugin")
                                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                chooser = Intent.createChooser(intent, "Share Plugin")
                                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                act.startActivity(chooser)
                                BulletinHelper.show_info("Plugin shared successfully")
                            except Exception as e:
                                log(f"InstallUI: failed to prepare file for sharing: {e}")
                                BulletinHelper.show_error("Failed to prepare file for sharing")
                        except Exception as e:
                            log(f"InstallUI: failed to open share: {e}")
                            BulletinHelper.show_error("Failed to share")

                    def copy_share_link():
                        try:
                            plugin_id = p.get("id")
                            if not plugin_id:
                                BulletinHelper.show_error("Plugin has no id")
                                return
                            share_link = f"tg://packit?install={repo_name}&{plugin_id}"
                            AndroidUtilities.addToClipboard(share_link)
                            try:
                                BulletinHelper.show_copied_to_clipboard()
                            except Exception:
                                BulletinHelper.show_info("Copied")
                        except Exception as e:
                            log(f"InstallUI: failed to copy link: {e}")

                    def create_pill(background, pressed, padding_h=14, padding_v=8):
                        pill_btn = LinearLayout(act)
                        pill_btn.setOrientation(LinearLayout.HORIZONTAL)
                        pill_btn.setGravity(Gravity.CENTER_VERTICAL)
                        pill_btn.setPadding(AndroidUtilities.dp(padding_h), AndroidUtilities.dp(padding_v), AndroidUtilities.dp(padding_h), AndroidUtilities.dp(padding_v))
                        pill_btn.setClickable(True)
                        pill_btn.setFocusable(True)
                        pill_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                            AndroidUtilities.dp(18),
                            background,
                            pressed
                        ))
                        return pill_btn

                    base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                    pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
                    install_btn = create_pill(base_color, pressed_color)
                    install_icon = ImageView(act)
                    icon_id = resolve_icon("msg_download")
                    if icon_id:
                        install_icon.setImageResource(icon_id)
                    try:
                        install_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
                    except Exception:
                        pass
                    icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                    icon_lp.rightMargin = AndroidUtilities.dp(6)
                    install_btn.addView(install_icon, icon_lp)
                    install_text = TextView(act)
                    install_text.setText("Install")
                    install_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                    install_text.setTypeface(AndroidUtilities.bold())
                    install_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
                    install_btn.addView(install_text)

                    def on_install(_=None):
                        try:
                            sheet.dismiss()
                        except Exception:
                            pass
                        self._install_via_system_dialog(p)
                    install_btn.setOnClickListener(OnClickListener(lambda v: on_install(v)))
                    self._apply_press_scale(install_btn)
                    buttons.addView(install_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 8, 0))
                    spacer = View(act)
                    buttons.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))

                    def create_icon_pill(icon_name, handler):
                        pill = create_pill(0, 0, padding_h=8, padding_v=8)
                        pill_icon = ImageView(act)
                        icon_id_inner = resolve_icon(icon_name)
                        if icon_id_inner:
                            pill_icon.setImageResource(icon_id_inner)
                        try:
                            pill_icon.setColorFilter(secondary_text_color)
                        except Exception:
                            pass
                        icon_lp_inner = LinearLayout.LayoutParams(AndroidUtilities.dp(22), AndroidUtilities.dp(22))
                        pill.addView(pill_icon, icon_lp_inner)
                        pill.setOnClickListener(OnClickListener(lambda v: handler()))
                        self._apply_press_scale(pill)
                        return pill

                    link_btn = create_icon_pill("msg_link2", copy_share_link)
                    buttons.addView(link_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 4, 0))
                    share_btn = create_icon_pill("msg_share", open_system_share)
                    buttons.addView(share_btn, LayoutHelper.createLinear(-2, -2))
                    top_row.addView(col, LayoutHelper.createLinear(-1, -2))

                    if p.get("description"):
                        desc_lp = LayoutHelper.createLinear(-1, -2, 0, 6, 0, 0)
                        container.addView(desc_tv, desc_lp)

                    buttons_lp = LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0)
                    container.addView(buttons, buttons_lp)
                    row.addView(container, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 0, 0, 0))
                    return row

                def build_list_with_sort(sort_type: str, q: str | None = None):
                    nonlocal current_sort_type
                    current_sort_type = sort_type
                    q = (q or "").strip()
                    items.removeAllViews()
                    filtered = []
                    for p in plugins:
                        if score(p, q)[0] < 3:
                            filtered.append(p)

                    if not q:
                        filtered = list(plugins)
                    else:
                        filtered.sort(key=lambda p: score(p, q))

                    if sort_type == "alpha_az":
                        filtered.sort(key=lambda p: str(p.get("name") or p.get("id") or "").lower())
                    elif sort_type == "alpha_za":
                        filtered.sort(key=lambda p: str(p.get("name") or p.get("id") or "").lower(), reverse=True)
                    elif sort_type == "authors":
                        filtered.sort(key=lambda p: str(p.get("author") or "").lower())
                    elif sort_type == "repo_order":
                        pass

                    if not filtered:
                        empty = TextView(act)
                        empty.setText("No plugins")
                        empty.setGravity(Gravity.CENTER)
                        empty.setTextColor(Theme.getColor(Theme.key_dialogTextGray2))
                        items.addView(empty, LayoutHelper.createLinear(-1, -2, 0, 24, 0, 24))
                    else:
                        for i, p in enumerate(filtered):
                            items.addView(make_item(p), LayoutHelper.createLinear(-1, -2, 0, 4, 0, 4))

                current_sort_type = "repo_order"
                
                def build_list(q: str | None):
                    q = (q or "").strip()
                    items.removeAllViews()
                    filtered = []
                    for p in plugins:
                        if score(p, q)[0] < 3:
                            filtered.append(p)
                    if not q:
                        filtered = list(plugins)
                    else:
                        filtered.sort(key=lambda p: score(p, q))

                    if not filtered:
                        empty = TextView(act)
                        empty.setText("No plugins")
                        empty.setGravity(Gravity.CENTER)
                        empty.setTextColor(Theme.getColor(Theme.key_dialogTextGray2))
                        items.addView(empty, LayoutHelper.createLinear(-1, -2, 0, 24, 0, 24))
                    else:
                        for i, p in enumerate(filtered):
                            items.addView(make_item(p), LayoutHelper.createLinear(-1, -2, 0, 4, 0, 4))

                build_list("")

                class Watcher(dynamic_proxy(TextWatcher)):
                    def __init__(self):
                        super().__init__()

                    def beforeTextChanged(self, s, start, count, after):
                        pass

                    def onTextChanged(self, s, start, before, count):
                        pass

                    def afterTextChanged(self, editable):
                        try:
                            build_list(str(editable))
                        except Exception:
                            pass

                search.addTextChangedListener(Watcher())

                try:
                    class _OnTouch(dynamic_proxy(View.OnTouchListener)):
                        def __init__(self, fn):
                            super().__init__()
                            self._fn = fn

                        def onTouch(self, v, event):
                            return self._fn(v, event)

                    def _on_search_touch(v, event):
                        try:
                            if event.getActionMasked() == MotionEvent.ACTION_DOWN:
                                v.requestFocus()
                                AndroidUtilities.showKeyboard(v)
                        except Exception:
                            pass
                        return False

                    search.setOnTouchListener(_OnTouch(_on_search_touch))
                except Exception:
                    pass
                try:
                    search.setFocusable(True)
                    search.setFocusableInTouchMode(True)
                    search.requestFocus()
                    AndroidUtilities.showKeyboard(search)
                except Exception:
                    pass

                content_layout.addView(scroll, LayoutHelper.createLinear(-1, 0, 1.0))
                close_btn = self._create_close_button(act)

                def on_close(v):
                    try:
                        sheet.dismiss()
                    except Exception:
                        pass

                close_btn.setOnClickListener(OnClickListener(lambda v: on_close(v)))
                self._apply_press_scale(close_btn)
                root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))
                sheet.setCustomView(root)
                sheet.show()
            except Exception as e:
                log(f"InstallUI plugins sheet error: {e}")

        run_on_ui_thread(show)

    def _install_via_system_dialog(self, plugin_info: dict):
        plugin_id = plugin_info.get("id")
        url = plugin_info.get("link") or plugin_info.get("raw")

        if not plugin_id or not url:
            BulletinHelper.show_error("Plugin has no link")
            return

        fragment = get_last_fragment()
        if not fragment:
            return

        def task():
            try:
                BulletinHelper.show_info("Downloading plugin...")

                r = requests.get(url, timeout=30)
                if r.status_code != 200:
                    log(f"InstallUI: failed to download plugin '{plugin_id}' from '{url}': HTTP {r.status_code}")
                    raise Exception(f"HTTP {r.status_code}")

                pkg = ApplicationLoader.applicationContext.getPackageName()
                plugins_dir = f"/data/data/{pkg}/files/plugins"
                try:
                    os.makedirs(plugins_dir, exist_ok=True)
                except Exception:
                    pass

                temp_path = os.path.join(plugins_dir, f".temp_{plugin_id}.plugin")
                with open(temp_path, "wb") as f:
                    f.write(r.content)

                def open_dialog():
                    try:
                        PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)
                    except Exception as e:
                        BulletinHelper.show_error(f"Failed to open install dialog: {e}")

                run_on_ui_thread(open_dialog)
            except Exception as e:
                log(f"InstallUI: error while downloading plugin '{plugin_id}' from '{url}': {e}")
                run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while downloading"))

        run_on_queue(task)
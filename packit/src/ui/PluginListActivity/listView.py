# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import threading
from collections import deque
from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView
from android.util import TypedValue
from android.text import TextWatcher, InputType
from android.view.inputmethod import EditorInfo
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy
from hook_utils import find_class
from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from packutil import logx
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"listView: import elyx failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"listView: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, EditTextBoldCursor
except Exception as e:
    import android_utils as _au; _au.log(f"listView: import LayoutHelper, EditTextBoldCursor failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"listView: import AndroidUtilities, R_tg failed: {e}")

from .helpers import uiHelpers
from .sheets.AISearchSheet import show_ai_search_sheet
from .sheets.SortBottomSheet import show_sort_menu
from .filter.filterDrawer import show_tag_drawer
from ...utils.media import playSound
from .helpers.utils import _build_plugin_count_label


def build_list_view(self) -> View:
    logx(f"InstallUI: build_list_view enter id={id(self)} show_loading_initial={self.show_loading_initial} loading_container={getattr(self, 'loading_container', None) is not None} data_ready_before_view={getattr(self, '_data_ready_before_view', False)}", True)
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
    except Exception:
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
                if _s.get("live_search", True) and not getattr(self.outer, "_ai_result_active", False):
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

    def on_clear_click():
        try:
            from elyx import assets
            playSound(assets.sounds.clear_search.path_str, "sfx_clear_search")
        except Exception:
            pass
        try:
            self._ai_result_active = False
            self._ai_result_plugins = []
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

    def onSearchBtnClick(v):
        try:
            from elyx import assets
            playSound(assets.sounds.search_btn.path_str, "sfx_search")
        except Exception:
            pass
        perform_search()

    search_btn.setOnClickListener(OnClickListener(onSearchBtnClick))
    self.install_ui._apply_press_scale(search_btn)
    try:
        from elyx import settings as _s
        if _s.get("live_search", True):
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
    ai_pill = LinearLayout(act)
    ai_pill.setOrientation(LinearLayout.HORIZONTAL)
    ai_pill.setGravity(Gravity.CENTER_VERTICAL)
    ai_pill.setClickable(True)
    ai_pill.setFocusable(True)
    try:
        ai_pill.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(16), self.card_bg_color, self.card_pressed_color
        ))
    except Exception:
        pass
    ai_pill.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(8), AndroidUtilities.dp(12), AndroidUtilities.dp(8))

    ai_pill_icon = ImageView(act)
    ai_pill_icon_id = self.install_ui._resolve_icon("msg_search")
    ai_pill_icon.setImageResource(ai_pill_icon_id)
    try:
        ai_pill_icon.setColorFilter(self.text_color)
    except Exception:
        pass
    ai_pill_icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
    ai_pill_icon_lp.rightMargin = AndroidUtilities.dp(6)
    ai_pill.addView(ai_pill_icon, ai_pill_icon_lp)

    ai_pill_label = TextView(act)
    ai_pill_label.setText("AI")
    ai_pill_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    ai_pill_label.setTypeface(AndroidUtilities.bold())
    try:
        ai_pill_label.setTextColor(self.text_color)
    except Exception:
        pass
    ai_pill.addView(ai_pill_label, LinearLayout.LayoutParams(-2, -2))

    ai_pill_lp = FrameLayout.LayoutParams(-2, -2, Gravity.LEFT | Gravity.CENTER_VERTICAL)
    header_row.addView(ai_pill, ai_pill_lp)

    def on_ai_pill_click(v):
        try:
            def _on_ai_results(names, query):
                # set search field text and filter list by AI-returned plugin names
                try:
                    ai_marker = "%ai response%"
                    # filter visible plugins to only those returned by AI, preserving order
                    name_set = set(n.lower() for n in names)
                    ordered = []
                    for name in names:
                        for p in self.plugins:
                            pname = str(p.get("name") or p.get("id") or "").strip()
                            if pname.lower() == name.lower():
                                ordered.append(p)
                                break
                    # fallback: include any plugin whose name is in name_set but not yet matched
                    matched_names = set(str(p.get("name") or p.get("id") or "").strip().lower() for p in ordered)
                    for p in self.plugins:
                        pname = str(p.get("name") or p.get("id") or "").strip().lower()
                        if pname in name_set and pname not in matched_names:
                            ordered.append(p)
                            matched_names.add(pname)
                    self._ai_result_plugins = ordered
                    # set flag before setText so watcher skips live search
                    self._ai_result_active = True
                    self.last_search_query = ai_marker
                    self.search.setText(ai_marker)
                    self.filtered_plugins = ordered
                    self.visible_plugins = []
                    self.lazy_load_queue = deque()
                    self.results_container.removeAllViews()
                    if hasattr(self, "subtitle"):
                        total = len(self.plugins)
                        self.subtitle.setText(f"{len(ordered)}/{_build_plugin_count_label(total)}")
                    self._load_initial_batch()
                except Exception as e:
                    logx(f"listView: on_ai_results error: {e}", False)

            show_ai_search_sheet(self.install_ui, act, on_ai_results=_on_ai_results)
        except Exception as e:
            logx(f"listView: ai search sheet error: {e}", False)

    ai_pill.setOnClickListener(OnClickListener(on_ai_pill_click))
    self.install_ui._apply_press_scale(ai_pill)

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
            logx(f"InstallUI: build_list_view skip animation, gate already done id={id(self)}", True)
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
                # data may have already arrived before this view was built, carry that over to the gate
                data_already_ready = getattr(self, '_data_ready_before_view', False)
                self._data_ready_before_view = False
                self._load_gate = [False, data_already_ready]  # [anim_done, data_ready]
                logx(f"InstallUI: _load_gate created id={id(self)} data_already_ready={data_already_ready}", True)

                def _try_finish():
                    logx(f"InstallUI: _try_finish id={id(self)} anim_done={self._load_gate[0]} data_ready={self._load_gate[1]}", True)
                    if self._load_gate[0] and self._load_gate[1]:
                        self._finish_loading_and_show_plugins(content_wrapper)

                def _on_anim_done():
                    logx(f"InstallUI: _on_anim_done fired id={id(self)}", True)
                    self._load_gate[0] = True
                    _try_finish()

                def _on_data_ready():
                    logx(f"InstallUI: _on_data_ready fired id={id(self)}", True)
                    self._load_gate[1] = True
                    run_on_ui_thread(_try_finish)

                self._on_data_ready_cb = _on_data_ready
                logx(f"InstallUI: _on_data_ready_cb assigned id={id(self)}", True)
                threading.Timer(1.0, lambda: run_on_ui_thread(_on_anim_done)).start()
            else:
                logx(f"InstallUI: build_list_view no loading_container, finishing immediately id={id(self)}", True)
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
        squareFab = True
        try:
            from hook_utils import find_class as _find_class
            _ExteraConfig = _find_class("com.exteragram.messenger.ExteraConfig")
            raw = _ExteraConfig.squareFab
            squareFab = bool(raw)
        except Exception:
            pass

        from android.graphics.drawable import GradientDrawable as _GD

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

    # attach NoInternetBanner to content_view
    try:
        banner = getattr(self, '_no_internet_banner', None)
        if banner:
            banner.content_view = self.content_view
            if not self.show_loading_initial:
                banner.on_config_loaded()
    except Exception as e:
        logx(f"listView: NoInternetBanner attach error: {e}", False)

    return self.content_view

import os
from android.view import View, Gravity, MotionEvent
from android.widget import LinearLayout, TextView, FrameLayout, HorizontalScrollView, ImageView, ScrollView
from android.util import TypedValue
from android.text import TextUtils
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy
from android_utils import log, OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class

try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"openFileFragment: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"openFileFragment: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"openFileFragment: import AndroidUtilities failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"openFileFragment: import UniversalFragment failed: {e}")
try:
    from org.telegram.ui.ActionBar import BottomSheet
except Exception as e:
    import android_utils as _au; _au.log(f"openFileFragment: import BottomSheet failed: {e}")

_BINARY_SAMPLE_SIZE = 8192


def _is_binary(path):
    try:
        with open(path, "rb") as f:
            chunk = f.read(_BINARY_SAMPLE_SIZE)
        return b"\x00" in chunk
    except Exception as e:
        log(f"openFileFragment: _is_binary error: {e}")
        return False


def _resolve_icon(name):
    try:
        R = find_class("org.telegram.messenger.R")
        return getattr(R.drawable, name)
    except Exception:
        return 0


def _make_toolbar_btn(act, icon_name, on_click):
    dp = AndroidUtilities.dp
    btn = ImageView(act)
    icon_id = _resolve_icon(icon_name)
    if icon_id:
        btn.setImageResource(icon_id)
    btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    btn.setClickable(True)
    btn.setFocusable(True)
    btn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
    btn.setPadding(dp(8), dp(8), dp(8), dp(8))
    btn.setOnClickListener(OnClickListener(on_click))
    return btn


def _show_binary_sheet(activity):
    try:
        from elyx import strings
        sheet = BottomSheet(activity, False, get_last_fragment().getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)

        container = LinearLayout(activity)
        container.setOrientation(LinearLayout.VERTICAL)
        container.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            from ui.settings import Header
            container.setBackground(Header._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                container.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass

        title = TextView(activity)
        title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title.setTypeface(AndroidUtilities.bold())
        title.setText(strings["binary_file_title"])
        title.setGravity(Gravity.CENTER)
        container.addView(title, LayoutHelper.createLinear(-1, -2, Gravity.TOP, 0, 16, 0, 16))

        msg_container = FrameLayout(activity)
        msg_container.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(12), AndroidUtilities.dp(12), AndroidUtilities.dp(12))
        border_bg = GradientDrawable()
        border_bg.setShape(GradientDrawable.RECTANGLE)
        border_bg.setCornerRadius(AndroidUtilities.dp(12))
        border_bg.setStroke(AndroidUtilities.dp(2), Theme.getColor(Theme.key_featuredStickers_addButton))
        border_bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        msg_container.setBackground(border_bg)
        
        msg = TextView(activity)
        msg.setText(strings["binary_file_message"])
        msg.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        msg.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        msg.setLineSpacing(AndroidUtilities.dp(2), 1.0)
        msg_container.addView(msg, FrameLayout.LayoutParams(-1, -2))
        container.addView(msg_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 20))

        close_btn = FrameLayout(activity)
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
        close_text = TextView(activity)
        close_text.setText(strings["close_button"])
        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_text.setTypeface(AndroidUtilities.bold())
        close_text.setGravity(Gravity.CENTER)
        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))

        def on_close(v):
            try:
                sheet.dismiss()
            except Exception:
                pass

        def _apply_press_scale(view):
            try:
                class _TouchListener(dynamic_proxy(View.OnTouchListener)):
                    def __init__(self):
                        super().__init__()
                    def onTouch(self, v, event):
                        try:
                            action = event.getActionMasked()
                            if action == MotionEvent.ACTION_DOWN:
                                v.animate().scaleX(0.93).scaleY(0.93).setDuration(100).start()
                            elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                                v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                        except Exception:
                            pass
                        return False
                view.setOnTouchListener(_TouchListener())
            except Exception:
                pass

        close_btn.setOnClickListener(OnClickListener(on_close))
        _apply_press_scale(close_btn)
        container.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        sheet.setCustomView(container)
        try:
            from ..viewUtils import applyFontToTree
            applyFontToTree(container)
        except Exception:
            pass
        sheet.show()
    except Exception as e:
        log(f"openFileFragment: _show_binary_sheet error: {e}")


_FIRST_CHUNK_SIZE = 16 * 1024   # 16 KB — shown immediately
_CHUNK_SIZE = 64 * 1024         # 64 KB per subsequent update
_CHUNK_INTERVAL_S = 0.1         # 100 ms pause between subsequent chunks


class OpenFileFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self._filename = os.path.basename(path)
        self._edit_mode = False
        self._content_view = None
        self._content_tv = None
        self._edit_tv = None
        self._frag_ref = [None]
        self._text = ""
        self._original_text = ""
        self._edit_btn = None
        self._save_btn = None
        self._reset_btn = None
        self._h_scroll = None
        self._v_scroll = None
        self._loading = False
        self._load_cancelled = False
        self._highlight_cancelled = False
        self._spannable = None
        self._highlighted = None

    def onFragmentCreate(self, *_):
        log(f"openFileFragment: onFragmentCreate path={self._path}")

    def onFragmentDestroy(self, *_):
        log("openFileFragment: onFragmentDestroy")
        self._load_cancelled = True
        self._highlight_cancelled = True
        try:
            if self._content_view is not None:
                parent = self._content_view.getParent()
                if parent is not None:
                    parent.removeView(self._content_view)
                self._content_view = None
                self._content_tv = None
                self._edit_tv = None
        except Exception as e:
            log(f"openFileFragment: onFragmentDestroy error: {e}")

    def getTitle(self):
        return self._filename

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
                log(f"openFileFragment: failed to finish fragment: {e}")
            return True
        return False

    def beforeCreateView(self):
        log(f"openFileFragment: beforeCreateView path={self._path}")

        frag = get_last_fragment()
        if not frag:
            return None
        act = frag.getParentActivity()
        if not act:
            return None
        self._frag_ref[0] = frag

        dp = AndroidUtilities.dp
        bg = Theme.getColor(Theme.key_windowBackgroundWhite)
        bg_gray = Theme.getColor(Theme.key_windowBackgroundGray)
        text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        text_gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        divider_color = Theme.getColor(Theme.key_divider)

        self._act = act
        self._theme = {
            "bg": bg, "bg_gray": bg_gray, "text_primary": text_primary,
            "text_gray": text_gray, "accent": accent, "divider": divider_color
        }

        self._content_view = FrameLayout(act)
        self._content_view.setBackgroundColor(bg)

        outer = LinearLayout(act)
        outer.setOrientation(LinearLayout.VERTICAL)
        self._content_view.addView(outer, FrameLayout.LayoutParams(-1, -1))

        # toolbar: file icon + name left, save/reset/edit right
        toolbar = FrameLayout(act)
        toolbar.setBackgroundColor(bg)

        toolbar_inner = LinearLayout(act)
        toolbar_inner.setOrientation(LinearLayout.HORIZONTAL)
        toolbar_inner.setGravity(Gravity.CENTER_VERTICAL)
        toolbar_inner.setPadding(dp(12), dp(8), dp(8), dp(8))

        file_icon = ImageView(act)
        file_icon_id = _resolve_icon("msg_filehq")
        if file_icon_id:
            file_icon.setImageResource(file_icon_id)
            file_icon.setColorFilter(accent)
        file_icon.setPadding(dp(4), dp(4), dp(4), dp(4))
        toolbar_inner.addView(file_icon, LayoutHelper.createLinear(32, 32, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

        name_tv = TextView(act)
        name_tv.setText(self._filename)
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        name_tv.setTextColor(text_primary)
        name_tv.setSingleLine(True)
        name_tv.setEllipsize(TextUtils.TruncateAt.END)
        toolbar_inner.addView(name_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        save_btn = _make_toolbar_btn(act, "msg_saved", lambda v: self._do_save())
        self._save_btn = save_btn
        save_btn.setVisibility(View.GONE)
        toolbar_inner.addView(save_btn, LayoutHelper.createLinear(40, 40, Gravity.CENTER_VERTICAL))

        reset_btn = _make_toolbar_btn(act, "msg_reset", lambda v: self._do_reset())
        self._reset_btn = reset_btn
        reset_btn.setVisibility(View.GONE)
        toolbar_inner.addView(reset_btn, LayoutHelper.createLinear(40, 40, Gravity.CENTER_VERTICAL))

        edit_btn = _make_toolbar_btn(act, "menu_topic_add_30", lambda v: self._toggle_edit())
        self._edit_btn = edit_btn
        toolbar_inner.addView(edit_btn, LayoutHelper.createLinear(40, 40, Gravity.CENTER_VERTICAL))

        toolbar.addView(toolbar_inner, FrameLayout.LayoutParams(-1, -2))

        div = View(act)
        div.setBackgroundColor(divider_color)
        toolbar.addView(div, LayoutHelper.createFrame(-1, 1, 0x50))

        outer.addView(toolbar, LayoutHelper.createLinear(-1, -2))

        # content scroll: h_scroll wraps v_scroll wraps content
        self._h_scroll = HorizontalScrollView(act)
        self._h_scroll.setHorizontalScrollBarEnabled(True)
        self._h_scroll.setFillViewport(True)
        self._h_scroll.setBackgroundColor(bg)

        self._v_scroll = ScrollView(act)
        self._v_scroll.setVerticalScrollBarEnabled(True)
        self._v_scroll.setFillViewport(False)

        self._content_tv = TextView(act)
        self._content_tv.setText("")
        self._content_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        self._content_tv.setTextColor(text_primary)
        self._content_tv.setSingleLine(False)
        self._content_tv.setMaxLines(999999)
        self._content_tv.setHorizontallyScrolling(True)
        self._content_tv.setPadding(dp(16), dp(12), dp(16), dp(32))
        try:
            from android.graphics import Typeface
            self._content_tv.setTypeface(Typeface.MONOSPACE)
        except Exception:
            pass

        self._v_scroll.addView(self._content_tv, LayoutHelper.createScroll(-2, -2, 0))
        self._h_scroll.addView(self._v_scroll, LayoutHelper.createScroll(-1, -1, 0))
        outer.addView(self._h_scroll, LayoutHelper.createLinear(-1, 0, 1.0))

        self._start_loading()
        return self._content_view

    def _start_loading(self):
        from client_utils import run_on_queue
        self._loading = True
        self._load_cancelled = False
        self._highlight_cancelled = False
        run_on_queue(self._load_chunked)

    def _load_chunked(self):
        # runs on background thread, appends chunks to TextView via UI thread
        import time
        try:
            from android_utils import run_on_ui_thread
            first = True

            with open(self._path, "r", encoding="utf-8", errors="replace") as f:
                while True:
                    if self._load_cancelled:
                        log("openFileFragment: load cancelled")
                        return

                    size = _FIRST_CHUNK_SIZE if first else _CHUNK_SIZE
                    chunk = f.read(size)
                    if not chunk:
                        break

                    if not self._load_cancelled:
                        run_on_ui_thread(lambda p=chunk: self._append_chunk(p))

                    if first:
                        first = False
                    else:
                        # throttle subsequent chunks so UI thread stays free
                        time.sleep(_CHUNK_INTERVAL_S)

            if not self._load_cancelled:
                run_on_ui_thread(self._on_load_done)
        except Exception as e:
            log(f"openFileFragment: _load_chunked error: {e}")
            if not self._load_cancelled:
                from android_utils import run_on_ui_thread
                run_on_ui_thread(self._on_load_done)

    def _append_chunk(self, chunk: str):
        # runs on UI thread
        if self._load_cancelled or self._content_tv is None:
            return
        try:
            self._text += chunk
            self._content_tv.append(chunk)
        except Exception as e:
            log(f"openFileFragment: _append_chunk error: {e}")

    def _on_load_done(self):
        # runs on UI thread
        self._loading = False
        self._original_text = self._text
        log(f"openFileFragment: load done, total={len(self._text)} chars")
        self._startHighlight()

    def _startHighlight(self):
        try:
            from elyx import settings
            if not settings.get("highlight_syntax", True):
                return
        except Exception:
            pass
        ext = os.path.splitext(self._path)[1].lower()
        if ext not in (".json", ".py", ".plugin", ".java", ".kt"):
            return
        self._highlight_cancelled = False
        from client_utils import run_on_queue
        run_on_queue(lambda: self._highlightBg(ext))

    def _highlightBg(self, ext: str):
        # runs on background thread — tokenize + char mapping in C, no Python UTF-8 walk
        try:
            from .packlight import tokenizeJson, tokenizePython, tokenizeJava, tokenizeKotlin, _resolveColors, _applySpans
            if self._highlight_cancelled:
                return
            text = self._text
            if ext == ".json":
                result = tokenizeJson(text)
            elif ext == ".java":
                result = tokenizeJava(text)
            elif ext == ".kt":
                result = tokenizeKotlin(text)
            else:
                result = tokenizePython(text)
            if result is None or self._highlight_cancelled:
                from android_utils import run_on_ui_thread
                return
            tokBuf, ranges, cnt = result
            colors = _resolveColors()
            if not colors or self._highlight_cancelled:
                return
            log(f"openFileFragment: highlight done, tokens={cnt}, applying chunked")
            from android_utils import run_on_ui_thread
            run_on_ui_thread(lambda: self._applyHighlightChunked(text, tokBuf, ranges, cnt, colors, 0))
        except Exception as e:
            log(f"openFileFragment: _highlightBg error: {e}")
            from android_utils import run_on_ui_thread

    # how many setSpan() calls per UI frame
    _SPAN_CHUNK = 1000

    def _applyHighlightChunked(self, text: str, tokBuf, ranges, cnt: int, colors: dict, offset: int):
        # runs on UI thread — no sleep, no blocking
        if self._highlight_cancelled or self._content_tv is None:
            tokBuf = None
            ranges = None
            return
        try:
            from android.text import SpannableString
            from .packlight import _applySpans

            if offset == 0:
                self._spannable = SpannableString(text)

            end = min(offset + self._SPAN_CHUNK, cnt)
            _applySpans(self._spannable, tokBuf, ranges, end - offset, colors, offset)

            if end < cnt and not self._highlight_cancelled:
                from android_utils import run_on_ui_thread
                run_on_ui_thread(
                    lambda: self._applyHighlightChunked(text, tokBuf, ranges, cnt, colors, end),
                    16
                )
            else:
                if not self._highlight_cancelled and self._content_tv is not None:
                    self._highlighted = self._spannable
                    self._content_tv.setText(self._spannable)
                    log("openFileFragment: highlight applied")
                self._spannable = None
                tokBuf = None
                ranges = None
        except Exception as e:
            log(f"openFileFragment: _applyHighlightChunked error: {e}")
            self._spannable = None
            tokBuf = None
            ranges = None

    def _toggle_edit(self):
        if self._loading:
            log("openFileFragment: _toggle_edit blocked: still loading")
            return
        self._edit_mode = not self._edit_mode
        log(f"openFileFragment: toggle edit mode={self._edit_mode}")
        try:
            t = self._theme

            if self._edit_mode:
                self._edit_btn.setColorFilter(t["accent"])
                self._save_btn.setVisibility(View.VISIBLE)
                self._reset_btn.setVisibility(View.VISIBLE)
                self._content_tv.setVisibility(View.GONE)
                self._h_scroll.setBackgroundColor(t["bg_gray"])
                self._ensure_edit_tv()
                self._edit_tv.setVisibility(View.VISIBLE)
                self._edit_tv.requestFocus()
                AndroidUtilities.showKeyboard(self._edit_tv)
            else:
                self._edit_btn.setColorFilter(t["text_gray"])
                self._save_btn.setVisibility(View.GONE)
                self._reset_btn.setVisibility(View.GONE)
                if self._edit_tv:
                    AndroidUtilities.hideKeyboard(self._edit_tv)
                    self._edit_tv.setVisibility(View.GONE)
                self._h_scroll.setBackgroundColor(t["bg"])
                self._content_tv.setText(self._highlighted if self._highlighted is not None else self._text)
                self._content_tv.setVisibility(View.VISIBLE)
        except Exception as e:
            log(f"openFileFragment: _toggle_edit error: {e}")

    def _ensure_edit_tv(self):
        if self._edit_tv is not None:
            self._edit_tv.setText(self._text)
            self._edit_tv.setSelection(0)
            return
        try:
            from org.telegram.ui.Components import EditTextBoldCursor
            from org.telegram.ui.ActionBar import Theme as TgTheme
            act = self._act
            dp = AndroidUtilities.dp

            edit = EditTextBoldCursor(act)
            edit.lineYFix = True
            edit.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            edit.setTextColor(TgTheme.getColor(TgTheme.key_windowBackgroundWhiteBlackText))
            edit.setHintColor(TgTheme.getColor(TgTheme.key_groupcreate_hintText))
            edit.setCursorColor(TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated))
            edit.setBackground(None)
            edit.setGravity(Gravity.TOP)
            edit.setSingleLine(False)
            edit.setMaxLines(999999)
            edit.setHorizontallyScrolling(False)
            edit.setPadding(dp(16), dp(12), dp(16), dp(32))
            try:
                from android.graphics import Typeface
                edit.setTypeface(Typeface.MONOSPACE)
            except Exception:
                pass
            edit.setText(self._text)
            edit.setSelection(0)

            self._edit_tv = edit
            self._v_scroll.removeAllViews()
            wrapper = LinearLayout(act)
            wrapper.setOrientation(LinearLayout.VERTICAL)
            wrapper.addView(self._content_tv, LayoutHelper.createLinear(-2, -2))
            wrapper.addView(self._edit_tv, LayoutHelper.createLinear(-1, -2))
            self._v_scroll.addView(wrapper, LayoutHelper.createScroll(-1, -2, 0))
        except Exception as e:
            log(f"openFileFragment: _ensure_edit_tv error: {e}")

    def _do_save(self):
        if not self._edit_tv:
            return
        try:
            new_text = str(self._edit_tv.getText())
            with open(self._path, "w", encoding="utf-8") as f:
                f.write(new_text)
            self._text = new_text
            self._highlighted = None
            self._startHighlight()
            log(f"openFileFragment: saved {self._path}")
        except Exception as e:
            log(f"openFileFragment: _do_save error: {e}")

    def _do_reset(self):
        if not self._edit_tv:
            return
        try:
            self._edit_tv.setText(self._original_text)
            self._edit_tv.setSelection(0)
            log("openFileFragment: reset to original")
        except Exception as e:
            log(f"openFileFragment: _do_reset error: {e}")


def open_file(path: str, binary: bool = False):
    # called on UI thread
    log(f"openFileFragment: open_file path={path} binary={binary}")
    try:
        if binary:
            frag = get_last_fragment()
            if frag:
                act = frag.getParentActivity()
                if act:
                    _show_binary_sheet(act)
            return

        frag = get_last_fragment()
        if not frag:
            log("openFileFragment: open_file no fragment")
            return
        delegate = OpenFileFragment(path)
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        try:
            new_frag.setTitle(os.path.basename(path), False, 0)
            try:
                action_bar = new_frag.getActionBar()
                if action_bar:
                    action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                    from org.telegram.messenger import R as R_tg
                    back_icon = getattr(R_tg.drawable, 'ic_ab_back', 0)
                    if back_icon:
                        action_bar.setBackButtonImage(back_icon)
                        action_bar.setBackButtonContentDescription("Back")
                        try:
                            back_button = action_bar.getBackButton()
                            if back_button:
                                def _on_back_click(v):
                                    f = get_last_fragment()
                                    if f: f.finishFragment()
                                back_button.setOnClickListener(OnClickListener(_on_back_click))
                        except Exception:
                            pass
            except Exception as e:
                log(f"openFileFragment: Failed to add back button: {e}")
            delegate._frag_ref[0] = new_frag
        except Exception as e:
            log(f"openFileFragment: open_file setup error: {e}")
    except Exception as e:
        log(f"openFileFragment: open_file error: {e}")

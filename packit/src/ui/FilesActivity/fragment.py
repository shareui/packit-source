import os
from android.view import View, Gravity, MotionEvent
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView
from android.util import TypedValue
from java import dynamic_proxy
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class

try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import AndroidUtilities failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import UniversalFragment failed: {e}")


def _resolve_icon(name):
    try:
        R = find_class("org.telegram.messenger.R")
        return getattr(R.drawable, name)
    except Exception:
        return 0


def _format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size // 1024} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def _get_cache_root():
    try:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        return f"/data/data/{pkg}/files/packitCache"
    except Exception as e:
        log(f"filesActivity: _get_cache_root error: {e}")
        return ""


def _list_dir(path):
    # returns (dirs, files) sorted by name
    try:
        entries = os.listdir(path)
        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(path, e))])
        return dirs, files
    except Exception as e:
        log(f"filesActivity: _list_dir error: {e}")
        return [], []


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self):
                super().__init__()
            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.97).scaleY(0.97).setDuration(80).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(150).start()
                except Exception:
                    pass
                return False
        view.setOnTouchListener(_TouchListener())
    except Exception:
        pass


class FilesFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):

    def __init__(self, root: str):
        super().__init__()
        self._root = root
        # history stack: root is always first, navigation pushes/pops
        self._stack = [root]
        self._alive = [True]
        self._content_view = None
        self._list_root = None
        self._path_tv = None
        self._frag_ref = [None]

    def onFragmentCreate(self, *_):
        log(f"filesActivity: onFragmentCreate stack={self._stack}")

    def onFragmentDestroy(self, *_):
        log(f"filesActivity: onFragmentDestroy stack={self._stack} alive={self._alive[0]}")
        self._alive[0] = False
        try:
            if self._content_view is not None:
                parent = self._content_view.getParent()
                log(f"filesActivity: onFragmentDestroy parent={parent}")
                if parent is not None:
                    parent.removeView(self._content_view)
                self._content_view = None
                self._list_root = None
                self._path_tv = None
                log("filesActivity: onFragmentDestroy views cleared")
        except Exception as e:
            log(f"filesActivity: onFragmentDestroy error: {e}")

    def getTitle(self):
        return self._rel_path(self._stack[-1])

    def onBackPressed(self):
        log(f"filesActivity: onBackPressed stack_len={len(self._stack)} stack={self._stack}")
        if len(self._stack) > 1:
            popped = self._stack.pop()
            log(f"filesActivity: onBackPressed popped={popped} remaining={self._stack}")
            run_on_ui_thread(lambda: self._render())
            return True
        log("filesActivity: onBackPressed at root, returning None (close)")
        return None

    def afterCreateView(self, v):
        return None

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def beforeCreateView(self):
        log(f"filesActivity: beforeCreateView stack={self._stack}")
        if self._content_view is not None:
            try:
                parent = self._content_view.getParent()
                if parent is not None:
                    parent.removeView(self._content_view)
            except Exception:
                pass
            self._content_view = None

        frag = get_last_fragment()
        if not frag:
            return None
        act = frag.getParentActivity()
        if not act:
            return None
        self._frag_ref[0] = frag

        dp = AndroidUtilities.dp
        bg = Theme.getColor(Theme.key_windowBackgroundGray)
        bg_white = Theme.getColor(Theme.key_windowBackgroundWhite)
        text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        text_gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        divider_color = Theme.getColor(Theme.key_divider)

        self._theme = {
            "bg": bg, "bg_white": bg_white, "text_primary": text_primary,
            "text_gray": text_gray, "accent": accent, "divider": divider_color
        }
        self._act = act

        self._content_view = FrameLayout(act)
        self._content_view.setBackgroundColor(bg)

        outer = LinearLayout(act)
        outer.setOrientation(LinearLayout.VERTICAL)
        self._content_view.addView(outer, FrameLayout.LayoutParams(-1, -1))

        # path bar
        path_bar = FrameLayout(act)
        path_bar.setBackgroundColor(bg_white)

        self._path_tv = TextView(act)
        self._path_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        self._path_tv.setTextColor(text_gray)
        self._path_tv.setSingleLine(True)
        self._path_tv.setPadding(dp(16), dp(10), dp(16), dp(10))
        path_bar.addView(self._path_tv, FrameLayout.LayoutParams(-1, -2))

        div_bar = View(act)
        div_bar.setBackgroundColor(divider_color)
        path_bar.addView(div_bar, LayoutHelper.createFrame(-1, 1, 0x50))

        outer.addView(path_bar, LayoutHelper.createLinear(-1, -2))

        scroll = ScrollView(act)
        scroll.setFillViewport(True)
        scroll.setVerticalScrollBarEnabled(False)

        self._list_root = LinearLayout(act)
        self._list_root.setOrientation(LinearLayout.VERTICAL)
        scroll.addView(self._list_root, LayoutHelper.createScroll(-1, -2, 0))

        outer.addView(scroll, LayoutHelper.createLinear(-1, 0, 1.0))

        self._render()
        return self._content_view

    def _rel_path(self, path):
        if path == self._root:
            return "../packitCache"
        rel = os.path.relpath(path, self._root)
        return f"../packitCache/{rel}"

    def _push(self, path):
        log(f"filesActivity: _push path={path} alive={self._alive[0]} stack_before={self._stack}")
        if not self._alive[0]:
            return
        self._stack.append(path)
        log(f"filesActivity: _push stack_after={self._stack}")
        self._render()

    def _render(self):
        if not self._alive[0]:
            log("filesActivity: _render skipped, not alive")
            return
        try:
            path = self._stack[-1]
            log(f"filesActivity: _render path={path} stack={self._stack} list_root={self._list_root is not None}")

            if self._path_tv:
                self._path_tv.setText(self._rel_path(path))

            # update actionbar title
            try:
                frag = self._frag_ref[0]
                if frag:
                    frag.setTitle(self._rel_path(path), False, 0)
            except Exception:
                pass

            list_root = self._list_root
            list_root.removeAllViews()

            act = self._act
            dp = AndroidUtilities.dp
            t = self._theme

            dirs, files = _list_dir(path)

            if not dirs and not files:
                empty_tv = TextView(act)
                empty_tv.setText("Empty folder")
                empty_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                empty_tv.setTextColor(t["text_gray"])
                empty_tv.setGravity(Gravity.CENTER)
                empty_tv.setPadding(dp(16), dp(32), dp(16), dp(32))
                list_root.addView(empty_tv, LayoutHelper.createLinear(-1, -2))
                return

            folder_icon_id = _resolve_icon("files_folder")
            file_icon_id = _resolve_icon("msg_sendfile")

            for i, name in enumerate(dirs):
                full = os.path.join(path, name)
                row = _make_row(act, name, None, folder_icon_id, t, is_dir=True)
                row.setOnClickListener(OnClickListener(lambda v, p=full: self._push(p)))
                _apply_press_scale(row)
                list_root.addView(row, LayoutHelper.createLinear(-1, -2))
                if i < len(dirs) - 1 or files:
                    list_root.addView(_make_divider(act, t["divider"]), LayoutHelper.createLinear(-1, 1, dp(56), 0, 0, 0))

            for i, name in enumerate(files):
                full = os.path.join(path, name)
                try:
                    size = _format_size(os.path.getsize(full))
                except Exception:
                    size = ""
                row = _make_row(act, name, size, file_icon_id, t, is_dir=False)
                _apply_press_scale(row)
                list_root.addView(row, LayoutHelper.createLinear(-1, -2))
                if i < len(files) - 1:
                    list_root.addView(_make_divider(act, t["divider"]), LayoutHelper.createLinear(-1, 1, dp(56), 0, 0, 0))

        except Exception as e:
            log(f"filesActivity: _render error: {e}")


def _make_row(act, name, subtitle, icon_id, t, is_dir):
    dp = AndroidUtilities.dp

    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setMinimumHeight(dp(56))
    row.setClickable(True)
    row.setFocusable(True)
    row.setBackground(Theme.createSelectorDrawable(
        Theme.getColor(Theme.key_listSelector), 2
    ))
    row.setPadding(dp(16), dp(8), dp(16), dp(8))

    icon_view = ImageView(act)
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_color = t["accent"] if is_dir else t["text_gray"]
        icon_view.setColorFilter(icon_color)
    row.addView(icon_view, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 0, 0, 16, 0))

    text_col = LinearLayout(act)
    text_col.setOrientation(LinearLayout.VERTICAL)

    name_tv = TextView(act)
    name_tv.setText(name)
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    name_tv.setTextColor(t["text_primary"])
    name_tv.setSingleLine(True)
    text_col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

    if subtitle:
        sub_tv = TextView(act)
        sub_tv.setText(subtitle)
        sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        sub_tv.setTextColor(t["text_gray"])
        text_col.addView(sub_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

    row.addView(text_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    return row


def _make_divider(act, color):
    div = View(act)
    div.setBackgroundColor(color)
    return div


def show_files_browser():
    try:
        frag = get_last_fragment()
        if not frag:
            log("filesActivity: show_files_browser no fragment")
            return
        root = _get_cache_root()
        if not root:
            log("filesActivity: show_files_browser no root")
            return
        delegate = FilesFragment(root)
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        try:
            new_frag.setTitle("../packitCache", False, 0)
            action_bar = new_frag.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
            delegate._frag_ref[0] = new_frag
        except Exception as e:
            log(f"filesActivity: show_files_browser actionBar error: {e}")
    except Exception as e:
        log(f"filesActivity: show_files_browser error: {e}")

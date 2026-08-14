# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ...utils.Ripple import safe_ripple as _safe_ripple
import os
from android.view import View, Gravity, MotionEvent
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, HorizontalScrollView
from android.util import TypedValue
from java import dynamic_proxy
from android_utils import run_on_ui_thread, OnClickListener
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
try:
    from org.telegram.ui.ActionBar import ActionBarPopupWindow
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import ActionBarPopupWindow failed: {e}")
try:
    from androidx.core.content import ContextCompat
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import ContextCompat failed: {e}")
try:
    from android.graphics.drawable import GradientDrawable, RippleDrawable
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import drawables failed: {e}")
try:
    from android.graphics import Color as AColor, PorterDuff
    from android.content.res import ColorStateList as AColorStateList
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import graphics failed: {e}")
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"filesActivity: import elyx.strings failed: {e}")


def _open_file(path, icon_view=None, delegate=None):
    try:
        from client_utils import run_on_queue

        def _set_spinner():
            try:
                from org.telegram.ui.Components import CircularProgressDrawable
                color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                spinner = CircularProgressDrawable(color)
                try:
                    spinner.size = float(AndroidUtilities.dp(20))
                    spinner.thickness = float(AndroidUtilities.dp(2))
                except Exception:
                    pass
                icon_view.setImageDrawable(spinner)
                icon_view.clearColorFilter()
                icon_view.setEnabled(False)
            except Exception as e:
                logx(f"filesActivity: _set_spinner error: {e}", False)

        def _restore_icon(icon_id):
            try:
                if icon_id:
                    icon_view.setImageResource(icon_id)
                    icon_view.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                icon_view.setEnabled(True)
            except Exception as e:
                logx(f"filesActivity: _restore_icon error: {e}", False)

        icon_id = [0]
        if icon_view is not None:
            try:
                icon_id[0] = _resolve_icon("msg_sendfile")
                run_on_ui_thread(lambda: _set_spinner())
            except Exception as e:
                logx(f"filesActivity: _open_file spinner setup error: {e}", False)

        def _task():
            try:
                from .OpenFileFragment import _is_binary, open_file
                if _is_binary(path):
                    logx("filesActivity: binary file, showing sheet", True)
                    if icon_view is not None:
                        run_on_ui_thread(lambda: _restore_icon(icon_id[0]))
                    frag = get_last_fragment()
                    if frag:
                        act = frag.getParentActivity()
                        if act:
                            run_on_ui_thread(lambda: open_file(path, binary=True))
                    return

                def _present():
                    if icon_view is not None:
                        _restore_icon(icon_id[0])
                    # disable back callback so it doesn't intercept back in OpenFileFragment
                    if delegate is not None:
                        try:
                            cb = delegate._back_callback
                            if cb is not None:
                                cb.setEnabled(False)
                        except Exception:
                            pass
                    open_file(path, on_finish=_on_file_closed if delegate is not None else None)

                def _on_file_closed():
                    # re-enable back callback when returning from OpenFileFragment
                    try:
                        cb = delegate._back_callback
                        if cb is not None:
                            cb.setEnabled(True)
                    except Exception:
                        pass

                run_on_ui_thread(_present)
            except Exception as e:
                logx(f"filesActivity: _open_file task error: {e}", False)
                if icon_view is not None:
                    run_on_ui_thread(lambda: _restore_icon(icon_id[0]))

        run_on_queue(_task)
    except Exception as e:
        logx(f"filesActivity: _open_file error: {e}", False)


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
        from ...utils.Paths import getCacheRoot
        return getCacheRoot()
    except Exception as e:
        logx(f"filesActivity: _get_cache_root error: {e}", False)
        return ""


def _list_dir(path):
    # returns (dirs, files) sorted by name
    try:
        from elyx import settings
        showHidden = settings.get("hidden_files", False)
    except Exception:
        showHidden = False
    try:
        entries = os.listdir(path)
        if not showHidden:
            entries = [e for e in entries if not e.startswith(".")]
        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(path, e))])
        return dirs, files
    except Exception as e:
        logx(f"filesActivity: _list_dir error: {e}", False)
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
        self._breadcrumb_bar = None
        self._frag_ref = [None]
        self._clipboard = None  # ("copy", path)
        self._back_callback = None

    def onFragmentCreate(self, *_):
        logx(f"filesActivity: onFragmentCreate stack={self._stack}", True)

    def onFragmentDestroy(self, *_):
        logx(f"filesActivity: onFragmentDestroy stack={self._stack} alive={self._alive[0]}", True)
        self._alive[0] = False
        self._unregister_back_callback()
        try:
            if self._content_view is not None:
                parent = self._content_view.getParent()
                logx(f"filesActivity: onFragmentDestroy parent={parent}", True)
                if parent is not None:
                    parent.removeView(self._content_view)
                self._content_view = None
                self._list_root = None
                self._breadcrumb_bar = None
                logx("filesActivity: onFragmentDestroy views cleared", True)
        except Exception as e:
            logx(f"filesActivity: onFragmentDestroy error: {e}", False)

    def _register_back_callback(self):
        if self._back_callback is not None:
            return
        try:
            act = getattr(self, '_act', None)
            if act is None:
                return
            from androidx.activity import OnBackPressedCallback
            from extera_utils.classes import Base, java_subclass, joverride
            delegate_ref = self

            @java_subclass(OnBackPressedCallback)
            class _BackCallback(Base):
                @joverride()
                def handleOnBackPressed(self):
                    if len(delegate_ref._stack) > 1:
                        delegate_ref._stack.pop()
                        run_on_ui_thread(lambda: delegate_ref._render())
                    if len(delegate_ref._stack) <= 1:
                        delegate_ref._unregister_back_callback()

            cb = _BackCallback.new_instance(True)
            self._back_callback = cb
            act.getOnBackPressedDispatcher().addCallback(act, cb.java)
            logx("filesActivity: back callback registered", True)
        except Exception as e:
            logx(f"filesActivity: _register_back_callback error: {e}", False)
            self._back_callback = None

    def _unregister_back_callback(self):
        try:
            cb = self._back_callback
            if cb is not None:
                cb.remove()
                self._back_callback = None
                logx("filesActivity: back callback unregistered", True)
        except Exception as e:
            logx(f"filesActivity: _unregister_back_callback error: {e}", False)

    def getTitle(self):
        current_path = self._stack[-1]
        if current_path == self._root:
            name = os.path.basename(self._root)
            if name == "packit":
                return "../packit"
            return f"../packit/{name}" if name else "../packit"
        return os.path.basename(current_path)

    def onBackPressed(self):
        logx(f"filesActivity: onBackPressed stack_len={len(self._stack)} stack={self._stack}", True)
        if len(self._stack) > 1:
            popped = self._stack.pop()
            logx(f"filesActivity: onBackPressed popped={popped} remaining={self._stack}", True)
            if len(self._stack) <= 1:
                self._unregister_back_callback()
            run_on_ui_thread(lambda: self._render())
            # delegate True -> java !True = False -> finishFragment not called = stay open
            return True
        logx("filesActivity: onBackPressed at root, closing fragment", True)
        # delegate False -> java !False = True -> finishFragment called = close
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
            if len(self._stack) > 1:
                self._stack.pop()
                run_on_ui_thread(lambda: self._render())
            else:
                try:
                    frag = get_last_fragment()
                    if frag:
                        frag.finishFragment()
                except Exception as e:
                    logx(f"filesActivity: failed to finish fragment: {e}", False)
            return True
        return False

    def beforeCreateView(self):
        logx(f"filesActivity: beforeCreateView stack={self._stack}", True)
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

        if len(self._stack) > 1:
            self._register_back_callback()

        self._content_view = FrameLayout(act)
        self._content_view.setBackgroundColor(bg)

        outer = LinearLayout(act)
        outer.setOrientation(LinearLayout.VERTICAL)
        self._content_view.addView(outer, FrameLayout.LayoutParams(-1, -1))

        # breadcrumb bar
        path_bar = FrameLayout(act)
        path_bar.setBackgroundColor(bg_white)

        breadcrumb_scroll = HorizontalScrollView(act)
        breadcrumb_scroll.setHorizontalScrollBarEnabled(False)
        breadcrumb_scroll.setFillViewport(False)

        self._breadcrumb_bar = LinearLayout(act)
        self._breadcrumb_bar.setOrientation(LinearLayout.HORIZONTAL)
        self._breadcrumb_bar.setGravity(Gravity.CENTER_VERTICAL)
        self._breadcrumb_bar.setPadding(dp(12), dp(8), dp(12), dp(8))
        breadcrumb_scroll.addView(self._breadcrumb_bar, LayoutHelper.createScroll(-2, -2, 0))

        path_bar.addView(breadcrumb_scroll, FrameLayout.LayoutParams(-1, -2))

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
        self._inject_fab()
        return self._content_view

    def _rel_path(self, path):
        root_name = os.path.basename(self._root)
        if root_name == "packit":
            prefix = "../packit"
        else:
            prefix = f"../packit/{root_name}" if root_name else "../packit"
        if path == self._root:
            return prefix
        rel = os.path.relpath(path, self._root)
        return f"{prefix}/{rel}"

    def _push(self, path):
        logx(f"filesActivity: _push path={path} alive={self._alive[0]} stack_before={self._stack}", True)
        if not self._alive[0]:
            return
        self._stack.append(path)
        logx(f"filesActivity: _push stack_after={self._stack}", True)
        self._register_back_callback()
        self._render()

    def _render_breadcrumbs(self):
        bar = self._breadcrumb_bar
        if not bar:
            return
        bar.removeAllViews()
        act = self._act
        dp = AndroidUtilities.dp
        t = self._theme

        root_name = os.path.basename(self._root)
        if root_name == "packit":
            prefix = "../packit"
        else:
            prefix = f"../packit/{root_name}" if root_name else "../packit"
        segments = [(prefix, self._root)]
        if len(self._stack) > 1:
            rel_parts = os.path.relpath(self._stack[-1], self._root).split(os.sep)
            for i, part in enumerate(rel_parts):
                target = os.path.join(self._root, *rel_parts[:i + 1])
                segments.append((part, target))

        for i, (label, target_path) in enumerate(segments):
            is_last = (i == len(segments) - 1)
            is_clickable = (target_path is not None) and not is_last

            seg_tv = TextView(act)
            seg_tv.setText(label)
            seg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            seg_tv.setTextColor(t["accent"] if is_clickable else t["text_gray"])
            seg_tv.setSingleLine(True)
            if is_clickable:
                # pop stack back to target_path
                seg_tv.setClickable(True)
                seg_tv.setFocusable(True)
                seg_tv.setBackground(Theme.createSelectorDrawable(
                    Theme.getColor(Theme.key_listSelector), 2
                ))
                seg_tv.setPadding(dp(4), dp(2), dp(4), dp(2))
                seg_tv.setOnClickListener(OnClickListener(
                    lambda v, p=target_path: self._navigate_to(p)
                ))
            else:
                seg_tv.setPadding(dp(4), dp(2), dp(4), dp(2))
            bar.addView(seg_tv)

            if not is_last and target_path is not None:
                sep = TextView(act)
                sep.setText(" / ")
                sep.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                sep.setTextColor(t["text_gray"])
                bar.addView(sep)

        # scroll to end so current folder is visible
        try:
            scroll_view = bar.getParent()
            from java.lang import Runnable as _Runnable
            class _ScrollRunnable(dynamic_proxy(_Runnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    scroll_view.scrollTo(999999, 0)
            scroll_view.post(_ScrollRunnable())
        except Exception:
            pass

    def _navigate_to(self, path):
        # pop stack down to the given path
        while len(self._stack) > 1 and self._stack[-1] != path:
            self._stack.pop()
        if len(self._stack) <= 1:
            self._unregister_back_callback()
        self._render()

    def _open_menu(self, anchor, path):
        act = self._act

        def on_rename():
            self._do_rename(path)

        def on_delete():
            self._do_delete(path)

        def on_copy():
            try:
                from org.telegram.messenger import AndroidUtilities, R as R_tg
                from ui.bulletin import BulletinHelper
                AndroidUtilities.addToClipboard(path)
                BulletinHelper.show_info(str(strings["copied_to_clipboard"]))
            except Exception as e:
                logx(f"filesActivity: on_copy error: {e}", False)

        _show_entry_menu(act, anchor, path, on_rename, on_delete, on_copy)

    def _do_rename(self, path):
        try:
            from org.telegram.ui.ActionBar import AlertDialog as TgAlertDialog, Theme as TgTheme
            from org.telegram.ui.Components import EditTextBoldCursor
            act = self._act
            name = os.path.basename(path)

            layout = LinearLayout(act)
            layout.setOrientation(LinearLayout.VERTICAL)

            edit = EditTextBoldCursor(act)
            edit.lineYFix = True
            edit.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
            edit.setText(name)
            edit.setSelection(len(name))
            edit.setTextColor(TgTheme.getColor(TgTheme.key_dialogTextBlack))
            edit.setHintColor(TgTheme.getColor(TgTheme.key_groupcreate_hintText))
            edit.setHintText(str(strings["fs_enter_name"]))
            edit.setFocusable(True)
            edit.setInputType(0x20001)  # TYPE_CLASS_TEXT | TYPE_TEXT_FLAG_CAP_SENTENCES
            edit.setCursorColor(TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated))
            edit.setLineColors(
                TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputField),
                TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated),
                TgTheme.getColor(TgTheme.key_text_RedRegular)
            )
            edit.setBackground(None)
            edit.setPadding(0, AndroidUtilities.dp(6), 0, AndroidUtilities.dp(6))
            layout.addView(edit, LayoutHelper.createLinear(-1, -2, 24, 0, 24, 10))

            dialog_ref = [None]
            builder = TgAlertDialog.Builder(act)
            builder.setTitle(str(strings["fs_rename"]))
            builder.makeCustomMaxHeight()
            builder.setView(layout)
            builder.setWidth(AndroidUtilities.dp(292))

            def on_ok(dialog, which):
                new_name = str(edit.getText()).strip()
                if not new_name or new_name == name:
                    return
                new_path = os.path.join(os.path.dirname(path), new_name)
                try:
                    os.rename(path, new_path)
                    for j, s in enumerate(self._stack):
                        if s == path or s.startswith(path + os.sep):
                            self._stack[j] = s.replace(path, new_path, 1)
                    run_on_ui_thread(lambda: self._render())
                except Exception as e:
                    logx(f"filesActivity: rename error: {e}", False)
                if dialog_ref[0]:
                    dialog_ref[0].dismiss()

            from java import dynamic_proxy as _dp
            from org.telegram.ui.ActionBar import AlertDialog as _AD
            class _OkListener(_dp(_AD.OnButtonClickListener)):
                def __init__(self): super().__init__()
                def onClick(self, dialog, which): on_ok(dialog, which)

            class _CancelListener(_dp(_AD.OnButtonClickListener)):
                def __init__(self): super().__init__()
                def onClick(self, dialog, which):
                    if dialog_ref[0]:
                        dialog_ref[0].dismiss()

            builder.setNegativeButton(str(strings["cancel_button"]), _CancelListener())

            class _ShowListener(_dp(_AD.OnShowListener)):
                def __init__(self): super().__init__()
                def onShow(self, dialog):
                    edit.requestFocus()
                    edit.setSelection(len(str(edit.getText())))
                    AndroidUtilities.showKeyboard(edit)

            class _DismissListener(_dp(_AD.OnDismissListener)):
                def __init__(self): super().__init__()
                def onDismiss(self, dialog): AndroidUtilities.hideKeyboard(edit)

            builder.setPositiveButton(str(strings["fs_rename"]), _OkListener())
            dialog = builder.create()
            dialog_ref[0] = dialog
            dialog.setDismissDialogByButtons(False)
            dialog.setOnShowListener(_ShowListener())
            dialog.setOnDismissListener(_DismissListener())
            dialog.show()
        except Exception as e:
            logx(f"filesActivity: _do_rename error: {e}", False)

    def _do_create_file(self):
        logx("filesActivity: _do_create_file called", True)
        try:
            logx(f"filesActivity: _do_create_file act={self._act} stack={self._stack}", True)
            from org.telegram.ui.ActionBar import AlertDialog as TgAlertDialog, Theme as TgTheme
            from org.telegram.ui.Components import EditTextBoldCursor
            act = self._act
            current_dir = self._stack[-1]
            logx(f"filesActivity: _do_create_file current_dir={current_dir}", True)

            layout = LinearLayout(act)
            layout.setOrientation(LinearLayout.VERTICAL)

            edit = EditTextBoldCursor(act)
            edit.lineYFix = True
            edit.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
            edit.setTextColor(TgTheme.getColor(TgTheme.key_dialogTextBlack))
            edit.setHintColor(TgTheme.getColor(TgTheme.key_groupcreate_hintText))
            edit.setHintText(str(strings["fs_file_name"]))
            edit.setFocusable(True)
            edit.setInputType(0x20001)  # TYPE_CLASS_TEXT | TYPE_TEXT_FLAG_CAP_SENTENCES
            edit.setCursorColor(TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated))
            edit.setLineColors(
                TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputField),
                TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated),
                TgTheme.getColor(TgTheme.key_text_RedRegular)
            )
            edit.setBackground(None)
            edit.setPadding(0, AndroidUtilities.dp(6), 0, AndroidUtilities.dp(6))
            layout.addView(edit, LayoutHelper.createLinear(-1, -2, 24, 0, 24, 10))

            dialog_ref = [None]
            builder = TgAlertDialog.Builder(act)
            builder.setTitle(str(strings["fs_new_file_title"]))
            builder.makeCustomMaxHeight()
            builder.setView(layout)
            builder.setWidth(AndroidUtilities.dp(292))
            def on_ok(dialog, which):
                name = str(edit.getText()).strip()
                if not name:
                    return
                new_path = os.path.join(current_dir, name)
                try:
                    open(new_path, "a").close()
                    run_on_ui_thread(lambda: self._render())
                except Exception as e:
                    logx(f"filesActivity: create file error: {e}", False)
                if dialog_ref[0]:
                    dialog_ref[0].dismiss()

            from java import dynamic_proxy as _dp
            from org.telegram.ui.ActionBar import AlertDialog as _AD

            class _OkListener(_dp(_AD.OnButtonClickListener)):
                def __init__(self): super().__init__()
                def onClick(self, dialog, which): on_ok(dialog, which)

            class _CancelListener(_dp(_AD.OnButtonClickListener)):
                def __init__(self): super().__init__()
                def onClick(self, dialog, which):
                    if dialog_ref[0]:
                        dialog_ref[0].dismiss()

            builder.setNegativeButton(str(strings["cancel_button"]), _CancelListener())

            class _ShowListener(_dp(_AD.OnShowListener)):
                def __init__(self): super().__init__()
                def onShow(self, dialog):
                    edit.requestFocus()
                    AndroidUtilities.showKeyboard(edit)

            class _DismissListener(_dp(_AD.OnDismissListener)):
                def __init__(self): super().__init__()
                def onDismiss(self, dialog): AndroidUtilities.hideKeyboard(edit)

            builder.setPositiveButton(str(strings["fs_create"]), _OkListener())
            dialog = builder.create()
            dialog_ref[0] = dialog
            dialog.setDismissDialogByButtons(False)
            dialog.setOnShowListener(_ShowListener())
            dialog.setOnDismissListener(_DismissListener())
            dialog.show()
        except Exception as e:
            logx(f"filesActivity: _do_create_file error: {e}", False)

    def _inject_fab(self):
        try:
            import math
            from android.widget import FrameLayout, ImageView
            from android.view import Gravity, MotionEvent, View
            from android.graphics.drawable import GradientDrawable
            from java import dynamic_proxy

            act = self._act
            dp = AndroidUtilities.dp

            squareFab = True
            try:
                ExteraConfig = find_class("com.exteragram.messenger.ExteraConfig")
                squareFab = bool(ExteraConfig.squareFab)
            except Exception:
                pass

            try:
                btn_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                icon_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
            except Exception:
                from android.graphics import Color
                btn_color = Color.parseColor("#2196F3")
                icon_color = 0xFFFFFFFF

            fab_size_dp = 56
            fab_size = dp(fab_size_dp)
            fab_margin = dp(16)

            bg = GradientDrawable()
            if squareFab:
                bg.setShape(GradientDrawable.RECTANGLE)
                corner = dp(float(math.ceil(fab_size_dp * 16.0 / 56.0)))
                bg.setCornerRadius(corner)
            else:
                bg.setShape(GradientDrawable.OVAL)
            bg.setColor(btn_color)

            fab = FrameLayout(act)
            fab.setClickable(True)
            fab.setFocusable(True)
            fab.setBackground(bg)
            try:
                fab.setElevation(dp(4))
            except Exception:
                pass

            fab_icon = ImageView(act)
            fab_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            icon_id = _resolve_icon("msg_addbot")
            if icon_id:
                fab_icon.setImageResource(icon_id)
                fab_icon.setColorFilter(icon_color)
            fab.addView(fab_icon, FrameLayout.LayoutParams(fab_size, fab_size))

            delegate_ref = self

            fab.setOnClickListener(OnClickListener(lambda v: delegate_ref._do_create_file()))

            def _on_touch(v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        fab.animate().scaleX(0.88).scaleY(0.88).alpha(0.72).setDuration(120).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        fab.animate().scaleX(1.0).scaleY(1.0).alpha(1.0).setDuration(220).start()
                except Exception:
                    pass
                return False

            class _TL(dynamic_proxy(View.OnTouchListener)):
                def onTouch(self, v, event):
                    return _on_touch(v, event)

            fab.setOnTouchListener(_TL())

            fab_lp = FrameLayout.LayoutParams(fab_size, fab_size)
            fab_lp.gravity = Gravity.BOTTOM | Gravity.END
            fab_lp.rightMargin = fab_margin
            fab_lp.bottomMargin = fab_margin

            self._content_view.addView(fab, fab_lp)
            fab.bringToFront()
            logx("filesActivity: FAB injected", True)
        except Exception as e:
            logx(f"filesActivity: _inject_fab error: {e}", False)

    def _do_delete(self, path):
        try:
            from ui.alert import AlertDialogBuilder
            act = self._act
            name = os.path.basename(path)
            is_dir = os.path.isdir(path)
            msg = f"Delete {'folder' if is_dir else 'file'} \"{name}\"?"

            builder = AlertDialogBuilder(act)
            builder.set_title(str(strings["fs_delete_title"]))
            builder.set_message(msg)
            builder.set_negative_button(str(strings["cancel_button"]), lambda b, w: b.dismiss())

            def on_yes(b, w):
                try:
                    import shutil
                    if is_dir:
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    # pop stack if deleted dir was in it
                    while len(self._stack) > 1 and (
                        self._stack[-1] == path or self._stack[-1].startswith(path + os.sep)
                    ):
                        self._stack.pop()
                    run_on_ui_thread(lambda: self._render())
                except Exception as e:
                    logx(f"filesActivity: delete error: {e}", False)

            builder.set_positive_button(str(strings["fs_delete_title"]), on_yes)
            try:
                builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
            except Exception as e:
                logx(f"filesActivity: make_button_red error: {e}", False)
            builder.show()
        except Exception as e:
            logx(f"filesActivity: _do_delete error: {e}", False)

    def _render(self):
        if not self._alive[0]:
            logx("filesActivity: _render skipped, not alive", True)
            return
        try:
            path = self._stack[-1]
            logx(f"filesActivity: _render path={path} stack={self._stack} list_root={self._list_root is not None}", True)

            self._render_breadcrumbs()

            list_root = self._list_root
            list_root.removeAllViews()

            act = self._act
            dp = AndroidUtilities.dp
            t = self._theme

            dirs, files = _list_dir(path)

            if not dirs and not files:
                empty_tv = TextView(act)
                empty_tv.setText(str(strings["fs_empty_folder"]))
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
                row, _ = _make_row(act, name, None, folder_icon_id, t, is_dir=True,
                                   on_menu=lambda btn, p=full: self._open_menu(btn, p))
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
                row, iv = _make_row(act, name, size, file_icon_id, t, is_dir=False,
                                    on_menu=lambda btn, p=full: self._open_menu(btn, p))
                row.setOnClickListener(OnClickListener(lambda v, p=full, icon=iv: _open_file(p, icon, delegate=self)))
                _apply_press_scale(row)
                list_root.addView(row, LayoutHelper.createLinear(-1, -2))
                if i < len(files) - 1:
                    list_root.addView(_make_divider(act, t["divider"]), LayoutHelper.createLinear(-1, 1, dp(56), 0, 0, 0))

        except Exception as e:
            logx(f"filesActivity: _render error: {e}", False)


def _make_row(act, name, subtitle, icon_id, t, is_dir, on_menu=None):
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
    row.setPadding(dp(16), dp(8), dp(4), dp(8))

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

    # three-dot menu button
    menu_btn = ImageView(act)
    try:
        R = find_class("org.telegram.messenger.R")
        menu_icon = getattr(R.drawable, "ic_ab_other", 0)
        if not menu_icon:
            menu_icon = getattr(R.drawable, "msg_more", 0)
    except Exception:
        menu_icon = 0
    if menu_icon:
        menu_btn.setImageResource(menu_icon)
        menu_btn.setColorFilter(t["text_gray"])
    menu_btn.setClickable(True)
    menu_btn.setFocusable(True)
    menu_btn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
    menu_btn.setPadding(dp(8), dp(8), dp(8), dp(8))
    if on_menu:
        menu_btn.setOnClickListener(OnClickListener(lambda v, btn=menu_btn: on_menu(btn)))
    row.addView(menu_btn, LayoutHelper.createLinear(40, 40, Gravity.CENTER_VERTICAL, 0, 0, 0, 0))

    return row, icon_view


def _make_divider(act, color):
    div = View(act)
    div.setBackgroundColor(color)
    return div


def _get_file_info(path):
    info = {}
    try:
        stat = os.stat(path)
        info["full_path"] = path
        info["size_bytes"] = stat.st_size
        info["size_human"] = _format_size(stat.st_size)
        import time
        info["modified"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        info["created"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime))
        info["is_dir"] = os.path.isdir(path)
        if info["is_dir"]:
            try:
                entries = os.listdir(path)
                info["children"] = len(entries)
                total = 0
                for e in entries:
                    ep = os.path.join(path, e)
                    if os.path.isfile(ep):
                        total += os.path.getsize(ep)
                info["dir_size_human"] = _format_size(total)
            except Exception:
                pass
        else:
            _, ext = os.path.splitext(path)
            info["extension"] = ext.lower() if ext else "(none)"
    except Exception as e:
        logx(f"filesActivity: _get_file_info error: {e}", False)
    return info


def _show_file_info(act, path):
    try:
        from .InfoDialog import show_info_dialog
        info = _get_file_info(path)
        name = os.path.basename(path)
        show_info_dialog(act, name, info)
    except Exception as e:
        logx(f"filesActivity: _show_file_info error: {e}", False)


def _show_entry_menu(act, anchor_view, path, on_rename, on_delete, on_copy):
    try:
        R = find_class("org.telegram.messenger.R")
        popup_layout = ActionBarPopupWindow.ActionBarPopupWindowLayout(act)
        popup_layout.setBackgroundColor(Theme.getColor(Theme.key_actionBarDefaultSubmenuBackground))
        popup_layout.setFitItems(True)
        popup_window_ref = [None]

        def create_item(icon_name, title, action, is_red=False):
            try:
                icon_res = getattr(R.drawable, icon_name, 0)
            except Exception:
                icon_res = 0

            item = FrameLayout(act)
            item.setMinimumWidth(AndroidUtilities.dp(160))
            item.setClickable(True)
            item.setFocusable(True)
            try:
                bg_color = Theme.getColor(Theme.key_dialogBackgroundGray) & 0x20FFFFFF | 0x10000000
                pressed_color = Theme.getColor(Theme.key_listSelector) & 0x40FFFFFF | 0x30000000
                btn_bg = GradientDrawable()
                btn_bg.setCornerRadius(AndroidUtilities.dp(10))
                btn_bg.setColor(bg_color)
                try:
                    ripple_color = AColorStateList.valueOf(AColor.parseColor("#40000000"))
                    pressed_bg = GradientDrawable()
                    pressed_bg.setCornerRadius(AndroidUtilities.dp(10))
                    pressed_bg.setColor(pressed_color)
                    item.setBackground(_safe_ripple(ripple_color, btn_bg, pressed_bg))
                except Exception:
                    item.setBackground(btn_bg)
            except Exception:
                item.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))

            row = LinearLayout(act)
            row.setOrientation(LinearLayout.HORIZONTAL)
            row.setGravity(Gravity.CENTER_VERTICAL)
            row.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))

            if icon_res:
                icon_view = ImageView(act)
                icon_view.setScaleType(ImageView.ScaleType.CENTER)
                try:
                    d = ContextCompat.getDrawable(act, icon_res)
                    try:
                        color = Theme.getColor(Theme.key_text_RedRegular) if is_red else Theme.getColor(Theme.key_dialogTextGray)
                    except Exception:
                        color = AColor.parseColor("#FF3B30") if is_red else AColor.parseColor("#808080")
                    d.setColorFilter(color, PorterDuff.Mode.SRC_IN)
                    icon_view.setImageDrawable(d)
                except Exception:
                    icon_view.setImageResource(icon_res)
                row.addView(icon_view, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

            tv = TextView(act)
            tv.setText(title)
            tv.setTextSize(14)
            try:
                color = Theme.getColor(Theme.key_text_RedRegular) if is_red else Theme.getColor(Theme.key_actionBarDefaultSubmenuItem)
                tv.setTextColor(color)
            except Exception:
                pass
            row.addView(tv, LayoutHelper.createLinear(-1, -2, 1.0, Gravity.CENTER_VERTICAL))
            item.addView(row)

            def _click(*_):
                try:
                    if popup_window_ref[0]:
                        popup_window_ref[0].dismiss()
                except Exception:
                    pass
                try:
                    action()
                except Exception:
                    pass

            item.setOnClickListener(OnClickListener(_click))
            popup_layout.addView(item, LayoutHelper.createLinear(-1, -2))

        create_item("msg_edit", str(strings["fs_rename"]), on_rename)
        create_item("msg_copy", str(strings["fs_copy_path"]), on_copy)
        create_item("msg_info", str(strings["fs_info"]), lambda: _show_file_info(act, path))
        create_item("msg_delete", str(strings["fs_delete_title"]), on_delete, is_red=True)

        popup_window = ActionBarPopupWindow(popup_layout, -2, -2)
        popup_window_ref[0] = popup_window
        popup_window.setOutsideTouchable(True)
        popup_window.setClippingEnabled(True)
        try:
            popup_window.setAnimationStyle(R.style.PopupContextAnimation)
        except Exception:
            pass
        popup_window.setFocusable(True)
        popup_layout.measure(
            View.MeasureSpec.makeMeasureSpec(AndroidUtilities.dp(1000), View.MeasureSpec.AT_MOST),
            View.MeasureSpec.makeMeasureSpec(AndroidUtilities.dp(1000), View.MeasureSpec.AT_MOST)
        )
        location = [0, 0]
        anchor_view.getLocationInWindow(location)
        popup_x = location[0] + anchor_view.getWidth() - popup_layout.getMeasuredWidth()
        popup_y = location[1] - popup_layout.getMeasuredHeight()
        popup_window.showAtLocation(anchor_view, Gravity.TOP | Gravity.LEFT, popup_x, popup_y)
        popup_window.dimBehind()
    except Exception as e:
        logx(f"filesActivity: _show_entry_menu error: {e}", False)


def _hook_swipe_back(plugin, frag_instance, delegate):
    try:
        from base_plugin import MethodReplacement

        class _CanBeginSlide(MethodReplacement):
            def replace_hooked_method(self, param):
                if param.thisObject is frag_instance:
                    return len(delegate._stack) <= 1
                return True

        method = frag_instance.getClass().getMethod("canBeginSlide")
        method.setAccessible(True)
        ref = plugin.hook_method(method, _CanBeginSlide())
        logx("filesActivity: canBeginSlide hook registered", True)
        return ref
    except Exception as e:
        logx(f"filesActivity: _hook_swipe_back error: {e}", False)
        return None


def show_files_browser(plugin=None):
    try:
        frag = get_last_fragment()
        if not frag:
            logx("filesActivity: show_files_browser no fragment", True)
            return
        root = _get_cache_root()
        if not root:
            logx("filesActivity: show_files_browser no root", True)
            return
        delegate = FilesFragment(root)
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        try:
            root_name = os.path.basename(root)
            if root_name == "packit":
                title = "../packit"
            else:
                title = f"../packit/{root_name}" if root_name else "../packit"
            new_frag.setTitle(title, False, 0)
            action_bar = new_frag.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                try:
                    from org.telegram.messenger import R as R_tg
                    back_icon = getattr(R_tg.drawable, 'ic_ab_back', 0)
                    if back_icon:
                        action_bar.setBackButtonImage(back_icon)
                        action_bar.setBackButtonContentDescription("Back")
                except Exception as e:
                    logx(f"filesActivity: Failed to add back button: {e}", False)
                try:
                    back_button = action_bar.getBackButton()
                    if back_button:
                        def _on_back_click(v):
                            new_frag.finishFragment()
                        back_button.setOnClickListener(OnClickListener(_on_back_click))
                except Exception as e:
                    logx(f"filesActivity: Failed to set back button click listener: {e}", False)

            delegate._frag_ref[0] = new_frag
        except Exception as e:
            logx(f"filesActivity: show_files_browser actionBar error: {e}", False)

        if plugin is not None:
            hook_ref = _hook_swipe_back(plugin, new_frag, delegate)
            if hook_ref is not None:
                orig_destroy = delegate.onFragmentDestroy

                def _on_destroy(*a):
                    try:
                        plugin.unhook_method(hook_ref)
                        logx("filesActivity: canBeginSlide hook removed", True)
                    except Exception as e:
                        logx(f"filesActivity: unhook error: {e}", False)
                    orig_destroy(*a)

                delegate.onFragmentDestroy = _on_destroy
    except Exception as e:
        logx(f"filesActivity: show_files_browser error: {e}", False)
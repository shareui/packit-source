from ui.settings import Header, Switch, Divider, Text, Input, Custom
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log, run_on_ui_thread, OnClickListener
try:
    from org.telegram.messenger import ApplicationLoader, AndroidUtilities, R
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader, AndroidUtilities failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme, BottomSheet
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.widget import LinearLayout, TextView, FrameLayout
from android.view import Gravity
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser as _Browser
except Exception:
    _Browser = None
from android.util import TypedValue
import shutil
import threading
import time
import os
import signal

from typing import List, Any, Callable
from dataclasses import dataclass, field


@dataclass
class ExpandableSwitch:
    key: str
    text: str
    children: List[Any] = field(default_factory=list)
    collapsed: bool = True
    on_switch_click: Callable = field(default=None, compare=False, repr=False)
    link_alias: str = None
    type: str = field(default="expandable_switch", init=False)


def _getCacheInfo(cacheDir):
    # returns (human-readable size string, file count)
    try:
        total = 0
        count = 0
        for dirpath, _, filenames in os.walk(cacheDir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                    count += 1
                except Exception:
                    pass
        if total < 1024:
            size = f"{total} B"
        elif total < 1024 * 1024:
            size = f"{total // 1024} KB"
        else:
            size = f"{total / (1024 * 1024):.1f} MB"
        return size, count
    except Exception:
        return "—", 0


def _getCacheSize(cacheDir):
    return _getCacheInfo(cacheDir)[0]


def _getFreeSpace(path):
    # returns human-readable free space for the given path
    try:
        stat = os.statvfs(path)
        free = stat.f_bavail * stat.f_frsize
        if free < 1024 * 1024:
            return f"{free // 1024} KB"
        elif free < 1024 * 1024 * 1024:
            return f"{free / (1024 * 1024):.1f} MB"
        else:
            return f"{free / (1024 * 1024 * 1024):.1f} GB"
    except Exception:
        return "—"


def _buildTextSubtextCell(context, text, subtext, icon, on_click):
    # native-looking cell: icon on left, title + subtitle stacked, full-row ripple tap
    try:
        from android.widget import ImageView
        from hook_utils import find_class
        dp = AndroidUtilities.dp
        log("other: _buildTextSubtextCell start")

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        row.setMinimumHeight(dp(64))
        row.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))
        row.setOnClickListener(OnClickListener(on_click))
        log("other: _buildTextSubtextCell row created")

        icon_id = 0
        try:
            R = find_class("org.telegram.messenger.R")
            icon_id = int(getattr(R.drawable, icon))
            log(f"other: _buildTextSubtextCell icon_id={icon_id}")
        except Exception as e:
            log(f"other: _buildTextSubtextCell icon resolve error: {e}")

        if icon_id:
            iconView = ImageView(context)
            iconView.setImageResource(icon_id)
            iconView.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
            # left=23 matches native TextCheckCell icon indent
            row.addView(iconView, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 23, 0, 0, 0))
            log("other: _buildTextSubtextCell icon added")

        textBlock = LinearLayout(context)
        textBlock.setOrientation(LinearLayout.VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(text))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        textBlock.addView(titleView, LayoutHelper.createLinear(-2, -2))

        subtitleView = TextView(context)
        subtitleView.setText(str(subtext))
        subtitleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        subtitleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        textBlock.addView(subtitleView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        # 23+24+25=72dp total left offset — matches native cell text start
        row.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL, 25, 10, 17, 10))

        log("other: _buildTextSubtextCell done")
        return row
    except Exception as e:
        log(f"other: _buildTextSubtextCell error: {e}")
        return None


def _buildCacheCard(context, cacheDir, on_clear, title=None):
    # card showing cache size with clear button
    try:
        dp = AndroidUtilities.dp

        card = LinearLayout(context)
        card.setOrientation(LinearLayout.HORIZONTAL)
        card.setGravity(Gravity.CENTER_VERTICAL)
        card.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        card.setPadding(dp(16), dp(14), dp(8), dp(14))

        left = LinearLayout(context)
        left.setOrientation(LinearLayout.VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(title) if title is not None else str(strings.clear_cache))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        left.addView(titleView, LayoutHelper.createLinear(-2, -2))

        sizeView = TextView(context)
        size, fileCount = _getCacheInfo(cacheDir)
        sizeView.setText(f"{size} • {fileCount} files")
        sizeView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        sizeView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        left.addView(sizeView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        card.addView(left, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        from android.widget import Button
        from android.graphics import Color

        clearBtn = Button(context)
        clearBtn.setText(str(strings.clear_cache_button))
        clearBtn.setAllCaps(False)
        clearBtn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        clearBtn.setTextColor(Theme.getColor(Theme.key_avatar_backgroundRed))
        clearBtn.setBackgroundColor(Color.TRANSPARENT)
        clearBtn.setPadding(dp(12), dp(8), dp(12), dp(8))
        clearBtn.setOnClickListener(OnClickListener(on_clear))
        card.addView(clearBtn, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

        return card
    except Exception as e:
        log(f"other: _buildCacheCard error: {e}")
        return None


def _showEditPathDialog(context, pathView, freeView):
    try:
        from android.text import InputType
        from android.content import DialogInterface
        from android.view import View
        from android.widget import ScrollView
        from java import dynamic_proxy
        from org.telegram.ui.ActionBar import AlertDialog
        from org.telegram.ui.Components import EditTextBoldCursor, OutlineTextContainerView, RLottieImageView

        dp = AndroidUtilities.dp

        builder = AlertDialog.Builder(context)

        frameLayout = FrameLayout(context)
        builder.setView(frameLayout)

        scrollView = ScrollView(context)
        scrollView.setFillViewport(True)
        frameLayout.addView(scrollView, LayoutHelper.createFrame(-1, -1))

        linear = LinearLayout(context)
        linear.setOrientation(LinearLayout.VERTICAL)
        linear.setGravity(Gravity.CENTER_HORIZONTAL)
        scrollView.addView(linear, LayoutHelper.createFrame(-1, -2, Gravity.TOP))

        try:
            anim = RLottieImageView(context)
            anim.setAnimation(R.raw.folder_in, 100, 100)
            anim.playAnimation()
            linear.addView(anim, LayoutHelper.createLinear(100, 100, Gravity.CENTER_HORIZONTAL, 0, 16, 0, 0))
        except Exception as e:
            log(f"other: folder_in anim error: {e}")

        title = TextView(context)
        title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        title.setGravity(Gravity.CENTER_HORIZONTAL)
        title.setTypeface(AndroidUtilities.bold())
        title.setText(str(strings.download_path))
        linear.addView(title, LayoutHelper.createFrame(-2, -2, Gravity.CENTER_HORIZONTAL, 24, 8, 24, 0))

        outlineView = OutlineTextContainerView(context)
        outlineView.setText(str(strings.download_path))
        outlineView.animateSelection(1, False)
        linear.addView(outlineView, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_HORIZONTAL, 24, 24, 24, 16))

        input = EditTextBoldCursor(context)
        input.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        input.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        input.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText))
        input.setBackground(None)
        input.setSingleLine(True)
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI)
        input.setCursorColor(Theme.getColor(Theme.key_windowBackgroundWhiteInputFieldActivated))
        input.setCursorWidth(1.5)
        padding = dp(16)
        input.setPadding(padding, padding, padding, padding)
        input.setText(pathView.getText())
        input.setSelection(input.getText().length())
        outlineView.addView(input, LayoutHelper.createFrame(-1, -2))
        outlineView.attachEditText(input)

        class _FocusListener(dynamic_proxy(View.OnFocusChangeListener)):
            def onFocusChange(self, v, hasFocus):
                outlineView.animateSelection(1 if hasFocus else 0)

        input.setOnFocusChangeListener(_FocusListener())

        dialog = builder.create()

        def onOk():
            newPath = str(input.getText()).strip()
            if not newPath:
                return
            try:
                settings.set("download_path", newPath)
            except Exception as e:
                log(f"other: save download_path error: {e}")
            pathView.setText(newPath)
            freeView.setText(f"Free: {_getFreeSpace(newPath)}")
            AndroidUtilities.hideKeyboard(input)
            dialog.dismiss()

        doneBtn = TextView(context)
        doneBtn.setText(str(strings.ok_button) if hasattr(strings, "ok_button") else "OK")
        doneBtn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        doneBtn.setGravity(Gravity.CENTER)
        doneBtn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(6),
            Theme.getColor(Theme.key_featuredStickers_addButton),
            Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        ))
        doneBtn.setClickable(True)
        doneBtn.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        doneBtn.setOnClickListener(OnClickListener(lambda v: onOk()))
        linear.addView(doneBtn, LayoutHelper.createFrame(-1, 44, Gravity.TOP, 30, 0, 30, 16))

        class _DismissListener(dynamic_proxy(DialogInterface.OnDismissListener)):
            def onDismiss(self, d):
                AndroidUtilities.hideKeyboard(input)

        class _ShowListener(dynamic_proxy(DialogInterface.OnShowListener)):
            def onShow(self, d):
                input.requestFocus()
                input.setSelection(input.getText().length())
                AndroidUtilities.showKeyboard(input)

        dialog.setOnDismissListener(_DismissListener())
        dialog.setOnShowListener(_ShowListener())
        dialog.show()
    except Exception as e:
        log(f"other: _showEditPathDialog error: {e}")

def _buildDownloadPathCard(context, currentPath):
    # card: text block on the left, edit icon on the right
    try:
        from android.widget import ImageView
        dp = AndroidUtilities.dp

        card = LinearLayout(context)
        card.setOrientation(LinearLayout.HORIZONTAL)
        card.setGravity(Gravity.CENTER_VERTICAL)
        card.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        card.setPadding(dp(16), dp(14), dp(8), dp(14))

        textBlock = LinearLayout(context)
        textBlock.setOrientation(LinearLayout.VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(strings.download_path))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        textBlock.addView(titleView, LayoutHelper.createLinear(-2, -2))

        pathView = TextView(context)
        pathView.setText(currentPath)
        pathView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        pathView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        try:
            pathView.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        textBlock.addView(pathView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 4))

        freeSpace = _getFreeSpace(currentPath)
        freeView = TextView(context)
        freeView.setText(f"Free: {freeSpace}")
        freeView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        freeView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        textBlock.addView(freeView, LayoutHelper.createLinear(-2, -2))

        card.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        editIcon = ImageView(context)
        editIcon.setImageResource(R.drawable.msg_edit)
        editIcon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        editIcon.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
        editIcon.setPadding(dp(8), dp(8), dp(8), dp(8))
        editIcon.setOnClickListener(OnClickListener(lambda v: _showEditPathDialog(context, pathView, freeView)))
        card.addView(editIcon, LayoutHelper.createLinear(40, 40, Gravity.CENTER_VERTICAL))

        return card
    except Exception as e:
        log(f"other: _buildDownloadPathCard error: {e}")
        return None


class OtherSettings:
    def __init__(self, chat_button=None, plugin=None):
        self.chat_button = chat_button
        self.plugin = plugin

    def _build_dialogs_btn_item(self, ctx):
        try:
            if ctx:
                view = _buildTextSubtextCell(
                    ctx,
                    text=strings.button_in_dialogs_menu,
                    subtext=strings.button_in_dialogs_menu_desc,
                    icon="msg_addbot",
                    on_click=self._open_main_menu_settings
                )
                if view is not None:
                    return Custom(view=view)
            log("other: _build_dialogs_btn_item falling back to Text")
        except Exception as e:
            log(f"other: _build_dialogs_btn_item error: {e}")
        return Text(
            text=strings.button_in_dialogs_menu,
            icon="msg_addbot",
            on_click=self._open_main_menu_settings
        )

    def _open_main_menu_settings(self, view):
        try:
            from hook_utils import find_class
            frag = get_last_fragment()
            if frag:
                MainMenuPreferencesActivity = find_class("com.exteragram.messenger.preferences.appearance.MainMenuPreferencesActivity")
                frag.presentFragment(MainMenuPreferencesActivity())
        except Exception as e:
            log(f"OtherSettings: _open_main_menu_settings error: {e}")

    def _build_pill_stack_item(self, ctx):
        try:
            if ctx:
                view = _buildTextSubtextCell(
                    ctx,
                    text=strings.pill_stack_settings,
                    subtext=strings.pill_stack_settings_desc,
                    icon="msg_view_file",
                    on_click=self._open_pill_stack_settings
                )
                if view is not None:
                    return Custom(view=view)
            log("other: _build_pill_stack_item falling back to Text")
        except Exception as e:
            log(f"other: _build_pill_stack_item error: {e}")
        return Text(
            text=strings.pill_stack_settings,
            icon="msg_view_file",
            on_click=self._open_pill_stack_settings
        )

    def _open_pill_stack_settings(self, view):
        try:
            from hook_utils import find_class
            PillStackPreferencesActivity = find_class("com.exteragram.messenger.pillstack.ui.PillStackPreferencesActivity")
            if PillStackPreferencesActivity is None:
                return
            frag = get_last_fragment()
            if frag:
                frag.presentFragment(PillStackPreferencesActivity())
        except Exception as e:
            log(f"OtherSettings: _open_pill_stack_settings error: {e}")

    def _getCacheDir(self) -> str:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        return f"/data/data/{pkg}/files/packitCache"

    def _killProcess(self):
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGKILL)

    def _onClearCacheClick(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return

            builder = AlertDialogBuilder(act)
            builder.set_title(strings.clear_cache_confirm_title)
            builder.set_message(strings.clear_cache_confirm_message)

            def onConfirm(b, w):
                b.dismiss()
                try:
                    cacheDir = self._getCacheDir()
                    if os.path.exists(cacheDir):
                        shutil.rmtree(cacheDir)
                except Exception as e:
                    log(f"clear cache error: {e}")

                try:
                    frag2 = get_last_fragment()
                    act2 = frag2.getParentActivity() if frag2 else None
                    if not act2:
                        return

                    restartBuilder = AlertDialogBuilder(act2)
                    restartBuilder.set_title(strings.clear_cache_done_title)
                    restartBuilder.set_message(strings.clear_cache_done_message)

                    def onRestart(rb, rw):
                        rb.dismiss()
                        thread = threading.Thread(target=self._killProcess)
                        thread.daemon = True
                        thread.start()

                    restartBuilder.set_positive_button(strings.restart_now, onRestart)
                    restartBuilder.set_negative_button(strings.restart_later, lambda rb, rw: rb.dismiss())
                    restartBuilder.show()
                except Exception as e:
                    log(f"clear cache restart dialog error: {e}")

            builder.set_positive_button(strings.clear_cache_button, onConfirm)
            builder.set_negative_button(strings.cancel_button, lambda b, w: b.dismiss())
            try:
                builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
            except Exception as e:
                log(f"make_button_red error: {e}")
            builder.show()
        except Exception as e:
            log(f"clear cache dialog error: {e}")

    def _onClearPluginCacheClick(self, view):
        try:
            pkg = ApplicationLoader.applicationContext.getPackageName()
            plugin_cache_dir = f"/data/data/{pkg}/files/packitCache/pluginCache"
            if os.path.exists(plugin_cache_dir):
                shutil.rmtree(plugin_cache_dir)
                log("other: plugin cache cleared")
        except Exception as e:
            log(f"other: clear plugin cache error: {e}")

    def _getContext(self):
        frag = get_last_fragment()
        return frag.getParentActivity() if frag else None

    def _onRestartRequiredSwitch(self, val):
        def show():
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return
                builder = AlertDialogBuilder(act)
                builder.set_title(strings.restart_required_title)
                builder.set_message(strings.restart_required_message)

                def onRestart(b, w):
                    b.dismiss()
                    thread = threading.Thread(target=self._killProcess)
                    thread.daemon = True
                    thread.start()

                builder.set_positive_button(strings.restart_now, onRestart)
                builder.set_negative_button(strings.restart_later, lambda b, w: b.dismiss())
                builder.show()
            except Exception as e:
                log(f"other: _onRestartRequiredSwitch error: {e}")

        from android_utils import run_on_ui_thread
        run_on_ui_thread(show)

    def build(self):
        ctx = self._getContext()

        items = [
            Header(text=strings.buttons_header),
            self._build_dialogs_btn_item(ctx),
            self._build_pill_stack_item(ctx),
            Switch(
                key="show_chat_menu",
                text=strings.button_in_chat_menu,
                subtext=strings.button_in_chat_menu_desc,
                default=False,
                icon="msg_settings",
                link_alias="show_chat_menu",
                on_change=self.chat_button.on_chat_switch if self.chat_button else None
            ),
            Switch(
                key="show_chat_plugins_menu",
                text=strings.button_in_chat_plugins,
                subtext=strings.button_in_chat_plugins_desc,
                default=False,
                icon="msg_plugins",
                link_alias="show_chat_plugins_menu",
                on_change=self.chat_button.on_chat_plugins_switch if self.chat_button else None
            ),

            Switch(
                key="show_settings_button",
                text=strings.show_settings_button,
                subtext=strings.show_settings_button_desc,
                default=True,
                icon="msg_settings",
                link_alias="show_settings_button",
                on_change=self._onRestartRequiredSwitch
            ),
        ]

        items += [
            Divider(text=strings.buttons_header_desc),
            Header(text=strings.interface_header),
            Switch(
                key="hide_unavailable_plugins",
                text=strings.hide_unavailable_plugins,
                subtext=strings.hide_unavailable_plugins_desc,
                default=False,
                icon="msg_block",
                link_alias="hide_unavailable_plugins"
            ),
            Switch(
                key="old_sort_menu_design",
                text=strings.classic_sort_menu,
                subtext=strings.classic_sort_menu_desc,
                default=False,
                icon="msg_list",
                link_alias="old_sort_menu_design"
            ),
            Switch(
                key="show_default_sticker",
                text=strings.show_default_sticker,
                subtext=strings.show_default_sticker_desc,
                default=False,
                icon="msg_sticker",
                link_alias="show_default_sticker"
            ),
            Divider(),
            Header(text=strings.plugin_card_header),
            Switch(
                key="show_plugin_tags",
                text=strings.show_plugin_tags,
                subtext=strings.show_plugin_tags_desc,
                default=True,
                icon="menu_tag_filter",
                link_alias="show_plugin_tags"
            ),
            Switch(
                key="show_plugin_size",
                text=strings.show_plugin_size,
                subtext=strings.show_plugin_size_desc,
                default=False,
                icon="files_internal",
                link_alias="show_plugin_size"
            ),
            Switch(
                key="show_plugin_min_version",
                text=strings.show_plugin_min_version,
                subtext=strings.show_plugin_min_version_desc,
                default=False,
                icon="msg_info",
                link_alias="show_plugin_min_version"
            ),
            Switch(
                key="show_plugin_deps_count",
                text=strings.show_plugin_deps_count,
                subtext=strings.show_plugin_deps_count_desc,
                default=False,
                icon="msg_link",
                link_alias="show_plugin_deps_count"
            ),
            Divider(),
            Header(text=strings.plugin_profile_header),
            Switch(
                key="show_extended_desc",
                text=strings.show_extended_desc,
                subtext=strings.show_extended_desc_desc,
                default=False,
            ),
            Divider(text=strings.show_extended_desc_hint),
            Header(text=strings.button_relocation),
            ExpandableSwitch(
                key="button_relocation_enabled",
                text=strings.button_relocation,
                collapsed=True,
                children=[
                    Switch(key="relocate_copy_link", text=strings["copy_link"], default=False, icon="msg_copy", link_alias="relocate_copy_link"),
                    Switch(key="relocate_share", text=strings["share"], default=False, icon="msg_share", link_alias="relocate_share"),
                    Switch(key="relocate_code", text=strings["code"], default=False, icon="msg_view_file", link_alias="relocate_code"),
                    Switch(key="relocate_download", text=strings["download"], default=False, icon="msg_download", link_alias="relocate_download"),
                    Switch(key="relocate_translate", text=strings["translate"], default=False, icon="msg_replace", link_alias="relocate_translate"),
                    Switch(key="relocate_report", text=strings["report"], default=False, icon="msg_report", link_alias="relocate_report"),
                ],
                link_alias="button_relocation_enabled"
            ),
            Divider(),
            Header(text=strings.install_sheet_header),
            Switch(
                key="install_sheet_links",
                text=strings.install_sheet_links,
                subtext=strings.install_sheet_links_desc,
                default=True,
                icon="msg_link",
                link_alias="install_sheet_links"
            ),
            Switch(
                key="install_sheet_hash",
                text=strings.install_sheet_hash,
                subtext=strings.install_sheet_hash_desc,
                default=True,
                icon="msg_sendfile",
                link_alias="install_sheet_hash"
            ),
            Switch(
                key="install_sheet_signatures",
                text=strings.install_sheet_signatures,
                subtext=strings.install_sheet_signatures_desc,
                default=True,
                icon="msg_policy",
                link_alias="install_sheet_signatures"
            ),
            Divider(),
            Header(text=strings.navigation_header),
            Switch(
                key="skip_repository_selection",
                text=strings.skip_repository_selection,
                subtext=strings.skip_repository_selection_desc,
                default=False,
                icon="msg_leave",
                link_alias="skip_repository_selection"
            ),
            Switch(
                key="version_picker_auto_expand",
                text=strings.version_picker_auto_expand,
                subtext=strings.version_picker_auto_expand_desc,
                default=False,
                icon="msg_list",
                link_alias="version_picker_auto_expand"
            ),
            Divider(text=strings.navigation_header_desc),
            Header(text=strings.sfx_header),
            ExpandableSwitch(
                key="sfx_enabled",
                text=strings.sfx_header,
                collapsed=True,
                children=[
                    Switch(key="sfx_install", text=strings.sfx_install, default=False, icon="msg_download", link_alias="sfx_install"),
                    Switch(key="sfx_copy_link", text=strings.sfx_copy_link, default=False, icon="msg_link", link_alias="sfx_copy_link"),
                    Switch(key="sfx_search", text=strings.sfx_search, default=False, icon="msg_search", link_alias="sfx_search"),
                    Switch(key="sfx_clear_search", text=strings.sfx_clear_search, default=False, icon="msg_close", link_alias="sfx_clear_search"),
                    Switch(key="sfx_achievement", text=strings.sfx_achievement, default=True, icon="msg_gift_premium", link_alias="sfx_achievement"),
                ],
                link_alias="sfx_enabled"
            ),
            Divider(text=strings.sfx_header_desc),
            Header(text=strings.misc_header),
            Switch(
                key="show_startup_status",
                text=strings.show_startup_status,
                subtext=strings.show_startup_status_desc,
                default=False,
                icon="msg_info",
                link_alias="show_startup_status"
            ),
            Switch(
                key="fuzzy_search",
                text=strings.fuzzy_search,
                subtext=strings.fuzzy_search_desc,
                default=False,
                icon="msg_search",
                link_alias="fuzzy_search"
            ),
            Switch(
                key="static_online_status",
                text=strings.static_online_status,
                subtext=strings.static_online_status_desc,
                default=False,
                icon="msg_online",
                link_alias="static_online_status"
            ),
        ]

        items.append(Switch(
            key="disable_achievements_notify",
            text=strings.disable_achievements_notify,
            subtext=strings.disable_achievements_notify_desc,
            default=False,
            icon="msg_gift_premium",
            link_alias="disable_achievements_notify"
        ))

        items.append(Divider())

        # filesystem section should always be at the bottom of the page
        items.append(Header(text=strings.filesystem_header))

        pathCardBuilt = False
        if ctx:
            currentPath = settings.get("download_path", "/storage/emulated/0/Download")
            pathCard = _buildDownloadPathCard(ctx, currentPath)
            if pathCard is not None:
                items.append(Custom(view=pathCard))
                pathCardBuilt = True
            else:
                log("OtherSettings.build: _buildDownloadPathCard returned None")

        if not pathCardBuilt:
            items.append(
                Input(
                    key="download_path",
                    text=strings.download_path,
                    default="/storage/emulated/0/Download",
                    icon="msg_download"
                )
            )

        if ctx:
            cacheDir = self._getCacheDir()
            cacheCard = _buildCacheCard(ctx, cacheDir, self._onClearCacheClick)
            if cacheCard is not None:
                items.append(Custom(view=cacheCard))
            else:
                items.append(Text(
                    text=strings.clear_cache,
                    icon="msg_delete",
                    on_click=self._onClearCacheClick,
                    red=True
                ))

            pkg = ApplicationLoader.applicationContext.getPackageName()
            pluginCacheDir = f"/data/data/{pkg}/files/packitCache/pluginCache"
            pluginCacheCard = _buildCacheCard(ctx, pluginCacheDir, self._onClearPluginCacheClick, title=strings.clear_plugin_cache)
            if pluginCacheCard is not None:
                items.append(Custom(view=pluginCacheCard))
            else:
                items.append(Text(
                    text=strings.clear_plugin_cache,
                    icon="msg_delete",
                    on_click=self._onClearPluginCacheClick,
                    red=True
                ))
        else:
            items.append(Text(
                text=strings.clear_cache,
                icon="msg_delete",
                on_click=self._onClearCacheClick,
                red=True
            ))
            items.append(Text(
                text=strings.clear_plugin_cache,
                icon="msg_delete",
                on_click=self._onClearPluginCacheClick,
                red=True
            ))

        items.append(Divider(text=strings.cache_header_desc))

        return items

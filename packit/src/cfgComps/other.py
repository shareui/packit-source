from ui.settings import Header, Switch, Divider, Text, Input, Custom
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log, run_on_ui_thread, OnClickListener
try:
    from org.telegram.messenger import ApplicationLoader, AndroidUtilities, R
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader, AndroidUtilities failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme, BottomSheet
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.widget import LinearLayout, TextView, FrameLayout
from android.view import Gravity
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


def _buildCacheCard(context, cacheDir, on_clear):
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
        titleView.setText(str(strings.clear_cache))
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
    def __init__(self, chat_button=None):
        self.chat_button = chat_button

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

    def _getContext(self):
        frag = get_last_fragment()
        return frag.getParentActivity() if frag else None

    def build(self):
        ctx = self._getContext()

        items = [
            Header(text=strings.buttons_header),
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
                key="show_dialogs_menu_button",
                text=strings.button_in_dialogs_menu,
                subtext=strings.button_in_dialogs_menu_desc,
                default=False,
                icon="msg_addbot",
                link_alias="show_dialogs_menu_button",
                on_change=self.chat_button.on_dialogs_menu_switch if self.chat_button else None
            ),
        ]

        items += [
            Divider(),
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
            Header(text=strings.navigation_header),
            Switch(
                key="skip_repository_selection",
                text=strings.skip_repository_selection,
                subtext=strings.skip_repository_selection_desc,
                default=False,
                icon="msg_leave",
                link_alias="skip_repository_selection"
            ),
            Divider(),
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
            Divider(),
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
        ]

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

        items.append(Switch(
            key="disable_achievements_notify",
            text=strings.disable_achievements_notify,
            subtext=strings.disable_achievements_notify_desc,
            default=False,
            icon="msg_gift_premium",
            link_alias="disable_achievements_notify"
        ))

        items.append(Divider())

        # cache should always be at the bottom of the page
        items.append(Header(text=strings.cache_header))

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
        else:
            items.append(Text(
                text=strings.clear_cache,
                icon="msg_delete",
                on_click=self._onClearCacheClick,
                red=True
            ))

        items.append(Divider())

        return items

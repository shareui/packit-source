import threading
import time
import traceback
from ui.settings import Header, Text, Divider
from elyx import strings, metainfo
from .cfg_comps.repos import RepositoriesSettings
from .cfg_comps.other import OtherSettings
from .cfg_comps.docs import DocumentationSettings
from .cfg_comps.contributors import ContributorsSettings
from base_plugin import BasePlugin, MethodHook
from android_utils import run_on_ui_thread
from hook_utils import find_class, get_private_field
from org.telegram.ui.ActionBar import Theme, BottomSheet
from org.telegram.ui.Components import LayoutHelper, UItem, BackupImageView, EffectsTextView, BulletinFactory
from com.exteragram.messenger.plugins.models import HeaderSetting
from android.widget import FrameLayout, TextView, LinearLayout, ScrollView
from android.view import Gravity
from android.util import TypedValue
from org.telegram.messenger import AndroidUtilities, ImageLocation, MediaDataController, R
from .ui.install import InstallUI
from client_utils import get_last_fragment
from org.telegram.messenger.browser import Browser
from android.net import Uri
from java import dynamic_proxy as dyp
from android_utils import OnClickListener, OnLongClickListener
from android.content import DialogInterface
from ui.bulletin import BulletinHelper
import android_utils

__icon__ = "plugin232/17"

EMPTY_LOGS = "It's empty here for now..." # перенести в стрингс
PLUGIN_ID = "shareui_packit"

class OnCancelListener(dyp(DialogInterface.OnCancelListener)):
    def __init__(self, func):
        super().__init__()
        self.func = func

    def onCancel(self, _):
        self.func()

class SettingsBuilder:
    def __init__(self, repoManager, plugin):
        self.repoManager = repoManager
        self.plugin = plugin
        self.repositoriesSettings = RepositoriesSettings(repoManager)
        self.otherSettings = OtherSettings(plugin.chatUI)
        self.documentationSettings = DocumentationSettings()
        self.contributorsSettings = ContributorsSettings()

    def _setup_settings_header_hook(self):
        try:
            class PackitSettingsHeaderHook(MethodHook):
                def __init__(self, settings_builder):
                    self.settings_builder = settings_builder

                def after_hooked_method(self, param):
                    try:
                        activity = param.thisObject
                        items = param.args[0]
                        
                        if not items or items.size() == 0:
                            return

                        for i in range(items.size()):
                            item = items.get(i)
                            if hasattr(item, 'settingItem') and str(item.settingItem) == "packit_header":
                                return

                        plugin_obj = get_private_field(activity, "plugin")
                        if not plugin_obj or str(plugin_obj.getId()) != "shareui_packit":
                            return

                        if get_private_field(activity, "createSubFragmentCallback") is not None:
                            return

                        searching = get_private_field(activity, "searching")
                        if searching:
                            return

                        header = self.settings_builder._create_settings_header(activity.getContext())
                        if header:
                            item = UItem.asCustom(header)
                            item.settingItem = HeaderSetting("packit_header")
                            try:
                                item.setTransparent(True)
                            except:
                                pass
                            items.add(0, item)
                            items.add(1, UItem.asShadow())
                    except Exception:
                        pass

            PSA = find_class("com.exteragram.messenger.plugins.ui.PluginSettingsActivity")
            if PSA:
                method = PSA.getClass().getDeclaredMethod("fillItems", find_class("java.util.ArrayList"), find_class("org.telegram.ui.Components.UniversalAdapter"))
                method.setAccessible(True)
                return self.plugin.hook_method(method, PackitSettingsHeaderHook(self))
        except Exception:
            pass
        return None

    def _create_settings_header(self, context):
        try:
            container = FrameLayout(context)
            main_layout = LinearLayout(context)
            main_layout.setOrientation(LinearLayout.VERTICAL)
            main_layout.setGravity(Gravity.CENTER)
            main_layout.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(20), AndroidUtilities.dp(20), AndroidUtilities.dp(20))
            imageView = BackupImageView(context)
            imageView.setRoundRadius(AndroidUtilities.dp(45))

            def try_load_sticker(img):
                try:
                    icon_parts = __icon__.split("/")
                    if len(icon_parts) == 2:
                        sticker_set_name = icon_parts[0]
                        sticker_index = int(icon_parts[1])
                        ss = MediaDataController.getInstance(0).getStickerSetByName(sticker_set_name) or MediaDataController.getInstance(
                            0).getStickerSetByEmojiOrName(sticker_set_name)
                        if ss and ss.documents and ss.documents.size() > sticker_index:
                            img.setImage(ImageLocation.getForDocument(ss.documents.get(sticker_index)), "130_130", None, None, 0, 1)
                            return True
                except:
                    pass
                return False

            if not try_load_sticker(imageView):
                try:
                    icon_parts = __icon__.split("/")
                    if len(icon_parts) == 2:
                        sticker_set_name = icon_parts[0]
                        MediaDataController.getInstance(0).loadStickersByEmojiOrName(sticker_set_name, False, False)
                        run_on_ui_thread(lambda: try_load_sticker(imageView), 1500)
                except:
                    pass

            main_layout.addView(imageView, LayoutHelper.createLinear(130, 130, Gravity.CENTER, 0, 0, 0, 16))
            text_container = LinearLayout(context)
            text_container.setOrientation(LinearLayout.VERTICAL)
            text_container.setGravity(Gravity.CENTER)
            title = TextView(context)
            title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
            title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 22)
            title.setText(strings.plugin_title_version.format(metainfo['version']))
            title.setSingleLine(True)
            title.setGravity(Gravity.CENTER)
            text_container.addView(title, LayoutHelper.createLinear(-1, -2, 0, 0, 4, 0))
            subtitle = TextView(context)
            subtitle.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            subtitle.setText(strings.plugin_subtitle)
            subtitle.setGravity(Gravity.CENTER)
            text_container.addView(subtitle, LayoutHelper.createLinear(-1, -2))
            main_layout.addView(text_container, LayoutHelper.createLinear(-1, -2, Gravity.CENTER))
            container.addView(main_layout, LayoutHelper.createFrame(-1, -2, Gravity.CENTER))

            return container
        except Exception:
            return None

    def _open_install_plugin(self, view):
        try:
            install_ui = InstallUI(self.plugin)
            install_ui.open()
        except Exception:
            pass
    
    def _check_updates(self, view):
        pass
    
    def _openPackitForum(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                uri = Uri.parse("https://t.me/+MlXY77j5URE2MTU8")
                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        except Exception:
            pass
    
    def _show_packit_logs(self, view):
        try:
            fragment = get_last_fragment()
            activity = fragment.getParentActivity()
            logs = getattr(android_utils, "_logs", {}).get(PLUGIN_ID, None) or EMPTY_LOGS
            checking = True

            bottom_sheet = BottomSheet(activity, False, fragment.getResourceProvider())
            bottom_sheet.fixNavigationBar()
            bottom_sheet.setTitle(strings.logs_of_plugin.format(PLUGIN_ID), True)

            frame_layout = FrameLayout(activity)
            linear_layout = LinearLayout(activity)
            linear_layout.setOrientation(LinearLayout.VERTICAL)
            linear_layout.setClipChildren(False)
            linear_layout.setClipToPadding(False)
            frame_layout.addView(linear_layout)

            code_view = EffectsTextView(activity)
            code_view.setGravity(Gravity.LEFT)
            code_view.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_REGULAR))
            code_view.setLinkTextColor(Theme.getColor(Theme.key_dialogTextLink))
            code_view.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            code_view.setText(logs)
            code_view.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            code_view.setOnClickListener(
                OnClickListener(lambda _: (
                    BulletinHelper.show_copied_to_clipboard()
                    if AndroidUtilities.addToClipboard(logs)
                    else None
                ))
            )

            def clear_logs():
                nonlocal logs, code_view
                android_utils._logs = getattr(android_utils, "_logs", {})
                android_utils._logs.pop(PLUGIN_ID, None)
                logs = EMPTY_LOGS

                def _fn():
                    try:
                        code_view.setText(logs)
                        BulletinFactory.of(bottom_sheet.getSheetContainer(),
                                           fragment.getResourceProvider()).createSuccessBulletin(strings.logs_cleared).show()
                    except:
                        pass

                run_on_ui_thread(_fn)

            code_view.setOnLongClickListener(OnLongClickListener(lambda *_: clear_logs()))
            code_view.setPadding(AndroidUtilities.dp(10), AndroidUtilities.dp(10), AndroidUtilities.dp(10),
                                 AndroidUtilities.dp(10))
            code_view.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(10),
                Theme.getColor(Theme.key_chat_serviceBackground),
                Theme.getColor(Theme.key_chat_serviceBackground)
            ))
            linear_layout.addView(code_view, LayoutHelper.createLinear(-1, -2, 0, 21, 28, 21, 0))

            def is_check():
                nonlocal checking
                return checking

            def _fn():
                nonlocal checking, code_view, logs
                while is_check():
                    logs_new = getattr(android_utils, "_logs", {}).get(PLUGIN_ID, None) or EMPTY_LOGS
                    if logs_new != logs:
                        logs = logs_new
                        run_on_ui_thread(lambda: code_view.setText(logs))
                    time.sleep(0.3)

            def _stop():
                nonlocal checking
                checking = False

            thread = threading.Thread(target=_fn)
            thread.daemon = True

            scroll_view = ScrollView(activity)
            scroll_view.addView(frame_layout)
            bottom_sheet.setCustomView(scroll_view)
            bottom_sheet.setOnCancelListener(OnCancelListener(lambda: _stop()))
            bottom_sheet.show()
            thread.start()
        except Exception:
            pass
    
    def buildMainSettings(self):
        return [
            Header(text=strings.plugins_header),
            
            Text(
                text=strings.install_plugin,
                icon="msg_download",
                on_click=self._open_install_plugin,
                link_alias="install"
            ),
            
            Text(
                text=strings.check_updates,
                icon="msg_retry",
                on_click=self._check_updates,
                link_alias="check_updates"
            ),
            
            Divider(),
            Header(text=strings.settings_header),
            
            Text(
                text=strings.deeplinks,
                icon="msg_link",
                on_click=lambda view: None
            ),
            
            Text(
                text=strings.repositories,
                icon="msg_folders",
                create_sub_fragment=self.repositoriesSettings.build
            ),
            
            Text(
                text=strings.show_logs,
                icon="msg_log",
                on_click=self._show_packit_logs,
                link_alias="show_logs"
            ),
            
            Text(
                text=strings.other_settings,
                icon="msg_settings",
                create_sub_fragment=self.otherSettings.build
            ),
            
            Divider(),
            Header(text=strings.community_header),
            
            Text(
                text=strings.packit_forum,
                icon="msg_groups",
                on_click=self._openPackitForum
            ),
            
            Text(
                text=strings.links_docs,
                icon="msg_help",
                create_sub_fragment=self.documentationSettings.build
            ),
            
            Text(
                text=strings.contributors,
                icon="msg_contacts",
                create_sub_fragment=self.contributorsSettings.build
            ),
            
            Divider(),
        ]

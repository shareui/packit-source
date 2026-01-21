from ui.settings import Header, Text, Divider
from elyx import strings
from .cfg_comps.interface import InterfaceSettings
from .cfg_comps.command import CommandSettings
from .cfg_comps.repos import RepositoriesSettings
from .cfg_comps.other import OtherSettings
from .cfg_comps.docs import DocumentationSettings
from .cfg_comps.contributors import ContributorsSettings
from base_plugin import BasePlugin, MethodHook
from android_utils import log, run_on_ui_thread
from hook_utils import find_class, get_private_field
from org.telegram.messenger import MediaDataController, ImageLocation, AndroidUtilities
from org.telegram.ui.ActionBar import Theme
from org.telegram.ui.Components import LayoutHelper, BackupImageView, UItem
from com.exteragram.messenger.plugins.models import HeaderSetting
from android.widget import FrameLayout, TextView
from android.view import Gravity
from android.util import TypedValue


class SettingsBuilder:
    def __init__(self, repoManager, plugin):
        self.repoManager = repoManager
        self.plugin = plugin
        self.interfaceSettings = InterfaceSettings()
        self.interfaceSettings.setPlugin(plugin)
        self.commandSettings = CommandSettings()
        self.repositoriesSettings = RepositoriesSettings(repoManager)
        self.otherSettings = OtherSettings()
        self.documentationSettings = DocumentationSettings()
        self.contributorsSettings = ContributorsSettings()
        self._setup_settings_header_hook()
    
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
                        
                        plugin_obj = get_private_field(activity, "plugin")
                        if not plugin_obj or str(plugin_obj.getId()) != "packit":
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
                            try: item.setTransparent(True)
                            except: pass
                            items.add(0, item)
                            items.add(1, UItem.asShadow())
                    except:
                        pass
            
            PSA = find_class("com.exteragram.messenger.plugins.ui.PluginSettingsActivity")
            if PSA:
                method = PSA.getClass().getDeclaredMethod("fillItems", find_class("java.util.ArrayList"), find_class("org.telegram.ui.Components.UniversalAdapter"))
                method.setAccessible(True)
                self.plugin.hook_method(method, PackitSettingsHeaderHook(self))
        except Exception as e:
            log(f"Failed to setup settings header hook: {e}")
    
    def _create_settings_header(self, context):
        try:
            container = FrameLayout(context)
            
            imageView = BackupImageView(context)
            imageView.setRoundRadius(AndroidUtilities.dp(54))
            
            def try_load_sticker(img):
                pack_name = "frieren"
                sticker_index = 0
                
                ss = MediaDataController.getInstance(0).getStickerSetByName(pack_name) or MediaDataController.getInstance(0).getStickerSetByEmojiOrName(pack_name)
                if ss and ss.documents and ss.documents.size() > 0:
                    sticker_index = min(sticker_index, ss.documents.size() - 1)
                    img.setImage(ImageLocation.getForDocument(ss.documents.get(sticker_index)), "108_108", None, None, 0, 1)
                    return True
                return False
            
            if not try_load_sticker(imageView):
                MediaDataController.getInstance(0).loadStickersByEmojiOrName("frieren", False, False)
                run_on_ui_thread(lambda: try_load_sticker(imageView), 1500)
            
            container.addView(imageView, LayoutHelper.createFrame(108, 108, Gravity.CENTER | Gravity.TOP, 0, 20, 0, 0))
            
            title = TextView(context)
            title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
            title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 22)
            title.setText("Settings")
            title.setSingleLine(True)
            title.setGravity(Gravity.CENTER)
            container.addView(title, LayoutHelper.createFrame(-2, -2, Gravity.CENTER | Gravity.TOP, 50, 145, 50, 0))
            
            subtitle = TextView(context)
            subtitle.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            subtitle.setText("Packit Plugin Manager")
            subtitle.setGravity(Gravity.CENTER)
            container.addView(subtitle, LayoutHelper.createFrame(-2, -2, Gravity.CENTER | Gravity.TOP, 60, 180, 60, 27))
            
            return container
        except Exception as e:
            log(f"Failed to create settings header: {e}")
            return None
    
    def _openPackitForum(self, view):
        try:
            from client_utils import get_last_fragment
            from org.telegram.messenger.browser import Browser
            from android.net import Uri
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                uri = Uri.parse("https://t.me/+MlXY77j5URE2MTU8")
                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        except Exception as e:
            log(f"failed to open packit forum: {e}")
    
    def buildMainSettings(self):
        return [
            Header(text="Settings"),
            
            Text(
                text=strings.interface_settings,
                icon="msg_palette",
                create_sub_fragment=self.interfaceSettings.build
            ),
            
            Text(
                text=strings.command_settings,
                icon="msg_edit",
                create_sub_fragment=self.commandSettings.build
            ),
            
            Text(
                text=strings.repositories,
                icon="msg_folders",
                create_sub_fragment=self.repositoriesSettings.build
            ),
            
            Text(
                text=strings.other_settings,
                icon="msg_settings",
                create_sub_fragment=self.otherSettings.build
            ),
            
            Divider(),
            Header(text="Community & info"),
            
            Text(
                text="Packit forum",
                icon="msg_groups",
                on_click=self._openPackitForum
            ),
            
            Text(
                text="Documentation",
                icon="msg_help",
                create_sub_fragment=self.documentationSettings.build
            ),
            
            Text(
                text="Contributors",
                icon="msg_contacts",
                create_sub_fragment=self.contributorsSettings.build
            ),
            
            Divider(text="With love <3")
        ]
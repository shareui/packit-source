from ui.settings import Header, Text, Divider
try:
    from elyx import strings, metainfo
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, metainfo failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
from .cfgComps.repos import RepositoriesSettings
from .cfgComps.deeplinks import DeeplinksSettings
from .cfgComps.other import OtherSettings
from .cfgComps.docs import DocumentationSettings
from .cfgComps.contributors import ContributorsSettings
from .cfgComps.profile import ProfileSettings
from ui.bulletin import BulletinHelper
from base_plugin import BasePlugin, MethodHook
from android_utils import run_on_ui_thread
from hook_utils import find_class, get_private_field
try:
    from org.telegram.ui.ActionBar import Theme, BottomSheet
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme, BottomSheet failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper, UItem, BackupImageView, EffectsTextView, BulletinFactory
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper, UItem, BackupImageView, EffectsTextView, BulletinFactory failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.plugins.models import HeaderSetting
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins.models import HeaderSetting failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.widget import FrameLayout, TextView, LinearLayout, ScrollView
from android.view import Gravity
from android.util import TypedValue
try:
    from org.telegram.messenger import AndroidUtilities, ImageLocation, MediaDataController, R
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, ImageLocation, MediaDataController, R failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
from .ui.installUi.uiMain import InstallUI
from client_utils import get_last_fragment
try:
    from org.telegram.messenger.browser import Browser
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger.browser import Browser failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.net import Uri
from java import dynamic_proxy as dyp
from android_utils import OnClickListener, OnLongClickListener
from android.content import DialogInterface
import android_utils

__icon__ = "plugin232/17"

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
        self.deeplinksSettings = DeeplinksSettings()
        self.otherSettings = OtherSettings(plugin.chatUI)
        self.documentationSettings = DocumentationSettings()
        self.contributorsSettings = ContributorsSettings()
        self.profileSettings = ProfileSettings()

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
        try:
            from ui.bulletin import BulletinHelper
            BulletinHelper.show_info(strings.not_ready_yet)
        except Exception:
            pass
    
    def _install_icons(self, view):
        try:
            from ui.bulletin import BulletinHelper
            BulletinHelper.show_info(strings.not_ready_yet)
        except Exception:
            pass
    
    def _install_config(self, view):
        try:
            from ui.bulletin import BulletinHelper
            BulletinHelper.show_info(strings.not_ready_yet)
        except Exception:
            pass

    def _security_scan(self, view):
        try:
            from ui.bulletin import BulletinHelper
            BulletinHelper.show_info(strings.not_ready_yet)
        except Exception:
            pass
    
    def _openPackitForum(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                uri = Uri.parse("https://t.me/packitGround")
                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
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
                text=strings.install_icons,
                icon="msg_smile_status",
                on_click=self._install_icons,
                link_alias="install_icons"
            ),
            
            Text(
                text=strings.install_config,
                icon="msg_settings_old",
                on_click=self._install_config,
                link_alias="install_config"
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
                create_sub_fragment=self.deeplinksSettings.build
            ),
            
            Text(
                text=strings.repositories,
                icon="msg_folders",
                create_sub_fragment=self.repositoriesSettings.build
            ),
            
            Text(
                text="Profile",
                icon="msg_contacts",
                create_sub_fragment=self.profileSettings.build
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

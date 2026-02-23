from android_utils import log
from hook_utils import find_class, get_private_field
try:
    from org.telegram.messenger import MessagesController
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import MessagesController failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
import threading
import urllib.request
import json
from java.util import Locale
from java.lang import Long

# Любая попытка неправомерного использования системы бейджей автоматически лишает ваш плагин права на публикацию через официальные источники, а также приведёт к перманентной блокировке во всех ресурсах exteraGram и AyuGram без возможности апелляции. Подробнее: https://teletype.in/@exterasquad/forum-rules-ru
# Any attempt to misuse the badge system will automatically revoke your plugin's right to be published through official sources and will result in permanent blocking from all exteraGram and AyuGram resources without the possibility of appeal. Learn more: https://teletype.in/@exterasquad/forum-rules-en

class MethodHook:
    def before_hooked_method(self, param):
        pass
    
    def after_hooked_method(self, param):
        pass


class BadgeManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self.custom_badges = {}
        self.badge_hook_refs = []
        self.developer_hook_refs = []
        self.extera_hook_refs = []
        self.verification_hook_refs = []
        self.TLRPC_User = None
        self.TLRPC_Chat = None
        self.config_url = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json"
        self.local_badges_config = {}
        self.api_badge_source = None

        try:
            self.current_lang = Locale.getDefault().getLanguage()
            if self.current_lang not in ['ru', 'en']:
                self.current_lang = 'en'
        except:
            self.current_lang = 'en'
    
    
    def setup_hooks(self):
        try:
            self._cache_classes()
            self._get_api_badge_source()
            self._setup_badge_hooks()
            self._load_custom_badges()
        except Exception as e:
            log(f"[Packit Badges] Error setting up custom badges hooks: {e}")
    
    def _cache_classes(self):
        try:
            self.TLRPC_User = find_class("org.telegram.tgnet.TLRPC$User")
            self.TLRPC_Chat = find_class("org.telegram.tgnet.TLRPC$Chat")
        except Exception as e:
            log(f"[Packit Badges] Error caching classes: {e}")
    
    def _get_api_badge_source(self):
        try:
            BadgesController = find_class("com.exteragram.messenger.badges.BadgesController")
            if not BadgesController:
                return
                
            badges_controller = BadgesController.INSTANCE
            self.api_badge_source = get_private_field(badges_controller, "apiBadgeSource")

        except Exception as e:
            log(f"[Packit Badges] Error getting ApiBadgeSource: {e}")
    
    def _setup_badge_hooks(self):
        try:
            if not self.api_badge_source:
                return

            ApiBadgeSource = find_class("com.exteragram.messenger.badges.source.ApiBadgeSource")
            if not ApiBadgeSource:
                return

            developer_hook = CustomDeveloperHook(self)
            self.developer_hook_refs = self.plugin.hook_all_methods(
                ApiBadgeSource,
                "isDeveloper",
                developer_hook
            )

            badge_hook = CustomBadgeHook(self)
            self.badge_hook_refs = self.plugin.hook_all_methods(
                ApiBadgeSource,
                "getBadge",
                badge_hook
            )

            change_hook = CustomChangeHook(self)
            change_hook_refs = self.plugin.hook_all_methods(
                ApiBadgeSource,
                "canChangeBadge",
                change_hook
            )
            
            if self.badge_hook_refs and self.developer_hook_refs:
                log("[Packit Badges] Successfully hooked ApiBadgeSource methods")
            else:
                log("[Packit Badges] Failed to hook some ApiBadgeSource methods")

        except Exception as e:
            log(f"[Packit Badges] Error setting up badge hooks: {e}")
    
    def _load_config_from_url(self):
        try:
            with urllib.request.urlopen(self.config_url, timeout=10) as response:
                raw_data = response.read().decode('utf-8')
                config = json.loads(raw_data)
                badges = config.get('badges', [])
                self.local_badges_config = {'badges': badges}
                return True
        except:
            return False
    
    def _load_custom_badges(self):
        try:
            self.custom_badges.clear()
            thread = threading.Thread(target=self._process_local_badges)
            thread.daemon = True
            thread.start()
        except Exception as e:
            log(f"[Packit Badges] Error loading custom badges: {e}")
    
    def _process_local_badges(self):
        try:
            if not self._load_config_from_url():
                self.local_badges_config = {'badges': []}
            
            badges_data = self.local_badges_config.get('badges', [])
            if not badges_data:
                return
                
            BadgeDTO = find_class("com.exteragram.messenger.api.dto.BadgeDTO")
            if not BadgeDTO:
                return

            self._add_badges_to_cache(badges_data, BadgeDTO)
                
        except Exception as e:
            log(f"[Packit Badges] Error processing local badges: {e}")
    
    def _add_badges_to_cache(self, badges_data, BadgeDTO):
        try:
            if not self.api_badge_source:
                return

            cache = get_private_field(self.api_badge_source, "cache")
            if not cache:
                return
            
            BadgeInfo = find_class("com.exteragram.messenger.badges.source.BadgeInfo")
            ProfileStatus = find_class("com.exteragram.messenger.api.model.ProfileStatus")
            
            if not BadgeInfo or not ProfileStatus:
                return
                
            for badge_info in badges_data:
                user_id = badge_info.get('user_id')
                chat_id = badge_info.get('chat_id')
                emoji_id = badge_info.get('emoji_id')
                text_template = badge_info.get(f'text_{self.current_lang}') or badge_info.get('text_en', '')
                
                if user_id and emoji_id and text_template:
                    user_name = self._get_user_name(user_id)
                    custom_text = text_template.format(user_name=user_name)
                    badge_dto = BadgeDTO(emoji_id, custom_text)
                    self.custom_badges[user_id] = badge_dto
                    badge_info_obj = BadgeInfo(badge_dto, ProfileStatus.DEVELOPER, True)
                    cache.put(Long.valueOf(user_id), badge_info_obj)
                    
                elif chat_id and emoji_id and text_template:
                    chat_name = self._get_chat_name(chat_id)
                    custom_text = text_template.format(chat_name=chat_name)
                    badge_dto = BadgeDTO(emoji_id, custom_text)
                    self.custom_badges[chat_id] = badge_dto
                    badge_info_obj = BadgeInfo(badge_dto, ProfileStatus.DEVELOPER, True)
                    cache.put(Long.valueOf(chat_id), badge_info_obj)
                    
        except Exception as e:
            log(f"[Packit Badges] Error adding badges to cache: {e}")
    
    def _get_user_name(self, user_id):
        try:
            user = MessagesController.getInstance(0).getUser(user_id)
            if user:
                return f"{user.first_name} {user.last_name or ''}".strip()
        except:
            pass
        return f"User {user_id}"
    
    def _get_chat_name(self, chat_id):
        try:
            chat = MessagesController.getInstance(0).getChat(-abs(chat_id))
            if chat:
                return chat.title
        except:
            pass
        return f"Channel {chat_id}"
    
    def cleanup(self):
        try:
            for ref in self.badge_hook_refs:
                if ref:
                    self.plugin.unhook_method(ref)
            for ref in self.developer_hook_refs:
                if ref:
                    self.plugin.unhook_method(ref)
            for ref in self.extera_hook_refs:
                if ref:
                    self.plugin.unhook_method(ref)
            for ref in self.verification_hook_refs:
                if ref:
                    self.plugin.unhook_method(ref)

            self.badge_hook_refs = []
            self.developer_hook_refs = []
            self.extera_hook_refs = []
            self.verification_hook_refs = []
            self.custom_badges.clear()

            if self.api_badge_source:
                cache = get_private_field(self.api_badge_source, "cache")
                if cache:
                    for badge_id in self.custom_badges.keys():
                        cache.remove(Long.valueOf(badge_id))
            
        except Exception as e:
            log(f"[Packit Badges] Error during cleanup: {e}")


class CustomBadgeHook(MethodHook):
    def __init__(self, badge_manager):
        self.badge_manager = badge_manager
        
    def before_hooked_method(self, param):
        try:
            user_id = param.args[0] if param.args else None
            is_user = param.args[1] if len(param.args) > 1 else True
            
            if user_id and user_id in self.badge_manager.custom_badges:
                custom_badge = self.badge_manager.custom_badges[user_id]
                param.setResult(custom_badge)
                return
                    
        except Exception as e:
            log(f"[Packit Badges] Error in CustomBadgeHook: {e}")


class CustomDeveloperHook(MethodHook):
    def __init__(self, badge_manager):
        self.badge_manager = badge_manager
        
    def before_hooked_method(self, param):
        try:
            user_id = param.args[0] if param.args else None
            if user_id and user_id in self.badge_manager.custom_badges:
                param.setResult(True)
                return
        except Exception as e:
            log(f"[Packit Badges] Error in CustomDeveloperHook: {e}")


class CustomChangeHook(MethodHook):
    def __init__(self, badge_manager):
        self.badge_manager = badge_manager
        
    def before_hooked_method(self, param):
        try:
            user_id = param.args[0] if param.args else None
            if user_id and user_id in self.badge_manager.custom_badges:
                param.setResult(True)
                return
        except Exception as e:
            log(f"[Packit Badges] Error in CustomChangeHook: {e}")

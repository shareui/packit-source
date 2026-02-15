from android_utils import log
from hook_utils import find_class
from base_plugin import MethodHook
from org.telegram.messenger import MessagesController
import threading
import urllib.request
import json
from java.util import Locale


class BadgeManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self.custom_badges = {}
        self.badge_hook_ref = None
        self.developer_hook_ref = None
        self.extera_hook_ref = None
        self.TLRPC_User = None
        self.TLRPC_Chat = None
        self.config_url = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json"
        self.local_badges_config = {}

        try:
            self.current_lang = Locale.getDefault().getLanguage()
            if self.current_lang not in ['ru', 'en']:
                self.current_lang = 'en'
        except:
            self.current_lang = 'en'
    
    
    def setup_hooks(self):
        try:
            self._cache_classes()
            self._setup_badge_hook()
            self._load_custom_badges()
        except Exception as e:
            log(f"[Packit Badges] Error setting up custom badges hooks: {e}")
    
    def _cache_classes(self):
        try:
            self.TLRPC_User = find_class("org.telegram.tgnet.TLRPC$User")
            self.TLRPC_Chat = find_class("org.telegram.tgnet.TLRPC$Chat")
        except Exception as e:
            log(f"[Packit Badges] Error caching classes: {e}")
    
    def _setup_badge_hook(self):
        try:
            BadgesController = find_class("com.exteragram.messenger.badges.BadgesController")
            if not BadgesController:
                return
                
            TLObject = find_class("org.telegram.tgnet.TLObject")
            method = BadgesController.getClass().getDeclaredMethod("getBadge", TLObject)
            method.setAccessible(True)
            
            self.badge_hook_ref = self.plugin.hook_method(method, CustomBadgeHook(self))
            
            if self.TLRPC_User:
                is_developer_method = BadgesController.getClass().getDeclaredMethod("isDeveloper", self.TLRPC_User)
                is_developer_method.setAccessible(True)
                self.developer_hook_ref = self.plugin.hook_method(is_developer_method, CustomDeveloperHook(self))
            
            if self.TLRPC_Chat:
                is_extera_method = BadgesController.getClass().getDeclaredMethod("isExtera", self.TLRPC_Chat)
                is_extera_method.setAccessible(True)
                self.extera_hook_ref = self.plugin.hook_method(is_extera_method, CustomExteraHook(self))

        except Exception as e:
            log(f"[Packit Badges] Error setting up badge hook: {e}")
    
    def _load_config_from_url(self):
        try:
            with urllib.request.urlopen(self.config_url, timeout=10) as response:
                raw_data = response.read().decode('utf-8')
                config = json.loads(raw_data)
                badges = config.get('badges', [])
                self.local_badges_config = {'badges': badges}
                return True
        except Exception as e:
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
                    
                elif chat_id and emoji_id and text_template:
                    chat_name = self._get_chat_name(chat_id)
                    custom_text = text_template.format(chat_name=chat_name)
                    badge_dto = BadgeDTO(emoji_id, custom_text)
                    self.custom_badges[chat_id] = badge_dto
                    
        except Exception as e:
            log(f"[Packit Badges] Error processing local badges: {e}")
    
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
            if self.badge_hook_ref:
                self.plugin.unhook_method(self.badge_hook_ref)
                self.badge_hook_ref = None
            if self.developer_hook_ref:
                self.plugin.unhook_method(self.developer_hook_ref)
                self.developer_hook_ref = None
            if self.extera_hook_ref:
                self.plugin.unhook_method(self.extera_hook_ref)
                self.extera_hook_ref = None
            self.custom_badges.clear()
        except Exception as e:
            log(f"[Packit Badges] Error during cleanup: {e}")


class CustomBadgeHook(MethodHook):
    def __init__(self, badge_manager):
        self.badge_manager = badge_manager
        
    def before_hooked_method(self, param):
        try:
            tl_object = param.args[0]
            
            if (self.badge_manager.TLRPC_User and 
                isinstance(tl_object, self.badge_manager.TLRPC_User) and 
                tl_object.id in self.badge_manager.custom_badges):
                custom_badge = self.badge_manager.custom_badges[tl_object.id]
                param.setResult(custom_badge)
                return custom_badge
                    
            if (self.badge_manager.TLRPC_Chat and 
                isinstance(tl_object, self.badge_manager.TLRPC_Chat) and 
                tl_object.id in self.badge_manager.custom_badges):
                custom_badge = self.badge_manager.custom_badges[tl_object.id]
                param.setResult(custom_badge)
                return custom_badge
                    
        except Exception as e:
            log(f"[Packit Badges] Error in CustomBadgeHook: {e}")


class CustomDeveloperHook(MethodHook):
    def __init__(self, badge_manager):
        self.badge_manager = badge_manager
        
    def before_hooked_method(self, param):
        try:
            user = param.args[0]
            if user.id in self.badge_manager.custom_badges:
                param.setResult(True)
                return True
        except Exception as e:
            log(f"[Packit Badges] Error in CustomDeveloperHook: {e}")


class CustomExteraHook(MethodHook):
    def __init__(self, badge_manager):
        self.badge_manager = badge_manager
        
    def before_hooked_method(self, param):
        try:
            chat = param.args[0]
            if chat.id in self.badge_manager.custom_badges:
                param.setResult(True)
                return True
        except Exception as e:
            log(f"[Packit Badges] Error in CustomExteraHook: {e}")
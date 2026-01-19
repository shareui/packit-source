import json
from android_utils import run_on_ui_thread, log
from client_utils import get_last_fragment
from base_plugin import BasePlugin, MenuItemData, MenuItemType, HookResult, HookStrategy, MethodHook
from ui.bulletin import BulletinHelper
from org.telegram.messenger import AndroidUtilities
from java import dynamic_proxy, jclass
from android.content import Context
from android.view import View
from org.telegram.ui import ChatActivity
from hook_utils import find_class
from com.exteragram.messenger.plugins import PluginsController
from com.exteragram.messenger.plugins.ui import PluginSettingsActivity

class ChatUI:
    def __init__(self, plugin):
        self.plugin = plugin
        self.packit_menu_id = 880034
    
    def get_text(self, key):
        texts = {
            'packit': 'PackIt',
            'packit_settings': 'PackIt Settings'
        }
        return texts.get(key, key)
    
    def initialize_chat_menu(self):
        try:
            self._add_buton_to_chat_header()
            self._hook_chat_activity_resume()
        except Exception as e:
            log(f"Failed to initialize chat menu: {e}")
    
    def _get_private_field(self, obj, name):
        try:
            cls = obj.getClass()
        except Exception:
            return None
        while cls is not None:
            try:
                field = cls.getDeclaredField(name)
                field.setAccessible(True)
                return field.get(obj)
            except Exception:
                try:
                    cls = cls.getSuperclass()
                except Exception:
                    break
        return None
    
    def _add_buton_to_chat_header(self):
        try:
            frag = get_last_fragment()
            if not frag or not isinstance(frag, ChatActivity):
                return
            
            chat_activity = frag
            headerItem = self._get_private_field(chat_activity, "headerItem")
            if headerItem is None:
                return
            R = find_class("org.telegram.messenger.R")
            try:
                icon_id = getattr(R.drawable, 'msg_settings')
            except Exception:
                try:
                    icon_id = getattr(R.drawable, 'msg_settings_14')
                except Exception:
                    icon_id = 0
            
            lazy_list = self._get_private_field(headerItem, "lazyList")
            lazy_map = self._get_private_field(headerItem, "lazyMap")

            try:
                if lazy_map is not None and lazy_map.get(self.packit_menu_id) is not None:
                    self._hook_chat_action_bar(chat_activity)
                    return
                if lazy_list is not None:
                    for i in range(lazy_list.size()):
                        item = lazy_list.get(i)
                        try:
                            item_id = self._get_private_field(item, "id")
                            if item_id == self.packit_menu_id:
                                self._hook_chat_action_bar(chat_activity)
                                return
                        except Exception:
                            continue
            except Exception:
                pass

            insert_position = -1
            try:
                if lazy_list is not None:
                    insert_position = lazy_list.size()
                    admin_gap = self._get_private_field(chat_activity, "adminItemsGap")
                    if admin_gap is not None and lazy_map is not None:
                        for i in range(lazy_list.size()):
                            item = lazy_list.get(i)
                            if item == admin_gap:
                                insert_position = i
                                break
            except Exception:
                pass

            try:
                ItemClass = jclass("org.telegram.ui.ActionBar.ActionBarMenuItem$Item")
                item_java_class = ItemClass.getClass()
                Integer = jclass("java.lang.Integer")
                Boolean = jclass("java.lang.Boolean")
                asSubItemMethod = item_java_class.getDeclaredMethod(
                    "asSubItem",
                    Integer.TYPE,
                    Integer.TYPE,
                    jclass("android.graphics.drawable.Drawable"),
                    jclass("java.lang.CharSequence"),
                    Boolean.TYPE,
                    Boolean.TYPE
                )
                asSubItemMethod.setAccessible(True)
                our_item = asSubItemMethod.invoke(None,
                    Integer(self.packit_menu_id),
                    Integer(icon_id),
                    None,
                    self.get_text('packit'),
                    Boolean(True),
                    Boolean(False)
                )
                if lazy_list is not None and insert_position >= 0:
                    lazy_list.add(insert_position, our_item)
                    if lazy_map is not None:
                        lazy_map.put(self.packit_menu_id, our_item)
                else:
                    try:
                        headerItem.lazilyAddSubItem(self.packit_menu_id, icon_id, self.get_text('packit'))
                    except Exception:
                        pass
                self._hook_chat_action_bar(chat_activity)
            except Exception:
                pass
        except Exception as e:
            log(f"Failed to add PackIt item to chat header: {e}")
    
    def _hook_chat_action_bar(self, chat_activity):
        try:
            action_bar = self._get_private_field(chat_activity, "actionBar")
            if action_bar is None:
                return
            current_callback = self._get_private_field(action_bar, "actionBarMenuOnItemClick")
            if current_callback is None:
                return
            callback_class = current_callback.getClass()
            from java import jclass
            jint = jclass("java.lang.Integer").TYPE
            onItemClickMethod = callback_class.getDeclaredMethod("onItemClick", jint)
            onItemClickMethod.setAccessible(True)
            
            chat_ui = self
            class PackItActionBarMenuItemClickHook(MethodHook):
                def __init__(self, chat_ui_ref, activity_ref):
                    self.chat_ui_ref = chat_ui_ref
                    self.activity_ref = activity_ref
                def before_hooked_method(self, param):
                    try:
                        item_id = int(param.args[0])
                        if item_id == self.chat_ui_ref.packit_menu_id:
                            run_on_ui_thread(self.chat_ui_ref.open_packit_settings)
                            param.setResult(None)
                    except Exception:
                        pass
            self.plugin.hook_method(onItemClickMethod, PackItActionBarMenuItemClickHook(self, chat_activity))
        except Exception as e:
            log(f"Failed to hook chat: {e}")
    
    def _hook_chat_activity_resume(self):
        try:
            ChatActivity = find_class("org.telegram.ui.ChatActivity")
            if ChatActivity is None:
                return
            target_method = None
            for m in ChatActivity.getClass().getDeclaredMethods():
                try:
                    name = m.getName()
                    if name == "onResume":
                        target_method = m
                        break
                except Exception:
                    pass
            if target_method is None:
                for m in ChatActivity.getClass().getDeclaredMethods():
                    try:
                        if m.getName() == "onFragmentCreate":
                            target_method = m
                            break
                    except Exception:
                        pass
            if target_method is None:
                return
            
            chat_ui = self
            class ChatResumeHook(MethodHook):
                def __init__(self, chat_ui_ref):
                    self.chat_ui_ref = chat_ui_ref
                def after_hooked_method(self, param):
                    try:
                        run_on_ui_thread(self.chat_ui_ref._add_buton_to_chat_header)
                    except Exception:
                        pass
            self.plugin.hook_method(target_method, ChatResumeHook(self))
        except Exception as e:
            log(f"Failed to hook chat activity resume: {e}")
    
    def open_packit_settings(self):
        try:
            def _open_settings():
                try:
                    fragment = get_last_fragment()
                    plugin = PluginsController.getInstance().plugins.get(self.plugin.id)
                    if plugin:
                        fragment.presentFragment(PluginSettingsActivity(plugin))
                    else:
                        BulletinHelper.show_error("PackIt plugin not found")
                except Exception as e:
                    BulletinHelper.show_error(f"Error opening settings: {e}")
            
            run_on_ui_thread(_open_settings)
        except Exception as e:
            BulletinHelper.show_error(f"Error: {e}")
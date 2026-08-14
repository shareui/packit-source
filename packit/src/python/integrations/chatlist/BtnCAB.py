# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from base_plugin import MethodHook
from java import jclass
try:
    from org.telegram.ui import ChatActivity
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui import ChatActivity failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
from hook_utils import find_class
try:
    from elyx import settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


class BtnCAB:
    def _add_button_to_chat_header(self):
        try:
            frag = get_last_fragment()
            if not frag or not isinstance(frag, ChatActivity):
                return
            
            chat_activity = frag
            show_chat = settings.get("show_chat_menu", True)
            ref_key = str(chat_activity)
            if not hasattr(self, "_ensured_refs"):
                self._ensured_refs = {}
            if self._ensured_refs.get(ref_key) == show_chat:
                return

            headerItem = self._get_private_field(chat_activity, "headerItem")
            if headerItem is None:
                return
            R = find_class("org.telegram.messenger.R")
            try:
                icon_id = getattr(R.drawable, 'msg_plugins')
            except Exception:
                try:
                    icon_id = getattr(R.drawable, 'msg_plugins_14')
                except Exception:
                    icon_id = 0
            
            lazy_list = self._get_private_field(headerItem, "lazyList")
            lazy_map = self._get_private_field(headerItem, "lazyMap")

            try:
                if lazy_map is not None and lazy_map.get(self.packit_menu_id) is not None:
                    self._hook_chat_action_bar(chat_activity)
                    self._ensured_refs[ref_key] = show_chat
                    return
                if lazy_list is not None:
                    for i in range(lazy_list.size()):
                        item = lazy_list.get(i)
                        try:
                            item_id = self._get_private_field(item, "id")
                            if item_id == self.packit_menu_id:
                                self._hook_chat_action_bar(chat_activity)
                                self._ensured_refs[ref_key] = show_chat
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
                self._ensured_refs[ref_key] = show_chat
            except Exception:
                pass
        except Exception:
            pass
    
    def _hook_chat_action_bar(self, chat_activity):
        try:
            action_bar = self._get_private_field(chat_activity, "actionBar")
            if action_bar is None:
                return
            current_callback = self._get_private_field(action_bar, "actionBarMenuOnItemClick")
            if current_callback is None:
                return
            callback_class = current_callback.getClass()
            jint = jclass("java.lang.Integer").TYPE
            onItemClickMethod = callback_class.getDeclaredMethod("onItemClick", jint)
            onItemClickMethod.setAccessible(True)
            
            chat_button = self
            class PackItActionBarMenuItemClickHook(MethodHook):
                def __init__(self, chat_button_ref, activity_ref):
                    self.chat_button_ref = chat_button_ref
                    self.activity_ref = activity_ref
                def before_hooked_method(self, param):
                    try:
                        item_id = int(param.args[0])
                        if item_id == self.chat_button_ref.packit_menu_id:
                            run_on_ui_thread(self.chat_button_ref.open_packit_settings)
                            param.setResult(None)
                    except Exception:
                        pass
            self.plugin.hook_method(onItemClickMethod, PackItActionBarMenuItemClickHook(self, chat_activity))
        except Exception:
            pass
    
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
            
            chat_button = self
            class ChatResumeHook(MethodHook):
                def __init__(self, chat_button_ref):
                    self.chat_button_ref = chat_button_ref
                def after_hooked_method(self, param):
                    try:
                        run_on_ui_thread(self.chat_button_ref._add_button_to_chat_header)
                    except Exception:
                        pass
            self.plugin.hook_method(target_method, ChatResumeHook(self))
        except Exception:
            pass
    
    def _remove_chat_button(self):
        try:
            frag = get_last_fragment()
            if not frag or not isinstance(frag, ChatActivity):
                return
            
            chat_activity = frag
            headerItem = self._get_private_field(chat_activity, "headerItem")
            if headerItem is None:
                return
            
            lazy_list = self._get_private_field(headerItem, "lazyList")
            lazy_map = self._get_private_field(headerItem, "lazyMap")
            
            if lazy_map is not None:
                lazy_map.remove(self.packit_menu_id)
            if lazy_list is not None:
                items_to_remove = []
                for i in range(lazy_list.size()):
                    item = lazy_list.get(i)
                    try:
                        item_id = self._get_private_field(item, "id")
                        if item_id == self.packit_menu_id:
                            items_to_remove.append(i)
                    except Exception:
                        continue
                for i in reversed(items_to_remove):
                    lazy_list.remove(i)
        except Exception:
            pass
    
    def _update_chat_menu(self):
        try:
            show_chat = settings.get("show_chat_menu", True)
            if show_chat:
                self._add_button_to_chat_header()
                self._hook_chat_activity_resume()
            else:
                self._remove_chat_button()
        except Exception:
            pass
    
    def on_chat_switch(self, val):
        try:
            if hasattr(self, "_ensured_refs"):
                self._ensured_refs.clear()
            settings.set("show_chat_menu", bool(val))
            run_on_ui_thread(self._update_chat_menu)
        except Exception:
            pass
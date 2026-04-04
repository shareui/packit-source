import os
import json
import weakref
import requests
from base_plugin import MethodHook
from client_utils import get_last_fragment
from hook_utils import find_class, get_private_field
from android_utils import run_on_ui_thread, log
from java import dynamic_proxy, jclass
from org.telegram.ui import ChatActivity
from markdown_utils import parse_markdown
from org.telegram.tgnet import TLRPC
from org.telegram.ui.Components import RecyclerListView


def _get_cache_dir():
    from ..utils.paths import getReposCacheDir
    return getReposCacheDir()


def _get_repo_cache_path(repo_id):
    from ..utils.paths import getRepoCachePath
    return getRepoCachePath(repo_id)


class _PackitAutocompleteHook(MethodHook):
    def __init__(self, plugin):
        MethodHook.__init__(self)
        self._plugin_ref = weakref.ref(plugin)

    @property
    def plugin(self):
        return self._plugin_ref() if self._plugin_ref else None

    def after_hooked_method(self, param):
        try:
            plugin = self.plugin
            if not plugin:
                return
            enter_view = param.thisObject
            def attach_watcher():
                plugin._packit_attach_text_watcher(enter_view)
            run_on_ui_thread(attach_watcher, delay=500)
        except Exception as e:
            log(f"PackitAutocompleteHook error: {e}")


def _packit_get_class(self, class_name):
    if class_name not in self._packit_class_cache:
        self._packit_class_cache[class_name] = find_class(class_name)
    return self._packit_class_cache[class_name]


def _packit_hook_enter_view_constructor(self):
    try:
        ChatActivityEnterView = self._packit_get_class("org.telegram.ui.Components.ChatActivityEnterView")
        Activity = self._packit_get_class("android.app.Activity")
        SizeNotifierFrameLayout = self._packit_get_class("org.telegram.ui.Components.SizeNotifierFrameLayout")
        ChatActivity = self._packit_get_class("org.telegram.ui.ChatActivity")
        ResourcesProvider = self._packit_get_class("org.telegram.ui.ActionBar.Theme$ResourcesProvider")
        if not all([ChatActivityEnterView, Activity, SizeNotifierFrameLayout, ChatActivity]):
            return
        constructor = ChatActivityEnterView.getClass().getDeclaredConstructor(
            Activity,
            SizeNotifierFrameLayout,
            ChatActivity,
            jclass("java.lang.Boolean").TYPE,
            ResourcesProvider
        )
        constructor.setAccessible(True)
        self.packit_hook_constructor_ref = self.hook_method(constructor, _PackitAutocompleteHook(self))
    except Exception as e:
        log(f"Packit hook constructor error: {e}")


def _packit_attach_text_watcher(self, enter_view):
    try:
        view_id = id(enter_view)
        if view_id in self.packit_attached_views:
            return
        message_edit_text = get_private_field(enter_view, "messageEditText")
        if not message_edit_text:
            return
        self.packit_current_enter_view_ref = weakref.ref(enter_view)
        TextWatcherInterface = self._packit_get_class("android.text.TextWatcher")
        plugin_ref = weakref.ref(self)
        
        class CustomTextWatcher(dynamic_proxy(TextWatcherInterface)):
            def beforeTextChanged(self, s, start, count, after):
                pass
            def onTextChanged(self, s, start, before, count):
                pass
            def afterTextChanged(self, editable):
                plugin = plugin_ref()
                if not plugin:
                    return
                try:
                    text = str(editable.toString()) if editable else ""
                    if text.startswith(".packit "):
                        search_key = text[8:].lower().strip()
                        plugin._packit_show_matching_plugins(search_key)
                    else:
                        plugin._packit_hide_popup()
                except Exception as e:
                    log(f"Packit text watcher error: {e}")
        
        watcher = CustomTextWatcher()
        message_edit_text.addTextChangedListener(watcher)
        self.packit_attached_views.add(view_id)
    except Exception as e:
        log(f"Packit attach text watcher error: {e}")


def _packit_load_plugins_from_cache(self):
    plugins_list = []
    try:
        cache_dir = _get_cache_dir()
        if not os.path.exists(cache_dir):
            return plugins_list
        
        repos = self.repoManager.getRepositories()
        for repo in repos:
            repo_id = repo.get("id")
            if not repo_id:
                continue
            
            cache_path = _get_repo_cache_path(repo_id)
            if not os.path.exists(cache_path):
                continue
            
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                
                plugins_url = cached.get("repomap", {}).get("plugins")
                if not plugins_url:
                    continue
                
                try:
                    r = requests.get(plugins_url, timeout=10)
                    if r.status_code != 200:
                        continue
                    config = r.json()
                    plugins_raw = config.get("plugins", {})
                    
                    if isinstance(plugins_raw, dict):
                        for pid, info in plugins_raw.items():
                            if isinstance(info, dict):
                                plugins_list.append({
                                    "id": pid,
                                    "repo_id": repo_id,
                                    "repo_name": repo.get("name", "Unknown"),
                                    **info
                                })
                    elif isinstance(plugins_raw, list):
                        for item in plugins_raw:
                            if isinstance(item, dict) and item.get("id"):
                                plugins_list.append({
                                    "id": item.get("id"),
                                    "repo_id": repo_id,
                                    "repo_name": repo.get("name", "Unknown"),
                                    **item
                                })
                except Exception as e:
                    log(f"Packit load plugins from url error: {e}")
            except Exception as e:
                log(f"Packit load repo cache error for {repo_id}: {e}")
    except Exception as e:
        log(f"Packit load plugins from cache error: {e}")
    
    return plugins_list


def _packit_show_matching_plugins(self, search_key):
    try:
        all_plugins = self._packit_load_plugins_from_cache()
        if not all_plugins:
            self._packit_hide_popup()
            return
        
        matching = []
        for plugin in all_plugins:
            name = plugin.get("name", "").lower()
            plugin_id = plugin.get("id", "").lower()
            if search_key:
                if search_key in name or search_key in plugin_id:
                    matching.append(plugin)
            else:
                matching.append(plugin)
        
        if not matching:
            self._packit_hide_popup()
            return
        
        self._packit_show_plugins_popup(matching[:10])
    except Exception as e:
        log(f"Packit show matching plugins error: {e}")


def _packit_show_plugins_popup(self, plugins):
    try:
        enter_view = self.packit_current_enter_view_ref() if self.packit_current_enter_view_ref else None
        if not enter_view:
            fragment = get_last_fragment()
            if fragment:
                enter_view = get_private_field(fragment, "chatActivityEnterView")
                if enter_view:
                    self.packit_current_enter_view_ref = weakref.ref(enter_view)
        if not enter_view:
            return
        
        bot_container = get_private_field(enter_view, "botCommandsMenuContainer")
        bot_adapter = get_private_field(enter_view, "botCommandsAdapter")
        
        if not bot_container:
            try:
                ChatActivityEnterView = self._packit_get_class("org.telegram.ui.Components.ChatActivityEnterView")
                create_method = ChatActivityEnterView.getClass().getDeclaredMethod("createBotCommandsMenuContainer")
                create_method.setAccessible(True)
                create_method.invoke(enter_view)
                bot_container = get_private_field(enter_view, "botCommandsMenuContainer")
                bot_adapter = get_private_field(enter_view, "botCommandsAdapter")
            except Exception as e:
                log(f"Packit create bot container error: {e}")
        
        if not bot_container or not bot_adapter:
            return
        
        commands = []
        descriptions = []
        self.packit_current_plugins = {}
        
        for plugin in plugins[:10]:
            name = plugin.get("name", "Unknown")
            description = plugin.get("description", "")
            cmd = description[:25] + "..." if len(description) > 25 else description
            desc = name[:15] + "..." if len(name) > 15 else name
            commands.append(cmd)
            descriptions.append(desc)
            self.packit_current_plugins[cmd] = plugin
        
        new_result_field = bot_adapter.getClass().getDeclaredField("newResult")
        new_result_field.setAccessible(True)
        new_result = new_result_field.get(bot_adapter)
        new_result.clear()
        for cmd in commands:
            new_result.add(cmd)
        
        new_result_help_field = bot_adapter.getClass().getDeclaredField("newResultHelp")
        new_result_help_field.setAccessible(True)
        new_result_help = new_result_help_field.get(bot_adapter)
        new_result_help.clear()
        for desc in descriptions:
            new_result_help.add(desc)
        
        bot_adapter.notifyDataSetChanged()
        
        plugin_ref = weakref.ref(self)
        
        class ClickListener(dynamic_proxy(RecyclerListView.OnItemClickListener)):
            def onItemClick(self, view, position):
                plugin = plugin_ref()
                if not plugin:
                    return
                try:
                    if hasattr(view, 'getCommand'):
                        command = view.getCommand()
                        plugin_data = plugin.packit_current_plugins.get(str(command))
                        if plugin_data:
                            plugin_id = plugin_data.get("id")
                            repo_id = plugin_data.get("repo_id")
                            
                            if plugin_id and repo_id:
                                def ui_actions():
                                    try:
                                        plugin._packit_send_plugin_info(plugin_data)
                                        bot_container.dismiss()
                                    except Exception as e:
                                        log(f"Packit click action error: {e}")
                                
                                run_on_ui_thread(ui_actions)
                except Exception as e:
                    log(f"Packit click listener error: {e}")
        
        bot_container.listView.setOnItemClickListener(ClickListener())
        
        try:
            from android.widget import LinearLayout
            parent = bot_container.listView.getParent()
            if parent and isinstance(parent, LinearLayout):
                parent.setPadding(0, 4, 0, 0)
            try:
                import android.graphics
                enter_view_rect = android.graphics.Rect()
                enter_view.getGlobalVisibleRect(enter_view_rect)
                enter_view_width = enter_view_rect.width()
                container_params = bot_container.getLayoutParams()
                if container_params:
                    container_params.width = enter_view_width
                    bot_container.setLayoutParams(container_params)
                    list_params = bot_container.listView.getLayoutParams()
                    if list_params:
                        list_params.width = enter_view_width
                        bot_container.listView.setLayoutParams(list_params)
            except Exception as e:
                log(f"Packit resize popup error: {e}")
            bot_container.requestLayout()
        except Exception as e:
            log(f"Packit popup layout error: {e}")
        
        self.packit_custom_container = bot_container
        bot_container.show()
    except Exception as e:
        log(f"Packit show plugins popup error: {e}")


def _packit_hide_popup(self):
    try:
        if self.packit_custom_container:
            self.packit_custom_container.dismiss()
    except Exception as e:
        log(f"Packit hide popup error: {e}")


def _packit_send_plugin_info(self, plugin_data):
    try:
        frag = get_last_fragment()
        if not frag:
            return
        if not isinstance(frag, ChatActivity):
            return
        
        chat_id = None
        try:
            dialog_id = frag.getDialogId()
            if dialog_id:
                chat_id = dialog_id
        except Exception:
            pass
        
        if not chat_id:
            try:
                current_chat = frag.getCurrentChat()
                if current_chat and hasattr(current_chat, 'id'):
                    chat_id = current_chat.id
            except Exception:
                pass
        
        if not chat_id:
            try:
                current_user = frag.getCurrentUser()
                if current_user and hasattr(current_user, 'id'):
                    chat_id = current_user.id
            except Exception:
                pass
        
        if not chat_id:
            try:
                current_peer = frag.getCurrentPeer()
                if current_peer and hasattr(current_peer, 'id'):
                    chat_id = current_peer.id
            except Exception:
                pass
        
        if not chat_id:
            try:
                args = frag.getArguments()
                if args:
                    dialog_id = args.getLong("dialog_id", 0)
                    if dialog_id:
                        chat_id = dialog_id
            except Exception:
                pass
        
        if not chat_id:
            log("Packit: Could not get chat_id for sending plugin info")
            return

        plugin_id = plugin_data.get("id", "unknown")
        repo_id = plugin_data.get("repo_id", "unknown")
        name = plugin_data.get("name", "Unknown Plugin")
        version = plugin_data.get("version", "")
        author = plugin_data.get("author", "")
        description = plugin_data.get("description", "")
        
        entities = []
        message_parts = []
        current_offset = 0

        plugin_link = f"tg://packit?plugin={plugin_id}&repo={repo_id}"
        name_text = name
        message_parts.append(name_text)
        
        entity_name = TLRPC.TL_messageEntityTextUrl()
        entity_name.offset = current_offset
        entity_name.length = len(name_text)
        entity_name.url = plugin_link
        entities.append(entity_name)
        
        current_offset += len(name_text)
        
        if version:
            version_text = f" (v{version})"
            message_parts.append(version_text)
            current_offset += len(version_text)
        
        message_parts.append("\n")
        current_offset += 1
        
        if author:
            by_text = "by "
            message_parts.append(by_text)
            current_offset += len(by_text)
            author_text = author
            message_parts.append(author_text)
            
            if author.startswith("@"):
                entity_author = TLRPC.TL_messageEntityTextUrl()
                entity_author.offset = current_offset
                entity_author.length = len(author_text)
                entity_author.url = f"https://t.me/{author[1:]}"
                entities.append(entity_author)
            
            current_offset += len(author_text)
            message_parts.append("\n")
            current_offset += 1

        message_parts.append("\n")
        current_offset += 1
        
        if description:
            parsed_desc = parse_markdown(description)
            desc_text = parsed_desc.text
            
            for ent in parsed_desc.entities:
                tl_entity = ent.to_tlrpc_object()
                tl_entity.offset = current_offset + ent.offset
                entities.append(tl_entity)
            
            message_parts.append(desc_text)
            current_offset += len(desc_text)
            message_parts.append("\n\n")
            current_offset += 2

        install_text = "Install"
        install_link = f"tg://packit?install&repo={repo_id}&plugin={plugin_id}"
        if version:
            install_link += f"&version={version}"
        
        message_parts.append(install_text)
        entity_install = TLRPC.TL_messageEntityTextUrl()
        entity_install.offset = current_offset
        entity_install.length = len(install_text)
        entity_install.url = install_link
        entities.append(entity_install)
        message_text = "".join(message_parts)
        
        try:
            from client_utils import send_message
            message_data = {
                "peer": chat_id,
                "message": message_text,
                "entities": entities,
                "no_webpage": True
            }
            send_message(message_data)
        except Exception:
            try:
                import time
                from org.telegram.messenger import SendMessagesHelper
                message = TLRPC.TL_message()
                message.message = message_text
                message.dialog_id = chat_id
                message.date = int(time.time())
                message.out = True
                message.flags = 2
                if entities:
                    message.entities = entities
                SendMessagesHelper.getInstance().sendMessage(message)
            except Exception as e2:
                log(f"Packit send plugin info fallback error: {e2}")
    except Exception as e:
        log(f"Packit send plugin info error: {e}")


def setup_packit_autocomplete(plugin):
    try:
        plugin._packit_class_cache = {}
        plugin.packit_hook_constructor_ref = None
        plugin.packit_current_enter_view_ref = None
        plugin.packit_attached_views = set()
        plugin.packit_custom_container = None
        plugin.packit_current_plugins = {}
        
        plugin._packit_hook_enter_view_constructor()
        log("Packit autocomplete setup complete")
    except Exception as e:
        log(f"Packit autocomplete setup error: {e}")
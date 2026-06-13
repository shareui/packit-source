# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os
import json
import weakref
import requests
from base_plugin import MethodHook
from client_utils import get_last_fragment, run_on_queue
from hook_utils import find_class, get_private_field
from android_utils import run_on_ui_thread
from java import dynamic_proxy, jclass
from org.telegram.ui import ChatActivity
from markdown_utils import parse_markdown
from org.telegram.tgnet import TLRPC
from org.telegram.ui.Components import RecyclerListView

def _parse_filter_flags(raw):
    # parses "filter:tags=\"a\",\"b\";author=\"@x\";app_version=\">=1.0\" output:type=\"update\""
    # returns (query_str, flags_dict, output_type_str)
    # flags_dict keys: "tags" -> list[str], "author" -> list[str], "app_version" -> list[str]
    # output_type_str: "update" | "release" | None

    # extract output:type="..." first (anywhere in string)
    output_type = None
    output_prefix = "output:type="
    out_idx = raw.lower().find(output_prefix)
    if out_idx != -1:
        val_start = raw.find('"', out_idx + len(output_prefix))
        if val_start != -1:
            val_end = raw.find('"', val_start + 1)
            if val_end != -1:
                output_type = raw[val_start + 1:val_end].strip().lower()
        # remove the output:... token from raw so it doesn't pollute query/filter
        token_end = val_end + 1 if (out_idx != -1 and val_end != -1) else out_idx + len(output_prefix)
        raw = (raw[:out_idx] + raw[token_end:]).strip()

    filter_prefix = "filter:"
    idx = raw.find(filter_prefix)
    if idx == -1:
        return raw.strip(), {}, output_type

    query = raw[:idx].strip()
    filter_part = raw[idx + len(filter_prefix):]

    flags = {}
    # split by ; to get individual key=value(s) pairs
    for segment in filter_part.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        eq = segment.find("=")
        if eq == -1:
            continue
        key = segment[:eq].strip().lower()
        values_raw = segment[eq + 1:]
        # extract all quoted values: "val1","val2",...
        values = []
        i = 0
        while i < len(values_raw):
            if values_raw[i] == '"':
                end = values_raw.find('"', i + 1)
                if end == -1:
                    break
                values.append(values_raw[i + 1:end].strip())
                i = end + 1
            else:
                i += 1
        if values:
            flags[key] = values
    return query, flags, output_type


def _apply_filter_flags(plugins, flags):
    if not flags:
        return plugins

    result = []
    for plugin in plugins:
        if not _flag_match(plugin, flags):
            continue
        result.append(plugin)
    return result


def _flag_match(plugin, flags):
    # tags: plugin must have at least one matching tag (case-insensitive)
    if "tags" in flags:
        required = {t.lower() for t in flags["tags"]}
        plugin_tags = plugin.get("tags", [])
        plugin_tag_names = set()
        if isinstance(plugin_tags, list):
            for tag_info in plugin_tags:
                if isinstance(tag_info, list) and tag_info:
                    plugin_tag_names.add(str(tag_info[0]).lower())
                elif isinstance(tag_info, str):
                    plugin_tag_names.add(tag_info.lower())
        if not required & plugin_tag_names:
            return False

    # author: plugin author must match one of the listed (case-insensitive)
    if "author" in flags:
        required = {a.lower().lstrip("@") for a in flags["author"]}
        plugin_author = str(plugin.get("author", "")).lower().lstrip("@")
        if plugin_author not in required:
            return False

    # app_version: each expression must pass check_app_version
    if "app_version" in flags:
        from ..utils.app_version import check_app_version
        for expr in flags["app_version"]:
            if not check_app_version(expr):
                return False

    return True


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
            from . import inlineState
            if not inlineState.get_state():
                return
            plugin = self.plugin
            if not plugin:
                return
            enter_view = param.thisObject
            def attach_watcher():
                plugin._packit_attach_text_watcher(enter_view)
            run_on_ui_thread(attach_watcher, delay=500)
        except Exception as e:
            logx(f"PackitAutocompleteHook error: {e}", False)

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
        logx(f"Packit hook constructor error: {e}", False)

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
                try:
                    from . import inlineState
                    if not inlineState.get_state():
                        return
                except Exception:
                    pass
                plugin = plugin_ref()
                if not plugin:
                    return
                try:
                    text = str(editable.toString()) if editable else ""

                    # double space trigger: field contains exactly two spaces
                    try:
                        from elyx import settings as _s
                        ds_enabled = _s.get("inline_search_double_space", False)
                        if ds_enabled:
                            if text == "  ":
                                cmd = _s.get("inline_search_command", ".packit").strip() or ".packit"
                                logx(f"packit_autocomplete: double space triggered, replacing with {cmd}", True)
                                editable.replace(0, editable.length(), cmd + " ")
                                return
                    except Exception as e:
                        logx(f"packit_autocomplete: double_space error: {e}", False)

                    try:
                        from elyx import settings as _s
                        cmd = _s.get("inline_search_command", ".packit").strip() or ".packit"
                    except Exception:
                        cmd = ".packit"
                    # normalize "{cmd[0]} {cmd[1:]}" typo (space after first char) → cmd
                    if len(cmd) > 1:
                        spaced_prefix = cmd[0] + " " + cmd[1:]
                        if text.startswith(spaced_prefix):
                            text = cmd + text[len(spaced_prefix):]
                    prefix = cmd + " "
                    if text.startswith(prefix):
                        search_key = text[len(prefix):]
                        token = object()
                        plugin._packit_search_token = token
                        plugin._packit_show_loading_popup()
                        def do_search():
                            plugin._packit_search_in_background(search_key, token)
                        run_on_queue(do_search)
                    else:
                        plugin._packit_search_token = None
                        plugin._packit_hide_popup()
                except Exception as e:
                    logx(f"Packit text watcher error: {e}", False)
        
        watcher = CustomTextWatcher()
        message_edit_text.addTextChangedListener(watcher)
        self.packit_attached_views.add(view_id)
    except Exception as e:
        logx(f"Packit attach text watcher error: {e}", False)


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
                    logx(f"Packit load plugins from url error: {e}", False)
            except Exception as e:
                logx(f"Packit load repo cache error for {repo_id}: {e}", False)
    except Exception as e:
        logx(f"Packit load plugins from cache error: {e}", False)
    
    return plugins_list


def _packit_show_loading_popup(self):
    try:
        # shows a single "Loading..." row so the user sees feedback immediately
        loading_placeholder = [{"name": "Loading...", "description": "", "_loading": True}]
        run_on_ui_thread(lambda: self._packit_show_plugins_popup(loading_placeholder))
    except Exception as e:
        logx(f"Packit show loading popup error: {e}", False)


def _packit_search_in_background(self, search_key, token):
    try:
        query, flags, output_type = _parse_filter_flags(search_key)
        query = query.lower().strip()
        self._packit_output_type = output_type

        all_plugins = self._packit_load_plugins_from_cache()

        if self._packit_search_token is not token:
            return

        if not all_plugins:
            run_on_ui_thread(lambda: self._packit_hide_popup())
            return

        candidates = _apply_filter_flags(all_plugins, flags)

        if not query:
            result = candidates[:10]
            run_on_ui_thread(lambda: self._packit_show_plugins_popup(result))
            return

        from ..ui.PluginListActivity.service.SearchEngine import build_index, score as search_score

        index = build_index(candidates)

        isRussian = False
        try:
            from java.util import Locale
            isRussian = Locale.getDefault().getLanguage() == "ru"
        except Exception:
            pass

        fuzzy = False
        try:
            from elyx import settings as _s
            fuzzy = _s.get("fuzzy_search", False)
        except Exception:
            pass

        scored = []
        for plugin in candidates:
            s = search_score(plugin, query, index, isRussian, fuzzy=fuzzy)
            if s[0] < 6:
                scored.append((s, plugin))
        scored.sort(key=lambda x: x[0])

        if self._packit_search_token is not token:
            return

        if not scored:
            not_found = [{"name": "Plugin not found :(", "description": "", "_loading": True}]
            run_on_ui_thread(lambda: self._packit_show_plugins_popup(not_found))
            return

        result = [p for _, p in scored[:10]]
        run_on_ui_thread(lambda: self._packit_show_plugins_popup(result))
    except Exception as e:
        logx(f"Packit search in background error: {e}", False)


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
        logx(f"Packit show matching plugins error: {e}", False)


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
                logx(f"Packit create bot container error: {e}", False)
        
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
        # ordered list for index-based lookup (long click uses position)
        plugins_by_index = list(plugins[:10])

        class ClickListener(dynamic_proxy(RecyclerListView.OnItemClickListener)):
            def onItemClick(self, view, position):
                plugin = plugin_ref()
                if not plugin:
                    return
                try:
                    if hasattr(view, 'getCommand'):
                        command = view.getCommand()
                        plugin_data = plugin.packit_current_plugins.get(str(command))
                        if plugin_data and not plugin_data.get("_loading"):
                            plugin_id = plugin_data.get("id")
                            repo_id = plugin_data.get("repo_id")

                            if plugin_id and repo_id:
                                def ui_actions():
                                    try:
                                        plugin._packit_pending_clear_reply = False
                                        plugin._packit_send_plugin_info(plugin_data)
                                        bot_container.dismiss()
                                        ev = enter_view
                                        msg_field = get_private_field(ev, "messageEditText")
                                        if msg_field:
                                            clear_field = False
                                            cmd = ".packit"
                                            try:
                                                from elyx import settings as _s
                                                clear_field = _s.get("inline_search_clear_field", False)
                                                cmd = _s.get("inline_search_command", ".packit").strip() or ".packit"
                                            except Exception:
                                                pass
                                            new_text = "" if clear_field else cmd + " "
                                            msg_field.setText(new_text)
                                            msg_field.setSelection(msg_field.getText().length())
                                        if getattr(plugin, "_packit_pending_clear_reply", False):
                                            plugin._packit_pending_clear_reply = False
                                            frag_ref = get_last_fragment()
                                            def do_clear_reply():
                                                try:
                                                    if frag_ref and hasattr(frag_ref, "showFieldPanel"):
                                                        frag_ref.showFieldPanel(False, None, None, None, None, True, 0, None, True, 0, True)
                                                    else:
                                                        logx("Packit: clear_reply - fragment or showFieldPanel not found", True)
                                                except Exception as e:
                                                    logx(f"Packit: clear reply error: {e}", False)
                                            run_on_ui_thread(do_clear_reply, 100)
                                    except Exception as e:
                                        logx(f"Packit click action error: {e}", False)

                                run_on_ui_thread(ui_actions)
                except Exception as e:
                    logx(f"Packit click listener error: {e}", False)

        class LongClickListener(dynamic_proxy(RecyclerListView.OnItemLongClickListener)):
            def onItemClick(self, view, position):
                plugin = plugin_ref()
                if not plugin:
                    return True
                try:
                    if position < 0 or position >= len(plugins_by_index):
                        return True
                    plugin_data = plugins_by_index[position]
                    if plugin_data.get("_loading"):
                        return True
                    repo_id = plugin_data.get("repo_id", "")

                    def open_profile():
                        try:
                            from ..ui.PluginListActivity.fragment import InstallUI
                            from ..ui.PluginActivity.fragment import show_plugin_profile

                            class _FakePlugin:
                                def __init__(self, rm):
                                    self.repoManager = rm

                            install_ui = InstallUI(_FakePlugin(plugin.repoManager))
                            bot_container.dismiss()
                            show_plugin_profile(plugin_data, install_ui, plugins_by_index, repo_id=repo_id)
                        except Exception as e:
                            logx(f"Packit long click open profile error: {e}", False)

                    run_on_ui_thread(open_profile)
                except Exception as e:
                    logx(f"Packit long click listener error: {e}", False)
                return True

        bot_container.listView.setOnItemClickListener(ClickListener())
        bot_container.listView.setOnItemLongClickListener(LongClickListener())
        
        try:
            from android.widget import LinearLayout
            parent = bot_container.listView.getParent()
            if parent and isinstance(parent, LinearLayout):
                parent.setPadding(0, 4, 0, 0)
            try:
                enter_view_width = enter_view.getWidth()
                if enter_view_width > 0:
                    container_params = bot_container.getLayoutParams()
                    if container_params:
                        container_params.width = enter_view_width
                        bot_container.setLayoutParams(container_params)
                        list_params = bot_container.listView.getLayoutParams()
                        if list_params:
                            list_params.width = enter_view_width
                            bot_container.listView.setLayoutParams(list_params)
            except Exception as e:
                logx(f"Packit resize popup error: {e}", False)
            bot_container.requestLayout()
        except Exception as e:
            logx(f"Packit popup layout error: {e}", False)
        
        self.packit_custom_container = bot_container
        self._packit_hook_container_dismiss(bot_container)
        bot_container.show()
    except Exception as e:
        logx(f"Packit show plugins popup error: {e}", False)


def _packit_hook_container_dismiss(self, bot_container):
    # TG calls dismiss() unconditionally in afterTextChanged — block it while our search is active.
    # hook is idempotent: skip if already hooked this container instance.
    try:
        container_id = id(bot_container)
        if container_id in self._packit_hooked_containers:
            return
        self._packit_hooked_containers.add(container_id)

        plugin_ref = weakref.ref(self)
        # dismiss is declared in BotCommandsMenuContainer, not the anonymous subclass
        dismiss_method = None
        klass = bot_container.getClass()
        while klass is not None:
            try:
                dismiss_method = klass.getDeclaredMethod("dismiss")
                break
            except Exception:
                klass = klass.getSuperclass()
        if dismiss_method is None:
            logx("Packit hook container dismiss error: dismiss method not found", True)
            return
        dismiss_method.setAccessible(True)

        class DismissHook(MethodHook):
            def before_hooked_method(self_hook, param):
                try:
                    from . import inlineState
                    if not inlineState.get_state():
                        return
                except Exception:
                    pass
                plugin = plugin_ref()
                if plugin is None:
                    return
                # allow dismiss when packit search is not active
                if plugin._packit_search_token is None:
                    return
                # block TG dismiss — packit controls visibility
                param.setResult(None)

        self.hook_method(dismiss_method, DismissHook())
    except Exception as e:
        logx(f"Packit hook container dismiss error: {e}", False)


def _packit_hide_popup(self):
    try:
        if self.packit_custom_container:
            # clear token first so the dismiss hook lets it through
            self._packit_search_token = None
            self.packit_custom_container.dismiss()
    except Exception as e:
        logx(f"Packit hide popup error: {e}", False)


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
            logx("Packit: Could not get chat_id for sending plugin info", True)
            return

        # resolve forum topic if the chat is a forum
        topic_msg_obj = None
        try:
            if frag.isTopic:
                topic_id = frag.getTopicId()
                if topic_id:
                    from org.telegram.messenger import MessageObject as MsgObj
                    mc = frag.getMessagesController()
                    topic = mc.getTopicsController().findTopic(-chat_id, topic_id)
                    if topic is not None and topic.topicStartMessage is not None:
                        topic_msg_obj = MsgObj(frag.getCurrentAccount(), topic.topicStartMessage, False, False)
                        topic_msg_obj.isTopicMainMessage = True
        except Exception as e:
            logx(f"Packit: topic resolve error: {e}", False)

        # get reply-to message if user is replying to something
        reply_msg_obj = None
        try:
            enter_view = self.packit_current_enter_view_ref() if self.packit_current_enter_view_ref else None
            if not enter_view:
                enter_view = get_private_field(frag, "chatActivityEnterView")
            if enter_view:
                candidate = get_private_field(enter_view, "replyingMessageObject")
                if candidate is not None and not getattr(candidate, "isTopicMainMessage", False):
                    reply_msg_obj = candidate
        except Exception as e:
            logx(f"Packit: reply resolve error: {e}", False)

        plugin_id = plugin_data.get("id", "unknown")
        repo_id = plugin_data.get("repo_id", "unknown")
        name = plugin_data.get("name", "Unknown Plugin")
        version = plugin_data.get("version", "")
        author = plugin_data.get("author", "")
        description = plugin_data.get("description", "")

        try:
            from elyx import settings as _s
            show_version = _s.get("inline_send_version", True)
            show_author = _s.get("inline_send_author", True)
            show_description = _s.get("inline_send_description", True)
            show_install = _s.get("inline_send_install", True)
        except Exception:
            show_version = show_author = show_description = show_install = True

        entities = []
        message_parts = []
        current_offset = 0

        output_type = getattr(self, "_packit_output_type", None)
        plugin_link = f"tg://packit?plugin={plugin_id}&repo={repo_id}"

        if output_type == "release":
            # "{name} has been released" — name is a link+bold, rest is plain
            name_text = name
            message_parts.append(name_text)
            entity_name = TLRPC.TL_messageEntityTextUrl()
            entity_name.offset = current_offset
            entity_name.length = len(name_text)
            entity_name.url = plugin_link
            entities.append(entity_name)
            entity_name_bold = TLRPC.TL_messageEntityBold()
            entity_name_bold.offset = current_offset
            entity_name_bold.length = len(name_text)
            entities.append(entity_name_bold)
            current_offset += len(name_text)
            suffix = " has been released!"
            message_parts.append(suffix)
            current_offset += len(suffix)

        elif output_type == "update":
            # "{name} updated to {version}" — name is link+bold, "updated to" is bold, version is plain
            name_text = name
            message_parts.append(name_text)
            entity_name = TLRPC.TL_messageEntityTextUrl()
            entity_name.offset = current_offset
            entity_name.length = len(name_text)
            entity_name.url = plugin_link
            entities.append(entity_name)
            entity_name_bold = TLRPC.TL_messageEntityBold()
            entity_name_bold.offset = current_offset
            entity_name_bold.length = len(name_text)
            entities.append(entity_name_bold)
            current_offset += len(name_text)
            updated_text = " updated to "
            message_parts.append(updated_text)
            entity_upd = TLRPC.TL_messageEntityBold()
            entity_upd.offset = current_offset
            entity_upd.length = len(updated_text)
            entities.append(entity_upd)
            current_offset += len(updated_text)
            ver_text = version if version else "?"
            message_parts.append(ver_text)
            current_offset += len(ver_text)

        else:
            # default: "{name} (v{version})"
            name_text = name
            message_parts.append(name_text)
            entity_name = TLRPC.TL_messageEntityTextUrl()
            entity_name.offset = current_offset
            entity_name.length = len(name_text)
            entity_name.url = plugin_link
            entities.append(entity_name)
            entity_name_bold = TLRPC.TL_messageEntityBold()
            entity_name_bold.offset = current_offset
            entity_name_bold.length = len(name_text)
            entities.append(entity_name_bold)
            current_offset += len(name_text)
            if show_version and version:
                version_text = f" (v{version})"
                message_parts.append(version_text)
                current_offset += len(version_text)

        message_parts.append("\n")
        current_offset += 1

        if show_author and author:
            by_text = "by "
            message_parts.append(by_text)
            current_offset += len(by_text)
            author_text = author
            message_parts.append(author_text)
            current_offset += len(author_text)
            message_parts.append("\n")
            current_offset += 1

        desc_quote_start = current_offset

        if show_description and description:
            parsed_desc = parse_markdown(description)
            desc_text = parsed_desc.text

            for ent in parsed_desc.entities:
                tl_entity = ent.to_tlrpc_object()
                tl_entity.offset = current_offset + ent.offset
                entities.append(tl_entity)

            message_parts.append(desc_text)
            current_offset += len(desc_text)
            message_parts.append("\n")
            current_offset += 1

            entity_blockquote = TLRPC.TL_messageEntityBlockquote()
            entity_blockquote.offset = desc_quote_start
            entity_blockquote.length = current_offset - desc_quote_start
            entities.append(entity_blockquote)

        if show_install:
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
            current_offset += len(install_text)

            via_sep = " via "
            message_parts.append(via_sep)
            current_offset += len(via_sep)

            packit_text = "PackIt"
            message_parts.append(packit_text)
            entity_via = TLRPC.TL_messageEntityTextUrl()
            entity_via.offset = current_offset
            entity_via.length = len(packit_text)
            entity_via.url = "https://t.me/packitX"
            entities.append(entity_via)

        message_text = "".join(message_parts)
        
        try:
            from client_utils import send_message
            message_data = {
                "peer": chat_id,
                "message": message_text,
                "entities": entities,
                "searchLinks": False,
                "params": {
                    "packit_inline": "1",
                    "packit_desc": description,
                    "packit_name": name,
                    "packit_version": version,
                    "packit_author": author,
                    "packit_plugin_id": plugin_id,
                    "packit_repo_id": repo_id,
                    "packit_output_type": output_type or "",
                    "packit_show_version": "1" if show_version else "0",
                    "packit_show_author": "1" if show_author else "0",
                    "packit_show_description": "1" if show_description else "0",
                    "packit_show_install": "1" if show_install else "0",
                },
            }
            if reply_msg_obj is not None:
                message_data["replyToMsg"] = reply_msg_obj
            elif topic_msg_obj is not None:
                message_data["replyToMsg"] = topic_msg_obj
                message_data["replyToTopMsg"] = topic_msg_obj
            send_message(message_data)
            if reply_msg_obj is not None:
                self._packit_pending_clear_reply = True
        except Exception:
            try:
                from org.telegram.messenger import SendMessagesHelper as SMH
                smh = SMH.getInstance(frag.getCurrentAccount())
                params = SMH.SendMessageParams.of(message_text, chat_id)
                params.entities = entities
                params.searchLinks = False
                if reply_msg_obj is not None:
                    params.replyToMsg = reply_msg_obj
                elif topic_msg_obj is not None:
                    params.replyToMsg = topic_msg_obj
                    params.replyToTopMsg = topic_msg_obj
                smh.sendMessage(params)
            except Exception as e2:
                logx(f"Packit send plugin info fallback error: {e2}", True)
    except Exception as e:
        logx(f"Packit send plugin info error: {e}", False)


def setup_packit_autocomplete(plugin):
    try:
        plugin._packit_class_cache = {}
        plugin.packit_hook_constructor_ref = None
        plugin.packit_current_enter_view_ref = None
        plugin.packit_attached_views = set()
        plugin.packit_custom_container = None
        plugin.packit_current_plugins = {}
        plugin._packit_search_token = None
        plugin._packit_output_type = None
        plugin._packit_pending_clear_reply = False
        plugin._packit_hooked_containers = set()
        
        plugin._packit_hook_enter_view_constructor()
        logx("Packit autocomplete setup complete", True)
    except Exception as e:
        logx(f"Packit autocomplete setup error: {e}", False)
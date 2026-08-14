# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from android_utils import run_on_ui_thread
from base_plugin import MethodHook
from hook_utils import find_class
from java import jclass
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")

_Integer = jclass("java.lang.Integer")

# unique id for packit install button in main menu
_PACKIT_MENU_ID = 880035


def _safe_find_class(class_name: str):
    try:
        from org.telegram.messenger import ApplicationLoader
        context = ApplicationLoader.applicationContext
        if context is not None:
            loader = context.getClassLoader()
            if loader is not None:
                loader.loadClass(class_name)
                return find_class(class_name)
    except Exception:
        pass
    return None


def _get_extera_config():
    try:
        return _safe_find_class("com.exteragram.messenger.ExteraConfig")
    except Exception:
        return None


_MENU_STATE_KEY = "dialogs_install_btn_enabled"


def _is_btn_enabled():
    try:
        from elyx import settings
        return settings.get(_MENU_STATE_KEY, True)
    except Exception:
        return True


def _set_btn_enabled(val):
    try:
        from elyx import settings
        settings.set(_MENU_STATE_KEY, bool(val))
    except Exception as e:
        logx(f"ChatDialogButton: _set_btn_enabled error: {e}", False)


def _register_menu_id():
    # sanitize removes our id every launch (unknown to MainMenuItem enum),
    # so we always re-add it to the correct list based on persisted state.
    # works for both drawer and dots mode — layout/hidden lists are shared.
    try:
        cfg = _get_extera_config()
        if cfg is None:
            logx("ChatDialogButton: ExteraConfig not found", True)
            return False
        layout = cfg.mainMenuLayout
        hidden = cfg.mainMenuHiddenItems
        if layout is None or hidden is None:
            logx("ChatDialogButton: mainMenuLayout/mainMenuHiddenItems not found", True)
            return False
        id_obj = _Integer(_PACKIT_MENU_ID)
        enabled = _is_btn_enabled()
        layout.remove(id_obj)
        hidden.remove(id_obj)
        if enabled:
            layout.add(id_obj)
        else:
            hidden.add(0, id_obj)
        try:
            cfg.saveMainMenuLayout()
        except Exception as e:
            logx(f"ChatDialogButton: saveMainMenuLayout error: {e}", False)
        return True
    except Exception as e:
        logx(f"ChatDialogButton: _register_menu_id error: {e}", False)
        return False


def _get_mode_icon_id(mode):
    _icon_names = ["msg_plugins", "msg_addbot", "input_smile"]
    name = _icon_names[mode] if 0 <= mode < len(_icon_names) else "msg_addbot"
    try:
        R = find_class("org.telegram.messenger.R")
        return int(getattr(R.drawable, name))
    except Exception:
        return 0


def _get_mode_label(mode):
    _label_keys = ["dialogs_menu_packit_settings", "install_plugin_btn", "dialogs_menu_install_icon"]
    key = _label_keys[mode] if 0 <= mode < len(_label_keys) else "install_plugin_btn"
    return strings[key]


def _get_current_mode():
    try:
        from elyx import settings as _s
        return _s.get("dialogs_menu_button", 0)
    except Exception:
        return 1


class ChatDialogButton:
    def setup_dialogs_menu_hook(self):
        try:
            _register_menu_id()
            self._setup_sanitize_hook()
            self._setup_main_menu_prefs_hooks()

            # install both resolvers regardless of the current navigation mode:
            # the dots overflow (DialogsActivity/MainTabs) and the drawer use
            # different MainMenuHelper methods, so hooking both makes the PackIt
            # entry appear in whichever surface the user opens, with no restart
            # needed after switching modes.
            self._setup_dots_hook()
            self._setup_drawer_hook()

            logx("ChatDialogButton: hooks set up", True)
        except Exception as e:
            logx(f"ChatDialogButton: setup_dialogs_menu_hook error: {e}", False)

    def _build_menu_runnable(self, menu_context):
        # onClick shared by the dots and drawer menu entries; opens the PackIt
        # UI selected by the current mode. menu_context.fragment() gives the
        # active fragment to present from.
        plugin = self.plugin
        _Runnable = jclass("java.lang.Runnable")
        from java import dynamic_proxy

        class _OnClick(dynamic_proxy(_Runnable)):
            def __init__(self):
                super().__init__()

            def run(self):
                try:
                    m = _get_current_mode()
                    if m == 0:
                        def _open():
                            try:
                                from com.exteragram.messenger.plugins import PluginsController
                                from com.exteragram.messenger.plugins.ui import PluginSettingsActivity
                                from client_utils import get_last_fragment
                                frag = get_last_fragment()
                                pluginObj = PluginsController.getInstance().plugins.get(plugin.id)
                                if pluginObj and frag:
                                    frag.presentFragment(PluginSettingsActivity(pluginObj))
                            except Exception as e:
                                logx(f"ChatDialogButton: open settings error: {e}", False)
                        run_on_ui_thread(_open)
                    elif m == 2:
                        from ..ui.iconslistactivity.Fragment import InstallIconsUI
                        run_on_ui_thread(lambda: InstallIconsUI(plugin).open())
                    else:
                        from ..ui.pluginlistactivity.Fragment import InstallUI
                        run_on_ui_thread(lambda: InstallUI(plugin).open())
                except Exception as e:
                    logx(f"ChatDialogButton: onClick error: {e}", False)

        return _OnClick()

    def _setup_dots_hook(self):
        # dots menu (dialogs "3 dots") is built by
        # MainMenuHelper.addConfiguredItemOption(ItemOptions, MenuContext, int);
        # for our custom id MainMenuItem.getById returns null, so hook it and
        # add our entry ourselves.
        try:
            MainMenuHelper = _safe_find_class("com.exteragram.messenger.utils.chats.MainMenuHelper")
            if MainMenuHelper is None:
                logx("ChatDialogButton: MainMenuHelper not found", True)
                return None

            add_option_method = None
            for m in MainMenuHelper.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "addConfiguredItemOption" and len(m.getParameterTypes()) == 3:
                        add_option_method = m
                        break
                except Exception:
                    continue

            if add_option_method is None:
                logx("ChatDialogButton: addConfiguredItemOption not found", True)
                return None

            add_option_method.setAccessible(True)
            builder = self._build_menu_runnable

            class AddConfiguredItemHook(MethodHook):
                def before_hooked_method(self_hook, param):
                    try:
                        if int(param.args[2]) != _PACKIT_MENU_ID:
                            return
                        item_options = param.args[0]
                        menu_context = param.args[1]
                        if item_options is None:
                            return
                        mode = _get_current_mode()
                        icon_id = _get_mode_icon_id(mode)
                        label = _get_mode_label(mode)
                        _String = jclass("java.lang.String")
                        item_options.add(icon_id, _String(label), builder(menu_context))
                        param.setResult(True)
                    except Exception as e:
                        logx(f"ChatDialogButton: addConfiguredItemOption hook error: {e}", False)

            return self.plugin.hook_method(add_option_method, AddConfiguredItemHook())
        except Exception as e:
            logx(f"ChatDialogButton: _setup_dots_hook error: {e}", False)
            return None

    def _setup_drawer_hook(self):
        # drawer (side menu) is built by
        # MainMenuHelper.resolveDrawerMenuItems(int, MenuContext); same story —
        # return a single MenuItemInfo for our id.
        try:
            MainMenuHelper = _safe_find_class("com.exteragram.messenger.utils.chats.MainMenuHelper")
            if MainMenuHelper is None:
                logx("ChatDialogButton: MainMenuHelper not found", True)
                return None

            resolve_method = None
            for m in MainMenuHelper.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "resolveDrawerMenuItems" and len(m.getParameterTypes()) == 2:
                        resolve_method = m
                        break
                except Exception:
                    continue

            if resolve_method is None:
                logx("ChatDialogButton: resolveDrawerMenuItems not found", True)
                return None

            resolve_method.setAccessible(True)

            MenuItemInfoCls = _safe_find_class(
                "com.exteragram.messenger.utils.chats.MainMenuHelper$MenuItemInfo"
            )
            if MenuItemInfoCls is None:
                logx("ChatDialogButton: MenuItemInfo not found", True)
                return None
            _CharSequence = jclass("java.lang.CharSequence")
            _Runnable = jclass("java.lang.Runnable")
            info_ctor = MenuItemInfoCls.getClass().getDeclaredConstructor(
                _Integer.TYPE, _CharSequence, _Runnable, _Runnable
            )
            info_ctor.setAccessible(True)
            Collections = jclass("java.util.Collections")
            builder = self._build_menu_runnable

            class ResolveDrawerHook(MethodHook):
                def before_hooked_method(self_hook, param):
                    try:
                        if int(param.args[0]) != _PACKIT_MENU_ID:
                            return
                        menu_context = param.args[1]
                        mode = _get_current_mode()
                        icon_id = _get_mode_icon_id(mode)
                        label = _get_mode_label(mode)
                        _String = jclass("java.lang.String")
                        info = info_ctor.newInstance(
                            _Integer(icon_id), _String(label), builder(menu_context), None
                        )
                        param.setResult(Collections.singletonList(info))
                    except Exception as e:
                        logx(f"ChatDialogButton: resolveDrawerMenuItems hook error: {e}", False)

            return self.plugin.hook_method(resolve_method, ResolveDrawerHook())
        except Exception as e:
            logx(f"ChatDialogButton: _setup_drawer_hook error: {e}", False)
            return None

    def _setup_sanitize_hook(self):
        try:
            cfg_class = _safe_find_class("com.exteragram.messenger.ExteraConfig")
            if cfg_class is None:
                return None

            sanitize_method = None
            for m in cfg_class.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "sanitizeMenu" and len(m.getParameterTypes()) == 0:
                        sanitize_method = m
                        break
                except Exception:
                    continue

            if sanitize_method is None:
                return None

            sanitize_method.setAccessible(True)

            class SanitizeMenuHook(MethodHook):
                def after_hooked_method(self_hook, param):
                    try:
                        _register_menu_id()
                    except Exception as e:
                        logx(f"ChatDialogButton: sanitize after hook error: {e}", False)

            return self.plugin.hook_method(sanitize_method, SanitizeMenuHook())
        except Exception as e:
            logx(f"ChatDialogButton: _setup_sanitize_hook error: {e}", False)
            return None

    def _setup_main_menu_prefs_hooks(self):
        # hooks for AppNavigationPreferencesActivity so our item renders in the
        # "Main menu" settings screen (initItemDetails, createMenuItem, onClick)
        try:
            activity_cls = _safe_find_class(
                "com.exteragram.messenger.preferences.appearance.AppNavigationPreferencesActivity"
            )
            if activity_cls is None:
                logx("ChatDialogButton: MainMenuPreferencesActivity not found", True)
                return

            item_info_cls = _safe_find_class(
                "com.exteragram.messenger.preferences.appearance.AppNavigationPreferencesActivity$ItemInfo"
            )
            if item_info_cls is None:
                logx("ChatDialogButton: ItemInfo class not found", True)
                return

            java_cls = activity_cls.getClass()
            item_info_java_cls = item_info_cls.getClass()

            item_details_field = java_cls.getDeclaredField("itemDetails")
            item_details_field.setAccessible(True)

            reorder_icon_field = java_cls.getDeclaredField("reorderIcon")
            reorder_icon_field.setAccessible(True)

            icon_res_field = item_info_java_cls.getDeclaredField("iconRes")
            icon_res_field.setAccessible(True)

            name_field = item_info_java_cls.getDeclaredField("name")
            name_field.setAccessible(True)

            _CharSequence = jclass("java.lang.CharSequence")
            item_info_ctor = item_info_java_cls.getDeclaredConstructor(
                _CharSequence, _Integer.TYPE
            )
            item_info_ctor.setAccessible(True)

            _String = jclass("java.lang.String")

            class InitItemDetailsHook(MethodHook):
                def after_hooked_method(self_hook, param):
                    try:
                        item_details = item_details_field.get(param.thisObject)
                        if item_details is None:
                            return
                        mode = _get_current_mode()
                        label = _String(_get_mode_label(mode))
                        info_obj = item_info_ctor.newInstance(label, _Integer(_get_mode_icon_id(mode)))
                        item_details.put(_Integer(_PACKIT_MENU_ID), info_obj)
                    except Exception as e:
                        logx(f"ChatDialogButton: initItemDetails hook error: {e}", False)

            init_method = java_cls.getDeclaredMethod("initItemDetails")
            init_method.setAccessible(True)
            self.plugin.hook_method(init_method, InitItemDetailsHook())

            UItem = jclass("org.telegram.ui.Components.UItem")
            create_method = None
            for m in java_cls.getDeclaredMethods():
                try:
                    if m.getName() == "createMenuItem" and len(m.getParameterTypes()) == 2:
                        create_method = m
                        break
                except Exception:
                    continue

            if create_method is not None:
                create_method.setAccessible(True)

                class CreateMenuItemHook(MethodHook):
                    def before_hooked_method(self_hook, param):
                        try:
                            item_id = int(param.args[0])
                            if item_id != _PACKIT_MENU_ID:
                                return
                            info = param.args[1]
                            icon = icon_res_field.getInt(info)
                            name = name_field.get(info)
                            uitem = UItem.asButton(item_id, icon, name)
                            uitem.object2 = reorder_icon_field.get(param.thisObject)
                            param.setResult(uitem)
                        except Exception as e:
                            logx(f"ChatDialogButton: createMenuItem hook error: {e}", False)

                self.plugin.hook_method(create_method, CreateMenuItemHook())

            NotificationCenter = jclass("org.telegram.messenger.NotificationCenter")
            base_activity_cls = _safe_find_class(
                "com.exteragram.messenger.preferences.BasePreferencesActivity"
            )
            list_view_field = None
            update_reset_method = None
            try:
                list_view_field = base_activity_cls.getClass().getDeclaredField("listView")
                list_view_field.setAccessible(True)
                update_reset_method = java_cls.getDeclaredMethod("updateResetButtonVisibility")
                update_reset_method.setAccessible(True)
            except Exception:
                pass

            on_click_method = None
            for m in java_cls.getDeclaredMethods():
                try:
                    if m.getName() == "onClick" and len(m.getParameterTypes()) == 5:
                        on_click_method = m
                        break
                except Exception:
                    continue

            if on_click_method is not None:
                on_click_method.setAccessible(True)

                class OnClickHook(MethodHook):
                    def before_hooked_method(self_hook, param):
                        try:
                            uitem = param.args[0]
                            if int(uitem.id) != _PACKIT_MENU_ID:
                                return
                            cfg = _get_extera_config()
                            id_obj = _Integer(_PACKIT_MENU_ID)
                            if cfg.mainMenuLayout.contains(id_obj):
                                cfg.mainMenuLayout.remove(id_obj)
                                if not cfg.mainMenuHiddenItems.contains(id_obj):
                                    cfg.mainMenuHiddenItems.add(0, id_obj)
                                _set_btn_enabled(False)
                            elif cfg.mainMenuHiddenItems.contains(id_obj):
                                cfg.mainMenuHiddenItems.remove(id_obj)
                                cfg.mainMenuLayout.add(id_obj)
                                _set_btn_enabled(True)
                            cfg.saveMainMenuLayout()
                            NotificationCenter.getGlobalInstance().postNotificationName(
                                NotificationCenter.mainUserInfoChanged
                            )
                            try:
                                if list_view_field is not None:
                                    lv = list_view_field.get(param.thisObject)
                                    if lv is not None and lv.adapter is not None:
                                        lv.adapter.update(True)
                            except Exception:
                                pass
                            try:
                                if update_reset_method is not None:
                                    update_reset_method.invoke(param.thisObject)
                            except Exception:
                                pass
                            param.setResult(None)
                        except Exception as e:
                            logx(f"ChatDialogButton: onClick hook error: {e}", False)

                self.plugin.hook_method(on_click_method, OnClickHook())

            logx("ChatDialogButton: main menu prefs hooks set up", True)
        except Exception as e:
            logx(f"ChatDialogButton: _setup_main_menu_prefs_hooks error: {e}", False)
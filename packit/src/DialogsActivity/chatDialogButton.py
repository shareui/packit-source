# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android_utils import log, run_on_ui_thread
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


def _is_drawer_mode():
    try:
        cfg = _get_extera_config()
        return bool(cfg.navigationDrawer) if cfg is not None else False
    except Exception:
        return False


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
        log(f"ChatDialogButton: _set_btn_enabled error: {e}")


def _register_menu_id():
    # sanitize removes our id every launch (unknown to MainMenuItem enum),
    # so we always re-add it to the correct list based on persisted state.
    # works for both drawer and dots mode — layout/hidden lists are shared.
    try:
        cfg = _get_extera_config()
        if cfg is None:
            log("ChatDialogButton: ExteraConfig not found")
            return False
        layout = cfg.mainMenuLayout
        hidden = cfg.mainMenuHiddenItems
        if layout is None or hidden is None:
            log("ChatDialogButton: mainMenuLayout/mainMenuHiddenItems not found")
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
            log(f"ChatDialogButton: saveMainMenuLayout error: {e}")
        return True
    except Exception as e:
        log(f"ChatDialogButton: _register_menu_id error: {e}")
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

            if _is_drawer_mode():
                self._setup_drawer_hook()
            else:
                self._setup_dots_hook()

            log("ChatDialogButton: hooks set up")
        except Exception as e:
            log(f"ChatDialogButton: setup_dialogs_menu_hook error: {e}")

    def _setup_dots_hook(self):
        try:
            DialogsActivity = find_class("org.telegram.ui.DialogsActivity")
            if DialogsActivity is None:
                log("ChatDialogButton: DialogsActivity not found")
                return None

            target_method = None
            for m in DialogsActivity.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "addMainMenuConfiguredItem" and len(m.getParameterTypes()) == 2:
                        target_method = m
                        break
                except Exception:
                    continue

            if target_method is None:
                log("ChatDialogButton: addMainMenuConfiguredItem not found")
                return None

            target_method.setAccessible(True)

            plugin = self.plugin

            class AddMainMenuItemHook(MethodHook):
                def before_hooked_method(self_hook, param):
                    try:
                        item_id = int(param.args[1])
                        if item_id != _PACKIT_MENU_ID:
                            return

                        io = param.args[0]
                        if io is None:
                            return

                        mode = _get_current_mode()
                        icon_id = _get_mode_icon_id(mode)
                        label = _get_mode_label(mode)

                        _String = jclass("java.lang.String")
                        _Runnable = jclass("java.lang.Runnable")
                        from java import dynamic_proxy

                        class _OnClick(dynamic_proxy(_Runnable)):
                            def __init__(self):
                                super().__init__()

                            def run(self):
                                try:
                                    m = _get_current_mode()
                                    if m == 0:
                                        from com.exteragram.messenger.plugins import PluginsController
                                        from com.exteragram.messenger.plugins.ui import PluginSettingsActivity
                                        from client_utils import get_last_fragment
                                        def _open():
                                            try:
                                                frag = get_last_fragment()
                                                pluginObj = PluginsController.getInstance().plugins.get(plugin.id)
                                                if pluginObj and frag:
                                                    frag.presentFragment(PluginSettingsActivity(pluginObj))
                                            except Exception as e:
                                                log(f"ChatDialogButton: open settings error: {e}")
                                        run_on_ui_thread(_open)
                                    elif m == 2:
                                        from ..ui.IconsListActivity.fragment import InstallIconsUI
                                        run_on_ui_thread(lambda: InstallIconsUI(plugin).open())
                                    else:
                                        from ..ui.PluginListActivity.fragment import InstallUI
                                        run_on_ui_thread(lambda: InstallUI(plugin).open())
                                except Exception as e:
                                    log(f"ChatDialogButton: onClick error: {e}")

                        io.add(icon_id, _String(label), _OnClick())
                        param.setResult(True)
                    except Exception as e:
                        log(f"ChatDialogButton: before_hooked_method error: {e}")

            return self.plugin.hook_method(target_method, AddMainMenuItemHook())
        except Exception as e:
            log(f"ChatDialogButton: _setup_dots_hook error: {e}")
            return None

    def _setup_drawer_hook(self):
        try:
            DrawerMenuViewClass = _safe_find_class("com.exteragram.messenger.drawer.DrawerMenuView")
            if DrawerMenuViewClass is None:
                log("ChatDialogButton: DrawerMenuView not found")
                return None

            rebuild_method = None
            for m in DrawerMenuViewClass.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "rebuildMenu" and len(m.getParameterTypes()) == 2:
                        rebuild_method = m
                        break
                except Exception:
                    continue

            if rebuild_method is None:
                log("ChatDialogButton: DrawerMenuView.rebuildMenu not found")
                return None

            rebuild_method.setAccessible(True)
            from base_plugin import MenuItemData, MenuItemType
            plugin = self.plugin
            mode = _get_current_mode()
            icon_name = ["msg_plugins", "msg_addbot", "input_smile"][mode] if 0 <= mode <= 2 else "msg_addbot"
            label = _get_mode_label(mode)

            def on_drawer_click(context):
                try:
                    m = _get_current_mode()
                    if m == 0:
                        from com.exteragram.messenger.plugins import PluginsController
                        from com.exteragram.messenger.plugins.ui import PluginSettingsActivity
                        from client_utils import get_last_fragment
                        frag = get_last_fragment()
                        pluginObj = PluginsController.getInstance().plugins.get(plugin.id)
                        if pluginObj and frag:
                            frag.presentFragment(PluginSettingsActivity(pluginObj))
                    elif m == 2:
                        from ..ui.IconsListActivity.fragment import InstallIconsUI
                        InstallIconsUI(plugin).open()
                    else:
                        from ..ui.PluginListActivity.fragment import InstallUI
                        InstallUI(plugin).open()
                except Exception as e:
                    log(f"ChatDialogButton: drawer onClick error: {e}")

            self.plugin.add_menu_item(MenuItemData(
                menu_type=MenuItemType.DRAWER_MENU,
                text=label,
                on_click=on_drawer_click,
                icon=icon_name
            ))
            log("ChatDialogButton: drawer menu item added")
        except Exception as e:
            log(f"ChatDialogButton: _setup_drawer_hook error: {e}")

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
                        log(f"ChatDialogButton: sanitize after hook error: {e}")

            return self.plugin.hook_method(sanitize_method, SanitizeMenuHook())
        except Exception as e:
            log(f"ChatDialogButton: _setup_sanitize_hook error: {e}")
            return None

    def _setup_main_menu_prefs_hooks(self):
        # hooks for AppNavigationPreferencesActivity so our item renders in the
        # "Main menu" settings screen (initItemDetails, createMenuItem, onClick)
        try:
            activity_cls = _safe_find_class(
                "com.exteragram.messenger.preferences.appearance.AppNavigationPreferencesActivity"
            )
            if activity_cls is None:
                log("ChatDialogButton: MainMenuPreferencesActivity not found")
                return

            item_info_cls = _safe_find_class(
                "com.exteragram.messenger.preferences.appearance.AppNavigationPreferencesActivity$ItemInfo"
            )
            if item_info_cls is None:
                log("ChatDialogButton: ItemInfo class not found")
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
                        log(f"ChatDialogButton: initItemDetails hook error: {e}")

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
                            log(f"ChatDialogButton: createMenuItem hook error: {e}")

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
                            log(f"ChatDialogButton: onClick hook error: {e}")

                self.plugin.hook_method(on_click_method, OnClickHook())

            log("ChatDialogButton: main menu prefs hooks set up")
        except Exception as e:
            log(f"ChatDialogButton: _setup_main_menu_prefs_hooks error: {e}")
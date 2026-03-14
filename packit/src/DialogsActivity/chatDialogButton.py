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


def _get_extera_config():
    try:
        return find_class("com.exteragram.messenger.ExteraConfig")
    except Exception:
        return None


def _register_menu_id():
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
        if layout.contains(id_obj) or hidden.contains(id_obj):
            return True
        layout.add(id_obj)
        try:
            cfg.saveMainMenuLayout()
        except Exception as e:
            log(f"ChatDialogButton: saveMainMenuLayout error: {e}")
        return True
    except Exception as e:
        log(f"ChatDialogButton: _register_menu_id error: {e}")
        return False


class ChatDialogButton:
    def setup_dialogs_menu_hook(self):
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

            self._setup_sanitize_hook()
            self._setup_main_menu_prefs_hooks()

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

                        R = find_class("org.telegram.messenger.R")
                        try:
                            icon_id = int(getattr(R.drawable, "msg_addbot"))
                        except Exception:
                            icon_id = 0

                        _String = jclass("java.lang.String")
                        _Runnable = jclass("java.lang.Runnable")
                        from java import dynamic_proxy

                        class _OnClick(dynamic_proxy(_Runnable)):
                            def __init__(self):
                                super().__init__()

                            def run(self):
                                try:
                                    from ..ui.PluginListActivity.fragment import InstallUI
                                    run_on_ui_thread(lambda: InstallUI(plugin).open())
                                except Exception as e:
                                    log(f"ChatDialogButton: onClick error: {e}")

                        io.add(icon_id, _String(strings["install_plugin_btn"]), _OnClick())
                        param.setResult(True)
                    except Exception as e:
                        log(f"ChatDialogButton: before_hooked_method error: {e}")

            _register_menu_id()

            hook_ref = plugin.hook_method(target_method, AddMainMenuItemHook())
            log("ChatDialogButton: hook set up")
            return hook_ref

        except Exception as e:
            log(f"ChatDialogButton: setup_dialogs_menu_hook error: {e}")
            return None

    def _setup_sanitize_hook(self):
        try:
            cfg_class = find_class("com.exteragram.messenger.ExteraConfig")
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
        # hooks for MainMenuPreferencesActivity so our item renders in the
        # "Main menu" settings screen (initItemDetails, createMenuItem, onClick)
        try:
            activity_cls = find_class(
                "com.exteragram.messenger.preferences.appearance.MainMenuPreferencesActivity"
            )
            if activity_cls is None:
                log("ChatDialogButton: MainMenuPreferencesActivity not found")
                return

            item_info_cls = find_class(
                "com.exteragram.messenger.preferences.appearance.MainMenuPreferencesActivity$ItemInfo"
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

            R = find_class("org.telegram.messenger.R")
            try:
                icon_id = int(getattr(R.drawable, "msg_addbot"))
            except Exception:
                icon_id = 0

            _String = jclass("java.lang.String")

            # register our item in itemDetails map so the activity knows name+icon
            class InitItemDetailsHook(MethodHook):
                def after_hooked_method(self_hook, param):
                    try:
                        item_details = item_details_field.get(param.thisObject)
                        if item_details is None:
                            return
                        label = _String(strings["install_plugin_btn"])
                        info_obj = item_info_ctor.newInstance(label, _Integer(icon_id))
                        item_details.put(_Integer(_PACKIT_MENU_ID), info_obj)
                    except Exception as e:
                        log(f"ChatDialogButton: initItemDetails hook error: {e}")

            init_method = java_cls.getDeclaredMethod("initItemDetails")
            init_method.setAccessible(True)
            self.plugin.hook_method(init_method, InitItemDetailsHook())

            # return UItem for our id so it renders correctly in the list
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

            # toggle visibility when user taps our item in prefs
            NotificationCenter = jclass("org.telegram.messenger.NotificationCenter")
            base_activity_cls = find_class(
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
                            elif cfg.mainMenuHiddenItems.contains(id_obj):
                                cfg.mainMenuHiddenItems.remove(id_obj)
                                cfg.mainMenuLayout.add(id_obj)
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

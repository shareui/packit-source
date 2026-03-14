from android_utils import log, run_on_ui_thread
from base_plugin import MethodHook
from hook_utils import find_class
from java import jclass, dynamic_proxy
from java.lang import Integer, Long

_PILL_ID = 880001
_PILL_LABEL = "PackIt"
_PREFS_NAME = "packit_pill"

_ACTION_SETTINGS = 0
_ACTION_INSTALL = 1
_ACTION_ICONS = 2

_system = None


def setup_pill_widget(plugin):
    log("PillWidget: setup start")
    try:
        if not _register_in_registry(plugin):
            log("PillWidget: registry registration failed")
            return None
        _restore_visibility()
        _sync_pillstack()
        _notify_update()
        log("PillWidget: setup complete")
        return True
    except Exception as e:
        log(f"PillWidget: setup error: {e}")
        return None


def _register_in_registry(plugin):
    try:
        PillRegistry = find_class("com.exteragram.messenger.pillstack.core.PillRegistry")
        if PillRegistry is None:
            log("PillWidget: PillRegistry not found")
            return False

        instances = plugin._pill_instances = {}

        _install_hooks(plugin)

        if PillRegistry.isRegistered(_PILL_ID):
            log("PillWidget: already registered")
            return True

        PillInfo = find_class("com.exteragram.messenger.pillstack.core.PillRegistry$PillInfo")
        PillCreatorInterface = find_class("com.exteragram.messenger.pillstack.core.PillRegistry$PillCreator")
        CachePill = find_class("com.exteragram.messenger.pillstack.ui.pills.system.CachePill")

        if not PillInfo or not PillCreatorInterface or not CachePill:
            log("PillWidget: required classes not found")
            return False

        class PackitPillCreator(dynamic_proxy(PillCreatorInterface)):
            def __init__(self):
                super().__init__()

            def create(self, context, resourcesProvider):
                try:
                    pill = CachePill(context, resourcesProvider)
                    instances[_pill_key(pill)] = pill
                    _apply_visuals(pill)
                    return pill
                except Exception as e:
                    log(f"PillWidget: creator.create error: {e}")
                    return None

        iconRes = _get_icon_res()
        creator = PackitPillCreator()
        info = PillInfo(_PILL_ID, _PILL_LABEL, iconRes, -1, -1, creator)
        PillRegistry.register(info)
        log(f"PillWidget: registered id={_PILL_ID}")
        return True
    except Exception as e:
        log(f"PillWidget: _register_in_registry error: {e}")
        return False


def _install_hooks(plugin):
    try:
        JClass = jclass("java.lang.Class")
        CachePillClass = JClass.forName("com.exteragram.messenger.pillstack.ui.pills.system.CachePill")
        for method in CachePillClass.getDeclaredMethods():
            name = method.getName()
            if name == "getPillId":
                plugin.hook_method(method, _GetIdHook(plugin))
            elif name == "getRefreshInterval":
                plugin.hook_method(method, _IntervalHook(plugin))
            elif name == "onPillClicked":
                plugin.hook_method(method, _ClickHook(plugin))
            elif name == "onPillLongClicked":
                plugin.hook_method(method, _LongClickHook(plugin))
            elif name == "onUpdateData":
                plugin.hook_method(method, _UpdateDataHook(plugin))
            elif name == "onAttachedToWindow":
                plugin.hook_method(method, _AttachHook(plugin))
        log("PillWidget: hooks installed")
    except Exception as e:
        log(f"PillWidget: _install_hooks error: {e}")


def _pill_key(obj):
    global _system
    try:
        if _system is None:
            _system = jclass("java.lang.System")
        return int(_system.identityHashCode(obj))
    except Exception:
        try:
            return int(obj.hashCode())
        except Exception:
            return id(obj)


def _is_ours(plugin, pill):
    try:
        instances = getattr(plugin, "_pill_instances", {})
        if _pill_key(pill) in instances:
            return True
    except Exception:
        pass
    # fallback for hot-reload: pill exists but instances dict is fresh
    try:
        return pill.getTag(0x7a000001) is not None
    except Exception:
        return False


def _get_icon_res():
    try:
        R = find_class("org.telegram.messenger.R")
        return int(getattr(R.drawable, "msg_plugins", 0))
    except Exception:
        return 0


def _get_prefs():
    try:
        ApplicationLoader = find_class("org.telegram.messenger.ApplicationLoader")
        return ApplicationLoader.applicationContext.getSharedPreferences(_PREFS_NAME, 0)
    except Exception:
        return None


def _get_saved_state():
    # 1 = active, 0 = hidden, -1 = unknown
    try:
        prefs = _get_prefs()
        if prefs:
            return int(prefs.getInt("pill_state", -1))
    except Exception:
        pass
    return -1


def _set_saved_state(state):
    try:
        prefs = _get_prefs()
        if prefs:
            prefs.edit().putInt("pill_state", int(state)).apply()
    except Exception:
        pass


def _get_saved_index():
    try:
        prefs = _get_prefs()
        if prefs:
            return int(prefs.getInt("pill_index", -1))
    except Exception:
        pass
    return -1


def _set_saved_index(idx):
    try:
        prefs = _get_prefs()
        if prefs:
            prefs.edit().putInt("pill_index", int(idx)).apply()
    except Exception:
        pass


def _get_saved_action():
    try:
        prefs = _get_prefs()
        if prefs:
            return int(prefs.getInt("pill_action", _ACTION_SETTINGS))
    except Exception:
        pass
    return _ACTION_SETTINGS


def _set_saved_action(action):
    try:
        prefs = _get_prefs()
        if prefs:
            prefs.edit().putInt("pill_action", int(action)).apply()
    except Exception:
        pass


def _java_int(v):
    try:
        return Integer(int(v))
    except Exception:
        return int(v)


def _active_index(active, pid_obj):
    try:
        idx = active.indexOf(pid_obj)
        if idx is not None and int(idx) >= 0:
            return int(idx)
    except Exception:
        pass
    try:
        for i in range(int(active.size())):
            if int(active.get(i)) == int(pid_obj):
                return i
    except Exception:
        pass
    return -1


def _place_in_active(active, pid_obj, idx):
    try:
        active.remove(pid_obj)
    except Exception:
        pass
    try:
        size = int(active.size())
        if idx is None or idx < 0 or idx > size:
            active.add(pid_obj)
        else:
            active.add(int(idx), pid_obj)
    except Exception:
        try:
            active.add(pid_obj)
        except Exception:
            pass


def _restore_visibility():
    # called before sanitizePills -> restores user's last known position
    try:
        state = _get_saved_state()
        if state not in (0, 1):
            return

        PillStackConfig = find_class("com.exteragram.messenger.pillstack.core.PillStackConfig")
        if PillStackConfig is None:
            return

        active = getattr(PillStackConfig, "activePills", None)
        hidden = getattr(PillStackConfig, "hiddenPills", None)
        if active is None or hidden is None:
            return

        pid = _java_int(_PILL_ID)
        idx = _get_saved_index()
        changed = False

        if state == 1:
            try:
                if hidden.contains(pid):
                    hidden.remove(pid)
                    changed = True
            except Exception:
                pass
            try:
                if not active.contains(pid):
                    _place_in_active(active, pid, idx)
                    changed = True
                elif idx >= 0:
                    cur = _active_index(active, pid)
                    if cur != idx:
                        _place_in_active(active, pid, idx)
                        changed = True
            except Exception:
                pass
        else:
            try:
                if active.contains(pid):
                    active.remove(pid)
                    changed = True
            except Exception:
                pass
            try:
                if not hidden.contains(pid):
                    hidden.add(pid)
                    changed = True
            except Exception:
                pass

        if changed:
            try:
                PillStackConfig.savePillsLayout()
            except Exception:
                pass

        log(f"PillWidget: restored state={state} idx={idx}")
    except Exception as e:
        log(f"PillWidget: _restore_visibility error: {e}")


def _sync_state_from_config():
    # saves current position to prefs so it survives restart
    try:
        PillStackConfig = find_class("com.exteragram.messenger.pillstack.core.PillStackConfig")
        if PillStackConfig is None:
            return
        active = getattr(PillStackConfig, "activePills", None)
        hidden = getattr(PillStackConfig, "hiddenPills", None)
        if active is None or hidden is None:
            return
        pid = _java_int(_PILL_ID)
        try:
            if active.contains(pid):
                _set_saved_state(1)
                idx = _active_index(active, pid)
                if idx >= 0:
                    _set_saved_index(idx)
                return
        except Exception:
            pass
        try:
            if hidden.contains(pid):
                _set_saved_state(0)
        except Exception:
            pass
    except Exception as e:
        log(f"PillWidget: _sync_state_from_config error: {e}")


def _sync_pillstack():
    # sanitize + save — called after restore so state is already correct
    try:
        PillStackConfig = find_class("com.exteragram.messenger.pillstack.core.PillStackConfig")
        if PillStackConfig is None:
            return
        try:
            PillStackConfig.sanitizePills()
        except Exception:
            pass
        try:
            PillStackConfig.savePillsLayout()
        except Exception:
            pass
        try:
            PillStackConfig.notifySettingsChanged()
        except Exception:
            pass
        log("PillWidget: pillstack synced")
    except Exception as e:
        log(f"PillWidget: _sync_pillstack error: {e}")


def _notify_update():
    try:
        def _do():
            try:
                PillStackConfig = find_class("com.exteragram.messenger.pillstack.core.PillStackConfig")
                if PillStackConfig:
                    PillStackConfig.notifySettingsChanged()
            except Exception as e:
                log(f"PillWidget: _notify_update inner error: {e}")
        run_on_ui_thread(_do)
    except Exception as e:
        log(f"PillWidget: _notify_update error: {e}")


def _apply_visuals(pill):
    try:
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.messenger import AndroidUtilities, LocaleController
        from org.telegram.ui.Components import LayoutHelper
        from android.widget import LinearLayout, ImageView, TextView
        from android.view import Gravity
        from android.graphics import PorterDuff

        pill.removeAllViews()

        ctx = pill.getContext()
        layout = LinearLayout(ctx)
        layout.setOrientation(LinearLayout.HORIZONTAL)
        layout.setGravity(Gravity.CENTER)
        layout.setMinimumWidth(AndroidUtilities.dp(48))
        layout.setPadding(AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8), 0)
        gravity = Gravity.CENTER_VERTICAL | (3 if LocaleController.isRTL else 5)
        pill.addView(layout, LayoutHelper.createFrame(-2, 28, gravity))

        icon = ImageView(ctx)
        icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        iconRes = _get_icon_res()
        if iconRes:
            icon.setImageResource(iconRes)
        layout.addView(icon, LayoutHelper.createLinear(16, 16, 0, 0, 6, 0))

        label = TextView(ctx)
        label.setText(_PILL_LABEL)
        label.setTextSize(13)
        label.setSingleLine(True)
        label.setIncludeFontPadding(False)
        layout.addView(label, LayoutHelper.createLinear(-2, -2, 16))

        pill.setTag(0x7a000001, layout)
        pill.setTag(0x7a000002, icon)
        pill.setTag(0x7a000003, label)

        _apply_colors(pill)
    except Exception as e:
        log(f"PillWidget: _apply_visuals error: {e}")


def _apply_colors(pill):
    try:
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.messenger import AndroidUtilities
        from android.graphics import PorterDuff

        layout = pill.getTag(0x7a000001)
        icon = pill.getTag(0x7a000002)
        label = pill.getTag(0x7a000003)
        if not layout:
            return

        color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        alpha75 = Theme.multAlpha(color, 0.75)
        isDark = Theme.isCurrentThemeDark()
        bgNormal = Theme.getColor(Theme.key_windowBackgroundWhite) if isDark else Theme.multAlpha(alpha75, 0.09)
        bg = Theme.createSimpleSelectorRoundRectDrawable(AndroidUtilities.dp(14), bgNormal, Theme.multAlpha(alpha75, 0.1))
        layout.setBackground(bg)
        if label:
            label.setTextColor(alpha75)
        if icon:
            icon.setColorFilter(alpha75, PorterDuff.Mode.SRC_IN)
    except Exception as e:
        log(f"PillWidget: _apply_colors error: {e}")


def _execute_action(plugin, action):
    if action == _ACTION_INSTALL:
        _open_install(plugin)
    elif action == _ACTION_ICONS:
        _open_icons(plugin)
    else:
        _open_settings(plugin)


def _open_settings(plugin):
    try:
        from client_utils import get_last_fragment
        from com.exteragram.messenger.plugins import PluginsController
        from com.exteragram.messenger.plugins.ui import PluginSettingsActivity

        fragment = get_last_fragment()
        p = PluginsController.getInstance().plugins.get(plugin.id)
        if p:
            fragment.presentFragment(PluginSettingsActivity(p))
        else:
            from ui.bulletin import BulletinHelper
            from elyx import strings
            BulletinHelper.show_error(strings.plugin_not_found)
    except Exception as e:
        log(f"PillWidget: _open_settings error: {e}")


def _open_install(plugin):
    try:
        from ..ui.installUi.uiMain import InstallUI
        InstallUI(plugin).open()
    except Exception as e:
        log(f"PillWidget: _open_install error: {e}")


def _open_icons(plugin):
    try:
        from ..ui.installIconsUi.uiMain import InstallIconsUI
        InstallIconsUI(plugin).open()
    except Exception as e:
        log(f"PillWidget: _open_icons error: {e}")


def _open_pill_stack_settings():
    try:
        from client_utils import get_last_fragment
        PillStackPreferencesActivity = find_class("com.exteragram.messenger.pillstack.ui.PillStackPreferencesActivity")
        if PillStackPreferencesActivity is None:
            return
        frag = get_last_fragment()
        if frag:
            frag.presentFragment(PillStackPreferencesActivity())
    except Exception as e:
        log(f"PillWidget: _open_pill_stack_settings error: {e}")


def _action_label(action, strings):
    if action == _ACTION_INSTALL:
        return str(strings.install_plugin)
    if action == _ACTION_ICONS:
        return str(strings.install_icons)
    return str(strings.pill_action_settings)


def _show_long_click_menu(plugin, pill):
    try:
        from client_utils import get_last_fragment
        from org.telegram.ui.Components import ItemOptions
        from org.telegram.ui.ActionBar import ActionBarMenuSubItem
        from org.telegram.messenger import R as R_tg
        from elyx import strings

        fragment = get_last_fragment()
        if fragment is None:
            return

        cur_action = _get_saved_action()

        options = ItemOptions.makeOptions(fragment, pill, True)

        # swipeback panel -> action picker
        swipeback = options.makeSwipeback()
        icon_back = int(getattr(R_tg.drawable, "ic_ab_back", 0))

        def make_back_runnable():
            from java import dynamic_proxy
            from java.lang import Runnable as JRunnable
            class R(dynamic_proxy(JRunnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    options.closeSwipeback()
            return R()

        swipeback.add(icon_back, str(strings.pill_action_change), make_back_runnable())
        swipeback.addGap()

        for action in (_ACTION_SETTINGS, _ACTION_INSTALL, _ACTION_ICONS):
            label = _action_label(action, strings)
            checked = (action == cur_action)

            def make_select_runnable(a=action):
                from java import dynamic_proxy
                from java.lang import Runnable as JRunnable
                class R(dynamic_proxy(JRunnable)):
                    def __init__(self):
                        super().__init__()
                    def run(self):
                        _set_saved_action(a)
                        options.dismiss()
                return R()

            swipeback.addChecked(checked, label, make_select_runnable())

        # main panel
        ctx = options.getContext()
        sub = ActionBarMenuSubItem(ctx, False, False, None)
        sub.setTextAndIcon(str(strings.pill_action_change), int(getattr(R_tg.drawable, "msg_mini_customize", 0)))
        sub.setSubtext(_action_label(cur_action, strings))
        sub.setItemHeight(56)

        from android_utils import OnClickListener
        sub.setOnClickListener(OnClickListener(lambda v: options.openSwipeback(swipeback)))

        options.add(sub)
        options.addGap()

        def make_channel_runnable():
            from java import dynamic_proxy
            from java.lang import Runnable as JRunnable
            class R(dynamic_proxy(JRunnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    try:
                        from client_utils import get_last_fragment
                        from android.net import Uri
                        from org.telegram.messenger.browser import Browser
                        frag = get_last_fragment()
                        act = frag.getParentActivity() if frag else None
                        if act:
                            Browser.openUrl(act, Uri.parse(str(strings.tg_channel_url)), True, True, True, None, None, False, False, False)
                    except Exception as e:
                        log(f"PillWidget: open channel error: {e}")
            return R()

        icon_channel = int(getattr(R_tg.drawable, "msg_channel", 0))
        options.add(icon_channel, str(strings.packit_channel), make_channel_runnable())

        def make_pill_settings_runnable():
            from java import dynamic_proxy
            from java.lang import Runnable as JRunnable
            class R(dynamic_proxy(JRunnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    _open_pill_stack_settings()
            return R()

        icon_pill = int(getattr(R_tg.drawable, "msg_settings", 0))
        options.add(icon_pill, str(strings.deeplinks_settings), make_pill_settings_runnable())

        options.setSwipebackGravity(True, False)
        options.setDrawScrim(False)
        options.setDimAlpha(0)
        options.show()
    except Exception as e:
        log(f"PillWidget: _show_long_click_menu error: {e}")


class _GetIdHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def before_hooked_method(self, param):
        try:
            if _is_ours(self.plugin, param.thisObject):
                param.setResult(Integer(_PILL_ID))
        except Exception:
            pass


class _IntervalHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def before_hooked_method(self, param):
        try:
            if _is_ours(self.plugin, param.thisObject):
                param.setResult(Long(0))
        except Exception:
            pass


class _ClickHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def before_hooked_method(self, param):
        try:
            if not _is_ours(self.plugin, param.thisObject):
                return
            run_on_ui_thread(lambda: _execute_action(self.plugin, _get_saved_action()))
            param.setResult(None)
        except Exception:
            pass


class _LongClickHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def before_hooked_method(self, param):
        try:
            if not _is_ours(self.plugin, param.thisObject):
                return
            pill = param.thisObject
            run_on_ui_thread(lambda: _show_long_click_menu(self.plugin, pill))
            param.setResult(True)
        except Exception:
            pass


class _UpdateDataHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def before_hooked_method(self, param):
        try:
            if _is_ours(self.plugin, param.thisObject):
                param.setResult(None)
        except Exception:
            pass


class _AttachHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def after_hooked_method(self, param):
        try:
            if _is_ours(self.plugin, param.thisObject):
                _sync_state_from_config()
                _apply_visuals(param.thisObject)
        except Exception:
            pass

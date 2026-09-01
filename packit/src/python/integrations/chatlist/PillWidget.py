# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from android_utils import run_on_ui_thread
from android.view import Gravity
from android.widget import LinearLayout, ImageView, TextView
from android.graphics import PorterDuff
from java import dynamic_proxy, jint
from java.lang import Runnable as JRunnable
from org.telegram.messenger import AndroidUtilities, LocaleController
from org.telegram.ui.ActionBar import Theme
from com.exteragram.messenger.pillstack.core import PillStackConfig, PillRegistry
from com.exteragram.messenger.pillstack.ui.pills import BasePill
from extera_utils.classes import Base, java_subclass, joverride, jfield, jgetmethod

_PILL_ID = 880001
_PILL_LABEL = "PackIt"
_ACTION_SETTINGS = 0
_ACTION_INSTALL = 1
_ACTION_ICONS = 2

_WRAP_CONTENT = -2
_dp = AndroidUtilities.dp


@java_subclass(BasePill)
class PackitPill(Base):
    PILL_ID = _PILL_ID

    llayout = jfield("android.widget.LinearLayout")
    icon_view = jfield("android.widget.ImageView")
    label_view = jfield("android.widget.TextView")

    refresh_interval = jfield("long", default=0, methods=[jgetmethod("getRefreshInterval")])
    pill_id = jfield("int", default=jint(_PILL_ID), methods=[jgetmethod("getPillId")])

    def on_post_init(self, context, resources_provider):
        self.llayout = layout = LinearLayout(context)
        layout.setOrientation(LinearLayout.HORIZONTAL)
        layout.setGravity(Gravity.CENTER)
        layout.setMinimumWidth(_dp(48))
        layout.setPadding(_dp(8), 0, _dp(8), 0)

        lp_layout = LinearLayout.LayoutParams(_WRAP_CONTENT, _dp(28))
        lp_layout.gravity = Gravity.CENTER_VERTICAL | (Gravity.LEFT if not LocaleController.isRTL else Gravity.RIGHT)
        self.addView(layout, lp_layout)

        self.icon_view = icon_view = ImageView(context)
        icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        icon_res = _get_icon_res()
        if icon_res:
            icon_view.setImageResource(icon_res)

        lp_icon = LinearLayout.LayoutParams(_dp(16), _dp(16))
        lp_icon.gravity = Gravity.CENTER_VERTICAL
        lp_icon.rightMargin = _dp(6)
        layout.addView(icon_view, lp_icon)

        self.label_view = label = TextView(context)
        label.setText(_PILL_LABEL)
        label.setTextSize(13)
        label.setSingleLine(True)
        label.setIncludeFontPadding(False)

        lp_label = LinearLayout.LayoutParams(_WRAP_CONTENT, _WRAP_CONTENT)
        lp_label.gravity = Gravity.CENTER_VERTICAL | Gravity.LEFT
        layout.addView(label, lp_label)

        self.setLoadingTargetView(layout)

        try:
            from org.telegram.ui.Components import ScaleStateListAnimator
            ScaleStateListAnimator.apply(layout)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"PillWidget: ScaleStateListAnimator error: {e}", False)

        self.updateColors()

    @joverride()
    def onUpdateData(self, force: bool):
        pass

    @joverride()
    def onAttachedToWindow(self):
        super().onAttachedToWindow()
        self.updateColors()

    @joverride()
    def onPillClicked(self):
        try:
            run_on_ui_thread(lambda: _execute_action(_plugin_ref[0], _get_saved_action()))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"PillWidget: onPillClicked error: {e}", False)

    @joverride()
    def onPillLongClicked(self) -> bool:
        try:
            pill_java = self.java
            run_on_ui_thread(lambda: _show_long_click_menu(_plugin_ref[0], pill_java))
            return True
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"PillWidget: onPillLongClicked error: {e}", False)
            return False

    @joverride()
    def updateColors(self):
        try:
            color = self.getThemedColor(Theme.key_windowBackgroundWhiteBlackText, 0.75)
            bg_color = (
                self.getThemedColor(Theme.key_windowBackgroundWhite)
                if Theme.isCurrentThemeDark()
                else Theme.multAlpha(color, 0.09)
            )
            self.llayout.setBackground(
                Theme.createSimpleSelectorRoundRectDrawable(_dp(14), bg_color, Theme.multAlpha(color, 0.1))
            )
            if self.label_view:
                self.label_view.setTextColor(color)
            if self.icon_view:
                self.icon_view.setColorFilter(color, PorterDuff.Mode.SRC_IN)
            self.updateLoadingColors()
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"PillWidget: updateColors error: {e}", False)

    @joverride()
    def setPressed(self, pressed: bool):
        super().setPressed(pressed)
        if self.llayout:
            self.llayout.setPressed(pressed)


class _PackitPillCreator(dynamic_proxy(PillRegistry.PillCreator)):
    def __init__(self, pill_class):
        super().__init__()
        self.clazz = pill_class

    def create(self, context, resources_provider):
        return self.clazz.new_instance(context, resources_provider).java


_plugin_ref = [None]


def setup_pill_widget(plugin):
    logx("PillWidget: setup start", True)
    try:
        _plugin_ref[0] = plugin
        _setup_save_hook(plugin)
        run_on_ui_thread(lambda: _register_pill(plugin))
        logx("PillWidget: setup scheduled", True)
        return True
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: setup error: {e}", False)
        return None


def _setup_save_hook(plugin):
    # hook PillStackConfig.savePillsLayout to capture state changes made in PillPreferences
    try:
        from hook_utils import find_class
        from base_plugin import MethodHook
        PillStackConfigClass = find_class("com.exteragram.messenger.pillstack.core.PillStackConfig")
        method = PillStackConfigClass.getClass().getDeclaredMethod("savePillsLayout")
        method.setAccessible(True)

        class SaveLayoutHook(MethodHook):
            def after_hooked_method(self, param):
                _sync_state_from_config()

        plugin.hook_method(method, SaveLayoutHook())
        logx("PillWidget: savePillsLayout hook installed", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _setup_save_hook error: {e}", False)


def _get_prefs():
    try:
        from hook_utils import find_class
        ApplicationLoader = find_class("org.telegram.messenger.ApplicationLoader")
        return ApplicationLoader.applicationContext.getSharedPreferences("packit_pill", 0)
    except Exception:
        return None


def _get_saved_state():
    try:
        prefs = _get_prefs()
        if prefs:
            # default 0 = hidden (disabled by default)
            return int(prefs.getInt("pill_state", 0))
    except Exception:
        pass
    return 0


def _set_saved_state(state):
    try:
        prefs = _get_prefs()
        if prefs:
            prefs.edit().putInt("pill_state", int(state)).apply()
            logx(f"PillWidget: saved state={state}", True)
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


def _ensure_visibility():
    # restore pill position from own prefs; default state=0 means hidden
    try:
        active = getattr(PillStackConfig, "activePills", None)
        hidden = getattr(PillStackConfig, "hiddenPills", None)
        if active is None or hidden is None:
            return
        pid = jint(_PILL_ID)
        state = _get_saved_state()
        if state == 1:
            idx = _get_saved_index()
            _place_in_active(active, pid, idx)
        else:
            try:
                if not hidden.contains(pid):
                    hidden.add(pid)
            except Exception:
                pass
        PillStackConfig.savePillsLayout()
        logx(f"PillWidget: ensure_visibility state={state}", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _ensure_visibility error: {e}", False)


def _sync_state_from_config():
    # called while pill is live — saves current pillstack state to own prefs
    try:
        active = getattr(PillStackConfig, "activePills", None)
        hidden = getattr(PillStackConfig, "hiddenPills", None)
        if active is None or hidden is None:
            logx("PillWidget: _sync_state_from_config: lists not available", True)
            return
        pid = jint(_PILL_ID)
        try:
            if active.contains(pid):
                _set_saved_state(1)
                idx = _active_index(active, pid)
                if idx >= 0:
                    _set_saved_index(idx)
                logx(f"PillWidget: sync -> active, idx={idx}", True)
                return
        except Exception:
            pass
        try:
            if hidden.contains(pid):
                _set_saved_state(0)
                logx("PillWidget: sync -> hidden", True)
                return
        except Exception:
            pass
        logx("PillWidget: sync -> pill not found in either list", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _sync_state_from_config error: {e}", False)


def _register_pill(plugin):
    try:
        pid = jint(_PILL_ID)
        icon_res = _get_icon_res()
        pill_info = PillRegistry.PillInfo(
            pid,
            _PILL_LABEL,
            icon_res,
            -8695125,   # top: #7B52AB purple
            -10801024,  # bottom: #5B3080 dark purple
            _PackitPillCreator(PackitPill)
        )
        _ensure_visibility()
        PillRegistry.register(pill_info)
        _sync_pillstack()
        _notify_update()
        logx(f"PillWidget: registered id={_PILL_ID}", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _register_pill error: {e}", False)


def _unregister_pill():
    try:
        PillRegistry.unregister(_PILL_ID)
        logx("PillWidget: unregistered", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _unregister_pill error: {e}", False)


def _get_icon_res():
    try:
        from hook_utils import find_class
        R = find_class("org.telegram.messenger.R")
        return int(getattr(R.drawable, "msg_plugins", 0))
    except Exception:
        return 0


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


def _sync_pillstack():
    try:
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
        logx("PillWidget: pillstack synced", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _sync_pillstack error: {e}", False)


def _notify_update():
    try:
        def _do():
            try:
                PillStackConfig.notifySettingsChanged()
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"PillWidget: _notify_update inner error: {e}", False)
        run_on_ui_thread(_do)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _notify_update error: {e}", False)


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
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _open_settings error: {e}", False)


def _open_install(plugin):
    try:
        from ...ui.plugins.Fragment import InstallUI
        InstallUI(plugin).open()
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _open_install error: {e}", False)


def _open_icons(plugin):
    try:
        from ...ui.icons.Fragment import InstallIconsUI
        InstallIconsUI(plugin).open()
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _open_icons error: {e}", False)


def _open_pill_stack_settings():
    try:
        from client_utils import get_last_fragment
        from hook_utils import find_class
        PillStackPreferencesActivity = find_class("com.exteragram.messenger.pillstack.ui.PillStackPreferencesActivity")
        if PillStackPreferencesActivity is None:
            return
        frag = get_last_fragment()
        if frag:
            frag.presentFragment(PillStackPreferencesActivity())
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _open_pill_stack_settings error: {e}", False)


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

        swipeback = options.makeSwipeback()
        icon_back = int(getattr(R_tg.drawable, "ic_ab_back", 0))

        def make_back_runnable():
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
                class R(dynamic_proxy(JRunnable)):
                    def __init__(self):
                        super().__init__()
                    def run(self):
                        _set_saved_action(a)
                        options.dismiss()
                return R()

            swipeback.addChecked(checked, label, make_select_runnable())

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
                    except Exception as _cython_exc_e:
                        e = _cython_exc_e
                        logx(f"PillWidget: open channel error: {e}", False)
            return R()

        icon_channel = int(getattr(R_tg.drawable, "msg_channel", 0))
        options.add(icon_channel, str(strings.packit_channel), make_channel_runnable())

        def make_pill_settings_runnable():
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
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"PillWidget: _show_long_click_menu error: {e}", False)
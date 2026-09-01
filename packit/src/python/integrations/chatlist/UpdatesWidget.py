# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ...utils.NetQueue import run_io
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

_PILL_ID = 880002
_WRAP_CONTENT = -2
_dp = AndroidUtilities.dp

# green gradient for has-updates state
_COLOR_GREEN_TOP    = -12345273
_COLOR_GREEN_BOTTOM = -13730510
# blue gradient for up-to-date state
_COLOR_BLUE_TOP    = -14776091
_COLOR_BLUE_BOTTOM = -15374912

# cached updates count, refreshed on check
_updates_count = [0]
_updates_list = [[]]  # cached list of update dicts


def _make_gradient_bg(color_top: int, color_bottom: int):
    from android.graphics.drawable import GradientDrawable
    from java import jarray, jint
    colors = jarray(jint)([jint(color_top), jint(color_bottom)])
    bg = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, colors)
    bg.setCornerRadius(float(_dp(14)))
    return bg


def _apply_press_anim(layout, enabled: bool):
    try:
        from org.telegram.ui.Components import ScaleStateListAnimator
        if enabled:
            ScaleStateListAnimator.apply(layout)
        else:
            layout.setStateListAnimator(None)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _apply_press_anim error: {e}", False)


@java_subclass(BasePill)
class UpdatesPill(Base):
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
        label.setText(_get_label())
        label.setTextSize(13)
        label.setSingleLine(True)
        label.setIncludeFontPadding(False)

        lp_label = LinearLayout.LayoutParams(_WRAP_CONTENT, _WRAP_CONTENT)
        lp_label.gravity = Gravity.CENTER_VERTICAL | Gravity.LEFT
        layout.addView(label, lp_label)

        self.setLoadingTargetView(layout)
        self.updateColors()
        _active_pill_ref[0] = self

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
            pill_self = self
            run_on_ui_thread(lambda: _on_click(_plugin_ref[0], pill_self))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: onPillClicked error: {e}", False)

    @joverride()
    def onPillLongClicked(self) -> bool:
        try:
            pill_java = self.java
            run_on_ui_thread(lambda: _show_menu(_plugin_ref[0], pill_java))
            return True
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: onPillLongClicked error: {e}", False)
            return False

    @joverride()
    def updateColors(self):
        try:
            has_updates = _updates_count[0] > 0
            if has_updates:
                color_top, color_bottom = _COLOR_GREEN_TOP, _COLOR_GREEN_BOTTOM
            else:
                color_top, color_bottom = _COLOR_BLUE_TOP, _COLOR_BLUE_BOTTOM

            self.llayout.setBackground(_make_gradient_bg(color_top, color_bottom))
            if self.label_view:
                self.label_view.setTextColor(-1)  # white
                self.label_view.setText(_get_label())
            if self.icon_view:
                icon_res = _get_icon_res()
                if icon_res:
                    self.icon_view.setImageResource(icon_res)
                self.icon_view.setColorFilter(-1, PorterDuff.Mode.SRC_IN)  # white
            self.updateLoadingColors()
            _apply_press_anim(self.llayout, has_updates)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: updateColors error: {e}", False)

    @joverride()
    def setPressed(self, pressed: bool):
        super().setPressed(pressed)
        if self.llayout:
            self.llayout.setPressed(pressed)


class _UpdatesPillCreator(dynamic_proxy(PillRegistry.PillCreator)):
    def __init__(self, pill_class):
        super().__init__()
        self.clazz = pill_class

    def create(self, context, resources_provider):
        return self.clazz.new_instance(context, resources_provider).java


_plugin_ref = [None]
_active_pill_ref = [None]


def setup_updates_widget(plugin):
    logx("UpdatesWidget: setup start", True)
    try:
        _plugin_ref[0] = plugin
        _setup_save_hook(plugin)
        # check updates before registering so pill shows correct state from the start
        _prefetch_and_register(plugin)
        logx("UpdatesWidget: setup scheduled", True)
        return True
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: setup error: {e}", False)
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
        logx("UpdatesWidget: savePillsLayout hook installed", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _setup_save_hook error: {e}", False)


def _prefetch_and_register(plugin):
    from client_utils import run_on_queue

    def task():
        try:
            from ...ui.updates.Fragment import _check_updates, _filter_ignored
            updates = _filter_ignored(None, _check_updates(None))
            _updates_count[0] = len(updates)
            _updates_list[0] = updates
            logx(f"UpdatesWidget: prefetch done, count={_updates_count[0]}", True)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: prefetch error: {e}", False)
        run_on_ui_thread(lambda: _register_pill(plugin))

    run_io(task)


def _get_prefs():
    try:
        from hook_utils import find_class
        ApplicationLoader = find_class("org.telegram.messenger.ApplicationLoader")
        return ApplicationLoader.applicationContext.getSharedPreferences("packit_updates_pill", 0)
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
            logx(f"UpdatesWidget: saved state={state}", True)
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
        logx(f"UpdatesWidget: ensure_visibility state={state}", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _ensure_visibility error: {e}", False)


def _sync_state_from_config():
    # called while pill is live — saves current pillstack state to own prefs
    try:
        active = getattr(PillStackConfig, "activePills", None)
        hidden = getattr(PillStackConfig, "hiddenPills", None)
        if active is None or hidden is None:
            logx("UpdatesWidget: _sync_state_from_config: lists not available", True)
            return
        pid = jint(_PILL_ID)
        try:
            if active.contains(pid):
                _set_saved_state(1)
                idx = _active_index(active, pid)
                if idx >= 0:
                    _set_saved_index(idx)
                logx(f"UpdatesWidget: sync -> active, idx={idx}", True)
                return
        except Exception:
            pass
        try:
            if hidden.contains(pid):
                _set_saved_state(0)
                logx("UpdatesWidget: sync -> hidden", True)
                return
        except Exception:
            pass
        logx("UpdatesWidget: sync -> pill not found in either list", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _sync_state_from_config error: {e}", False)


def _register_pill(plugin):
    try:
        from elyx import strings
        from hook_utils import find_class
        pid = jint(_PILL_ID)
        # static name and icon for settings list — always shows "Available updates" / "Доступные обновления"
        static_name = str(strings['updates_widget_label'])
        R = find_class("org.telegram.messenger.R")
        static_icon = int(getattr(R.drawable, "msg_retry", 0))
        pill_info = PillRegistry.PillInfo(
            pid,
            static_name,
            static_icon,
            _COLOR_BLUE_TOP,
            _COLOR_BLUE_BOTTOM,
            _UpdatesPillCreator(UpdatesPill)
        )
        _ensure_visibility()
        PillRegistry.register(pill_info)
        _sync_pillstack()
        _notify_update()
        logx(f"UpdatesWidget: registered id={_PILL_ID}", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _register_pill error: {e}", False)


def _get_icon_res():
    try:
        from hook_utils import find_class
        R = find_class("org.telegram.messenger.R")
        if _updates_count[0] > 0:
            return int(getattr(R.drawable, "msg_download", 0))
        return int(getattr(R.drawable, "msg_retry", 0))
    except Exception:
        return 0


def _get_label():
    from elyx import strings
    count = _updates_count[0]
    if count == 1:
        return str(strings('updates_widget_one_update', count=count))
    if count > 1:
        return str(strings('updates_widget_many_updates', count=count))
    return str(strings['updates_widget_up_to_date'])


def _on_click(plugin, pill):
    count = _updates_count[0]
    if count == 1:
        _install_single(plugin, _updates_list[0][0])
    elif count > 1:
        _open_updates(plugin)
    else:
        _run_check(plugin, pill)


def _install_single(plugin, item):
    # installs the single available update directly, then re-checks on success
    from client_utils import run_on_queue
    from ...ui.updates.Fragment import _get_repos, _get_repo_plugins_url
    import requests as _req

    pid = str(item.get("id") or "")
    repo_id = str(item.get("repo_id") or "")

    def _on_installed(installed_pid):
        if installed_pid != pid:
            return
        try:
            from ...core.Core import remove_install_listener
            remove_install_listener(_on_installed)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: remove_install_listener error: {e}", False)
        _run_check(plugin, _active_pill_ref[0])

    def task():
        try:
            repos = _get_repos()
            repo = next((r for r in repos if str(r.get("id") or "") == repo_id), None)
            if not repo:
                logx(f"UpdatesWidget: _install_single repo '{repo_id}' not found", True)
                return
            repo_url = str(repo.get("url") or "").strip()
            plugins_url = _get_repo_plugins_url(None, repo_id, repo_url)
            r = _req.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
            if r.status_code != 200:
                logx(f"UpdatesWidget: _install_single HTTP {r.status_code}", True)
                return
            data = r.json()
            plugins_raw = data.get("plugins", {})
            plugin_data = None
            all_plugins = []
            if isinstance(plugins_raw, dict):
                for _pid, info in plugins_raw.items():
                    if isinstance(info, dict):
                        all_plugins.append({"id": _pid, **info})
                info = plugins_raw.get(pid)
                if isinstance(info, dict):
                    plugin_data = {"id": pid, **info}
            elif isinstance(plugins_raw, list):
                all_plugins = [p for p in plugins_raw if isinstance(p, dict)]
                for p in plugins_raw:
                    if isinstance(p, dict) and p.get("id") == pid:
                        plugin_data = p
                        break
            if not plugin_data:
                logx(f"UpdatesWidget: _install_single plugin '{pid}' not found in repo", True)
                return
            from ...core.Core import install_plugin, add_install_listener
            add_install_listener(_on_installed)
            from android_utils import run_on_ui_thread
            run_on_ui_thread(lambda: install_plugin(plugin_data, all_plugins=all_plugins, rm_rid=repo_id))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: _install_single task error: {e}", False)

    run_on_queue(task)


def _open_updates(plugin):
    try:
        from ...ui.updates.Fragment import show_updates_fragment
        show_updates_fragment(plugin)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _open_updates error: {e}", False)


def _run_check(plugin, pill=None):
    # runs update check in background with loading animation like TonPill
    from client_utils import run_on_queue

    def start_loading():
        try:
            if pill is not None:
                pill.animateSizeChange()
                pill.startLoading()
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: start_loading error: {e}", False)

    def finish_loading(count, updates):
        try:
            _updates_count[0] = count
            _updates_list[0] = updates
            if pill is not None:
                pill.animateSizeChange()
                pill.stopLoading()
                pill.updateColors()
            _notify_update()
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: finish_loading error: {e}", False)

    run_on_ui_thread(start_loading)

    def task():
        try:
            from ...ui.updates.Fragment import _check_updates, _filter_ignored
            updates = _filter_ignored(None, _check_updates(None))
            count = len(updates)
            run_on_ui_thread(lambda: finish_loading(count, updates))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"UpdatesWidget: _run_check task error: {e}", False)
            run_on_ui_thread(lambda: finish_loading(_updates_count[0], _updates_list[0]))

    run_on_queue(task)


def notify_updates_count(count: int):
    # called externally to update badge count
    _updates_count[0] = count
    run_on_ui_thread(_notify_update)


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
        logx("UpdatesWidget: pillstack synced", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _sync_pillstack error: {e}", False)


def _notify_update():
    try:
        def _do():
            try:
                PillStackConfig.notifySettingsChanged()
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"UpdatesWidget: _notify_update inner error: {e}", False)
        run_on_ui_thread(_do)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _notify_update error: {e}", False)


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
        logx(f"UpdatesWidget: _open_pill_stack_settings error: {e}", False)


def _show_menu(plugin, pill):
    try:
        from client_utils import get_last_fragment
        from org.telegram.ui.Components import ItemOptions
        from org.telegram.messenger import R as R_tg
        from elyx import strings

        fragment = get_last_fragment()
        if fragment is None:
            return

        options = ItemOptions.makeOptions(fragment, pill, True)

        def make_runnable(fn):
            class R(dynamic_proxy(JRunnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    fn()
            return R()

        icon_open = int(getattr(R_tg.drawable, "msg_plugins", 0))
        options.add(icon_open, str(strings["updates_title"]), make_runnable(lambda: _open_updates(plugin)))

        icon_refresh = int(getattr(R_tg.drawable, "msg_retry", 0))
        options.add(icon_refresh, str(strings["updates_btn_refresh"]), make_runnable(lambda: _run_check(plugin, _active_pill_ref[0])))

        options.addGap()

        def open_channel():
            try:
                from android.net import Uri
                from org.telegram.messenger.browser import Browser
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if act:
                    Browser.openUrl(act, Uri.parse(str(strings["tg_channel_url"])), True, True, True, None, None, False, False, False)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"UpdatesWidget: open channel error: {e}", False)

        icon_channel = int(getattr(R_tg.drawable, "msg_channel", 0))
        options.add(icon_channel, str(strings["packit_channel"]), make_runnable(open_channel))

        icon_settings = int(getattr(R_tg.drawable, "msg_settings", 0))
        options.add(icon_settings, str(strings["deeplinks_settings"]), make_runnable(_open_pill_stack_settings))

        options.setSwipebackGravity(True, False)
        options.setDrawScrim(False)
        options.setDimAlpha(0)
        options.show()
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"UpdatesWidget: _show_menu error: {e}", False)
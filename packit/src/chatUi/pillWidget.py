from android_utils import log, run_on_ui_thread
from base_plugin import MethodHook
from hook_utils import find_class
from java import jclass

_PILL_ID = 880001
_PILL_LABEL = "PackIt"


def setup_pill_widget(plugin):
    log("PillWidget: setup_pill_widget start")
    try:
        PillStackConfig = find_class("com.exteragram.messenger.pillstack.core.PillStackConfig")
        if PillStackConfig is None:
            log("PillWidget: PillStackConfig not found")
            return None
        log("PillWidget: PillStackConfig found")

        FragmentSearchField = find_class("org.telegram.ui.Components.FragmentSearchField")
        if FragmentSearchField is None:
            log("PillWidget: FragmentSearchField not found")
            return None
        log("PillWidget: FragmentSearchField found")

        getPillMethod = None
        for m in FragmentSearchField.getClass().getDeclaredMethods():
            try:
                if m.getName() == "getPill" and len(m.getParameterTypes()) == 1:
                    getPillMethod = m
                    break
            except Exception:
                continue

        if getPillMethod is None:
            log("PillWidget: getPill method not found")
            return None

        getPillMethod.setAccessible(True)
        log("PillWidget: getPill method found")

        updatePillStackMethod = None
        for m in FragmentSearchField.getClass().getDeclaredMethods():
            try:
                if m.getName() == "updatePillStack" and len(m.getParameterTypes()) == 1:
                    updatePillStackMethod = m
                    break
            except Exception:
                continue

        if updatePillStackMethod is None:
            log("PillWidget: updatePillStack method not found")
            return None

        updatePillStackMethod.setAccessible(True)
        log("PillWidget: updatePillStack method found")

        class UpdatePillStackHook(MethodHook):
            def before_hooked_method(self, param):
                try:
                    _inject_pill_id(PillStackConfig)
                except Exception as e:
                    log(f"PillWidget: UpdatePillStackHook.before error: {e}")

        class GetPillHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    pill_id = int(param.args[0])
                    if pill_id != _PILL_ID:
                        return
                    log("PillWidget: GetPillHook triggered for our id")
                    ctx = param.thisObject.getContext()
                    rp = _get_field(param.thisObject, "resourcesProvider")
                    pill = _create_packit_pill(ctx, rp, plugin)
                    if pill is not None:
                        param.setResult(pill)
                        log("PillWidget: pill instance set as result")
                    else:
                        log("PillWidget: pill creation returned None")
                except Exception as e:
                    log(f"PillWidget: GetPillHook.after error: {e}")

        ref1 = plugin.hook_method(updatePillStackMethod, UpdatePillStackHook())
        ref2 = plugin.hook_method(getPillMethod, GetPillHook())
        log("PillWidget: hooks installed")

        _notify_update()
        return (ref1, ref2)

    except Exception as e:
        log(f"PillWidget: setup_pill_widget error: {e}")
        return None


def _inject_pill_id(PillStackConfig):
    try:
        activePills = PillStackConfig.activePills
        Integer = jclass("java.lang.Integer")
        for i in range(activePills.size()):
            if int(activePills.get(i)) == _PILL_ID:
                return
        activePills.add(Integer(_PILL_ID))
        log(f"PillWidget: injected id {_PILL_ID} into activePills")
    except Exception as e:
        log(f"PillWidget: _inject_pill_id error: {e}")


def _notify_update():
    try:
        def _do():
            try:
                NotificationCenter = find_class("org.telegram.messenger.NotificationCenter")
                if NotificationCenter is None:
                    log("PillWidget: NotificationCenter not found for notify")
                    return
                nc = NotificationCenter.getGlobalInstance()
                event_id = int(NotificationCenter.pillStackLayoutChanged)
                # call via reflection (method name contains $ which is invalid Python syntax)
                Integer = jclass("java.lang.Integer")
                postMethod = None
                for m in nc.getClass().getMethods():
                    try:
                        if m.getName() == "postNotificationName":
                            postMethod = m
                            break
                    except Exception:
                        continue
                if postMethod:
                    postMethod.invoke(nc, [Integer(event_id), []])
                    log("PillWidget: pillStackLayoutChanged posted")
                else:
                    log("PillWidget: postNotificationName not found")
            except Exception as e:
                log(f"PillWidget: _notify_update inner error: {e}")
        run_on_ui_thread(_do)
    except Exception as e:
        log(f"PillWidget: _notify_update error: {e}")


def _get_field(obj, name):
    try:
        cls = obj.getClass()
        while cls is not None:
            try:
                f = cls.getDeclaredField(name)
                f.setAccessible(True)
                return f.get(obj)
            except Exception:
                try:
                    cls = cls.getSuperclass()
                except Exception:
                    break
        return None
    except Exception as e:
        log(f"PillWidget: _get_field({name}) error: {e}")
        return None


def _create_packit_pill(ctx, resourcesProvider, plugin):
    log("PillWidget: _create_packit_pill called")
    try:
        CachePill = find_class("com.exteragram.messenger.pillstack.ui.pills.system.CachePill")
        if CachePill is None:
            log("PillWidget: CachePill class not found")
            return None

        ctor = None
        for c in CachePill.getClass().getDeclaredConstructors():
            try:
                if len(c.getParameterTypes()) == 2:
                    ctor = c
                    break
            except Exception:
                continue

        if ctor is None:
            log("PillWidget: CachePill constructor(Context, ResourcesProvider) not found")
            return None

        ctor.setAccessible(True)
        pill = ctor.newInstance([ctx, resourcesProvider])
        log("PillWidget: CachePill instance created, patching")

        _patch_pill_ui(pill, ctx, resourcesProvider)
        _patch_pill_hooks(pill, plugin, resourcesProvider)
        return pill

    except Exception as e:
        log(f"PillWidget: _create_packit_pill error: {e}")
        return None


def _patch_pill_ui(pill, ctx, resourcesProvider):
    try:
        from android.widget import LinearLayout, ImageView, TextView
        from android.view import Gravity
        from org.telegram.messenger import AndroidUtilities, LocaleController
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import LayoutHelper

        pill.removeAllViews()

        layout = LinearLayout(ctx)
        layout.setOrientation(LinearLayout.HORIZONTAL)
        layout.setGravity(Gravity.CENTER)
        layout.setMinimumWidth(AndroidUtilities.dp(48))
        layout.setPadding(AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8), 0)
        gravity = Gravity.CENTER_VERTICAL | (3 if LocaleController.isRTL else 5)
        pill.addView(layout, LayoutHelper.createFrame(-2, 28, gravity))

        icon = ImageView(ctx)
        icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        try:
            R = find_class("org.telegram.messenger.R")
            icon_res = int(getattr(R.drawable, "msg_plugins"))
            icon.setImageResource(icon_res)
        except Exception as e:
            log(f"PillWidget: icon load error: {e}")
        layout.addView(icon, LayoutHelper.createLinear(16, 16, 16, 0, 0, 6, 0))

        label = TextView(ctx)
        label.setText(_PILL_LABEL)
        label.setTextSize(13)
        label.setSingleLine(True)
        label.setIncludeFontPadding(False)
        layout.addView(label, LayoutHelper.createLinear(-2, -2, 16))

        # store refs as tag for color hook
        pill.setTag([layout, icon, label])

        _apply_colors(layout, label, icon, resourcesProvider)
        log("PillWidget: pill UI patched")

    except Exception as e:
        log(f"PillWidget: _patch_pill_ui error: {e}")


def _patch_pill_hooks(pill, plugin, resourcesProvider):
    try:
        pillCls = pill.getClass()

        for m in pillCls.getDeclaredMethods():
            try:
                name = m.getName()
                m.setAccessible(True)

                if name == "getPillId":
                    class GetPillIdHook(MethodHook):
                        def after_hooked_method(self, param):
                            param.setResult(jclass("java.lang.Integer")(_PILL_ID))
                    plugin.hook_method(m, GetPillIdHook())

                elif name == "onPillClicked":
                    class OnPillClickedHook(MethodHook):
                        def before_hooked_method(self, param):
                            run_on_ui_thread(lambda: _open_settings(plugin))
                            param.setResult(None)
                    plugin.hook_method(m, OnPillClickedHook())

                elif name == "onPillLongClicked":
                    class OnPillLongClickedHook(MethodHook):
                        def before_hooked_method(self, param):
                            run_on_ui_thread(lambda: _open_settings(plugin))
                            param.setResult(True)
                    plugin.hook_method(m, OnPillLongClickedHook())

                elif name == "onUpdateData":
                    class OnUpdateDataHook(MethodHook):
                        def before_hooked_method(self, param):
                            param.setResult(None)
                    plugin.hook_method(m, OnUpdateDataHook())

                elif name == "updateColors":
                    _rp = resourcesProvider
                    class UpdateColorsHook(MethodHook):
                        def before_hooked_method(self, param):
                            try:
                                tag = param.thisObject.getTag()
                                if tag and len(tag) == 3:
                                    _apply_colors(tag[0], tag[2], tag[1], _rp)
                            except Exception as e:
                                log(f"PillWidget: UpdateColorsHook error: {e}")
                            param.setResult(None)
                    plugin.hook_method(m, UpdateColorsHook())

            except Exception as e:
                log(f"PillWidget: hook install error for {name}: {e}")

        log("PillWidget: behaviour hooks installed")

    except Exception as e:
        log(f"PillWidget: _patch_pill_hooks error: {e}")


def _apply_colors(layout, label, icon, resourcesProvider):
    try:
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.messenger import AndroidUtilities

        color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        alpha75 = Theme.multAlpha(color, 0.75)
        is_dark = Theme.isCurrentThemeDark()
        bg_normal = Theme.getColor(Theme.key_windowBackgroundWhite) if is_dark else Theme.multAlpha(alpha75, 0.09)
        bg = Theme.createSimpleSelectorRoundRectDrawable(AndroidUtilities.dp(14), bg_normal, Theme.multAlpha(alpha75, 0.1))
        layout.setBackground(bg)
        label.setTextColor(alpha75)
        try:
            from android.graphics import PorterDuff
            icon.setColorFilter(alpha75, PorterDuff.Mode.SRC_IN)
        except Exception as e:
            log(f"PillWidget: icon color filter error: {e}")
    except Exception as e:
        log(f"PillWidget: _apply_colors error: {e}")


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

import math
from android_utils import log, run_on_ui_thread, OnClickListener
from base_plugin import MethodHook
from hook_utils import find_class


def setup_icon_packs_activity_fab(plugin):
    try:
        AppearanceClass = find_class(
            "com.exteragram.messenger.preferences.appearance.AppearancePreferencesActivity"
        )
        if AppearanceClass is None:
            log("addIconsFab: AppearancePreferencesActivity not found")
            return None

        target = None
        for m in AppearanceClass.getClass().getDeclaredMethods():
            params = [p.getName() for p in m.getParameterTypes()]
            if params == [
                "org.telegram.ui.Components.UItem",
                "android.view.View",
                "int",
                "float",
                "float",
            ]:
                target = m
                break

        if target is None:
            log("addIconsFab: onClick method not found in AppearancePreferencesActivity")
            return None

        target.setAccessible(True)

        state = {"hook_ref": None, "installed": False}

        class OnClickHook(MethodHook):
            def after_hooked_method(self_hook, param):
                if state["installed"]:
                    return
                hook_ref = _try_install_create_view_hook(plugin, param.thisObject)
                if hook_ref is not None:
                    state["hook_ref"] = hook_ref
                    state["installed"] = True

        hook_ref = plugin.hook_method(target, OnClickHook())
        log("addIconsFab: AppearancePreferencesActivity.onClick hooked, waiting for navigation")
        return hook_ref
    except Exception as e:
        log(f"addIconsFab: setup_icon_packs_activity_fab error: {e}")
        return None


def _try_install_create_view_hook(plugin, appearance_instance):
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        if frag is None:
            log("addIconsFab: no last fragment after onClick")
            return None

        frag_class = frag.getClass()
        real_name = frag_class.getName()
        log(f"addIconsFab: last fragment = {real_name}")


        # verify it's a BasePreferencesActivity subclass
        superclass = frag_class.getSuperclass()
        while superclass is not None:
            if superclass.getName() == "com.exteragram.messenger.preferences.BasePreferencesActivity":
                break
            superclass = superclass.getSuperclass()
        else:
            log(f"addIconsFab: {real_name} is not a BasePreferencesActivity subclass, skipping")
            return None

        # find createView(Context) -> View by signature
        create_view_method = None
        for m in frag_class.getDeclaredMethods():
            params = m.getParameterTypes()
            if (len(params) == 1
                    and params[0].getName() == "android.content.Context"
                    and m.getReturnType().getName() == "android.view.View"):
                create_view_method = m
                break

        if create_view_method is None:
            log(f"addIconsFab: createView not found on {real_name}")
            return None

        create_view_method.setAccessible(True)
        log(f"addIconsFab: found createView on {real_name}, installing hook")

        class CreateViewHook(MethodHook):
            def after_hooked_method(self_hook, param):
                try:
                    frag_view = param.getResult()
                    if frag_view is None:
                        log("addIconsFab: createView returned null")
                        return
                    log("addIconsFab: createView fired, injecting FAB")
                    run_on_ui_thread(lambda: _inject_fab(plugin, frag_view))
                except Exception as e:
                    log(f"addIconsFab: after_hooked_method error: {e}")

        hook_ref = plugin.hook_method(create_view_method, CreateViewHook())
        log(f"addIconsFab: {real_name}.createView hooked")

        # createView already ran for current visit — inject into live view immediately
        try:
            current_view = frag.getFragmentView()
            if current_view is not None:
                log("addIconsFab: injecting FAB into current live view")
                run_on_ui_thread(lambda: _inject_fab(plugin, current_view))
            else:
                log("addIconsFab: getFragmentView returned null, will inject on next createView")
        except Exception as e:
            log(f"addIconsFab: immediate inject error: {e}")

        return hook_ref
    except Exception as e:
        log(f"addIconsFab: _try_install_create_view_hook error: {e}")
        return None


def _inject_fab(plugin, frag_view):
    log(f"addIconsFab: _inject_fab called, view={frag_view}")
    try:
        from elyx import settings
        if not settings.get("show_icon_packs_fab", True):
            log("addIconsFab: show_icon_packs_fab is disabled, skipping")
            return
    except Exception:
        pass
    try:
        from android.widget import FrameLayout, ImageView
        from android.view import Gravity
        from android.graphics.drawable import GradientDrawable
        from org.telegram.messenger import AndroidUtilities
        from org.telegram.ui.ActionBar import Theme

        # same size/margins as FragmentFloatingButton.createDefaultLayoutParams(): 48dp, margin 20/14
        fab_size_dp = 48
        fab_size = AndroidUtilities.dp(fab_size_dp)
        margin_side = AndroidUtilities.dp(20)
        margin_bottom = AndroidUtilities.dp(14)

        squareFab = False
        try:
            ExteraConfig = find_class("com.exteragram.messenger.ExteraConfig")
            squareFab = bool(ExteraConfig.squareFab)
        except Exception:
            pass

        btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)

        bg = GradientDrawable()
        if squareFab:
            bg.setShape(GradientDrawable.RECTANGLE)
            corner = AndroidUtilities.dp(float(math.ceil(fab_size_dp * 16.0 / 56.0)))
            bg.setCornerRadius(corner)
        else:
            bg.setShape(GradientDrawable.OVAL)
        bg.setColor(btn_base)

        ctx = frag_view.getContext()
        fab = FrameLayout(ctx)
        fab.setClickable(True)
        fab.setFocusable(True)
        fab.setBackground(bg)
        try:
            fab.setTranslationZ(AndroidUtilities.dpf2(0.5))
        except Exception:
            pass

        fab_icon = ImageView(ctx)
        fab_icon.setScaleType(ImageView.ScaleType.CENTER)
        try:
            R_tg = find_class("org.telegram.messenger.R")
            icon_id = getattr(R_tg.drawable, "msg_addbot", 0)
            fab_icon.setImageResource(icon_id)
            fab_icon.setColorFilter(Theme.getColor(Theme.key_chats_actionIcon))
        except Exception as e:
            log(f"addIconsFab: icon setup error: {e}")
        fab.addView(fab_icon, FrameLayout.LayoutParams(-1, -1))

        def on_fab_click(v):
            try:
                from ..ui.IconsListActivity.fragment import InstallIconsUI
                InstallIconsUI(plugin).open()
            except Exception as e:
                log(f"addIconsFab: on_fab_click error: {e}")

        fab.setOnClickListener(OnClickListener(on_fab_click))

        fab_lp = FrameLayout.LayoutParams(fab_size, fab_size)
        fab_lp.gravity = Gravity.BOTTOM | Gravity.START
        fab_lp.leftMargin = margin_side
        fab_lp.bottomMargin = margin_bottom

        frag_view.addView(fab, fab_lp)
        fab.bringToFront()

        log(f"addIconsFab: FAB injected, view child count={frag_view.getChildCount()}")
    except Exception as e:
        log(f"addIconsFab: _inject_fab error: {e}")

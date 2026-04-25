import math
from android_utils import log, run_on_ui_thread, OnClickListener
from base_plugin import MethodHook
from hook_utils import find_class


def setup_plugins_activity_fab(plugin):
    try:
        PluginsActivityClass = find_class(
            "com.exteragram.messenger.plugins.ui.PluginsActivity"
        )
        if PluginsActivityClass is None:
            log("addPluginFab: PluginsActivity not found")
            return None

        ContextClass = find_class("android.content.Context")
        create_view_method = PluginsActivityClass.getClass().getDeclaredMethod(
            "createView", ContextClass
        )
        create_view_method.setAccessible(True)

        class PluginsActivityCreateViewHook(MethodHook):
            def after_hooked_method(self_hook, param):
                try:
                    frag_view = param.getResult()
                    if frag_view is None:
                        return
                    run_on_ui_thread(lambda: _inject_fab(plugin, frag_view))
                except Exception as e:
                    log(f"addPluginFab: after_hooked_method error: {e}")

        hook_ref = plugin.hook_method(create_view_method, PluginsActivityCreateViewHook())
        log("addPluginFab: PluginsActivity.createView hooked")
        return hook_ref
    except Exception as e:
        log(f"addPluginFab: setup_plugins_activity_fab error: {e}")
        return None


def _inject_fab(plugin, frag_view):
    try:
        from elyx import settings
        if not settings.get("show_plugin_list_fab", True):
            return
    except Exception:
        pass
    try:
        from android.widget import FrameLayout, ImageView
        from android.view import Gravity
        from android.graphics.drawable import GradientDrawable
        from org.telegram.messenger import AndroidUtilities
        from org.telegram.ui.ActionBar import Theme

        squareFab = True
        try:
            ExteraConfig = find_class("com.exteragram.messenger.ExteraConfig")
            squareFab = bool(ExteraConfig.squareFab)
        except Exception:
            pass

        try:
            btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
            btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
        except Exception:
            from android.graphics import Color
            btn_base = Color.parseColor("#2196F3")
            btn_text_color = 0xFFFFFFFF

        fab_size_dp = 56
        fab_size = AndroidUtilities.dp(fab_size_dp)
        fab_margin = AndroidUtilities.dp(16)

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
            fab.setElevation(AndroidUtilities.dp(4))
        except Exception:
            pass

        fab_icon = ImageView(ctx)
        fab_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        try:
            R_tg = find_class("org.telegram.messenger.R")
            icon_id = getattr(R_tg.drawable, "msg_addbot", 0)
            fab_icon.setImageResource(icon_id)
            fab_icon.setColorFilter(btn_text_color)
        except Exception:
            pass
        fab.addView(fab_icon, FrameLayout.LayoutParams(fab_size, fab_size))

        state_ref = {"animating": False}

        def on_fab_click(v):
            try:
                from ..ui.PluginListActivity.fragment import InstallUI
                InstallUI(plugin).open()
            except Exception as e:
                log(f"addPluginFab: on_fab_click error: {e}")

        fab.setOnClickListener(OnClickListener(on_fab_click))

        _attach_press_animation(fab, state_ref)

        fab_lp = FrameLayout.LayoutParams(fab_size, fab_size)
        fab_lp.gravity = Gravity.BOTTOM | Gravity.END
        fab_lp.rightMargin = fab_margin
        fab_lp.bottomMargin = fab_margin

        frag_view.addView(fab, fab_lp)
        fab.bringToFront()

        _attach_scroll_listener(frag_view, fab, fab_lp, fab_margin, state_ref)

        log("addPluginFab: FAB injected into PluginsActivity")
    except Exception as e:
        log(f"addPluginFab: _inject_fab error: {e}")


def _attach_scroll_listener(frag_view, fab, fab_lp, fab_margin, state_ref):
    try:
        from androidx.recyclerview.widget import RecyclerView
        from android.animation import AnimatorSet, ObjectAnimator
        from android.view import View
        from extera_utils.classes import Base, java_subclass, joverride

        list_view = None
        for i in range(frag_view.getChildCount()):
            child = frag_view.getChildAt(i)
            if child is not None and isinstance(child, RecyclerView):
                list_view = child
                break

        if list_view is None:
            return

        state_ref["at_bottom"] = False

        def _animate_hide():
            if state_ref["animating"]:
                return
            state_ref["animating"] = True

            scale_x_out = ObjectAnimator.ofFloat(fab, "scaleX", 1.0, 0.0)
            scale_y_out = ObjectAnimator.ofFloat(fab, "scaleY", 1.0, 0.0)
            alpha_out = ObjectAnimator.ofFloat(fab, "alpha", 1.0, 0.0)
            rotate_out = ObjectAnimator.ofFloat(fab, "rotation", 0.0, 90.0)
            scale_x_out.setDuration(180)
            scale_y_out.setDuration(180)
            alpha_out.setDuration(180)
            rotate_out.setDuration(180)

            phase1 = AnimatorSet()
            phase1.playTogether(scale_x_out, scale_y_out, alpha_out, rotate_out)

            def on_hide_end():
                try:
                    fab.setVisibility(View.GONE)
                    state_ref["animating"] = False
                except Exception as e:
                    log(f"addPluginFab: on_hide_end error: {e}")

            phase1.addListener(_make_end_listener(on_hide_end))
            phase1.start()

        def _animate_show():
            if state_ref["animating"]:
                return
            state_ref["animating"] = True

            fab.setVisibility(View.VISIBLE)
            fab.setRotation(-90.0)
            fab.setScaleX(0.0)
            fab.setScaleY(0.0)
            fab.setAlpha(0.0)

            # overshoot: grow past 1.0 then snap back
            scale_x_in = ObjectAnimator.ofFloat(fab, "scaleX", 0.0, 1.25, 1.0)
            scale_y_in = ObjectAnimator.ofFloat(fab, "scaleY", 0.0, 1.25, 1.0)
            alpha_in = ObjectAnimator.ofFloat(fab, "alpha", 0.0, 1.0)
            rotate_in = ObjectAnimator.ofFloat(fab, "rotation", -90.0, 0.0)
            scale_x_in.setDuration(280)
            scale_y_in.setDuration(280)
            alpha_in.setDuration(200)
            rotate_in.setDuration(280)

            phase2 = AnimatorSet()
            phase2.playTogether(scale_x_in, scale_y_in, alpha_in, rotate_in)

            def on_show_end():
                try:
                    state_ref["animating"] = False
                except Exception as e:
                    log(f"addPluginFab: on_show_end error: {e}")

            phase2.addListener(_make_end_listener(on_show_end))
            phase2.start()

        def update_fab_visibility(rv):
            at_bottom = not rv.canScrollVertically(1)
            if at_bottom == state_ref["at_bottom"]:
                return
            state_ref["at_bottom"] = at_bottom
            if at_bottom:
                run_on_ui_thread(_animate_hide)
            else:
                run_on_ui_thread(_animate_show)

        # fires once when scroll stops — no per-frame cost
        @java_subclass(RecyclerView.OnScrollListener)
        class FabScrollListener(Base):
            @joverride()
            def onScrollStateChanged(self, rv, newState):
                try:
                    if newState == 0:  # SCROLL_STATE_IDLE
                        update_fab_visibility(rv)
                except Exception as e:
                    log(f"addPluginFab: onScrollStateChanged error: {e}")

        list_view.addOnScrollListener(FabScrollListener.new_java_instance())
    except Exception as e:
        log(f"addPluginFab: _attach_scroll_listener error: {e}")


def _attach_press_animation(fab, state_ref):
    try:
        from android.view import MotionEvent, View
        from java import dynamic_proxy

        def _on_touch(v, event):
            try:
                if state_ref["animating"]:
                    return False
                action = event.getActionMasked()
                if action == MotionEvent.ACTION_DOWN:
                    fab.animate().scaleX(0.88).scaleY(0.88).alpha(0.72).setDuration(120).start()
                elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    fab.animate().scaleX(1.0).scaleY(1.0).alpha(1.0).setDuration(220).start()
            except Exception as e:
                log(f"addPluginFab: press touch error: {e}")
            return False

        class _TL(dynamic_proxy(View.OnTouchListener)):
            def onTouch(self, v, event):
                return _on_touch(v, event)

        fab.setOnTouchListener(_TL())
    except Exception as e:
        log(f"addPluginFab: _attach_press_animation error: {e}")


def _make_end_listener(on_end):
    from android.animation import Animator
    from java import dynamic_proxy

    class _Listener(dynamic_proxy(Animator.AnimatorListener)):
        def onAnimationEnd(self, a, *args):
            try:
                on_end()
            except Exception as e:
                log(f"addPluginFab: AnimatorListener.onAnimationEnd error: {e}")

        def onAnimationStart(self, a, *args): pass

        def onAnimationCancel(self, a, *args): pass

        def onAnimationRepeat(self, a, *args): pass

    return _Listener()

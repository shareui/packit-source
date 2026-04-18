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

        def on_fab_click(v):
            try:
                from ..ui.PluginListActivity.fragment import InstallUI
                InstallUI(plugin).open()
            except Exception as e:
                log(f"addPluginFab: on_fab_click error: {e}")

        fab.setOnClickListener(OnClickListener(on_fab_click))

        fab_lp = FrameLayout.LayoutParams(fab_size, fab_size)
        fab_lp.gravity = Gravity.BOTTOM | Gravity.END
        fab_lp.rightMargin = fab_margin
        fab_lp.bottomMargin = fab_margin

        frag_view.addView(fab, fab_lp)
        fab.bringToFront()

        log("addPluginFab: FAB injected into PluginsActivity")
    except Exception as e:
        log(f"addPluginFab: _inject_fab error: {e}")

import math
from android_utils import log, run_on_ui_thread, OnClickListener
from base_plugin import MethodHook
from hook_utils import find_class


def setup_icon_packs_activity_fab(plugin):
    try:
        IconPacksActivityClass = find_class(
            "com.exteragram.messenger.icons.ui.IconPacksActivity"
        )
        if IconPacksActivityClass is None:
            log("addIconsFab: IconPacksActivity not found")
            return None

        ContextClass = find_class("android.content.Context")
        create_view_method = IconPacksActivityClass.getClass().getDeclaredMethod(
            "createView", ContextClass
        )
        create_view_method.setAccessible(True)

        class IconPacksActivityCreateViewHook(MethodHook):
            def after_hooked_method(self_hook, param):
                try:
                    frag_view = param.getResult()
                    if frag_view is None:
                        return
                    run_on_ui_thread(lambda: _inject_fab(plugin, frag_view))
                except Exception as e:
                    log(f"addIconsFab: after_hooked_method error: {e}")

        hook_ref = plugin.hook_method(create_view_method, IconPacksActivityCreateViewHook())
        log("addIconsFab: IconPacksActivity.createView hooked")
        return hook_ref
    except Exception as e:
        log(f"addIconsFab: setup_icon_packs_activity_fab error: {e}")
        return None


def _inject_fab(plugin, frag_view):
    try:
        from elyx import settings
        if not settings.get("show_icon_packs_fab", True):
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
        except Exception:
            pass
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

        log("addIconsFab: FAB injected into IconPacksActivity")
    except Exception as e:
        log(f"addIconsFab: _inject_fab error: {e}")

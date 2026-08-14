# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import math
from android_utils import run_on_ui_thread, OnClickListener
from base_plugin import MethodHook
from hook_utils import find_class

FAB_TAG = "packit_icons_fab"


def setup_icon_packs_activity_fab(plugin):
    # direct hook on the real (non-obfuscated) icon packs activity, mirroring
    # addPluginFab: hook IconPacksActivity.createView and inject the FAB.
    try:
        IconPacksActivityClass = find_class(
            "com.exteragram.messenger.icons.ui.IconPacksActivity"
        )
        if IconPacksActivityClass is None:
            logx("addIconsFab: IconPacksActivity not found", True)
            return None

        ContextClass = find_class("android.content.Context")
        create_view_method = IconPacksActivityClass.getClass().getDeclaredMethod(
            "createView", ContextClass
        )
        create_view_method.setAccessible(True)

        class IconPacksCreateViewHook(MethodHook):
            def after_hooked_method(self_hook, param):
                try:
                    frag_view = param.getResult()
                    if frag_view is None:
                        return
                    fragment = param.thisObject
                    run_on_ui_thread(lambda: _inject_fab(plugin, frag_view, fragment))
                except Exception as e:
                    logx(f"addIconsFab: after_hooked_method error: {e}", False)

        hook_refs = [plugin.hook_method(create_view_method, IconPacksCreateViewHook())]
        logx("addIconsFab: IconPacksActivity.createView hooked", True)

        # the native FAB is lifted above the nav bar by onInsets
        # (floatingButton.setTranslationY(-bottom)); keep ours level with it
        try:
            from java.lang import Integer
            on_insets_method = IconPacksActivityClass.getClass().getDeclaredMethod(
                "onInsets", Integer.TYPE, Integer.TYPE, Integer.TYPE, Integer.TYPE
            )
            on_insets_method.setAccessible(True)

            class IconPacksInsetsHook(MethodHook):
                def after_hooked_method(self_hook, param):
                    try:
                        bottom = param.args[3]
                        root = param.thisObject.fragmentView
                        if root is None:
                            return
                        fab = root.findViewWithTag(FAB_TAG)
                        if fab is not None:
                            fab.setTranslationY(-float(bottom))
                    except Exception as e:
                        logx(f"addIconsFab: onInsets hook error: {e}", False)

            hook_refs.append(plugin.hook_method(on_insets_method, IconPacksInsetsHook()))
            logx("addIconsFab: IconPacksActivity.onInsets hooked", True)
        except Exception as e:
            logx(f"addIconsFab: onInsets hook setup error: {e}", False)

        return hook_refs
    except Exception as e:
        logx(f"addIconsFab: setup_icon_packs_activity_fab error: {e}", False)
        return None


def _inject_fab(plugin, frag_view, fragment=None):
    logx(f"addIconsFab: _inject_fab called, view={frag_view}", True)
    try:
        from elyx import settings
        if not settings.get("show_icon_packs_fab", True):
            logx("addIconsFab: show_icon_packs_fab is disabled, skipping", True)
            return
    except Exception:
        pass
    try:
        if frag_view.findViewWithTag(FAB_TAG) is not None:
            logx("addIconsFab: FAB already injected, skipping", True)
            return
    except Exception:
        pass
    try:
        from android.widget import FrameLayout, ImageView
        from android.view import Gravity
        from android.graphics.drawable import GradientDrawable
        from org.telegram.messenger import AndroidUtilities
        from org.telegram.ui.ActionBar import Theme

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
            logx(f"addIconsFab: icon setup error: {e}", False)
        fab.addView(fab_icon, FrameLayout.LayoutParams(-1, -1))

        def on_fab_click(v):
            try:
                from ..ui.iconslistactivity.Fragment import InstallIconsUI
                InstallIconsUI(plugin).open()
            except Exception as e:
                logx(f"addIconsFab: on_fab_click error: {e}", False)

        fab.setOnClickListener(OnClickListener(on_fab_click))

        fab_lp = FrameLayout.LayoutParams(fab_size, fab_size)
        fab_lp.gravity = Gravity.BOTTOM | Gravity.START
        fab_lp.leftMargin = margin_side
        fab_lp.bottomMargin = margin_bottom

        fab.setTag(FAB_TAG)
        frag_view.addView(fab, fab_lp)
        fab.bringToFront()

        # match the native FAB, which onInsets lifts above the nav bar
        try:
            if fragment is not None:
                fab.setTranslationY(-float(fragment.getBottomInset()))
        except Exception as e:
            logx(f"addIconsFab: bottom inset error: {e}", False)

        logx(f"addIconsFab: FAB injected, view child count={frag_view.getChildCount()}", True)
    except Exception as e:
        logx(f"addIconsFab: _inject_fab error: {e}", False)
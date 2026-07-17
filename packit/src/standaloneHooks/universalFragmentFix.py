# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from base_plugin import MethodHook
from hook_utils import find_class


def setup_universal_fragment_fix(plugin):
    # UniversalFragment.createView returns the delegate's beforeCreateView()
    # view without assigning BaseFragment.fragmentView, and ActionBarLayout
    # never assigns it either. With fragmentView == null,
    # getLayoutContainer() is null and Bulletin.show() silently no-ops, so
    # no bulletin ever appears on PackIt screens. Mirror what stock
    # fragments do: set fragmentView to whatever createView returned.
    try:
        UniversalFragmentClass = find_class(
            "com.exteragram.messenger.plugins.ui.components.templates.UniversalFragment"
        )
        if UniversalFragmentClass is None:
            logx("universalFragmentFix: UniversalFragment not found", True)
            return None

        ContextClass = find_class("android.content.Context")
        create_view_method = UniversalFragmentClass.getClass().getDeclaredMethod(
            "createView", ContextClass
        )
        create_view_method.setAccessible(True)

        class CreateViewFragmentViewHook(MethodHook):
            def after_hooked_method(self_hook, param):
                try:
                    view = param.getResult()
                    if view is None:
                        return
                    param.thisObject.fragmentView = view
                except Exception as e:
                    logx(f"universalFragmentFix: after_hooked_method error: {e}", False)

        hook_ref = plugin.hook_method(create_view_method, CreateViewFragmentViewHook())
        logx("universalFragmentFix: UniversalFragment.createView hooked", True)
        return hook_ref
    except Exception as e:
        logx(f"universalFragmentFix: setup error: {e}", False)
        return None

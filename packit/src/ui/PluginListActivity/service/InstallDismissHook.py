# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from base_plugin import MethodHook
from hook_utils import find_class



class _InstallSuccessHook(MethodHook):
    def after_hooked_method(self, param):
        try:
            error_str = param.args[1]
            if error_str is not None:
                return
            try:
                from ....ui.AchievementsActivity.service.AchivementsEngine import increment_category
                increment_category("Installing plugins")
            except Exception as e:
                logx(f"installSuccessHook: achievements increment error: {e}", False)
            from ....utils.installIndex import commit_pending
            commit_pending()
        except Exception as e:
            logx(f"installSuccessHook: error: {e}", False)


def setup_install_dismiss_hook(plugin) -> list:
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
            logx("installDismissHook: InstallPluginBottomSheet not found", True)
            return hooks

        target = None
        for m in InstallSheet.getClass().getDeclaredMethods():
            params = m.getParameterTypes()
            names = [p.getName() for p in params]
            if (len(params) == 3
                    and names[0] == "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
                    and names[1] == "java.lang.String"
                    and names[2] == "org.telegram.ui.ActionBar.BaseFragment"):
                target = m
                break

        if target is None:
            logx("installDismissHook: load callback lambda not found", True)
            return hooks

        target.setAccessible(True)
        hooks.append(plugin.hook_method(target, _InstallSuccessHook()))
        logx(f"installDismissHook: install success hook registered ({target.getName()})", True)
    except Exception as e:
        logx(f"installDismissHook: setup error: {e}", False)

    return hooks
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log


class _InstallSuccessHook(MethodHook):
    # hooks obfuscated lambda: (InstallPluginBottomSheet, String loadError, BaseFragment)
    # args[1]=loadError, null means successful install

    def after_hooked_method(self, param):
        try:
            error_str = param.args[1]
            if error_str is not None:
                return
            try:
                from ....ui.AchievementsActivity.service.AchivementsEngine import increment_category
                increment_category("Installing plugins")
            except Exception as e:
                log(f"installSuccessHook: achievements increment error: {e}")
            from ....utils.installIndex import commit_pending
            commit_pending()
        except Exception as e:
            log(f"installSuccessHook: error: {e}")


def setup_install_dismiss_hook(plugin) -> list:
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
            log("installDismissHook: InstallPluginBottomSheet not found")
            return hooks

        # after R8/lsparanoid obfuscation lambda names change, so match by parameter types:
        # (InstallPluginBottomSheet, String, BaseFragment)
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
            log("installDismissHook: load callback lambda not found")
            return hooks

        target.setAccessible(True)
        hooks.append(plugin.hook_method(target, _InstallSuccessHook()))
        log(f"installDismissHook: install success hook registered ({target.getName()})")
    except Exception as e:
        log(f"installDismissHook: setup error: {e}")

    return hooks

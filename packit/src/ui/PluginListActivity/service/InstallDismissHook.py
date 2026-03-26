from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log


class _InstallSuccessHook(MethodHook):
    # hooks lambda$new$6(String str, PluginValidationResult, BaseFragment)
    # str == null means successful install via PluginsController, non-null means error

    def after_hooked_method(self, param):
        try:
            error_str = param.args[0]
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
        PluginValidationResult = find_class(
            "com.exteragram.messenger.plugins.PluginsController$PluginValidationResult"
        )
        BaseFragment = find_class("org.telegram.ui.ActionBar.BaseFragment")
        String = find_class("java.lang.String")
        if not InstallSheet:
            log("installDismissHook: InstallPluginBottomSheet not found")
            return hooks

        method = InstallSheet.getClass().getDeclaredMethod(
            "lambda$new$6", String, PluginValidationResult, BaseFragment
        )
        method.setAccessible(True)
        hooks.append(plugin.hook_method(method, _InstallSuccessHook()))
        log("installDismissHook: install success hook registered")
    except Exception as e:
        log(f"installDismissHook: setup error: {e}")

    return hooks

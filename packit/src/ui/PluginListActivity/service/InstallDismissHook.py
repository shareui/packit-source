from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log


class _DismissHook(MethodHook):

    def after_hooked_method(self, param):
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
            increment_category("Installing plugins")
        except Exception as e:
            log(f"installDismissHook: achievements increment error: {e}")


def setup_install_dismiss_hook(plugin) -> list:
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
            log("installDismissHook: InstallPluginBottomSheet not found")
            return hooks

        method = InstallSheet.getClass().getDeclaredMethod("dismiss")
        method.setAccessible(True)
        hooks.append(plugin.hook_method(method, _DismissHook()))
        log("installDismissHook: dismiss hook registered")
    except Exception as e:
        log(f"installDismissHook: setup error: {e}")
    return hooks

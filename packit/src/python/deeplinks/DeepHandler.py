# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import run_on_ui_thread
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment

try:
    from elyx import strings as _dh_strings
except Exception:
    _dh_strings = None

from . import MainMenu
from . import Settings
from . import DeeplinkMenu
from . import Other
from . import Contributors
from . import Docs
from . import Forum
from . import Repo
from . import Install
from . import Update
from . import Problems
from . import Pkill
from . import Plugin
from .secret import Premium
from .secret import Terraria
from .secret import Aytist
from . import Suggestion


class PackItDeeplinkHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin
        self.pending_intent = None
        self.pending_param = None
        self.is_processing = False

    def before_hooked_method(self, param):
        try:
            if len(param.args) < 7:
                return

            intent = param.args[0]
            if not intent or intent.getAction() != "android.intent.action.VIEW":
                return

            data = intent.getData()
            if not data:
                return

            url = str(data)
            if url.startswith("tg://packit"):
                _params = url.split("?", 1)[1] if "?" in url else ""
                logx(f'[PackIt] link "{url}" is triggered, parameters: {_params}', True)
                self.pending_intent = intent
                self.pending_param = param
                param.setResult(None)
                run_on_ui_thread(lambda: self.show_packit_notification(url))
                return
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"[PackIt] Error in deeplink hook: {e}", False)

    def show_packit_notification(self, url):
        try:
            MainMenu.handle(url)
            Settings.handle(url, self.plugin)
            DeeplinkMenu.handle(url)
            Other.handle(url)
            Contributors.handle(url)
            Docs.handle(url)
            Forum.handle(url)
            Repo.handle(url, self.plugin.repoManager)
            Install.handle(url, self.plugin.repoManager)
            Update.handle(url, self.plugin.repoManager)
            Problems.handle(url)
            Pkill.handle(url)
            Plugin.handle(url, self.plugin.repoManager)
            Premium.handle(url)
            Terraria.handle(url)
            Aytist.handle(url)
            Suggestion.handle(url, self.plugin)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"[PackIt] Error showing notification: {e}", False)
            try:
                fragment = get_last_fragment()
                activity = fragment.getParentActivity() if fragment else None
                if activity:
                    builder = AlertDialogBuilder(activity)
                    builder.set_title(str(_dh_strings["packit"]) if _dh_strings else "PackIt")
                    builder.set_message(url)
                    builder.set_positive_button(str(_dh_strings["dl_packit_ok"]) if _dh_strings else "OK", lambda b, w: self.proceed_deeplink())
                    builder.set_on_cancel_listener(lambda b: self.proceed_deeplink())
                    builder.show()
                else:
                    self.proceed_deeplink()
            except:
                self.proceed_deeplink()

    def proceed_deeplink(self):
        try:
            self.pending_intent = None
            self.pending_param = None
            self.is_processing = False
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"[PackIt] Error proceeding deeplink: {e}", False)
            self.is_processing = False


def setup_deeplink_hook(plugin):
    try:
        LaunchActivity = find_class("org.telegram.ui.LaunchActivity")
        if LaunchActivity:
            method = LaunchActivity.getClass().getDeclaredMethod(
                "handleIntent",
                find_class("android.content.Intent").getClass(),
                find_class("java.lang.Boolean").TYPE,
                find_class("java.lang.Boolean").TYPE,
                find_class("java.lang.Boolean").TYPE,
                find_class("org.telegram.messenger.browser.Browser$Progress").getClass(),
                find_class("java.lang.Boolean").TYPE,
                find_class("java.lang.Boolean").TYPE
            )
            method.setAccessible(True)
            return plugin.hook_method(method, PackItDeeplinkHook(plugin))
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"[PackIt] Error setting up deeplink hook: {e}", False)
    return None
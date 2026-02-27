from ui.settings import Header, Switch, Divider, Text
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
import shutil
import threading
import time
import os
import signal


class OtherSettings:
    def __init__(self, chat_button=None):
        self.chat_button = chat_button

    def _getCacheDir(self) -> str:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        return f"/data/data/{pkg}/files/packitCache"

    def _killProcess(self):
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGKILL)

    def _onClearCacheClick(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return

            builder = AlertDialogBuilder(act)
            builder.set_title(strings.clear_cache_confirm_title)
            builder.set_message(strings.clear_cache_confirm_message)

            def onConfirm(b, w):
                b.dismiss()
                try:
                    cacheDir = self._getCacheDir()
                    if os.path.exists(cacheDir):
                        shutil.rmtree(cacheDir)
                except Exception as e:
                    log(f"clear cache error: {e}")

                try:
                    frag2 = get_last_fragment()
                    act2 = frag2.getParentActivity() if frag2 else None
                    if not act2:
                        return

                    restartBuilder = AlertDialogBuilder(act2)
                    restartBuilder.set_title(strings.clear_cache_done_title)
                    restartBuilder.set_message(strings.clear_cache_done_message)

                    def onRestart(rb, rw):
                        rb.dismiss()
                        thread = threading.Thread(target=self._killProcess)
                        thread.daemon = True
                        thread.start()

                    restartBuilder.set_positive_button(strings.restart_now, onRestart)
                    restartBuilder.set_negative_button(strings.restart_later, lambda rb, rw: rb.dismiss())
                    restartBuilder.show()
                except Exception as e:
                    log(f"clear cache restart dialog error: {e}")

            builder.set_positive_button(strings.clear_cache_button, onConfirm)
            builder.set_negative_button(strings.cancel_button, lambda b, w: b.dismiss())
            try:
                builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
            except Exception as e:
                log(f"make_button_red error: {e}")
            builder.show()
        except Exception as e:
            log(f"clear cache dialog error: {e}")

    def build(self):
        return [
            Header(text=strings.buttons_header),
            Switch(
                key="show_chat_menu",
                text=strings.button_in_chat_menu,
                subtext=strings.button_in_chat_menu_desc,
                default=False,
                icon="msg_settings",
                link_alias="show_chat_menu",
                on_change=self.chat_button.on_chat_switch if self.chat_button else None
            ),
            Switch(
                key="show_chat_plugins_menu",
                text=strings.button_in_chat_plugins,
                subtext=strings.button_in_chat_plugins_desc,
                default=False,
                icon="msg_plugins",
                link_alias="show_chat_plugins_menu",
                on_change=self.chat_button.on_chat_plugins_switch if self.chat_button else None
            ),
            Divider(),
            Header(text=strings.interface_header),
            Switch(
                key="hide_unavailable_plugins",
                text="Hide unavailable plugins",
                subtext="Hide plugins that are incompatible with your client.",
                default=False,
                icon="msg_block",
                link_alias="hide_unavailable_plugins"
            ),
            Switch(
                key="old_sort_menu_design",
                text=strings.classic_sort_menu,
                subtext=strings.classic_sort_menu_desc,
                default=False,
                icon="msg_list",
                link_alias="old_sort_menu_design"
            ),
            Switch(
                key="show_default_sticker",
                text=strings.show_default_sticker,
                subtext=strings.show_default_sticker_desc,
                default=False,
                icon="msg_sticker",
                link_alias="show_default_sticker"
            ),
            Switch(
                key="skip_repository_selection",
                text=strings.skip_repository_selection,
                subtext=strings.skip_repository_selection_desc,
                default=False,
                icon="msg_leave",
                link_alias="skip_repository_selection"
            ),
            Switch(
                key="hide_repository_selection_button",
                text=strings.hide_repository_selection_button,
                subtext=strings.hide_repository_selection_button_desc,
                default=False,
                icon="msg_unpin",
                link_alias="hide_repository_selection_button"
            ),
            Divider(),
            Header(text=strings.sfx_header),
            Switch(
                key="sfx_enabled",
                text=strings.enable_sfx,
                subtext=strings.enable_sfx_desc,
                default=False,
                icon="msg_voicechat",
                link_alias="sfx_enabled"
            ),
            Divider(),
            # cache should always be at the bottom of the page
            Header(text=strings.cache_header),
            Text(
                text=strings.clear_cache,
                icon="msg_delete",
                on_click=self._onClearCacheClick,
                red=True
            ),
            Divider(),
        ]

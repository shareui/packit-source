import hashlib
from ui.settings import Header, Input, Divider, Text
from ui.bulletin import BulletinHelper
from android_utils import log
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from ..other.localConfig import LocalConfig


def _hashPassword(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SecuritySettings:
    def _onPasswordChange(self, value: str):
        try:
            hashed = _hashPassword(value) if value else ""
            LocalConfig.set("sudoPassword", hashed)
            if value:
                BulletinHelper.show_success(strings.sudo_password_saved)
        except Exception as e:
            log(f"security: failed to save sudo password: {e}")

    def _onNotReady(self, view):
        BulletinHelper.show_info(strings.not_ready_yet)

    def build(self):
        return [
            Header(text=strings.scanning_header),
            Text(
                text=strings.signature_scan,
                icon="msg_search",
                on_click=self._onNotReady
            ),
            Text(
                text=strings.hash_comparison,
                icon="msg_sendfile",
                on_click=self._onNotReady
            ),
            Divider(),
            Header(text=strings.security_header),
            Input(
                key="sudo_password_input",
                text=strings.sudo_password,
                default="",
                icon="fingerprint",
                on_change=self._onPasswordChange
            ),
            Divider(text="This feature is not fully implemented yet."),
        ]

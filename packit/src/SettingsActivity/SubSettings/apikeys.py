from ui.settings import Header, Text, Divider, Selector, Switch
from elyx import strings, settings
from android_utils import log
from client_utils import get_last_fragment


def _open_url(url: str):
    try:
        from android_utils import run_on_ui_thread
        from android.net import Uri

        def _do():
            try:
                from org.telegram.messenger.browser import Browser
                act = get_last_fragment().getParentActivity()
                Browser.openUrl(act, Uri.parse(url), True, True, True, None, None, False, False, False)
            except Exception as e:
                log(f"apikeys: _open_url ui error: {e}")

        run_on_ui_thread(_do)
    except Exception as e:
        log(f"apikeys: _open_url error: {e}")


def _get_device_id() -> str:
    try:
        from android.provider import Settings
        from org.telegram.messenger import ApplicationLoader
        ctx = ApplicationLoader.applicationContext
        return str(Settings.Secure.getString(ctx.getContentResolver(), Settings.Secure.ANDROID_ID)) or "default"
    except Exception as e:
        log(f"apikeys: _get_device_id error: {e}")
        return "default"


def _get_gemini_key_preview() -> "str | None":
    # returns "AB..xyz" preview or None if key not set
    try:
        import ctypes
        from ...nativeLoader import loadPackitKey
        from ...utils.paths import getKeysDir

        lib = loadPackitKey()
        if not lib:
            return None

        keysDir = getKeysDir()
        deviceId = _get_device_id()

        exists = lib.packitkey_exists(
            keysDir.encode("utf-8"),
            deviceId.encode("utf-8"),
            b"gemini",
        )
        if exists != 1:
            return None

        buf = (ctypes.c_uint8 * 4096)()
        length = ctypes.c_uint32(4096)
        result = lib.packitkey_load(
            keysDir.encode("utf-8"),
            deviceId.encode("utf-8"),
            b"gemini",
            buf,
            ctypes.byref(length),
        )
        if result != 0:
            return None

        key = bytes(buf[:length.value]).decode("utf-8", errors="replace")
        if len(key) <= 5:
            return key
        return key[:2] + ".." + key[-3:]
    except Exception as e:
        log(f"apikeys: _get_gemini_key_preview error: {e}")
        return None


def _save_gemini_key(keyValue: str):
    try:
        import ctypes
        from ...nativeLoader import loadPackitKey
        from ...utils.paths import getKeysDir
        import os

        keysDir = getKeysDir()
        os.makedirs(keysDir, exist_ok=True)

        lib = loadPackitKey()
        if not lib:
            log("apikeys: libpackitkey not loaded")
            return

        deviceId = _get_device_id()
        keyBytes = keyValue.encode("utf-8")
        keyLen = len(keyBytes)
        buf = (ctypes.c_uint8 * keyLen)(*keyBytes)

        result = lib.packitkey_store(
            keysDir.encode("utf-8"),
            deviceId.encode("utf-8"),
            b"gemini",
            buf,
            ctypes.c_uint32(keyLen),
        )
        if result != 0:
            log(f"apikeys: packitkey_store returned {result}")
        else:
            log("apikeys: gemini key saved")
    except Exception as e:
        log(f"apikeys: _save_gemini_key error: {e}")


def _delete_gemini_key():
    try:
        from ...nativeLoader import loadPackitKey
        from ...utils.paths import getKeysDir

        lib = loadPackitKey()
        if not lib:
            log("apikeys: libpackitkey not loaded")
            return

        deviceId = _get_device_id()
        result = lib.packitkey_delete(
            getKeysDir().encode("utf-8"),
            deviceId.encode("utf-8"),
            b"gemini",
        )
        if result != 0:
            log(f"apikeys: packitkey_delete returned {result}")
        else:
            log("apikeys: gemini key deleted")
    except Exception as e:
        log(f"apikeys: _delete_gemini_key error: {e}")


def _has_gemini_cache() -> bool:
    try:
        import json, os
        from ...utils.paths import getGeminiCachePath
        path = getGeminiCachePath()
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and len(data) > 0
    except Exception:
        return False


def _on_reset_gemini_cache(view):
    try:
        from ui.alert import AlertDialogBuilder
        from ui.bulletin import BulletinHelper
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        def _on_confirm(b, w):
            b.dismiss()
            try:
                import os
                from ...utils.paths import getGeminiCachePath
                path = getGeminiCachePath()
                if os.path.exists(path):
                    os.remove(path)
                log("apikeys: gemini cache cleared")
            except Exception as e:
                log(f"apikeys: _on_reset_gemini_cache delete error: {e}")
            try:
                from com.exteragram.messenger.plugins import PluginsController
                PluginsController.getInstance().loadPluginSettings("shareui_packit")
            except Exception as e:
                log(f"apikeys: settings reload failed: {e}")
            BulletinHelper.show_success(str(strings.api_key_reset_success), get_last_fragment())

        builder = AlertDialogBuilder(act)
        builder.set_title(str(strings.reset_gemini_cache))
        builder.set_message(str(strings.reset_gemini_api_key_confirm))
        builder.set_positive_button(str(strings.reset_button), _on_confirm)
        builder.set_negative_button(str(strings.cancel_button), lambda b, w: b.dismiss())
        builder.show()
    except Exception as e:
        log(f"apikeys: _on_reset_gemini_cache error: {e}")


def _on_reset_gemini_key(view):
    try:
        from ui.alert import AlertDialogBuilder
        from ui.bulletin import BulletinHelper
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        def _on_confirm(b, w):
            b.dismiss()
            _delete_gemini_key()
            post_frag = get_last_fragment()
            if _get_gemini_key_preview() is None:
                try:
                    from com.exteragram.messenger.plugins import PluginsController
                    PluginsController.getInstance().loadPluginSettings("shareui_packit")
                except Exception as e:
                    log(f"apikeys: settings reload failed: {e}")
                BulletinHelper.show_success(str(strings.api_key_reset_success), post_frag)
            else:
                BulletinHelper.show_error(str(strings.api_key_saved_error), post_frag)

        builder = AlertDialogBuilder(act)
        builder.set_title(str(strings.reset_gemini_api_key))
        builder.set_message(str(strings.reset_gemini_api_key_confirm))
        builder.set_positive_button(str(strings.reset_button), _on_confirm)
        builder.set_negative_button(str(strings.cancel_button), lambda b, w: b.dismiss())
        builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
        builder.show()
    except Exception as e:
        log(f"apikeys: _on_reset_gemini_key error: {e}")


def _on_add_gemini_key(view):
    try:
        from ..service.AddKeyDialog import show_add_key_dialog
        from ui.bulletin import BulletinHelper
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return
        keyIsSet = _get_gemini_key_preview() is not None
        hint = str(strings.change_gemini_api_key_dialog_hint) if keyIsSet else str(strings.add_gemini_api_key_dialog_hint)
        button_text = str(strings.change_gemini_api_key_dialog_button) if keyIsSet else str(strings.add_gemini_api_key_dialog_button)

        def _on_confirm(keyValue: str):
            _save_gemini_key(keyValue)
            saved_frag = get_last_fragment()
            if _get_gemini_key_preview() is not None:
                try:
                    from com.exteragram.messenger.plugins import PluginsController
                    PluginsController.getInstance().loadPluginSettings("shareui_packit")
                except Exception as e:
                    log(f"apikeys: settings reload failed: {e}")
                BulletinHelper.show_success(str(strings.api_key_saved_success), saved_frag)
            else:
                BulletinHelper.show_error(str(strings.api_key_saved_error), saved_frag)

        show_add_key_dialog(
            act,
            title=str(strings.add_gemini_api_key_dialog_title),
            subtitle=str(strings.add_gemini_api_key_dialog_subtitle),
            hint=hint,
            button_text=button_text,
            on_confirm=_on_confirm,
            outline_label=str(strings.api_key_dialog_outline_label),
        )
    except Exception as e:
        log(f"apikeys: _on_add_gemini_key error: {e}")


def build_apikeys_page():
    preview = _get_gemini_key_preview()
    keyIsSet = preview is not None

    if keyIsSet:
        gemini_text = strings.change_gemini_api_key
        gemini_subtext = strings("add_gemini_api_key_desc_set", preview=preview)
        gemini_icon = "msg_edit"
    else:
        gemini_text = strings.add_gemini_api_key
        gemini_subtext = strings.add_gemini_api_key_desc
        gemini_icon = "msg_addbot"

    items = [
        Header(text=strings.api_keys_header),
        Text(
            text=strings.api_keys_safety_title,
            subtext=strings.api_keys_safety_desc,
            icon="msg_info",
            on_click=lambda v: _open_url("https://t.me/packitGround/13/11696"),
        ),
        Text(
            text=strings.api_keys_why_is_this,
            icon="msg_help",
            on_click=lambda v: _open_url("https://t.me/packitGround/13/11732"),
        ),
        Divider(),
        Header(text=strings.gemini_header),
        Text(
            text=gemini_text,
            subtext=gemini_subtext,
            icon=gemini_icon,
            on_click=_on_add_gemini_key,
            link_alias="gemini_api_key",
        ),
    ]

    if keyIsSet:
        items.append(Selector(
            key="gemini_model",
            text=strings.gemini_model_selector,
            default=0,
            items=["2.5 Flash", "2.5 Flash Lite", "2.5 Pro"],
            icon="msg_list",
        ))
        items.append(Switch(
            key="gemini_cache_enabled",
            text=strings.gemini_cache_result,
            subtext=strings.gemini_cache_result_desc,
            icon="menu_clear_cache_remix",
            default=True,
        ))
        if _has_gemini_cache():
            items.append(Text(
                text=strings.reset_gemini_cache,
                subtext=strings.reset_gemini_cache_desc,
                icon="msg_reset",
                on_click=_on_reset_gemini_cache,
            ))
        items.append(Text(
            text=strings.reset_gemini_api_key,
            subtext=strings.reset_gemini_api_key_desc,
            icon="msg_clear",
            red=True,
            on_click=_on_reset_gemini_key,
        ))

    items.append(Divider(text=strings.get_gemini_key_hint))

    return items

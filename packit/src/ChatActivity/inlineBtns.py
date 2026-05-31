# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import weakref
import threading
import random
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, run_on_ui_thread
from extera_utils.classes import Base, java_subclass, joverride
from java import jint

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"inlineBtns: import strings failed: {e}")

# must not collide with ButtonCustom constants (1-8)
_PACKIT_TRANSLATE_BTN_ID = 101

_PENDING_KEYS = [
    "translate_pending_1",
    "translate_pending_2",
    "translate_pending_3",
    "translate_pending_4",
    "translate_pending_5",
    "translate_pending_6",
    "translate_pending_7",
    "translate_pending_8",
]

_BotInlineKeyboard = None


def _get_bot_inline_keyboard_class():
    global _BotInlineKeyboard
    if _BotInlineKeyboard is None:
        _BotInlineKeyboard = find_class("org.telegram.messenger.BotInlineKeyboard")
    return _BotInlineKeyboard


def _is_packit_inline_message(message_object):
    # checks if message was sent via pluginAutocomplete by reading the params marker
    try:
        owner = message_object.messageOwner
        if owner is None:
            log("inlineBtns: _is_packit_inline_message: messageOwner is None")
            return False
        msg_params = owner.params
        if msg_params is None:
            return False
        result = msg_params.get("packit_inline") == "1"
        if result:
            log("inlineBtns: packit_inline message confirmed")
        return result
    except Exception as e:
        log(f"inlineBtns: _is_packit_inline_message error: {e}")
        return False


def _build_translate_button_class():
    BotInlineKeyboard = _get_bot_inline_keyboard_class()
    if BotInlineKeyboard is None:
        log("inlineBtns: BotInlineKeyboard class not found")
        return None
    ButtonBase = find_class("org.telegram.messenger.BotInlineKeyboard$ButtonCustom")
    if ButtonBase is None:
        log("inlineBtns: BotInlineKeyboard$ButtonCustom class not found")
        return None

    try:
        @java_subclass(ButtonBase)
        class PackitTranslateButton(Base):
            @joverride("getText")
            def get_text(self):
                try:
                    return strings["translate"]
                except Exception:
                    return "Translate"

            @joverride("getIconRes")
            def get_icon_res(self):
                return 0

            @joverride("getIconEmoji")
            def get_icon_emoji(self):
                return 0

        log("inlineBtns: PackitTranslateButton class built")
        return PackitTranslateButton
    except Exception as e:
        log(f"inlineBtns: _build_translate_button_class error: {e}")
        return None


_TranslateButtonClass = None


def _get_translate_button_class():
    global _TranslateButtonClass
    if _TranslateButtonClass is None:
        _TranslateButtonClass = _build_translate_button_class()
    return _TranslateButtonClass


def _get_random_pending_text():
    try:
        key = random.choice(_PENDING_KEYS)
        return strings[key]
    except Exception:
        return "Translating..."


def _do_translate_inline(message_object):
    # runs on background thread: replaces message with pending text, translates, restores
    try:
        from client_utils import edit_message
        from ..ui.PluginListActivity.translation import _translate_text
        from java.util import Locale

        owner = message_object.messageOwner
        if owner is None:
            log("inlineBtns: _do_translate_inline: messageOwner is None")
            return

        original_text = owner.message or ""
        if not original_text.strip():
            log("inlineBtns: _do_translate_inline: original text is empty")
            return

        log(f"inlineBtns: translating message, len={len(original_text)}")

        pending_text = _get_random_pending_text()

        def set_pending():
            try:
                edit_message(message_object, text=pending_text)
                log("inlineBtns: pending text set")
            except Exception as e:
                log(f"inlineBtns: set_pending error: {e}")

        run_on_ui_thread(set_pending)

        target_lang = Locale.getDefault().getLanguage() or "en"
        log(f"inlineBtns: translating to lang={target_lang}")
        translated = _translate_text(original_text, target_lang)
        log(f"inlineBtns: translation done, len={len(translated)}")

        def set_translated():
            try:
                edit_message(message_object, text=translated)
                log("inlineBtns: translated text set")
            except Exception as e:
                log(f"inlineBtns: set_translated error: {e}")

        run_on_ui_thread(set_translated)

    except Exception as e:
        log(f"inlineBtns: _do_translate_inline error: {e}")


class _MeasureInlineButtonsHook(MethodHook):
    def __init__(self, plugin):
        MethodHook.__init__(self)
        self._plugin_ref = weakref.ref(plugin)

    def after_hooked_method(self, param):
        try:
            message_object = param.thisObject
            if not _is_packit_inline_message(message_object):
                return

            TranslateButton = _get_translate_button_class()
            if TranslateButton is None:
                return

            BotInlineKeyboard = _get_bot_inline_keyboard_class()
            if BotInlineKeyboard is None:
                return

            builder = BotInlineKeyboard.Builder()

            existing = message_object.getInlineBotButtons()
            if existing is not None:
                builder.addKeyboardSource(existing)
                builder.addSeparator()

            btn_instance = TranslateButton.new_java_instance(
                jint(_PACKIT_TRANSLATE_BTN_ID),
                jint(0),
                jint(0),
            )

            from java import dynamic_proxy
            SourceInterface = find_class("org.telegram.messenger.BotInlineKeyboard$Source")

            class SingleRowSource(dynamic_proxy(SourceInterface)):
                def getRowsCount(self):
                    return 1

                def getColumnsCount(self, row_idx):
                    return 1

                def getButton(self, row_idx, col):
                    return btn_instance

                def hasSeparator(self, row_idx):
                    return False

            builder.addKeyboardSource(SingleRowSource())

            new_source = builder.build()

            from hook_utils import set_private_field
            set_private_field(message_object, "inlineKeyboardSource", new_source)

        except Exception as e:
            log(f"inlineBtns: _MeasureInlineButtonsHook error: {e}")


class _DidPressCustomBotButtonHook(MethodHook):
    def before_hooked_method(self, param):
        try:
            log(f"inlineBtns: didPressCustomBotButton fired, args={len(param.args)}")

            # args[0] = ChatMessageCell, args[1] = BotInlineKeyboard.ButtonCustom
            if len(param.args) < 2:
                log("inlineBtns: not enough args")
                return

            button = param.args[1]
            if button is None:
                log("inlineBtns: button is None")
                return

            try:
                btn_id = button.id
                log(f"inlineBtns: button.id={btn_id}")
            except Exception as e:
                log(f"inlineBtns: cannot read button.id: {e}")
                return

            if btn_id != _PACKIT_TRANSLATE_BTN_ID:
                log(f"inlineBtns: not our button (id={btn_id}), skip")
                return

            cell = param.args[0]
            if cell is None:
                log("inlineBtns: cell is None")
                return

            try:
                message_object = cell.getMessageObject()
            except Exception as e:
                log(f"inlineBtns: getMessageObject error: {e}")
                return

            if message_object is None:
                log("inlineBtns: message_object is None")
                return

            if not _is_packit_inline_message(message_object):
                log("inlineBtns: not a packit inline message")
                return

            log("inlineBtns: starting translate thread")
            threading.Thread(
                target=_do_translate_inline,
                args=(message_object,),
                daemon=True
            ).start()

        except Exception as e:
            log(f"inlineBtns: _DidPressCustomBotButtonHook error: {e}")


def setup_inline_translate_button(plugin):
    try:
        # hook measureInlineBotButtons to inject translate button
        MessageObject = find_class("org.telegram.messenger.MessageObject")
        if MessageObject is None:
            log("inlineBtns: MessageObject not found")
            return

        measure_method = None
        for m in MessageObject.getClass().getDeclaredMethods():
            try:
                if m.getName() == "measureInlineBotButtons" and len(m.getParameterTypes()) == 0:
                    measure_method = m
                    break
            except Exception:
                continue

        if measure_method is None:
            log("inlineBtns: measureInlineBotButtons not found")
            return

        measure_method.setAccessible(True)
        plugin.hook_method(measure_method, _MeasureInlineButtonsHook(plugin))
        log("inlineBtns: measureInlineBotButtons hook set")

        # hook didPressCustomBotButton on ChatActivity$ChatMessageCellDelegate (actual impl)
        ChatMessageCellDelegate = find_class("org.telegram.ui.ChatActivity$ChatMessageCellDelegate")
        if ChatMessageCellDelegate is None:
            log("inlineBtns: ChatMessageCellDelegate not found")
            return

        log("inlineBtns: hooking all didPressCustomBotButton on ChatActivity$ChatMessageCellDelegate")
        plugin.hook_all_methods(ChatMessageCellDelegate, "didPressCustomBotButton", _DidPressCustomBotButtonHook())
        log("inlineBtns: setup done")

    except Exception as e:
        log(f"inlineBtns: setup error: {e}")

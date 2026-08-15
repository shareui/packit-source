# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import weakref
import threading
import random
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import run_on_ui_thread
from extera_utils.classes import Base, java_subclass, joverride
from java import jint

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"inlineBtns: import strings failed: {e}")

# must not collide with ButtonCustom constants (1-8)
_PACKIT_TRANSLATE_BTN_ID = 101
_PACKIT_SEND_FILE_BTN_ID = 102

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
            logx("inlineBtns: _is_packit_inline_message: messageOwner is None", True)
            return False
        msg_params = owner.params
        if msg_params is None:
            return False
        result = msg_params.get("packit_inline") == "1"
        if result:
            logx("inlineBtns: packit_inline message confirmed", True)
        return result
    except Exception as e:
        logx(f"inlineBtns: _is_packit_inline_message error: {e}", False)
        return False


def _build_translate_button_class():
    BotInlineKeyboard = _get_bot_inline_keyboard_class()
    if BotInlineKeyboard is None:
        logx("inlineBtns: BotInlineKeyboard class not found", True)
        return None
    ButtonBase = find_class("org.telegram.messenger.BotInlineKeyboard$ButtonCustom")
    if ButtonBase is None:
        logx("inlineBtns: BotInlineKeyboard$ButtonCustom class not found", True)
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

        logx("inlineBtns: PackitTranslateButton class built", True)
        return PackitTranslateButton
    except Exception as e:
        logx(f"inlineBtns: _build_translate_button_class error: {e}", False)
        return None


_TranslateButtonClass = None


def _get_translate_button_class():
    global _TranslateButtonClass
    if _TranslateButtonClass is None:
        _TranslateButtonClass = _build_translate_button_class()
    return _TranslateButtonClass


def _build_send_file_button_class():
    ButtonBase = find_class("org.telegram.messenger.BotInlineKeyboard$ButtonCustom")
    if ButtonBase is None:
        logx("inlineBtns: BotInlineKeyboard$ButtonCustom class not found for SendFileButton", True)
        return None
    try:
        @java_subclass(ButtonBase)
        class PackitSendFileButton(Base):
            @joverride("getText")
            def get_text(self):
                try:
                    return strings["send_as_file"]
                except Exception:
                    return "Send as file"

            @joverride("getIconRes")
            def get_icon_res(self):
                return 0

            @joverride("getIconEmoji")
            def get_icon_emoji(self):
                return 0

        logx("inlineBtns: PackitSendFileButton class built", True)
        return PackitSendFileButton
    except Exception as e:
        logx(f"inlineBtns: _build_send_file_button_class error: {e}", False)
        return None


_SendFileButtonClass = None


def _get_send_file_button_class():
    global _SendFileButtonClass
    if _SendFileButtonClass is None:
        _SendFileButtonClass = _build_send_file_button_class()
    return _SendFileButtonClass


def _get_random_pending_text():
    try:
        key = random.choice(_PENDING_KEYS)
        return strings[key]
    except Exception:
        return "Translating..."


def _build_plugin_message(params, translated_desc: str):
    # rebuilds the full plugin message from stored params and the translated
    # description, using the same builder as the original send so the result is
    # formatted identically. params may be a Java HashMap — single-arg .get().

    def _p(key):
        v = params.get(key)
        return str(v) if v is not None else ""

    from .MessageBuilder import build_plugin_message
    return build_plugin_message(
        _p("packit_name"), _p("packit_version"), _p("packit_author"),
        _p("packit_plugin_id"), _p("packit_repo_id"), translated_desc,
        output_type=_p("packit_output_type") or None,
        show_version=_p("packit_show_version") != "0",
        show_author=_p("packit_show_author") != "0",
        show_description=_p("packit_show_description") != "0",
        show_install=_p("packit_show_install") != "0",
    )


def _do_translate_inline(message_object):
    # runs on background thread: translates only the description, rebuilds message with formatting
    try:
        from client_utils import edit_message
        from ....utils.Translation import _translate_text
        from java.util import Locale

        owner = message_object.messageOwner
        if owner is None:
            logx("inlineBtns: _do_translate_inline: messageOwner is None", True)
            return

        msg_params = owner.params
        if msg_params is None:
            logx("inlineBtns: _do_translate_inline: no params on message", True)
            return

        raw_desc = msg_params.get("packit_desc") or ""
        if not raw_desc.strip():
            logx("inlineBtns: _do_translate_inline: description is empty, nothing to translate", True)
            return

        logx(f"inlineBtns: translating description, len={len(raw_desc)}", True)

        pending_text = _get_random_pending_text()

        def set_pending():
            try:
                edit_message(message_object, text=pending_text)
                logx("inlineBtns: pending text set", True)
            except Exception as e:
                logx(f"inlineBtns: set_pending error: {e}", False)

        run_on_ui_thread(set_pending)

        target_lang = Locale.getDefault().getLanguage() or "en"
        logx(f"inlineBtns: translating to lang={target_lang}", True)
        translated_desc = _translate_text(raw_desc, target_lang)
        logx(f"inlineBtns: translation done, len={len(translated_desc)}", True)

        rebuilt_text, rebuilt_entities = _build_plugin_message(msg_params, translated_desc)
        logx(f"inlineBtns: rebuilt message, len={len(rebuilt_text)} entities={len(rebuilt_entities)}", True)

        def set_translated():
            try:
                from .MessageBuilder import edit_message_with_entities
                if not edit_message_with_entities(message_object, rebuilt_text, rebuilt_entities):
                    # last resort: at least put the translated text in place
                    edit_message(message_object, text=rebuilt_text)
                logx("inlineBtns: translated message set", True)
            except Exception as e:
                logx(f"inlineBtns: set_translated error: {e}", False)

        run_on_ui_thread(set_translated)

    except Exception as e:
        logx(f"inlineBtns: _do_translate_inline error: {e}", False)


def _rebuild_keyboard_without_send_file(message_object):
    # removes send file button from inlineKeyboardSource, keeps everything else
    try:
        BotInlineKeyboard = _get_bot_inline_keyboard_class()
        if BotInlineKeyboard is None:
            return
        builder = BotInlineKeyboard.Builder()
        existing = message_object.getInlineBotButtons()
        if existing is not None:
            from java import dynamic_proxy
            SourceInterface = find_class("org.telegram.messenger.BotInlineKeyboard$Source")

            class FilteredSource(dynamic_proxy(SourceInterface)):
                def __init__(self, src):
                    super().__init__()
                    self._src = src
                    self._rows = []
                    for i in range(src.getRowsCount()):
                        cols = src.getColumnsCount(i)
                        row = [src.getButton(i, c) for c in range(cols)]
                        # skip rows that contain only our send file button
                        if len(row) == 1:
                            try:
                                if row[0].id == _PACKIT_SEND_FILE_BTN_ID:
                                    continue
                            except Exception:
                                pass
                        self._rows.append((i, row))

                def getRowsCount(self):
                    return len(self._rows)

                def getColumnsCount(self, row_idx):
                    return len(self._rows[row_idx][1])

                def getButton(self, row_idx, col):
                    return self._rows[row_idx][1][col]

                def hasSeparator(self, row_idx):
                    original_row_idx = self._rows[row_idx][0]
                    return self._src.hasSeparator(original_row_idx)

            builder.addKeyboardSource(FilteredSource(existing))

        new_source = builder.build()
        from hook_utils import set_private_field
        set_private_field(message_object, "inlineKeyboardSource", new_source)
        logx("inlineBtns: send file button removed from keyboard", True)
    except Exception as e:
        logx(f"inlineBtns: _rebuild_keyboard_without_send_file error: {e}", False)


def _resolve_topic_message(dialog_id):
    # topic start message of the chat currently open, or None outside forums —
    # sending needs it as replyToTopMsg or the message lands in General
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        if frag is None or not getattr(frag, "isTopic", False):
            return None
        topic_id = frag.getTopicId()
        if not topic_id:
            return None
        from org.telegram.messenger import MessageObject as MsgObj
        topic = frag.getMessagesController().getTopicsController().findTopic(-dialog_id, topic_id)
        if topic is None or topic.topicStartMessage is None:
            return None
        topic_msg = MsgObj(frag.getCurrentAccount(), topic.topicStartMessage, False, False)
        topic_msg.isTopicMainMessage = True
        return topic_msg
    except Exception as e:
        logx(f"inlineBtns: topic resolve error: {e}", False)
        return None


def _do_send_file_inline(message_object, plugin_ref):
    # background thread: resolves plugin link, downloads, sends as document, removes button
    try:
        import os
        import requests as _req
        from android_utils import run_on_ui_thread as _run
        from client_utils import get_last_fragment
        from ui.alert import AlertDialogBuilder

        owner = message_object.messageOwner
        if owner is None:
            logx("inlineBtns: _do_send_file_inline: messageOwner is None", True)
            return

        msg_params = owner.params
        if msg_params is None:
            logx("inlineBtns: _do_send_file_inline: no params on message", True)
            return

        plugin_id = str(msg_params.get("packit_plugin_id") or "")
        repo_id = str(msg_params.get("packit_repo_id") or "")

        if not plugin_id or not repo_id:
            logx("inlineBtns: _do_send_file_inline: missing plugin_id or repo_id", True)
            _run(lambda: _show_send_file_error(strings["send_as_file_no_link"]))
            return

        logx(f"inlineBtns: resolving plugin link for plugin_id={plugin_id} repo_id={repo_id}", True)

        # resolve plugins url from repo cache
        link = None
        try:
            from ....ui.updates.Fragment import _get_repos, _get_repo_plugins_url, _fetch_repo_plugins
            repos = _get_repos()
            repo_url = None
            for r in repos:
                if r.get("id") == repo_id:
                    repo_url = r.get("url", "")
                    break
            if repo_url:
                plugins_url = _get_repo_plugins_url(None, repo_id, repo_url)
                plugins_data = _fetch_repo_plugins(plugins_url)
                plugin_info = plugins_data.get(plugin_id) or {}
                link = plugin_info.get("link") or plugin_info.get("raw")
        except Exception as e:
            logx(f"inlineBtns: _do_send_file_inline: repo resolve error: {e}", False)

        if not link:
            logx("inlineBtns: _do_send_file_inline: no download link found", True)
            _run(lambda: _show_send_file_error(strings["send_as_file_no_link"]))
            return

        logx(f"inlineBtns: downloading plugin from {link}", True)

        # show loading dialog
        dlg_ref = [None]

        def show_loading():
            try:
                fragment = get_last_fragment()
                if not fragment:
                    return
                ctx = fragment.getContext()
                builder = AlertDialogBuilder(ctx, AlertDialogBuilder.ALERT_TYPE_SPINNER)
                builder.set_title(strings["send_as_file_sending"])
                builder.set_cancelable(False)
                dlg_ref[0] = builder.create()
                dlg_ref[0].show()
            except Exception as e:
                logx(f"inlineBtns: show_loading error: {e}", False)

        def dismiss_loading():
            try:
                if dlg_ref[0]:
                    dlg_ref[0].dismiss()
            except Exception as e:
                logx(f"inlineBtns: dismiss_loading error: {e}", False)

        _run(show_loading)

        # download file
        try:
            from org.telegram.messenger import ApplicationLoader
            cache_dir = ApplicationLoader.applicationContext.getCacheDir().getAbsolutePath()
        except Exception:
            cache_dir = "/data/data/com.exteragram.messenger/cache"

        url_filename = link.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        _, url_ext = os.path.splitext(url_filename)
        filename = f"{plugin_id}{url_ext}" if url_ext else f"{plugin_id}.plugin"
        file_path = os.path.join(str(cache_dir), filename)

        r = _req.get(link, timeout=30)
        if r.status_code != 200:
            _run(dismiss_loading)
            _run(lambda: _show_send_file_error(strings["send_as_file_failed"]))
            return

        os.makedirs(str(cache_dir), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(r.content)
        logx(f"inlineBtns: downloaded {len(r.content)} bytes to {file_path}", True)

        # send document to the current dialog — and, in a forum, to the topic
        # the message lives in. send_document() only takes a peer, so the file
        # always landed in the General topic; send_message() carries
        # replyToTopMsg the same way the inline message send does.
        try:
            dialog_id = message_object.getDialogId()
            params = {"peer": dialog_id, "path": file_path}
            topic_msg_obj = _resolve_topic_message(dialog_id)
            if topic_msg_obj is not None:
                params["replyToMsg"] = topic_msg_obj
                params["replyToTopMsg"] = topic_msg_obj
            from client_utils import send_message
            send_message(params)
            logx(f"inlineBtns: sent document to dialog_id={dialog_id} topic={topic_msg_obj is not None}", True)
        except Exception as e:
            logx(f"inlineBtns: send document error: {e}", False)
            _run(dismiss_loading)
            _run(lambda: _show_send_file_error(strings["send_as_file_failed"]))
            return

        _run(dismiss_loading)

        # remove send file button from keyboard
        _run(lambda: _rebuild_keyboard_without_send_file(message_object))

    except Exception as e:
        logx(f"inlineBtns: _do_send_file_inline error: {e}", False)
        try:
            from android_utils import run_on_ui_thread as _run
            _run(lambda: _show_send_file_error(strings["send_as_file_failed"]))
        except Exception:
            pass


def _show_send_file_error(msg):
    try:
        from ui.bulletin import BulletinHelper
        BulletinHelper.show_error(str(msg))
    except Exception as e:
        logx(f"inlineBtns: _show_send_file_error: {e}", False)


class _MeasureInlineButtonsHook(MethodHook):
    def __init__(self, plugin):
        MethodHook.__init__(self)
        self._plugin_ref = weakref.ref(plugin)

    def after_hooked_method(self, param):
        try:
            from . import InlineState
            if not InlineState.get_state():
                return
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

            SendFileButton = _get_send_file_button_class()

            from java import dynamic_proxy
            SourceInterface = find_class("org.telegram.messenger.BotInlineKeyboard$Source")

            if SendFileButton is not None:
                send_file_btn_instance = SendFileButton.new_java_instance(
                    jint(_PACKIT_SEND_FILE_BTN_ID),
                    jint(0),
                    jint(0),
                )

                class TwoButtonRowSource(dynamic_proxy(SourceInterface)):
                    def getRowsCount(self):
                        return 1

                    def getColumnsCount(self, row_idx):
                        return 2

                    def getButton(self, row_idx, col):
                        if col == 0:
                            return btn_instance
                        return send_file_btn_instance

                    def hasSeparator(self, row_idx):
                        return False

                builder.addKeyboardSource(TwoButtonRowSource())
            else:
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
            logx(f"inlineBtns: _MeasureInlineButtonsHook error: {e}", False)


class _DidPressCustomBotButtonHook(MethodHook):
    def before_hooked_method(self, param):
        try:
            from . import InlineState
            if not InlineState.get_state():
                return
            logx(f"inlineBtns: didPressCustomBotButton fired, args={len(param.args)}", True)

            # args[0] = ChatMessageCell, args[1] = BotInlineKeyboard.ButtonCustom
            if len(param.args) < 2:
                logx("inlineBtns: not enough args", True)
                return

            button = param.args[1]
            if button is None:
                logx("inlineBtns: button is None", True)
                return

            try:
                btn_id = button.id
                logx(f"inlineBtns: button.id={btn_id}", True)
            except Exception as e:
                logx(f"inlineBtns: cannot read button.id: {e}", False)
                return

            if btn_id not in (_PACKIT_TRANSLATE_BTN_ID, _PACKIT_SEND_FILE_BTN_ID):
                logx(f"inlineBtns: not our button (id={btn_id}), skip", True)
                return

            cell = param.args[0]
            if cell is None:
                logx("inlineBtns: cell is None", True)
                return

            try:
                message_object = cell.getMessageObject()
            except Exception as e:
                logx(f"inlineBtns: getMessageObject error: {e}", False)
                return

            if message_object is None:
                logx("inlineBtns: message_object is None", True)
                return

            if not _is_packit_inline_message(message_object):
                logx("inlineBtns: not a packit inline message", True)
                return

            if btn_id == _PACKIT_TRANSLATE_BTN_ID:
                logx("inlineBtns: starting translate thread", True)
                threading.Thread(
                    target=_do_translate_inline,
                    args=(message_object,),
                    daemon=True
                ).start()
            else:
                logx("inlineBtns: starting send file thread", True)
                threading.Thread(
                    target=_do_send_file_inline,
                    args=(message_object, None),
                    daemon=True
                ).start()

        except Exception as e:
            logx(f"inlineBtns: _DidPressCustomBotButtonHook error: {e}", False)


def setup_inline_translate_button(plugin):
    try:
        # hook measureInlineBotButtons to inject translate button
        MessageObject = find_class("org.telegram.messenger.MessageObject")
        if MessageObject is None:
            logx("inlineBtns: MessageObject not found", True)
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
            logx("inlineBtns: measureInlineBotButtons not found", True)
            return

        measure_method.setAccessible(True)
        plugin.hook_method(measure_method, _MeasureInlineButtonsHook(plugin))
        logx("inlineBtns: measureInlineBotButtons hook set", True)

        # hook didPressCustomBotButton on ChatActivity$ChatMessageCellDelegate (actual impl)
        ChatMessageCellDelegate = find_class("org.telegram.ui.ChatActivity$ChatMessageCellDelegate")
        if ChatMessageCellDelegate is None:
            logx("inlineBtns: ChatMessageCellDelegate not found", True)
            return

        logx("inlineBtns: hooking all didPressCustomBotButton on ChatActivity$ChatMessageCellDelegate", True)
        plugin.hook_all_methods(ChatMessageCellDelegate, "didPressCustomBotButton", _DidPressCustomBotButtonHook())
        logx("inlineBtns: setup done", True)

    except Exception as e:
        logx(f"inlineBtns: setup error: {e}", False)

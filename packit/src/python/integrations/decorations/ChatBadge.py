# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later


from packutil import logx
from hook_utils import find_class, get_private_field
from android.text import SpannableStringBuilder
from android.text import Spanned
from org.telegram.ui.Components import AnimatedEmojiSpan
import weakref
_dialog_ids = weakref.WeakKeyDictionary()
_hints = weakref.WeakKeyDictionary()


class MethodHook:
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        pass


class _TopPanelHook(MethodHook):
    def __init__(self, cache_lookup):
        self._lookup = cache_lookup

    def after_hooked_method(self, param):
        try:
            try:
                from elyx import settings as _s
                if not _s.get("packit_verification", True):
                    return
            except Exception:
                pass

            activity = param.thisObject
            dialog_id = _dialog_ids.get(activity)
            if dialog_id is None:
                dialog_id = get_private_field(activity, "dialog_id")
                if dialog_id is not None:
                    _dialog_ids[activity] = dialog_id

            if dialog_id is None:
                return

            did = int(dialog_id)
            entity_id = did if did > 0 else abs(did)

            entry = self._lookup(entity_id)
            if not entry:
                return

            hint = _hints.get(activity)
            if hint is None:
                hint = get_private_field(activity, "emojiStatusSpamHint")
                if hint is not None:
                    _hints[activity] = hint

            if not hint:
                return

            # only inject when hint is currently visible (banner is shown)
            from android.view import View
            if hint.getVisibility() != View.VISIBLE:
                return

            paint_metrics = hint.getPaint().getFontMetricsInt()
            sb = SpannableStringBuilder()
            sb.append("x")
            sb.setSpan(
                AnimatedEmojiSpan(int(entry["emoji_id"]), paint_metrics),
                0, 1,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
            )
            sb.append(" ")
            sb.append(entry["text"])
            hint.setText(sb)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"[Packit Badges] ChatHook error: {e}", False)


def setup_chat_badge_hook(plugin, cache_lookup):
    try:
        chat_cls = find_class("org.telegram.ui.ChatActivity")
        if not chat_cls:
            logx("[Packit Badges] ChatActivity class not found", True)
            return []
        refs = plugin.hook_all_methods(chat_cls, "updateTopPanel", _TopPanelHook(cache_lookup))
        if refs:
            logx(f"[Packit Badges] hooked updateTopPanel ({len(refs)} overload(s))", True)
        else:
            logx("[Packit Badges] updateTopPanel hook failed", True)
        return refs or []
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"[Packit Badges] chat hook setup error: {e}", False)
        return []
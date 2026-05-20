from android_utils import log
from hook_utils import find_class, get_private_field
from android.text import SpannableStringBuilder
from android.text import Spanned
from org.telegram.ui.Components import AnimatedEmojiSpan


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
            dialog_id = get_private_field(activity, "dialog_id")
            if dialog_id is None:
                return

            did = int(dialog_id)
            entity_id = did if did > 0 else abs(did)

            entry = self._lookup(entity_id)
            if not entry:
                return

            hint = get_private_field(activity, "emojiStatusSpamHint")
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
        except Exception as e:
            log(f"[Packit Badges] ChatHook error: {e}")


def setup_chat_badge_hook(plugin, cache_lookup):
    try:
        chat_cls = find_class("org.telegram.ui.ChatActivity")
        if not chat_cls:
            log("[Packit Badges] ChatActivity class not found")
            return []
        refs = plugin.hook_all_methods(chat_cls, "updateTopPanel", _TopPanelHook(cache_lookup))
        if refs:
            log(f"[Packit Badges] hooked updateTopPanel ({len(refs)} overload(s))")
        else:
            log("[Packit Badges] updateTopPanel hook failed")
        return refs or []
    except Exception as e:
        log(f"[Packit Badges] chat hook setup error: {e}")
        return []

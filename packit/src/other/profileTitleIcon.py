# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android_utils import log
from hook_utils import find_class, get_private_field, set_private_field
from org.telegram.messenger import AndroidUtilities

_SwapDrawable = None
_CACHE_STATUS = None
_CACHE_KEYBOARD = None


def _init_classes():
    global _SwapDrawable, _CACHE_STATUS, _CACHE_KEYBOARD
    if _SwapDrawable is not None:
        return True
    try:
        AnimatedEmojiDrawable = find_class("org.telegram.ui.Components.AnimatedEmojiDrawable")
        if not AnimatedEmojiDrawable:
            log("[Packit Badges] AnimatedEmojiDrawable not found")
            return False
        _SwapDrawable = find_class("org.telegram.ui.Components.AnimatedEmojiDrawable$SwapAnimatedEmojiDrawable")
        if not _SwapDrawable:
            log("[Packit Badges] SwapAnimatedEmojiDrawable not found")
            return False
        # fallback values used if field lookup fails
        _CACHE_STATUS = 4
        _CACHE_KEYBOARD = 3
        try:
            from hook_utils import get_static_private_field
            s = get_static_private_field(AnimatedEmojiDrawable, "CACHE_TYPE_EMOJI_STATUS")
            k = get_static_private_field(AnimatedEmojiDrawable, "CACHE_TYPE_KEYBOARD")
            if s is not None:
                _CACHE_STATUS = s
            if k is not None:
                _CACHE_KEYBOARD = k
        except Exception:
            pass
        return True
    except Exception as e:
        log(f"[Packit Badges] _init_classes error: {e}")
        return False


def _make_drawable(name_view, index):
    try:
        cache_type = _CACHE_STATUS if index == 0 else _CACHE_KEYBOARD
        size = AndroidUtilities.dp(17)
        d = _SwapDrawable(name_view, size, cache_type)
        d.offset(0, AndroidUtilities.dp(1))
        return d
    except Exception as e:
        log(f"[Packit Badges] _make_drawable [{index}] error: {e}")
        return None


class MethodHook:
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        pass


class _UpdateProfileDataHook(MethodHook):
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

            if not _init_classes():
                return

            profile = param.thisObject
            user_id = get_private_field(profile, "userId")
            chat_id = get_private_field(profile, "chatId")

            did = int(user_id) if user_id and int(user_id) != 0 else 0
            cid = int(chat_id) if chat_id and int(chat_id) != 0 else 0
            entity_id = did if did != 0 else abs(cid)
            if entity_id == 0:
                return

            entry = self._lookup(entity_id)
            if not entry:
                return

            emoji_id = int(entry["emoji_id"])
            drawables = get_private_field(profile, "botVerificationDrawable")
            name_views = get_private_field(profile, "nameTextView")
            if drawables is None or name_views is None:
                return

            attached = get_private_field(profile, "fragmentViewAttached")

            for i in range(len(drawables)):
                name_view = name_views[i]
                if not name_view:
                    continue
                d = drawables[i]
                if d is None:
                    d = _make_drawable(name_view, i)
                    if not d:
                        continue
                    drawables[i] = d
                    if attached:
                        d.attach()
                d.set(emoji_id, False)
                name_view.setLeftDrawableOutside(True)
                name_view.setLeftDrawable(d)
        except Exception as e:
            log(f"[Packit Badges] ProfileDataHook error: {e}")


def setup_profile_title_icon_hook(plugin, cache_lookup):
    try:
        profile_cls = find_class("org.telegram.ui.ProfileActivity")
        if not profile_cls:
            log("[Packit Badges] ProfileActivity class not found (title icon)")
            return []
        refs = plugin.hook_all_methods(profile_cls, "updateProfileData", _UpdateProfileDataHook(cache_lookup))
        if refs:
            log(f"[Packit Badges] hooked updateProfileData ({len(refs)} overload(s))")
        else:
            log("[Packit Badges] updateProfileData hook failed")
        return refs or []
    except Exception as e:
        log(f"[Packit Badges] profile title icon setup error: {e}")
        return []
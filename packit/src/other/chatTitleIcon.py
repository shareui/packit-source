from android_utils import log
from hook_utils import find_class, get_private_field
import weakref

# { ChatActivity instance -> last rightIcon drawable }
_right_icons = weakref.WeakValueDictionary()
# separate dict for None values (weakref can't store None)
_right_icons_none = weakref.WeakSet()


class MethodHook:
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        pass


class _SetTitleIconsHook(MethodHook):
    """Saves the rightIcon passed to setTitleIcons for later reuse."""
    def before_hooked_method(self, param):
        try:
            container = param.thisObject
            right = param.args[1] if len(param.args) > 1 else None
            # store on container object via tag
            container.setTag(right)
        except Exception as e:
            log(f"[Packit Badges] SetTitleIconsHook error: {e}")


class _UpdateTitleIconsHook(MethodHook):
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

            container = get_private_field(activity, "avatarContainer")
            if not container:
                return

            drawable = container.getBotVerificationDrawable(int(entry["emoji_id"]), False)
            if not drawable:
                return

            # retrieve saved rightIcon from tag
            right = container.getTag()
            container.setTitleIcons(drawable, right)
        except Exception as e:
            log(f"[Packit Badges] TitleIconHook error: {e}")


def setup_title_icon_hook(plugin, cache_lookup):
    try:
        chat_cls = find_class("org.telegram.ui.ChatActivity")
        if not chat_cls:
            log("[Packit Badges] ChatActivity class not found (title icon)")
            return []

        container_cls = find_class("org.telegram.ui.Components.ChatAvatarContainer")
        if not container_cls:
            log("[Packit Badges] ChatAvatarContainer class not found")
            return []

        refs = []

        set_refs = plugin.hook_all_methods(container_cls, "setTitleIcons", _SetTitleIconsHook())
        if set_refs:
            refs.extend(set_refs)
            log(f"[Packit Badges] hooked setTitleIcons ({len(set_refs)} overload(s))")

        update_refs = plugin.hook_all_methods(chat_cls, "updateTitleIcons", _UpdateTitleIconsHook(cache_lookup))
        if update_refs:
            refs.extend(update_refs)
            log(f"[Packit Badges] hooked updateTitleIcons ({len(update_refs)} overload(s))")
        else:
            log("[Packit Badges] updateTitleIcons hook failed")

        return refs
    except Exception as e:
        log(f"[Packit Badges] title icon hook setup error: {e}")
        return []

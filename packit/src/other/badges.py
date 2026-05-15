from android_utils import log
from hook_utils import find_class, get_private_field
try:
    from org.telegram.messenger import MessagesController
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import MessagesController failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import ApplicationLoader
except:
    ApplicationLoader = None
import threading
import urllib.request
import json
from java.util import Locale
from java.lang import Long
from java.lang.reflect import Modifier

# Любая попытка неправомерного использования системы бейджей автоматически лишает ваш плагин права на публикацию через официальные источники, а также приведёт к перманентной блокировке во всех ресурсах exteraGram и AyuGram без возможности апелляции. Подробнее: https://teletype.in/@exterasquad/forum-rules-ru
# Any attempt to misuse the badge system will automatically revoke your plugin's right to be published through official sources and will result in permanent blocking from all exteraGram and AyuGram resources without the possibility of appeal. Learn more: https://teletype.in/@exterasquad/forum-rules-en


_OBF_API_SOURCE = "x.hl"
_OBF_BADGE_INFO = "x.iz"
_LEGACY_CONTROLLER = "com.exteragram.messenger.badges.BadgesController"
_LEGACY_SOURCE = "com.exteragram.messenger.badges.source.ApiBadgeSource"
_LEGACY_BADGE_INFO = "com.exteragram.messenger.badges.source.BadgeInfo"


class MethodHook:
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        pass


def _loader():
    if not ApplicationLoader:
        return None
    try:
        return ApplicationLoader.applicationContext.getClassLoader()
    except Exception:
        return None


def _load(name):
    loader = _loader()
    if not loader:
        return None
    try:
        return loader.loadClass(name)
    except Exception:
        return None


def _static_instance(cls):
    if not cls:
        return None
    for field in cls.getDeclaredFields():
        try:
            if not Modifier.isStatic(field.getModifiers()):
                continue
            field.setAccessible(True)
            val = field.get(None)
            if val and cls.isInstance(val):
                return val
        except Exception:
            continue
    try:
        companion_field = cls.getDeclaredField("Companion")
        companion_field.setAccessible(True)
        companion = companion_field.get(None)
        if companion:
            for m in companion.getClass().getDeclaredMethods():
                if len(m.getParameterTypes()) != 0:
                    continue
                ret = m.getReturnType()
                if ret and cls.isAssignableFrom(ret):
                    m.setAccessible(True)
                    val = m.invoke(companion)
                    if val:
                        return val
    except Exception:
        pass
    return None


def _source_from_controller(source_cls):
    if not source_cls:
        return None
    source_name = source_cls.getName()
    try:
        from dalvik.system import DexFile
        apk = ApplicationLoader.applicationContext.getPackageCodePath()
        entries = DexFile(apk).entries()
        while entries.hasMoreElements():
            name = entries.nextElement()
            if not name.startswith("x.") or name == source_name:
                continue
            cls = _load(name)
            if not cls or cls.isInterface():
                continue
            controller = _static_instance(cls)
            if not controller:
                continue
            for field in cls.getDeclaredFields():
                try:
                    if field.getType().getName() != source_name:
                        continue
                    field.setAccessible(True)
                    val = field.get(controller)
                    if val:
                        log(f"[Packit Badges] source from {name}.{field.getName()}")
                        return val
                except Exception:
                    continue
    except Exception as e:
        log(f"[Packit Badges] controller scan: {e}")
    return None


def _resolve_badge_api():
    ctrl = _load(_LEGACY_CONTROLLER)
    if ctrl:
        try:
            inst = get_private_field(ctrl.INSTANCE, "apiBadgeSource")
            if inst:
                log("[Packit Badges] legacy BadgesController")
                return inst.getClass(), inst
        except Exception:
            pass

    src_cls = _load(_LEGACY_SOURCE) or _load(_OBF_API_SOURCE)
    if not src_cls:
        log("[Packit Badges] ApiBadgeSource class missing")
        return None, None

    inst = _static_instance(src_cls)
    if inst:
        log(f"[Packit Badges] instance ok ({src_cls.getName()})")
    else:
        log(f"[Packit Badges] hooks on class {src_cls.getName()} (cache later)")
    return src_cls, inst


def _get_cache(source_inst):
    if not source_inst:
        return None
    try:
        c = get_private_field(source_inst, "cache")
        if c:
            return c
    except Exception:
        pass
    for field in source_inst.getClass().getDeclaredFields():
        try:
            field.setAccessible(True)
            val = field.get(source_inst)
            if not val:
                continue
            for m in val.getClass().getMethods():
                if m.getName() == "put" and len(m.getParameterTypes()) == 2:
                    return val
        except Exception:
            continue
    return None


def _is_long(t):
    n = t.getName()
    return n in ("long", "java.lang.Long")


def _is_bool(t):
    n = t.getName()
    return n in ("boolean", "java.lang.Boolean")


def _norm_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _badge_info_class():
    return find_class(_LEGACY_BADGE_INFO) or find_class(_OBF_BADGE_INFO)


def _make_badge_info(badge_dto, profile_status_cls):
    BadgeInfo = _badge_info_class()
    if not BadgeInfo or not profile_status_cls:
        return None
    try:
        return BadgeInfo(badge_dto, profile_status_cls.DEVELOPER, True)
    except Exception as e:
        log(f"[Packit Badges] BadgeInfo ctor: {e}")
        return None


def _lookup_badge(custom_badges, entity_id, is_user=True):
    entity_id = _norm_id(entity_id)
    if entity_id is None:
        return None
    badge = custom_badges.get(entity_id)
    if badge is not None:
        return badge
    if is_user:
        return None
    for alt in (abs(entity_id), -abs(entity_id)):
        badge = custom_badges.get(alt)
        if badge is not None:
            return badge
    return None


def _has_custom_badge(custom_badges, entity_id, is_user=True):
    return _lookup_badge(custom_badges, entity_id, is_user) is not None


def _install_hooks(plugin, api_class, manager):
    refs = []
    badge_dto = _load("com.exteragram.messenger.api.dto.BadgeDTO")
    if not badge_dto:
        return refs
    dto_name = badge_dto.getName()
    bool_hooks = 0
    seen = set()

    for m in list(api_class.getDeclaredMethods()) + list(api_class.getMethods()):
        key = str(m)
        if key in seen:
            continue
        seen.add(key)
        params = m.getParameterTypes()
        ret = m.getReturnType()
        if not ret:
            continue
        rn = ret.getName()

        if len(params) == 2 and _is_long(params[0]) and _is_bool(params[1]) and rn == dto_name:
            m.setAccessible(True)
            r = plugin.hook_method(m, CustomBadgeHook(manager))
            if r:
                refs.append(r)
            continue

        if len(params) == 1 and _is_long(params[0]) and rn == "boolean" and bool_hooks < 2:
            m.setAccessible(True)
            r = plugin.hook_method(m, CustomBooleanBadgeHook(manager))
            if r:
                refs.append(r)
            bool_hooks += 1

    if not refs:
        for name, hook in (
            ("getBadge", CustomBadgeHook),
            ("a", CustomBadgeHook),
            ("isDeveloper", CustomBooleanBadgeHook),
            ("canChangeBadge", CustomBooleanBadgeHook),
        ):
            try:
                extra = plugin.hook_all_methods(api_class, name, hook(manager))
                if extra:
                    refs.extend(extra)
            except Exception:
                pass
    return refs


class BadgeManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self.custom_badges = {}
        self.badge_hook_refs = []
        self.api_class = None
        self.api_badge_source = None
        self._cache = None
        self.config_url = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json"
        self.local_badges_config = {}
        self.context = ApplicationLoader.applicationContext if ApplicationLoader else None
        try:
            self.current_lang = Locale.getDefault().getLanguage()
            if self.current_lang not in ('ru', 'en'):
                self.current_lang = 'en'
        except Exception:
            self.current_lang = 'en'

    def setup_hooks(self):
        try:
            self.api_class, self.api_badge_source = _resolve_badge_api()
            if not self.api_class:
                return
            self.badge_hook_refs = _install_hooks(self.plugin, self.api_class, self)
            if self.badge_hook_refs:
                log(f"[Packit Badges] hooked {len(self.badge_hook_refs)} method(s)")
            else:
                log("[Packit Badges] hook install failed")
            self._load_custom_badges()
        except Exception as e:
            log(f"[Packit Badges] setup error: {e}")

    def _load_config_from_url(self):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    self.config_url,
                    headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"},
                ),
                timeout=10,
            ) as response:
                config = json.loads(response.read().decode('utf-8'))
                self.local_badges_config = {'badges': config.get('badges', [])}
                return True
        except Exception:
            return False

    def _load_from_prefs(self):
        if not self.context:
            return False
        try:
            s = self.context.getSharedPreferences("packit_badges", 0).getString("badges_config", None)
            if s:
                self.local_badges_config = json.loads(s)
                return True
        except Exception:
            pass
        return False

    def _save_to_prefs(self):
        if not self.context:
            return
        try:
            self.context.getSharedPreferences("packit_badges", 0).edit().putString(
                "badges_config", json.dumps(self.local_badges_config)
            ).apply()
        except Exception:
            pass

    def _ensure_cache(self):
        if self._cache:
            return
        if not self.api_badge_source and self.api_class:
            self.api_badge_source = _source_from_controller(self.api_class)
        if self.api_badge_source:
            self._cache = _get_cache(self.api_badge_source)

    def _register_badge(self, key, dto, profile_status_cls):
        key = _norm_id(key)
        if key is None:
            return
        aid = abs(key)
        ids = {key, aid, -aid}
        for alt in ids:
            self.custom_badges[alt] = dto

        self._ensure_cache()
        if not self._cache:
            return
        info = _make_badge_info(dto, profile_status_cls)
        if not info:
            return
        try:
            for alt in ids:
                self._cache.put(Long.valueOf(int(alt)), info)
        except Exception as e:
            log(f"[Packit Badges] cache.put: {e}")

    def _fill_custom_badges(self, badges_data):
        BadgeDTO = find_class("com.exteragram.messenger.api.dto.BadgeDTO")
        ProfileStatus = find_class("com.exteragram.messenger.api.model.ProfileStatus")
        if not BadgeDTO or not ProfileStatus:
            log("[Packit Badges] BadgeDTO/ProfileStatus missing")
            return

        count = 0
        for entry in badges_data:
            emoji_id = entry.get('emoji_id')
            text = entry.get(f'text_{self.current_lang}') or entry.get('text_en', '')
            if not emoji_id or not text:
                continue

            user_id = entry.get('user_id')
            chat_id = entry.get('chat_id')
            if user_id:
                name = self._user_name(user_id)
                dto = BadgeDTO(int(emoji_id), text.format(user_name=name))
                self._register_badge(user_id, dto, ProfileStatus)
                count += 1
            elif chat_id:
                name = self._chat_name(chat_id)
                dto = BadgeDTO(int(emoji_id), text.format(chat_name=name))
                self._register_badge(chat_id, dto, ProfileStatus)
                count += 1
        log(f"[Packit Badges] loaded {count} custom badge(s), keys={len(self.custom_badges)}")

    def _load_custom_badges(self):
        try:
            self.custom_badges.clear()
            self._load_from_prefs()
            data = self.local_badges_config.get('badges', [])
            if data:
                self._fill_custom_badges(data)
            threading.Thread(target=self._update_from_url, daemon=True).start()
        except Exception as e:
            log(f"[Packit Badges] load error: {e}")

    def _update_from_url(self):
        try:
            old = self.local_badges_config.copy()
            if self._load_config_from_url() and old != self.local_badges_config:
                self._save_to_prefs()
                self.custom_badges.clear()
                self._fill_custom_badges(self.local_badges_config.get('badges', []))
        except Exception:
            pass

    def _user_name(self, user_id):
        try:
            u = MessagesController.getInstance(0).getUser(user_id)
            if u:
                return f"{u.first_name} {u.last_name or ''}".strip()
        except Exception:
            pass
        return f"User {user_id}"

    def _chat_name(self, chat_id):
        try:
            c = MessagesController.getInstance(0).getChat(-abs(chat_id))
            if c:
                return c.title
        except Exception:
            pass
        return f"Channel {chat_id}"

    def cleanup(self):
        try:
            for ref in self.badge_hook_refs:
                if ref:
                    self.plugin.unhook_method(ref)
            self.badge_hook_refs.clear()
            if self._cache and self.custom_badges:
                for bid in list(self.custom_badges.keys()):
                    try:
                        self._cache.remove(Long.valueOf(bid))
                    except Exception:
                        pass
            self.custom_badges.clear()
        except Exception as e:
            log(f"[Packit Badges] cleanup error: {e}")


class CustomBadgeHook(MethodHook):
    def __init__(self, manager):
        self.manager = manager

    def before_hooked_method(self, param):
        try:
            entity_id = param.args[0] if param.args else None
            is_user = param.args[1] if len(param.args) > 1 else True
            badge = _lookup_badge(self.manager.custom_badges, entity_id, is_user)
            if badge is not None:
                param.setResult(badge)
        except Exception as e:
            log(f"[Packit Badges] CustomBadgeHook: {e}")


class CustomBooleanBadgeHook(MethodHook):
    def __init__(self, manager):
        self.manager = manager

    def before_hooked_method(self, param):
        try:
            entity_id = param.args[0] if param.args else None
            if _has_custom_badge(self.manager.custom_badges, entity_id, True):
                param.setResult(True)
            elif _has_custom_badge(self.manager.custom_badges, entity_id, False):
                param.setResult(True)
        except Exception as e:
            log(f"[Packit Badges] CustomBooleanBadgeHook: {e}")

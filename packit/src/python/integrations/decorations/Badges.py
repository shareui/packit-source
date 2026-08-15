# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later


from packutil import logx
from hook_utils import find_class, get_private_field
try:
    from org.telegram.messenger import ApplicationLoader
except:
    ApplicationLoader = None
import threading
import urllib.request
import json
from java.util import Locale

# Любая попытка неправомерного использования системы бейджей автоматически лишает ваш плагин права на публикацию через официальные источники, а также приведёт к перманентной блокировке во всех ресурсах exteraGram и AyuGram без возможности апелляции. Подробнее: https://teletype.in/@exterasquad/forum-rules-ru
# Any attempt to misuse the badge system will automatically revoke your plugin's right to be published through official sources and will result in permanent blocking from all exteraGram and AyuGram resources without the possibility of appeal. Learn more: https://teletype.in/@exterasquad/forum-rules-en

_CONFIG_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json"

# { user_id/chat_id -> {"emoji_id": int, "text": str} }
_cache = {}
_cache_lock = threading.Lock()


class MethodHook:
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        pass


def _get_lang():
    try:
        lang = Locale.getDefault().getLanguage()
        return lang if lang in ('ru', 'en') else 'en'
    except Exception:
        return 'en'


def _build_cache(badges_data, lang):
    result = {}
    for entry in badges_data:
        emoji_id = entry.get('emoji_id')
        text = entry.get(f'text_{lang}') or entry.get('text_en', '')
        if not emoji_id or not text:
            continue
        user_id = entry.get('user_id')
        chat_id = entry.get('chat_id')
        if user_id:
            result[int(user_id)] = {"emoji_id": int(emoji_id), "text": text}
        elif chat_id:
            # store positive; lookup uses abs(chat_id)
            result[int(chat_id)] = {"emoji_id": int(emoji_id), "text": text}
    return result


def _lookup(entity_id):
    """entity_id: positive user_id or positive abs(chat_id)"""
    with _cache_lock:
        return _cache.get(int(entity_id))


def _set_cache(new_cache):
    with _cache_lock:
        _cache.clear()
        _cache.update(new_cache)


def _load_from_prefs(context):
    if not context:
        return None
    try:
        s = context.getSharedPreferences("packit_badges", 0).getString("badges_config", None)
        if s:
            data = json.loads(s)
            if isinstance(data, list):
                return {"badges": data}
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def _save_to_prefs(context, data):
    if not context:
        return
    try:
        context.getSharedPreferences("packit_badges", 0).edit().putString(
            "badges_config", json.dumps(data)
        ).apply()
    except Exception:
        pass


def _fetch_config():
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                _CONFIG_URL,
                headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"},
            ),
            timeout=10,
        ) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return None


class BadgeManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self._hook_refs = []
        self._dex_loaded = False
        self.context = ApplicationLoader.applicationContext if ApplicationLoader else None

    def setup_hooks(self):
        try:
            enabled = True
            try:
                from elyx import settings as _s
                enabled = bool(_s.get("packit_verification", True))
            except Exception:
                pass

            # primary path: precompiled Kotlin dex (config fetch + cache + hooks
            # all live in packit/dex/packit.dex, source in packit/src/kotlin/)
            try:
                from ...core.DexLoader import loadBadges
                if loadBadges(self.context, enabled):
                    self._dex_loaded = True
                    logx("[Packit Badges] using precompiled dex", True)
                    return
            except Exception as e:
                logx(f"[Packit Badges] dex load failed, falling back to python: {e}", False)

            # fallback: pure-python implementation (below)
            if not enabled:
                logx("[Packit Badges] disabled via settings", True)
                return

            lang = _get_lang()
            prefs = _load_from_prefs(self.context)
            if prefs:
                new_cache = _build_cache(prefs.get('badges', []), lang)
                _set_cache(new_cache)
                logx(f"[Packit Badges] loaded {len(_cache)} entry(s) from prefs", True)

            threading.Thread(target=self._update_from_url, daemon=True).start()
            self._install_hooks()
        except Exception as e:
            logx(f"[Packit Badges] setup error: {e}", False)

    def _update_from_url(self):
        try:
            config = _fetch_config()
            if not config:
                return
            lang = _get_lang()
            new_cache = _build_cache(config.get('badges', []), lang)
            _set_cache(new_cache)
            _save_to_prefs(self.context, config)
            logx(f"[Packit Badges] updated {len(_cache)} entry(s) from url", True)
        except Exception as e:
            logx(f"[Packit Badges] update error: {e}", False)

    def _install_hooks(self):
        try:
            adapter_cls = find_class("org.telegram.ui.ProfileActivity$ListAdapter")
            if not adapter_cls:
                logx("[Packit Badges] ListAdapter class not found", True)
                return
            refs = self.plugin.hook_all_methods(adapter_cls, "onBindViewHolder", _BindHook())
            if refs:
                self._hook_refs.extend(refs)
                logx(f"[Packit Badges] hooked onBindViewHolder ({len(refs)} overload(s))", True)
            else:
                logx("[Packit Badges] onBindViewHolder hook failed", True)
        except Exception as e:
            logx(f"[Packit Badges] hook install error: {e}", False)

        try:
            from .ChatBadge import setup_chat_badge_hook
            chat_refs = setup_chat_badge_hook(self.plugin, _lookup)
            self._hook_refs.extend(chat_refs)
        except Exception as e:
            logx(f"[Packit Badges] chat hook error: {e}", False)

        try:
            from .ChatTitleIcon import setup_title_icon_hook
            title_refs = setup_title_icon_hook(self.plugin, _lookup)
            self._hook_refs.extend(title_refs)
        except Exception as e:
            logx(f"[Packit Badges] title icon hook error: {e}", False)

        try:
            from .ProfileTitleIcon import setup_profile_title_icon_hook
            profile_refs = setup_profile_title_icon_hook(self.plugin, _lookup)
            self._hook_refs.extend(profile_refs)
        except Exception as e:
            logx(f"[Packit Badges] profile title icon hook error: {e}", False)

    def cleanup(self):
        try:
            if self._dex_loaded:
                try:
                    from ...core.DexLoader import unloadBadges
                    unloadBadges()
                except Exception as e:
                    logx(f"[Packit Badges] dex unload error: {e}", False)
                self._dex_loaded = False
            for ref in self._hook_refs:
                if ref:
                    self.plugin.unhook_method(ref)
            self._hook_refs.clear()
        except Exception as e:
            logx(f"[Packit Badges] cleanup error: {e}", False)


class _BindHook(MethodHook):
    # VIEW_TYPE_SHADOW_TEXT = 26 (ProfileActivity.ListAdapter constant)
    _SHADOW_TEXT_TYPE = 26

    def after_hooked_method(self, param):
        try:
            holder = param.args[0]
            if holder.getItemViewType() != self._SHADOW_TEXT_TYPE:
                return

            adapter = param.thisObject
            profile = get_private_field(adapter, "this$0")
            if not profile:
                return

            info_row = get_private_field(profile, "infoSectionRow")
            position = param.args[1]
            if info_row is None or int(info_row) != int(position):
                return

            user_id = get_private_field(profile, "userId")
            chat_id = get_private_field(profile, "chatId")

            entity_id = None
            if user_id and int(user_id) != 0:
                entity_id = int(user_id)
            elif chat_id and int(chat_id) != 0:
                entity_id = int(abs(chat_id))

            if entity_id is None:
                return

            entry = _lookup(entity_id)
            if not entry:
                return

            _apply_cell(holder.itemView, entry["emoji_id"], entry["text"])
        except Exception as e:
            logx(f"[Packit Badges] BindHook error: {e}", False)


def _apply_cell(cell, emoji_id, text):
    try:
        from android.text import SpannableStringBuilder
        from org.telegram.ui.Components import AnimatedEmojiSpan
        from android.text import Spanned

        tv = cell.getTextView()
        paint_metrics = tv.getPaint().getFontMetricsInt()

        sb = SpannableStringBuilder()
        sb.append("x")
        sb.setSpan(
            AnimatedEmojiSpan(int(emoji_id), paint_metrics),
            0, 1,
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        sb.append(" ")
        sb.append(text)

        cell.setFixedSize(0)
        cell.setText(sb)
    except Exception as e:
        logx(f"[Packit Badges] apply cell error: {e}", False)
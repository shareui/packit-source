import os
import json
import threading
import urllib.request
from android_utils import log
from hook_utils import find_class
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    ApplicationLoader = None
    log(f"[everyone] import ApplicationLoader failed: {e}")

_INTERNAL_CFG_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json"
_CACHE_FILENAME = "everyone_ids.json"
_TRIGGER = "!everynyan"

_everyone_ids: set = set()
_lock = threading.Lock()


def _get_cache_path() -> str:
    from ..utils.paths import getCacheRoot
    cache_dir = getCacheRoot()
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, _CACHE_FILENAME)


def _load_from_cache() -> bool:
    global _everyone_ids
    try:
        path = _get_cache_path()
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = data.get("everyone")
        if not isinstance(ids, list):
            return False
        with _lock:
            _everyone_ids = set(ids)
        return True
    except Exception as e:
        log(f"[everyone] cache load error: {e}")
        return False


def _fetch_and_save():
    global _everyone_ids
    try:
        req = urllib.request.Request(
            _INTERNAL_CFG_URL,
            headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        cfg = json.loads(raw)
        ids = cfg.get("permissions", {}).get("everyone")
        if not isinstance(ids, list):
            return
        with _lock:
            _everyone_ids = set(ids)
        path = _get_cache_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"everyone": ids}, f)
    except Exception as e:
        log(f"[everyone] fetch error: {e}")


def _is_allowed_sender(user_id: int) -> bool:
    with _lock:
        return user_id in _everyone_ids


def _patch_message(msg):
    try:
        text = getattr(msg, "message", None)
        if not isinstance(text, str) or _TRIGGER not in text:
            return
        from_id = getattr(msg, "from_id", None)
        if from_id is None:
            return
        sender_id = getattr(from_id, "user_id", None)
        if sender_id is None or not _is_allowed_sender(sender_id):
            return
        msg.mentioned = True
        msg.media_unread = True
        log(f"[everyone] mentioned patched from {sender_id}")
    except Exception as e:
        log(f"[everyone] patch error: {e}")


class PutMessagesHook:
    def before_hooked_method(self, param):
        try:
            messages = param.args[0]
            if messages is None or not hasattr(messages, "size"):
                return
            for i in range(messages.size()):
                _patch_message(messages.get(i))
        except Exception as e:
            log(f"[everyone] hook error: {e}")


def setup_hook(plugin) -> list:
    refs = []
    try:
        MessagesStorage = find_class("org.telegram.messenger.MessagesStorage")
        if MessagesStorage is None:
            return refs
        refs = plugin.hook_all_methods(MessagesStorage, "putMessages", PutMessagesHook())
    except Exception as e:
        log(f"[everyone] setup_hook error: {e}")
    return refs


def init():
    _load_from_cache()
    t = threading.Thread(target=_fetch_and_save, daemon=True)
    t.start()

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
_TRIGGER = "@everynyan"

_everyone_ids: set = set()
_lock = threading.Lock()


def _get_cache_path() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    cache_dir = f"/data/data/{pkg}/files/packitCache"
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, _CACHE_FILENAME)


def _load_from_cache() -> bool:
    global _everyone_ids
    try:
        path = _get_cache_path()
        log(f"[everyone] loading cache from {path}")
        if not os.path.exists(path):
            log("[everyone] cache file not found")
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = data.get("everyone")
        if not isinstance(ids, list):
            log(f"[everyone] cache invalid: 'everyone' is {type(ids)}")
            return False
        with _lock:
            _everyone_ids = set(ids)
        log(f"[everyone] loaded from cache: {ids}")
        return True
    except Exception as e:
        log(f"[everyone] cache load error: {e}")
        return False


def _fetch_and_save():
    global _everyone_ids
    log("[everyone] fetching internal_cfg from network")
    try:
        req = urllib.request.Request(
            _INTERNAL_CFG_URL,
            headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        log(f"[everyone] raw response length: {len(raw)}")
        cfg = json.loads(raw)
        ids = cfg.get("permissions", {}).get("everyone")
        if not isinstance(ids, list):
            log(f"[everyone] 'everyone' key missing or invalid: {ids}")
            return
        with _lock:
            _everyone_ids = set(ids)
        log(f"[everyone] ids loaded: {ids}")
        path = _get_cache_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"everyone": ids}, f)
        log(f"[everyone] saved to cache: {path}")
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
        log(f"[everyone] trigger found: {repr(text)}")
        from_id = getattr(msg, "from_id", None)
        if from_id is None:
            log("[everyone] from_id is None")
            return
        sender_id = getattr(from_id, "user_id", None)
        log(f"[everyone] sender_id={sender_id}, allowed={_everyone_ids}")
        if sender_id is None or not _is_allowed_sender(sender_id):
            log(f"[everyone] sender {sender_id} not allowed")
            return
        msg.mentioned = True
        msg.media_unread = True
        log("[everyone] patched: mentioned=True, media_unread=True")
    except Exception as e:
        log(f"[everyone] _patch_message error: {e}")


class PutMessagesHook:
    def before_hooked_method(self, param):
        try:
            log(f"[everyone] putMessages fired, args={len(param.args)}")
            messages = param.args[0]
            if messages is None:
                return
            for i in range(messages.size()):
                _patch_message(messages.get(i))
        except Exception as e:
            log(f"[everyone] PutMessagesHook error: {e}")


def setup_hook(plugin) -> list:
    log("[everyone] setting up hook")
    refs = []
    try:
        MessagesStorage = find_class("org.telegram.messenger.MessagesStorage")
        if MessagesStorage is None:
            log("[everyone] MessagesStorage not found")
            return refs
        refs = plugin.hook_all_methods(MessagesStorage, "putMessages", PutMessagesHook())
        log(f"[everyone] hooked {len(refs)} putMessages overloads")
    except Exception as e:
        log(f"[everyone] setup_hook error: {e}")
    return refs


def init():
    log("[everyone] init started")
    _load_from_cache()
    t = threading.Thread(target=_fetch_and_save, daemon=True)
    t.start()
    log("[everyone] fetch thread started")

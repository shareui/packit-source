import os
import json
import zlib
import ctypes
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader, UserConfig
except Exception as e:
    import android_utils as _au; _au.log(f"achievements: import failed: {e}")
    from ....utils.importFailed import showImportFailedAlert as _sifa; _sifa()

_achievement_pending = False
_bulletin_container = None


def is_achievement_pending() -> bool:
    return _achievement_pending


def register_bulletin_container(container):
    global _bulletin_container
    _bulletin_container = container


def unregister_bulletin_container(container):
    global _bulletin_container
    if _bulletin_container is container:
        _bulletin_container = None


def _load_achievements() -> list:
    path = os.path.join(os.path.dirname(__file__), "../../../../res/achievList.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


ACHIEVEMENTS = _load_achievements()


def _get_configs_dir() -> str:
    from ....utils._paths import getConfigsDir
    return getConfigsDir()


def _get_db_path() -> str:
    return f"{_get_configs_dir()}/achievements.packdb"


def _get_snap_path() -> str:
    return f"{_get_configs_dir()}/achievements_snap.packdb"


def _hash_account_id(user_id: int) -> str:
    import hashlib
    raw = f"packit:{user_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _get_current_account_id() -> str:
    try:
        account = getattr(UserConfig, "selectedAccount", 0)
        user_id = UserConfig.getInstance(account).getClientUserId()
        return _hash_account_id(user_id)
    except Exception as e:
        log(f"achievements._get_current_account_id: {e}")
        return "0"

def _load_lib():
    try:
        so_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "../../../../res/native/libpackitdb.so"
        ))
        log(f"packitdb: loading from {so_path}, exists={os.path.exists(so_path)}")
        lib = ctypes.CDLL(so_path)
        vp  = ctypes.c_void_p
        cp  = ctypes.c_char_p
        i64 = ctypes.c_int64
        u32 = ctypes.c_uint32
        sz  = ctypes.c_size_t
        ci  = ctypes.c_int
        u8p = ctypes.POINTER(ctypes.c_uint8)
        u32p = ctypes.POINTER(ctypes.c_uint32)

        lib.packdb_write_raw.restype = ci
        lib.packdb_write_raw.argtypes = [cp, cp, u8p, u32]

        lib.packdb_read_raw.restype = ci
        lib.packdb_read_raw.argtypes = [cp, cp, u8p, u32p]

        lib.packdb_open_from_payload.restype = vp
        lib.packdb_open_from_payload.argtypes = [cp, cp, u8p, u32]

        lib.packdb_serialize_to.restype = ci
        lib.packdb_serialize_to.argtypes = [vp, u8p, u32p]

        lib.packdb_open.restype = vp
        lib.packdb_open.argtypes = [cp, cp]

        lib.packdb_close.restype = ci
        lib.packdb_close.argtypes = [vp]

        lib.packdb_get.restype = i64
        lib.packdb_get.argtypes = [vp, cp, i64]

        lib.packdb_set.restype = ci
        lib.packdb_set.argtypes = [vp, cp, i64]

        lib.packdb_increment.restype = i64
        lib.packdb_increment.argtypes = [vp, cp, i64]

        lib.packdb_award_has.restype = ci
        lib.packdb_award_has.argtypes = [vp, cp]

        lib.packdb_award_add.restype = ci
        lib.packdb_award_add.argtypes = [vp, cp]

        lib.packdb_award_list.restype = ci
        lib.packdb_award_list.argtypes = [vp, cp, sz]

        lib.packdb_award_count.restype = ci
        lib.packdb_award_count.argtypes = [vp]

        lib.packdb_entry_count.restype = ci
        lib.packdb_entry_count.argtypes = [vp]

        log("packitdb: libpackitdb loaded ok")
        return lib
    except Exception as e:
        log(f"packitdb: load failed: {e}")
        return None

_lib = _load_lib()

_BUF_SIZE = 65536


def _open_db_from_file(path: str, account_id: str):
    if not os.path.exists(path):
        return _lib.packdb_open_from_payload(
            path.encode(), account_id.encode(), None, 0
        )
    buf = (ctypes.c_uint8 * _BUF_SIZE)()
    out_len = ctypes.c_uint32(_BUF_SIZE)
    rc = _lib.packdb_read_raw(path.encode(), account_id.encode(), buf, ctypes.byref(out_len))
    if rc == -3:
        log(f"packitdb: INVALID sig in {os.path.basename(path)} for {account_id}")
        return None
    if rc != 0:
        log(f"packitdb: read_raw error {rc} for {os.path.basename(path)}")
        return None
    compressed = bytes(buf[:out_len.value])
    try:
        raw = zlib.decompress(compressed)
    except Exception as e:
        log(f"packitdb: decompress error: {e}")
        return None
    raw_buf = (ctypes.c_uint8 * len(raw))(*raw)
    return _lib.packdb_open_from_payload(
        path.encode(), account_id.encode(), raw_buf, len(raw)
    )


def _close_and_write(db, path: str, account_id: str):
    raw_buf = (ctypes.c_uint8 * _BUF_SIZE)()
    out_len = ctypes.c_uint32(_BUF_SIZE)
    rc = _lib.packdb_serialize_to(db, raw_buf, ctypes.byref(out_len))
    _lib.packdb_close(db)
    if rc != 0:
        log(f"packitdb: serialize_to error {rc}")
        return
    raw = bytes(raw_buf[:out_len.value])
    compressed = zlib.compress(raw, 6)
    cbuf = (ctypes.c_uint8 * len(compressed))(*compressed)
    rc2 = _lib.packdb_write_raw(path.encode(), account_id.encode(), cbuf, len(compressed))
    if rc2 != 0:
        log(f"packitdb: write_raw error {rc2}")


def _db_to_dict(db) -> dict:
    buf = ctypes.create_string_buffer(8192)
    _lib.packdb_award_list(db, buf, 8192)
    awarded = [s for s in buf.value.decode("utf-8").splitlines() if s]
    data = {"_awarded": awarded}
    for a in ACHIEVEMENTS:
        aid = a["id"]
        data[aid] = int(_lib.packdb_get(db, aid.encode(), 0))
    data["_xp"] = int(_lib.packdb_get(db, b"_xp", 0))
    return data


def _dict_to_db(db, data: dict):
    for key, val in data.items():
        if key == "_awarded":
            continue
        if isinstance(val, int):
            _lib.packdb_set(db, key.encode(), val)
    for aid in data.get("_awarded", []):
        _lib.packdb_award_add(db, aid.encode())


def _load_account(account_id: str = None) -> dict:
    if account_id is None:
        account_id = _get_current_account_id()
    os.makedirs(_get_configs_dir(), exist_ok=True)
    db = _open_db_from_file(_get_db_path(), account_id)
    if not db:
        log(f"packitdb: load failed for {account_id}, trying snapshot")
        db = _open_db_from_file(_get_snap_path(), account_id)
        if not db:
            return {}
    data = _db_to_dict(db)
    _lib.packdb_close(db)
    return data


def _save_account(data: dict, account_id: str = None):
    if account_id is None:
        account_id = _get_current_account_id()
    os.makedirs(_get_configs_dir(), exist_ok=True)
    db_path   = _get_db_path()
    snap_path = _get_snap_path()

    # snapshot current valid state before overwriting
    existing = _open_db_from_file(db_path, account_id)
    if existing:
        _close_and_write(existing, snap_path, account_id)

    db = _lib.packdb_open(db_path.encode(), account_id.encode())
    if not db:
        log("packitdb: packdb_open returned NULL on save")
        return
    _dict_to_db(db, data)
    _close_and_write(db, db_path, account_id)
    log(f"packitdb: saved account {account_id}")


def load_account_data_for_import(account_id: str, account_data: dict):
    os.makedirs(_get_configs_dir(), exist_ok=True)
    db = _lib.packdb_open(_get_db_path().encode(), account_id.encode())
    if not db:
        return
    _dict_to_db(db, account_data)
    _close_and_write(db, _get_db_path(), account_id)


# XP system

_XP_REWARDS = {
    "first_plugin": 100,   "plugins_5": 200,    "plugins_10": 400,
    "plugins_25": 900,     "plugins_50": 1600,  "plugins_100": 3000,
    "plugins_250": 6000,   "plugins_500": 12000,
    "repo_1": 150,         "repo_3": 350,       "repo_5": 600,
    "repo_10": 1200,       "repo_50": 4000,
    "share_1": 100,        "share_5": 300,      "share_10": 600,
    "share_25": 1300,      "share_50": 2400,    "share_100": 5000,
    "download_1": 100,     "download_5": 300,   "download_10": 600,
    "download_25": 1300,   "download_50": 2400,
    "code_1": 150,         "code_3": 350,       "code_5": 700,
    "code_10": 1400,       "code_25": 3000,     "code_50": 6000,
    "code_100": 10000,     "code_200": 18000,
    "report_1": 200,       "report_5": 600,     "report_10": 1200,
    "report_25": 2800,     "report_50": 5600,   "report_100": 11000,
    "copy_1": 100,         "copy_5": 300,       "copy_10": 600,
    "copy_50": 2000,       "copy_100": 4000,    "copy_250": 9000,
    "level_1": 0,  "level_5": 0,  "level_10": 0, "level_25": 0,
    "level_50": 0, "level_60": 0,
    "copy_25": 950,      "download_100": 4500,  "repo_20": 2500,
    "share_200": 7000,   "plugins_75": 2000,    "plugins_200": 4500,
    "report_200": 12000, "code_75": 7500,       "code_150": 10000,
    "days_30": 2000,    "days_182": 5500,   "days_365": 10000,  "days_730": 30000,
    "days_1095": 60000, "days_1460": 100000, "days_1825": 150000, "days_2190": 200000,
    "days_2555": 260000, "days_2920": 330000, "days_3285": 400000, "days_3650": 500000,
    "secret_premium": 666,
    "secret_terraria": 911,
    "secret_identity": 0,
    "secret_curiosity": 1500,
    "secret_subscriber": 5000,
}


def _xp_for_level(level: int) -> int:
    return 50 * (level - 1) * (level - 1)


def _level_from_xp(total_xp: int) -> int:
    level = 1
    while _xp_for_level(level + 1) <= total_xp:
        level += 1
    return min(level, 60)


def get_total_xp(data: dict) -> int:
    return data.get("_xp", 0)


def get_level_info(data: dict) -> tuple:
    total_xp = get_total_xp(data)
    level = _level_from_xp(total_xp)
    if level >= 60:
        return 60, total_xp, _xp_for_level(60)
    current_level_xp = _xp_for_level(level)
    next_level_xp = _xp_for_level(level + 1)
    return level, total_xp - current_level_xp, next_level_xp - current_level_xp


_LEVEL_ACHIEVEMENTS = {
    "level_1": 1, "level_5": 5, "level_10": 10, "level_25": 25,
    "level_50": 50, "level_60": 60,
}

_LOYALTY_ACHIEVEMENTS = {
    "days_30": 30, "days_182": 182, "days_365": 365, "days_730": 730,
    "days_1095": 1095, "days_1460": 1460, "days_1825": 1825, "days_2190": 2190,
    "days_2555": 2555, "days_2920": 2920, "days_3285": 3285, "days_3650": 3650,
}

_SECRET_ACHIEVEMENTS = {"secret_premium", "secret_terraria", "secret_identity", "secret_curiosity", "secret_subscriber"}


def sync_completed(data: dict) -> tuple:
    current_level = _level_from_xp(data.get("_xp", 0))
    for aid in _LEVEL_ACHIEVEMENTS:
        data[aid] = current_level

    try:
        from ....utils.localConfig import days_since_install
        days = days_since_install()
    except Exception:
        days = 0
    for aid in _LOYALTY_ACHIEVEMENTS:
        data[aid] = days

    awarded = data.get("_awarded", [])
    total_xp = data.get("_xp", 0)

    cat_max = {}
    for a in ACHIEVEMENTS:
        aid = a["id"]
        if aid in _LEVEL_ACHIEVEMENTS or aid in _LOYALTY_ACHIEVEMENTS or aid in _SECRET_ACHIEVEMENTS:
            continue
        cat = a.get("category_key", a["category"])
        val = data.get(aid, 0)
        if val > cat_max.get(cat, 0):
            cat_max[cat] = val
    for a in ACHIEVEMENTS:
        aid = a["id"]
        if aid in _LEVEL_ACHIEVEMENTS or aid in _LOYALTY_ACHIEVEMENTS or aid in _SECRET_ACHIEVEMENTS:
            continue
        if data.get(aid, 0) == 0 and aid not in awarded:
            cat = a.get("category_key", a["category"])
            data[aid] = cat_max.get(cat, 0)

    newly_completed = []
    for a in ACHIEVEMENTS:
        aid = a["id"]
        progress = data.get(aid, 0)
        if progress >= a["goal"] and aid not in awarded:
            total_xp += _XP_REWARDS.get(aid, 0)
            awarded.append(aid)
            newly_completed.append(a)

    new_level = _level_from_xp(total_xp)
    if new_level != current_level:
        log(f"achievements.sync_completed: level changed {current_level} -> {new_level}, re-checking level achievements")
        for aid in _LEVEL_ACHIEVEMENTS:
            data[aid] = new_level
        for a in ACHIEVEMENTS:
            aid = a["id"]
            if aid not in _LEVEL_ACHIEVEMENTS:
                continue
            if data.get(aid, 0) >= a["goal"] and aid not in awarded:
                total_xp += _XP_REWARDS.get(aid, 0)
                awarded.append(aid)
                newly_completed.append(a)
    data["_xp"] = total_xp
    data["_awarded"] = awarded
    return data, newly_completed


def _show_achievement_bulletin(achievement: dict, on_hide=None):
    try:
        from android_utils import run_on_ui_thread
        from client_utils import get_last_fragment
        from org.telegram.ui.Components import BulletinFactory
        from hook_utils import find_class
        from androidx.core.content import ContextCompat
        from java import dynamic_proxy
        from java.lang import Runnable
        from elyx import strings

        icon_name = achievement.get("icon", "msg_fave")
        title_key = achievement.get("title_key", "")
        title_fallback = achievement.get("title", "")

        class _Runnable(dynamic_proxy(Runnable)):
            def __init__(self, fn):
                super().__init__()
                self._fn = fn
            def run(self):
                try:
                    self._fn()
                except Exception as _e:
                    log(f"achievements: bulletin runnable error: {_e}")

        def show():
            fragment = get_last_fragment()
            if fragment is None:
                if on_hide:
                    on_hide()
                return

            def _open():
                from ....ui.AchievementsActivity.fragment import show_hint_sheet
                show_hint_sheet(achievement)

            ctx = fragment.getContext()
            try:
                R_tg = find_class("org.telegram.messenger.R")
                icon_res = getattr(R_tg.drawable, icon_name)
                drawable = ContextCompat.getDrawable(ctx, icon_res)
            except Exception as _e:
                log(f"achievements: bulletin icon error: {_e}")
                drawable = None

            title = str(strings[title_key]) if title_key and title_key in strings else title_fallback

            container = _bulletin_container
            if container is not None:
                rp = fragment.getResourceProvider()
                factory = BulletinFactory.of(container, rp)
            else:
                factory = BulletinFactory.of(fragment)

            if drawable is not None:
                bulletin = factory.createSimpleBulletin(drawable, strings.achiev_unlocked, title, strings.achiev_open, _Runnable(_open))
            else:
                bulletin = factory.createSimpleBulletin(strings.achiev_unlocked, title, strings.achiev_open, _Runnable(_open))
            if on_hide:
                bulletin.setOnHideListener(_Runnable(on_hide))
            bulletin.show(True)

        run_on_ui_thread(show)
    except Exception as e:
        log(f"achievements._show_achievement_bulletin: error: {e}")


def _play_achievement_sound():
    try:
        from ....utils.media import playSound
        sound_path = os.path.join(os.path.dirname(__file__), "../../../../res/sounds/received-achievement.mp3")
        playSound(sound_path, "sfx_achievement", check_pending=False, default=True)
    except Exception as e:
        log(f"achievements._play_achievement_sound: error: {e}")


def _notify_newly_completed(newly_completed: list):
    log(f"achievements._notify_newly_completed: count={len(newly_completed)}")
    if not newly_completed:
        return
    _show_achievement_queue(list(newly_completed))


def _show_achievement_queue(queue: list):
    if not queue:
        return
    try:
        from elyx import settings
        if settings.get("disable_achievements_notify", False):
            return
    except Exception as e:
        log(f"achievements._show_achievement_queue: settings check error: {e}")
    a = queue[0]
    rest = queue[1:]
    log(f"achievements._show_achievement_queue: id={a['id']}, remaining={len(rest)}")
    if a.get("playSound", True):
        _play_achievement_sound()
    _show_achievement_bulletin(a, on_hide=lambda: _show_achievement_queue(rest))


# public API

def get_progress(achievement_id: str) -> int:
    return _load_account().get(achievement_id, 0)


def set_progress(achievement_id: str, value: int):
    data = _load_account()
    data[achievement_id] = value
    data, newly_completed = sync_completed(data)
    _save_account(data)
    _notify_newly_completed(newly_completed)


def increment(achievement_id: str, by: int = 1):
    data = _load_account()
    data[achievement_id] = data.get(achievement_id, 0) + by
    data, newly_completed = sync_completed(data)
    _save_account(data)
    _notify_newly_completed(newly_completed)


def increment_category(category: str, by: int = 1):
    data = _load_account()
    for a in ACHIEVEMENTS:
        if a["category"] == category:
            data[a["id"]] = data.get(a["id"], 0) + by
    data, newly_completed = sync_completed(data)
    _save_account(data)
    _notify_newly_completed(newly_completed)


def unlock_secret(achievement_id: str):
    full_id = f"secret_{achievement_id}"
    log(f"achievements.unlock_secret: id={full_id}")
    data = _load_account()
    log(f"achievements.unlock_secret: current value={data.get(full_id)}, awarded={full_id in data.get('_awarded', [])}")
    data[full_id] = 1
    data, newly_completed = sync_completed(data)
    log(f"achievements.unlock_secret: newly_completed={[a['id'] for a in newly_completed]}")
    _save_account(data)
    _notify_newly_completed(newly_completed)


def is_completed(achievement_id: str) -> bool:
    for a in ACHIEVEMENTS:
        if a["id"] == achievement_id:
            return get_progress(achievement_id) >= a["goal"]
    return False


def get_all_with_progress() -> list:
    data = _load_account()
    result = []
    for a in ACHIEVEMENTS:
        progress = data.get(a["id"], 0)
        is_secret = a["id"] in _SECRET_ACHIEVEMENTS
        unlocked = progress >= a["goal"]
        result.append({**a, "progress": min(progress, a["goal"]), "secret": is_secret, "unlocked": unlocked})
    return result


def get_stats() -> dict:
    data = _load_account()
    data, _ = sync_completed(data)
    _save_account(data)
    return {
        "installed_plugins": data.get("first_plugin", 0),
        "repositories_added": data.get("repo_1", 0),
        "plugins_shared": data.get("share_1", 0),
        "plugins_downloaded": data.get("download_1", 0),
        "code_views": data.get("code_1", 0),
        "reports_sent": data.get("report_1", 0),
        "links_copied": data.get("copy_1", 0),
        "level_info": get_level_info(data),
        "total_xp": get_total_xp(data),
        "completed": len(data.get("_awarded", [])),
        "total": len(ACHIEVEMENTS),
    }


def sync_accounts():
    try:
        from org.telegram.messenger import UserConfig as _UC
        active_ids = set()
        for i in range(_UC.MAX_ACCOUNT_COUNT):
            instance = _UC.getInstance(i)
            if instance.isClientActivated():
                active_ids.add(_hash_account_id(instance.getClientUserId()))
        log(f"achievements.sync_accounts: active accounts={len(active_ids)}")
    except Exception as e:
        log(f"achievements.sync_accounts: {e}")

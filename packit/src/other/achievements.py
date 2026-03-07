import os
import json
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()

def _load_achievements() -> list:
    path = os.path.join(os.path.dirname(__file__), "../../res/achievList.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


ACHIEVEMENTS = _load_achievements()


def _get_configs_dir() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache/packitConfigs"


def _get_achievements_path() -> str:
    return f"{_get_configs_dir()}/achievements.json"


def _load() -> dict:
    path = _get_achievements_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"achievements._load: error: {e}")
        return {}


def _save(data: dict):
    try:
        os.makedirs(_get_configs_dir(), exist_ok=True)
        with open(_get_achievements_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"achievements._save: error: {e}")


#  XP system 

# xp reward per achievement id, assigned by difficulty
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
    # level achievements give no XP
    "level_1": 0,  "level_5": 0,  "level_10": 0, "level_25": 0,
    "level_50": 0, "level_75": 0, "level_80": 0, "level_90": 0,
    "level_95": 0, "level_100": 0,
    # loyalty achievements
    "days_30": 2000,    "days_182": 5500,   "days_365": 10000,  "days_730": 30000,
    "days_1095": 60000, "days_1460": 100000, "days_1825": 150000, "days_2190": 200000,
    "days_2555": 260000, "days_2920": 330000, "days_3285": 400000, "days_3650": 500000,
    # secret achievements
    "secret_premium": 666,
    "secret_terraria": 911,
    "secret_identity": 0,
}

# total XP needed to reach a given level: 50 * (level-1)^2
def _xp_for_level(level: int) -> int:
    return 50 * (level - 1) * (level - 1)


def _level_from_xp(total_xp: int) -> int:
    level = 1
    while _xp_for_level(level + 1) <= total_xp:
        level += 1
    return min(level, 100)


def get_total_xp(data: dict) -> int:
    return data.get("_xp", 0)


def get_level_info(data: dict) -> tuple:
    # returns (level, xp_into_current_level, xp_needed_for_current_level)
    total_xp = get_total_xp(data)
    level = _level_from_xp(total_xp)
    if level >= 100:
        return 100, total_xp, _xp_for_level(100)
    current_level_xp = _xp_for_level(level)
    next_level_xp = _xp_for_level(level + 1)
    xp_into = total_xp - current_level_xp
    xp_needed = next_level_xp - current_level_xp
    return level, xp_into, xp_needed


#  sync: awards XP for newly completed achievements 

_LEVEL_ACHIEVEMENTS = {
    "level_1": 1, "level_5": 5, "level_10": 10, "level_25": 25,
    "level_50": 50, "level_75": 75, "level_80": 80, "level_90": 90,
    "level_95": 95, "level_100": 100,
}

_LOYALTY_ACHIEVEMENTS = {
    "days_30": 30, "days_182": 182, "days_365": 365, "days_730": 730,
    "days_1095": 1095, "days_1460": 1460, "days_1825": 1825, "days_2190": 2190,
    "days_2555": 2555, "days_2920": 2920, "days_3285": 3285, "days_3650": 3650,
}


def sync_completed(data: dict) -> tuple:
    # returns (updated_data, list_of_newly_completed_achievement_dicts)
    current_level = _level_from_xp(data.get("_xp", 0))
    for aid in _LEVEL_ACHIEVEMENTS:
        data[aid] = current_level

    try:
        from .localConfig import days_since_install
        days = days_since_install()
    except Exception:
        days = 0
    for aid in _LOYALTY_ACHIEVEMENTS:
        data[aid] = days

    awarded = data.get("_awarded", [])
    total_xp = data.get("_xp", 0)
    newly_completed = []
    for a in ACHIEVEMENTS:
        aid = a["id"]
        progress = data.get(aid, 0)
        if progress >= a["goal"] and aid not in awarded:
            total_xp += _XP_REWARDS.get(aid, 0)
            awarded.append(aid)
            newly_completed.append(a)
    data["_xp"] = total_xp
    data["_awarded"] = awarded
    return data, newly_completed


def _show_achievement_bulletin(achievement: dict):
    try:
        from android_utils import run_on_ui_thread
        from client_utils import get_last_fragment
        from org.telegram.ui.Components import BulletinFactory
        from org.telegram.messenger import R
        from androidx.core.content import ContextCompat

        icon_name = achievement["icon"]
        title = achievement["title"]

        def show():
            fragment = get_last_fragment()
            if fragment is None:
                return
            try:
                icon_res = getattr(R.drawable, icon_name)
                drawable = ContextCompat.getDrawable(fragment.getContext(), icon_res)
            except Exception as e:
                log(f"achievements._show_achievement_bulletin: drawable error: {e}")
                drawable = None

            factory = BulletinFactory.of(fragment)
            if drawable is not None:
                bulletin = factory.createSimpleBulletin(drawable, "Achievement Unlocked!", title)
            else:
                bulletin = factory.createSimpleBulletin("Achievement Unlocked!", title)
            bulletin.show(True)

        run_on_ui_thread(show)
    except Exception as e:
        log(f"achievements._show_achievement_bulletin: error: {e}")


def _play_achievement_sound():
    try:
        from android.media import MediaPlayer, AudioManager
        from java import dynamic_proxy

        sound_path = os.path.join(os.path.dirname(__file__), "../../res/sounds/received-achievement.mp3")

        if not os.path.exists(sound_path):
            log(f"achievements._play_achievement_sound: file not found: {sound_path}")
            return

        player = MediaPlayer()
        try:
            player.setAudioStreamType(AudioManager.STREAM_MUSIC)
            player.setDataSource(sound_path)
            player.prepare()
        except Exception as e:
            log(f"achievements._play_achievement_sound: prepare error: {e}")
            try:
                player.reset()
                player.release()
            except Exception:
                pass
            return

        try:
            player.start()
        except Exception as e:
            log(f"achievements._play_achievement_sound: start error: {e}")
            try:
                player.reset()
                player.release()
            except Exception:
                pass
            return

        class _Listener(dynamic_proxy(MediaPlayer.OnCompletionListener)):
            def onCompletion(self, mp):
                try:
                    mp.reset()
                    mp.release()
                except Exception:
                    pass

        try:
            player.setOnCompletionListener(_Listener())
        except Exception as e:
            log(f"achievements._play_achievement_sound: listener error: {e}")
    except Exception as e:
        log(f"achievements._play_achievement_sound: error: {e}")


def _notify_newly_completed(newly_completed: list):
    if not newly_completed:
        return
    for a in newly_completed:
        if a.get("playSound", True):
            _play_achievement_sound()
        _show_achievement_bulletin(a)


#  public API 

def get_progress(achievement_id: str) -> int:
    return _load().get(achievement_id, 0)


def set_progress(achievement_id: str, value: int):
    data = _load()
    data[achievement_id] = value
    data, newly_completed = sync_completed(data)
    _save(data)
    _notify_newly_completed(newly_completed)


def increment(achievement_id: str, by: int = 1):
    data = _load()
    current = data.get(achievement_id, 0)
    data[achievement_id] = current + by
    data, newly_completed = sync_completed(data)
    _save(data)
    _notify_newly_completed(newly_completed)


def increment_category(category: str, by: int = 1):
    # increments all achievements in the given category
    data = _load()
    for a in ACHIEVEMENTS:
        if a["category"] == category:
            current = data.get(a["id"], 0)
            data[a["id"]] = current + by
    data, newly_completed = sync_completed(data)
    _save(data)
    _notify_newly_completed(newly_completed)


_SECRET_ACHIEVEMENTS = {"secret_premium", "secret_terraria", "secret_identity"}


def unlock_secret(achievement_id: str):
    full_id = f"secret_{achievement_id}"
    data = _load()
    data[full_id] = 1
    data, newly_completed = sync_completed(data)
    _save(data)
    _notify_newly_completed(newly_completed)


def is_completed(achievement_id: str) -> bool:
    for a in ACHIEVEMENTS:
        if a["id"] == achievement_id:
            return get_progress(achievement_id) >= a["goal"]
    return False


def get_all_with_progress() -> list:
    # returns list of dicts: achievement + current progress + secret flag
    data = _load()
    result = []
    for a in ACHIEVEMENTS:
        progress = data.get(a["id"], 0)
        is_secret = a["id"] in _SECRET_ACHIEVEMENTS
        unlocked = progress >= a["goal"]
        result.append({**a, "progress": min(progress, a["goal"]), "secret": is_secret, "unlocked": unlocked})
    return result


def get_stats() -> dict:
    # returns raw progress counters for statistics display
    data = _load()
    # sync in case achievements were completed before XP system existed
    data, _ = sync_completed(data)
    _save(data)
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

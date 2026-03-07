import os
import json
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()

# each achievement: id, category, title, goal (int), hint shown on click
ACHIEVEMENTS = [
    # Installing plugins
    {
        "id": "first_plugin",
        "category": "Installing plugins",
        "title": "Newbie",
        "goal": 1,
        "hint": "Open PackIt, go to the installation interface and pick any plugin from the repository. Tap the install button and confirm the installation."
    },
    {
        "id": "plugins_5",
        "category": "Installing plugins",
        "title": "Getting Started",
        "goal": 5,
        "hint": "Browse through the available repositories and install 5 plugins in total. Try exploring different categories to find something useful."
    },
    {
        "id": "plugins_10",
        "category": "Installing plugins",
        "title": "Enthusiast",
        "goal": 10,
        "hint": "You are getting the hang of it. Install 10 plugins across any repositories. A good moment to add a few extra repos to expand your options."
    },
    {
        "id": "plugins_25",
        "category": "Installing plugins",
        "title": "Collector",
        "goal": 25,
        "hint": "At this point you clearly enjoy customizing your client. Keep installing plugins until you reach 25 total installations."
    },
    {
        "id": "plugins_50",
        "category": "Installing plugins",
        "title": "Power User",
        "goal": 50,
        "hint": "50 installations means you know what you want. At this point you probably have a solid setup. Keep going."
    },
    {
        "id": "plugins_100",
        "category": "Installing plugins",
        "title": "Hoarder",
        "goal": 100,
        "hint": "100 plugins installed. You have tried almost everything out there. Do you even remember what half of them do?"
    },
    {
        "id": "plugins_250",
        "category": "Installing plugins",
        "title": "Obsessed",
        "goal": 250,
        "hint": "250 installations. At this point PackIt is basically your lifestyle. Keep installing, there is no going back."
    },
    {
        "id": "plugins_500",
        "category": "Installing plugins",
        "title": "No Life",
        "goal": 500,
        "hint": "500 plugin installations. We are not sure if this is impressive or concerning. Either way, you have earned this."
    },

    # Repositories
    {
        "id": "repo_1",
        "category": "Repositories",
        "title": "First Source",
        "goal": 1,
        "hint": "Add your first repository. Open PackIt settings, go to Repositories and paste a valid repository URL."
    },
    {
        "id": "repo_3",
        "category": "Repositories",
        "title": "Expanding Horizons",
        "goal": 3,
        "hint": "Add 3 repositories in total. More sources mean more plugins to discover."
    },
    {
        "id": "repo_5",
        "category": "Repositories",
        "title": "Multi-Source",
        "goal": 5,
        "hint": "You are pulling plugins from 5 different repositories. At this point you know exactly where to look."
    },
    {
        "id": "repo_10",
        "category": "Repositories",
        "title": "Aggregator",
        "goal": 10,
        "hint": "10 repositories added. You have probably seen every plugin available at this point."
    },
    {
        "id": "repo_50",
        "category": "Repositories",
        "title": "Repository Maniac",
        "goal": 50,
        "hint": "50 repositories. There is no way all of these are active. Are you okay?"
    },

    # Sharing
    {
        "id": "share_1",
        "category": "Sharing",
        "title": "Spread the Word",
        "goal": 1,
        "hint": "Share a plugin file with someone. Open any plugin in the installation interface, tap the burger menu and hit Share."
    },
    {
        "id": "share_5",
        "category": "Sharing",
        "title": "Evangelist",
        "goal": 5,
        "hint": "You have shared 5 plugins. Your friends are either grateful or confused by now."
    },
    {
        "id": "share_10",
        "category": "Sharing",
        "title": "Distributor",
        "goal": 10,
        "hint": "10 shares done. You are basically running your own plugin delivery service at this point."
    },
    {
        "id": "share_25",
        "category": "Sharing",
        "title": "Plugin Dealer",
        "goal": 25,
        "hint": "25 plugins shared. People probably come to you when they need a recommendation."
    },
    {
        "id": "share_50",
        "category": "Sharing",
        "title": "Community Pillar",
        "goal": 50,
        "hint": "50 shares. You are holding this community together one plugin file at a time."
    },
    {
        "id": "share_100",
        "category": "Sharing",
        "title": "The Supplier",
        "goal": 100,
        "hint": "100 plugins shared. At this point sharing is just a reflex for you."
    },

    # Downloading
    {
        "id": "download_1",
        "category": "Downloading",
        "title": "Grab and Go",
        "goal": 1,
        "hint": "Download a plugin file to your device. Open any plugin in the installation interface, tap the burger menu and hit Download."
    },
    {
        "id": "download_5",
        "category": "Downloading",
        "title": "Local Hoarder",
        "goal": 5,
        "hint": "You have downloaded 5 plugin files. Your downloads folder is getting interesting."
    },
    {
        "id": "download_10",
        "category": "Downloading",
        "title": "Backup Freak",
        "goal": 10,
        "hint": "10 plugin files downloaded. Clearly you like having things locally, just in case."
    },
    {
        "id": "download_25",
        "category": "Downloading",
        "title": "Archivist",
        "goal": 25,
        "hint": "25 downloads. You are building quite the offline collection."
    },
    {
        "id": "download_50",
        "category": "Downloading",
        "title": "The Vault",
        "goal": 50,
        "hint": "50 plugin files saved locally. Nothing gets past you without being downloaded first."
    },

    # Viewing code
    {
        "id": "code_1",
        "category": "Viewing code",
        "title": "Curious",
        "goal": 1,
        "hint": "Open the source code of any plugin. Tap the burger menu in the installation interface and hit Code."
    },
    {
        "id": "code_3",
        "category": "Viewing code",
        "title": "Peeking Inside",
        "goal": 3,
        "hint": "You have looked at the code of 3 plugins. Good habit — always know what you are installing."
    },
    {
        "id": "code_5",
        "category": "Viewing code",
        "title": "Code Reader",
        "goal": 5,
        "hint": "5 plugins inspected. You are getting comfortable reading other people's code."
    },
    {
        "id": "code_10",
        "category": "Viewing code",
        "title": "Reviewer",
        "goal": 10,
        "hint": "10 code reviews done. At this point you probably have opinions about code style."
    },
    {
        "id": "code_25",
        "category": "Viewing code",
        "title": "Auditor",
        "goal": 25,
        "hint": "25 plugins reviewed. You take security seriously and that is genuinely admirable."
    },
    {
        "id": "code_50",
        "category": "Viewing code",
        "title": "Inspector",
        "goal": 50,
        "hint": "50 code views. You probably spot patterns across plugins by now."
    },
    {
        "id": "code_100",
        "category": "Viewing code",
        "title": "Paranoid",
        "goal": 100,
        "hint": "100 plugins checked before installing. Trust no one. Read everything. Stay safe."
    },
    {
        "id": "code_200",
        "category": "Viewing code",
        "title": "The Analyst",
        "goal": 200,
        "hint": "200 code reviews. At this point you have read more plugin code than most plugin authors."
    },

    # Reporting
    {
        "id": "report_1",
        "category": "Reporting",
        "title": "Whistleblower",
        "goal": 1,
        "hint": "Report a plugin for the first time. If something looks wrong, tap the burger menu in the installation interface and hit Report."
    },
    {
        "id": "report_5",
        "category": "Reporting",
        "title": "Watchdog",
        "goal": 5,
        "hint": "5 reports submitted. You are actively helping keep the ecosystem clean."
    },
    {
        "id": "report_10",
        "category": "Reporting",
        "title": "Moderator at Heart",
        "goal": 10,
        "hint": "10 reports. You clearly care about the quality of what gets distributed here."
    },
    {
        "id": "report_25",
        "category": "Reporting",
        "title": "Quality Guardian",
        "goal": 25,
        "hint": "25 reports filed. The community is safer because of people like you."
    },
    {
        "id": "report_50",
        "category": "Reporting",
        "title": "The Sheriff",
        "goal": 50,
        "hint": "50 reports. Nobody gets away with a bad plugin on your watch."
    },
    {
        "id": "report_100",
        "category": "Reporting",
        "title": "Zero Tolerance",
        "goal": 100,
        "hint": "100 reports submitted. Either you have very high standards or very low tolerance. Probably both."
    },

    # Copying links
    {
        "id": "copy_1",
        "category": "Copying links",
        "title": "Link Sharer",
        "goal": 1,
        "hint": "Copy a plugin link for the first time. Open any plugin in the installation interface, tap the burger menu and hit Copy link."
    },
    {
        "id": "copy_5",
        "category": "Copying links",
        "title": "Referrer",
        "goal": 5,
        "hint": "5 links copied. You like sending people directly to specific plugins."
    },
    {
        "id": "copy_10",
        "category": "Copying links",
        "title": "Link Machine",
        "goal": 10,
        "hint": "10 links copied. You are a reliable source of plugin references."
    },
    {
        "id": "copy_50",
        "category": "Copying links",
        "title": "Hyperlinker",
        "goal": 50,
        "hint": "50 links copied. Your clipboard history must be fascinating."
    },
    {
        "id": "copy_100",
        "category": "Copying links",
        "title": "Deep Linker",
        "goal": 100,
        "hint": "100 plugin links copied. At this point copy-pasting is basically muscle memory."
    },
    {
        "id": "copy_250",
        "category": "Copying links",
        "title": "The Index",
        "goal": 250,
        "hint": "250 links copied. You are a living directory of plugin links at this point."
    },

    # Levels
    {
        "id": "level_1",
        "category": "Levels",
        "title": "Just downloaded PackIt",
        "goal": 1,
        "hint": "Welcome. You are just getting started."
    },
    {
        "id": "level_5",
        "category": "Levels",
        "title": "Getting Comfortable",
        "goal": 5,
        "hint": "You have spent enough time with PackIt to know your way around. Level 5 reached."
    },
    {
        "id": "level_10",
        "category": "Levels",
        "title": "Part of the Routine",
        "goal": 10,
        "hint": "PackIt is no longer new to you. It is just part of how you use Telegram now."
    },
    {
        "id": "level_25",
        "category": "Levels",
        "title": "Here to Stay",
        "goal": 25,
        "hint": "Level 25. At this point it is safe to say you are not going anywhere."
    },
    {
        "id": "level_50",
        "category": "Levels",
        "title": "Halfway There",
        "goal": 50,
        "hint": "Level 50. The halfway point. You have come a long way and there is still more ahead."
    },
    {
        "id": "level_75",
        "category": "Levels",
        "title": "Deep in the Rabbit Hole",
        "goal": 75,
        "hint": "Level 75. Most people never get this far. You are not most people."
    },
    {
        "id": "level_80",
        "category": "Levels",
        "title": "No Turning Back",
        "goal": 80,
        "hint": "Level 80. You have invested too much to stop now. Not that you would want to."
    },
    {
        "id": "level_90",
        "category": "Levels",
        "title": "The Final Stretch",
        "goal": 90,
        "hint": "Level 90. The end is in sight. You can almost see the top from here."
    },
    {
        "id": "level_95",
        "category": "Levels",
        "title": "Almost There",
        "goal": 95,
        "hint": "Level 95. Five levels away from the absolute maximum. Finish what you started."
    },
    {
        "id": "level_100",
        "category": "Levels",
        "title": "Transcendent",
        "goal": 100,
        "hint": "Level 100. The maximum. There is nothing beyond this point. You have seen it all."
    },

    # Loyalty
    {
        "id": "days_30",
        "category": "Loyalty",
        "title": "First Month",
        "goal": 30,
        "hint": "You have been using PackIt for a month. The plugins are already part of your daily setup."
    },
    {
        "id": "days_182",
        "category": "Loyalty",
        "title": "Half a Year",
        "goal": 182,
        "hint": "Six months with PackIt. You have seen updates come and go and you are still here."
    },
    {
        "id": "days_365",
        "category": "Loyalty",
        "title": "One Year",
        "goal": 365,
        "hint": "A full year. PackIt has been part of your Telegram experience through all of it."
    },
    {
        "id": "days_730",
        "category": "Loyalty",
        "title": "Two Years",
        "goal": 730,
        "hint": "Two years in. Assuming PackIt and exteraGram are still around — and if you are reading this, they are."
    },
    {
        "id": "days_1095",
        "category": "Loyalty",
        "title": "Three Years",
        "goal": 1095,
        "hint": "Three years. Honestly impressive. We hope the plugin ecosystem is still alive and well by now."
    },
    {
        "id": "days_1460",
        "category": "Loyalty",
        "title": "Four Years",
        "goal": 1460,
        "hint": "Four years. At this point you have probably outlasted a few Telegram forks. We appreciate your loyalty."
    },
    {
        "id": "days_1825",
        "category": "Loyalty",
        "title": "Five Years",
        "goal": 1825,
        "hint": "Five years. Half a decade. We genuinely did not expect anyone to reach this. Is exteraGram even still a thing?"
    },
    {
        "id": "days_2190",
        "category": "Loyalty",
        "title": "Six Years",
        "goal": 2190,
        "hint": "Six years. If you are still using PackIt in 2030 or whenever this is, you deserve a medal. Or a doctor."
    },
    {
        "id": "days_2555",
        "category": "Loyalty",
        "title": "Seven Years",
        "goal": 2555,
        "hint": "Seven years. PackIt is either immortal or you forgot to uninstall it. Either way — respect."
    },
    {
        "id": "days_2920",
        "category": "Loyalty",
        "title": "Eight Years",
        "goal": 2920,
        "hint": "Eight years. At this point we are genuinely surprised this codebase still runs. So are you, probably."
    },
    {
        "id": "days_3285",
        "category": "Loyalty",
        "title": "Nine Years",
        "goal": 3285,
        "hint": "Nine years. Is Telegram still relevant? Is exteraGram maintained? We have no idea. But here you are."
    },
    {
        "id": "days_3650",
        "category": "Loyalty",
        "title": "Ten Years",
        "goal": 3650,
        "hint": "Ten years. A decade. This achievement was written as a joke. We did not think anyone would ever see it. Hi."
    },

    # Unknown achievements
    {
        "id": "secret_premium",
        "category": "Unknown achievements",
        "title": "You got premium",
        "goal": 1,
        "hint": "I feel sorry for you if you were in a public place, or near your parents. But at least now you have premium."
    },
    {
        "id": "secret_terraria",
        "category": "Unknown achievements",
        "title": "Now you are a terrorist",
        "goal": 1,
        "hint": "Now you're a terrorist... Should I call the police? Or the FBI?"
    },
    {
        "id": "secret_identity",
        "category": "Unknown achievements",
        "title": "Are you sure it's you?",
        "goal": 1,
        "hint": "Bro, I don't think you're seriously the creator of the PackIt. Real or fake?"
    },
]


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


# --- XP system ---

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


# --- sync: awards XP for newly completed achievements ---

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


def sync_completed(data: dict) -> dict:
    # auto-update level achievement progress from current XP
    current_level = _level_from_xp(data.get("_xp", 0))
    for aid in _LEVEL_ACHIEVEMENTS:
        data[aid] = current_level

    # auto-update loyalty achievement progress from days since install
    try:
        from .localConfig import days_since_install
        days = days_since_install()
    except Exception:
        days = 0
    for aid in _LOYALTY_ACHIEVEMENTS:
        data[aid] = days

    # award XP for newly completed achievements
    awarded = data.get("_awarded", [])
    total_xp = data.get("_xp", 0)
    for a in ACHIEVEMENTS:
        aid = a["id"]
        progress = data.get(aid, 0)
        if progress >= a["goal"] and aid not in awarded:
            total_xp += _XP_REWARDS.get(aid, 0)
            awarded.append(aid)
    data["_xp"] = total_xp
    data["_awarded"] = awarded
    return data


# --- public API ---

def get_progress(achievement_id: str) -> int:
    return _load().get(achievement_id, 0)


def set_progress(achievement_id: str, value: int):
    data = _load()
    data[achievement_id] = value
    data = sync_completed(data)
    _save(data)


def increment(achievement_id: str, by: int = 1):
    data = _load()
    current = data.get(achievement_id, 0)
    data[achievement_id] = current + by
    data = sync_completed(data)
    _save(data)


def increment_category(category: str, by: int = 1):
    # increments all achievements in the given category
    data = _load()
    for a in ACHIEVEMENTS:
        if a["category"] == category:
            current = data.get(a["id"], 0)
            data[a["id"]] = current + by
    data = sync_completed(data)
    _save(data)


_SECRET_ACHIEVEMENTS = {"secret_premium", "secret_terraria", "secret_identity"}


def unlock_secret(achievement_id: str):
    full_id = f"secret_{achievement_id}"
    data = _load()
    data[full_id] = 1
    data = sync_completed(data)
    _save(data)


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
    data = sync_completed(data)
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

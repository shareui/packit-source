# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android_utils import log

def _filesDir() -> str:
    from org.telegram.messenger import ApplicationLoader
    return ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()

def _cacheDir() -> str:
    from org.telegram.messenger import ApplicationLoader
    return ApplicationLoader.applicationContext.getCacheDir().getAbsolutePath()

def getCacheRoot() -> str:
    return _filesDir() + "/packit"

def getConfigsDir() -> str:
    return _filesDir() + "/packit/packitConfigs"

def getReposCacheDir() -> str:
    return _filesDir() + "/packit/reposCache"

def getTempDir() -> str:
    return _filesDir() + "/packit/packitTemp"

def getPluginCacheDir(subdir: str) -> str:
    return _filesDir() + f"/packit/.cache/plugins/{subdir}"

def getPluginsDir() -> str:
    return _filesDir() + "/plugins"

def getElyxArchivesDir() -> str:
    return _filesDir() + "/plugins/ElyxPlugins/archives"

def getPackitArchivesDir() -> str:
    return _filesDir() + "/plugins/ElyxPlugins/packit"

def getBitHashSoPath() -> str:
    from ..nativeLoader import detectArch
    return _filesDir() + f"/plugins/ElyxPlugins/shareui_packit/packit/native/{detectArch()}/libbithash.so"

def getRepoCachePath(repoId: str) -> str:
    return _filesDir() + f"/packit/reposCache/{repoId}.json"

def getRepoIndexPath(rmRid: str) -> str:
    return _filesDir() + f"/packit/reposCache/{rmRid}-index.json"

def getIconPackTmpPath(packId: str) -> str:
    return _cacheDir() + f"/packit_iconpack_{packId}.icons"

def getClassesCachePath() -> str:
    return _filesDir() + "/packit/.cache/classes/icons.json"

def getKeysDir() -> str:
    return _filesDir() + "/packit/.secret/keys"

def getGeminiCachePath() -> str:
    return _filesDir() + "/packit/.cache/api/gemini.json"

def getPackItPluginDir() -> str:
    return _filesDir() + "/plugins/ElyxPlugins/shareui_packit"

def _externalCacheDir() -> str:
    from org.telegram.messenger import ApplicationLoader
    d = ApplicationLoader.applicationContext.getExternalCacheDir()
    return d.getAbsolutePath() if d else _cacheDir()

def getShareCachePath(filename: str) -> str:
    # Any file handed to ShareAlert / SendMessagesHelper MUST live in EXTERNAL
    # app storage. Telegram's AndroidUtilities.isInternalUri() blocks sending
    # any file whose path is under the app's internal data dir
    # (/data/user/0/<pkg>/... incl. getCacheDir()) as a security measure — the
    # send then shows "attachment not supported" or silently drops. External
    # app-specific cache needs no runtime permission on any Android version and
    # passes the check. Use this for every shared temp file in the project.
    return _externalCacheDir() + "/" + filename

def getLogShareCachePath() -> str:
    return getShareCachePath("packit_latestlog.txt")

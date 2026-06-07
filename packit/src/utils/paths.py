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
    return _filesDir() + "/plugins/ElyxPlugins/shareui_packit/packit/native/libbithash.so"

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

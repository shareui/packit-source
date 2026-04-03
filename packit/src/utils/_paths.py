from android_utils import log


def _filesDir() -> str:
    from org.telegram.messenger import ApplicationLoader
    return ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()


def _cacheDir() -> str:
    from org.telegram.messenger import ApplicationLoader
    return ApplicationLoader.applicationContext.getCacheDir().getAbsolutePath()


def getCacheRoot() -> str:
    return _filesDir() + "/packitCache"


def getConfigsDir() -> str:
    return _filesDir() + "/packitCache/packitConfigs"


def getReposCacheDir() -> str:
    return _filesDir() + "/packitCache/reposCache"


def getTempDir() -> str:
    return _filesDir() + "/packitCache/packitTemp"


def getPluginCacheDir(subdir: str) -> str:
    return _filesDir() + f"/packitCache/pluginCache/{subdir}"


def getPluginsDir() -> str:
    return _filesDir() + "/plugins"


def getElyxArchivesDir() -> str:
    return _filesDir() + "/plugins/ElyxPlugins/archives"


def getBitHashSoPath() -> str:
    return _filesDir() + "/plugins/ElyxPlugins/shareui_packit/packit/res/native/libbithash.so"


def getRepoCachePath(repoId: str) -> str:
    return _filesDir() + f"/packitCache/reposCache/{repoId}.json"


def getRepoIndexPath(rmRid: str) -> str:
    return _filesDir() + f"/packitCache/reposCache/{rmRid}-index.json"


def getIconPackTmpPath(packId: str) -> str:
    return _cacheDir() + f"/packit_iconpack_{packId}.icons"

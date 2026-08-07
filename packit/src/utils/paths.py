# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx

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

_stagingDir = None

def _isWritableDir(path: str) -> bool:
    # probes with the same call stageFileForUpload uses. It used to differ from
    # the real write and the mismatch cost a whole feature: the probe's plain
    # open() succeeded on the emulated external volume while the actual staging
    # went through tempfile + copy2, which that volume refuses — so the dir was
    # declared usable and every upload then died with EACCES.
    if not path:
        return False
    try:
        import os
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".packit_write_probe")
        with open(probe, "wb") as f:
            f.write(b"1")
        os.remove(probe)
        return True
    except Exception as e:
        logx(f"paths: {path} not writable: {e}", False)
        return False

def getStagingDir() -> str:
    # Directory for files we hand to Telegram (share sheet, suggestion upload).
    #
    # External app cache first: AndroidUtilities.isInternalUri() refuses to send
    # anything under the app's internal data dir, so a file staged there shows
    # "attachment not supported" or silently drops. But the external path is not
    # always usable either — some ROMs deny writes to
    # /storage/emulated/0/Android/data/<pkg>/... outright (EACCES), so probe it
    # instead of assuming, and fall back to the internal cache. Callers that
    # send a file from the fallback must hook isInternalUri for that path.
    global _stagingDir
    if _stagingDir is None:
        for candidate in (_externalCacheDir(), _cacheDir()):
            if _isWritableDir(candidate):
                _stagingDir = candidate
                break
        else:
            _stagingDir = _cacheDir()
        logx(f"paths: staging dir = {_stagingDir}", True)
    return _stagingDir


def stageFileForUpload(src: str, suffix: str = "") -> str:
    # Copies src to a place Telegram will read and returns the new path.
    #
    # Plain open() + byte copy on purpose. tempfile.NamedTemporaryFile opens
    # with O_EXCL|O_NOFOLLOW at mode 0600 and shutil.copy2 chmods the result
    # afterwards; the FUSE-emulated external volume refuses those even in a
    # directory where an ordinary write works (which is how the log export
    # writes to the very same folder). That EACCES aborted the whole
    # suggestion upload before anything was sent.
    #
    # If the external dir refuses the copy anyway, fall back to the internal
    # cache — always writable, and callers hook isInternalUri for such paths.
    import os
    import shutil
    import uuid
    name = f"packit_{uuid.uuid4().hex[:12]}{suffix}"
    last = None
    for directory in (getStagingDir(), _cacheDir()):
        dst = os.path.join(directory, name)
        try:
            os.makedirs(directory, exist_ok=True)
            shutil.copyfile(src, dst)
            logx(f"paths: staged {src} -> {dst}", True)
            return dst
        except Exception as e:
            last = e
            logx(f"paths: staging into {directory} failed: {e}", False)
            try:
                os.unlink(dst)
            except Exception:
                pass
    raise last if last is not None else Exception("staging failed")

def isInternalPath(path: str) -> bool:
    # matches what isInternalUri() rejects: the app's own private storage
    return bool(path) and (str(path).startswith("/data/") or "/files/" in str(path))

def getShareCachePath(filename: str) -> str:
    return getStagingDir() + "/" + filename

def getLogShareCachePath() -> str:
    return getShareCachePath("packit_latestlog.txt")

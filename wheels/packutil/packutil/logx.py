# pyright: reportMissingImports=false

import os
import time
from android_utils import log as _log

def _getPluginsDir() -> str:
    from org.telegram.messenger import ApplicationLoader
    return ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath() + "/plugins"

def _getCacheRoot() -> str:
    from org.telegram.messenger import ApplicationLoader
    return ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath() + "/packit"

def _isWriteLogsEnabled() -> bool:
    try:
        path = _getPluginsDir() + "/plugin_settings.json"
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
        return bool(data.get("shareui_packit", {}).get("write_logs", False))
    except Exception:
        return False

def _writeToFile(msg: str):
    try:
        logPath = _getCacheRoot() + "/latestlog.txt"
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(logPath, "a", encoding="utf-8") as f:
            f.write(f"{ts} ~> {msg}\n")
    except Exception:
        pass

def logx(msg: str, isDebug: bool):
    if isDebug:
        try:
            from elyx import settings as _s
            if not _s.get("debug_logs", False):
                return
        except Exception:
            return
    _log(msg)
    if _isWriteLogsEnabled():
        _writeToFile(msg)

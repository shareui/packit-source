# pyright: reportMissingImports=false
from android_utils import log as _log

def logx(msg: str, isDebug: bool):
    if isDebug:
        try:
            from elyx import settings as _s
            if not _s.get("debug_logs", False):
                return
        except Exception:
            return
    _log(msg)

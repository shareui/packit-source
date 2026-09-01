# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx


_CLIENT_NAMES = {
    "com.exteragram.messenger": "exteraGram",
    "com.radolyn.ayugram": "AyuGram",
}

# keys consumed below; metainfo exposes the packed meta.yml (ElyxBuilder
# injects client/staticVer/sourceHash into it at build time)
_META_KEYS = ("client", "staticVer", "sourceHash")

def _readMeta():
    try:
        from elyx import metainfo
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"buildInfo: failed to import elyx metainfo: {e}", False)
        return {}
    meta = {}
    for key in _META_KEYS:
        try:
            value = metainfo[key]
        except Exception:
            continue
        if value is not None:
            meta[key] = value
    return meta

def _resolveClientName(pkg):
    if pkg is None:
        return "Universal"
    return _CLIENT_NAMES.get(pkg, "Unknown")
# client name in build: Universal/AyuGram/exteraGram/Unknown

def getBuildClientName():
    return _resolveClientName(_readMeta().get("client"))
    
# return raw pkg
def getBuildClientPkg():
    return _readMeta().get("client")
    
# return build static version
def getBuildStaticVersion():
    return _readMeta().get("staticVer")
    
# return current pkg
def getCurrClientPkg():
    try:
        from org.telegram.messenger import ApplicationLoader
        return str(ApplicationLoader.applicationContext.getPackageName())
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"buildInfo: failed to get current package: {e}", False)
        return None
        
# return current client name Universal/AyuGram/exteraGram/Unknown
def getCurrClientName():
    return _resolveClientName(getCurrClientPkg())
    
# return sourceHash from build info (sha256 of sources), or None if absent
def getBuildHash():
    return _readMeta().get("sourceHash")

# return current client ver
def getClientVersion():
    try:
        from org.telegram.messenger import BuildVars
        return str(BuildVars.BUILD_VERSION_STRING)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"buildInfo: failed to get client version: {e}", False)
        return None

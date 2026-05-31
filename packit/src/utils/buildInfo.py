# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import yaml
from android_utils import log

_META_PATH = os.path.join(os.path.dirname(__file__), "../../meta.yml")

_CLIENT_NAMES = {
    "com.exteragram.messenger": "exteraGram",
    "com.radolyn.ayugram": "AyuGram",
}

def _readMeta():
    try:
        with open(_META_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log(f"buildInfo: failed to read meta.yml: {e}")
        return {}

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
    return _readMeta().get("static_ver")
    
# return current pkg
def getCurrClientPkg():
    try:
        from org.telegram.messenger import ApplicationLoader
        return str(ApplicationLoader.applicationContext.getPackageName())
    except Exception as e:
        log(f"buildInfo: failed to get current package: {e}")
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
    except Exception as e:
        log(f"buildInfo: failed to get client version: {e}")
        return None
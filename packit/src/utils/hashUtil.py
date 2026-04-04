import hashlib
import os
import ctypes

from android_utils import log

METHOD_SHA256 = 0
METHOD_BITHASH = 1

_lib = None
_libLoaded = False


def getHashMethod() -> int:
    try:
        from elyx import settings
        return int(settings.get("hash_function", METHOD_SHA256))
    except Exception:
        return METHOD_SHA256

def _getBitHashLib():
    global _lib, _libLoaded
    if _libLoaded:
        return _lib
    _libLoaded = True
    from ..nativeLoader import loadBitHash
    _lib = loadBitHash()
    if _lib is not None:
        log("hashutil: libbithash.so loaded successfully!")
    return _lib


def _hashFileSha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _hashFileBithash(path: str) -> str:
    lib = _getBitHashLib()
    if lib is None:
        log("hashutil: bithash unavailable, falling back to sha256")
        return _hashFileSha256(path)

    BUF_SIZE = 256 * 1024
    buf = ctypes.create_string_buffer(BUF_SIZE)

    # use bitHash_file_fp via python file object is not straightforward,
    # so we read in chunks and use bitHash_update through the streaming API
    try:
        class BitHashState(ctypes.Structure):
            _fields_ = [
                ("s0", ctypes.c_uint64),
                ("s1", ctypes.c_uint64),
                ("s2", ctypes.c_uint64),
                ("s3", ctypes.c_uint64),
                ("totalLen", ctypes.c_uint64),
                ("buf", ctypes.c_uint8 * 32),
                ("bufLen", ctypes.c_uint32),
            ]

        lib.bitHash_init.argtypes = [ctypes.POINTER(BitHashState), ctypes.c_uint64]
        lib.bitHash_init.restype = None
        lib.bitHash_update.argtypes = [ctypes.POINTER(BitHashState), ctypes.c_void_p, ctypes.c_size_t]
        lib.bitHash_update.restype = None
        lib.bitHash_finish.argtypes = [ctypes.POINTER(BitHashState)]
        lib.bitHash_finish.restype = ctypes.c_uint64

        state = BitHashState()
        lib.bitHash_init(ctypes.byref(state), ctypes.c_uint64(0))

        with open(path, "rb") as f:
            while True:
                chunk = f.read(BUF_SIZE)
                if not chunk:
                    break
                c_chunk = (ctypes.c_uint8 * len(chunk)).from_buffer_copy(chunk)
                lib.bitHash_update(ctypes.byref(state), c_chunk, ctypes.c_size_t(len(chunk)))

        result = lib.bitHash_finish(ctypes.byref(state))
        return format(result, "016x")
    except Exception as e:
        log(f"hashutil: bithash compute error: {e}")
        return _hashFileSha256(path)


def hashFile(path: str) -> str:
    # returns hex digest using method selected in settings
    if getHashMethod() == METHOD_BITHASH:
        return _hashFileBithash(path)
    return _hashFileSha256(path)


def matchesStoredHash(path: str, sha256: str, bithash: str, label: str = "") -> bool:
    # checks file hash against stored values with fallback between methods
    # preferred method from settings, falls back to whichever hash is available
    # returns True (skip) if neither hash is stored
    has_sha256 = bool(sha256)
    has_bithash = bool(bithash)

    if not has_sha256 and not has_bithash:
        log(f"hashutil: no stored hash for '{label or path}', skipping check")
        return True

    preferred = getHashMethod()

    if preferred == METHOD_BITHASH and has_bithash:
        # only use bithash if the lib is actually available
        if _getBitHashLib() is not None:
            return _hashFileBithash(path) == bithash
        # lib unavailable, fall back to sha256
        if has_sha256:
            return _hashFileSha256(path) == sha256
        log(f"hashutil: bithash lib unavailable and no sha256 stored for '{label or path}', skipping check")
        return True
    if preferred == METHOD_SHA256 and has_sha256:
        return _hashFileSha256(path) == sha256

    # preferred hash unavailable, use whichever is present
    if has_sha256:
        return _hashFileSha256(path) == sha256
    if _getBitHashLib() is not None:
        return _hashFileBithash(path) == bithash
    log(f"hashutil: bithash lib unavailable and no sha256 stored for '{label or path}', skipping check")
    return True

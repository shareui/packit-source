import ctypes
import os

from android_utils import log

CHECK_SO_PATHS = True

_BASE = "/plugins/ElyxPlugins/shareui_packit/packit/native"


def _soPath(libName: str) -> str:
    from .utils.paths import _filesDir
    return _filesDir() + _BASE + "/" + libName + ".so"


def checkSoPaths():
    for name in ("libbithash", "libsearch", "libpacklight", "libpackitdb", "libexport"):
        path = _soPath(name)
        exists = os.path.exists(path)
        log(f"nativeLoader: {'Lib ' + path + ' exists!' if exists else 'Lib ' + path + ' NOT FOUND'}")


def loadBitHash() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libbithash"))
        lib.bitHash_oneshot.restype = ctypes.c_uint64
        lib.bitHash_oneshot.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64]
        return lib
    except Exception as e:
        log(f"nativeLoader: libbithash load error: {e}")
        return None


def loadSearch() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libsearch"))
        lib.search_build_index.restype = ctypes.c_int
        lib.search_build_index.argtypes = [ctypes.c_char_p]
        lib.search_score.restype = ctypes.c_void_p
        lib.search_score.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p,
                                     ctypes.c_int, ctypes.c_int]
        lib.search_free_index.restype = None
        lib.search_free_index.argtypes = [ctypes.c_int]
        lib.search_free_str.restype = None
        lib.search_free_str.argtypes = [ctypes.c_void_p]
        return lib
    except Exception as e:
        log(f"nativeLoader: libsearch load error: {e}")
        return None


def loadPackLight() -> "ctypes.CDLL | None":
    try:
        class _Token(ctypes.Structure):
            _fields_ = [("start", ctypes.c_uint32), ("length", ctypes.c_uint32), ("type", ctypes.c_uint8)]

        class _CharRange(ctypes.Structure):
            _fields_ = [("byte_start", ctypes.c_uint32), ("byte_end", ctypes.c_uint32),
                        ("char_start", ctypes.c_uint32), ("char_end", ctypes.c_uint32)]

        _MAX = 65536
        lib = ctypes.CDLL(_soPath("libpacklight"))
        _sig = [ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(_Token), ctypes.c_uint32]
        for name in ("packlight_json", "packlight_python", "packlight_java", "packlight_kotlin"):
            getattr(lib, name).argtypes = _sig
            getattr(lib, name).restype = ctypes.c_uint32
        lib.packlight_tokens_to_chars.argtypes = [
            ctypes.c_char_p, ctypes.c_uint32,
            ctypes.POINTER(_Token), ctypes.c_uint32,
            ctypes.POINTER(_CharRange), ctypes.c_uint32,
        ]
        lib.packlight_tokens_to_chars.restype = ctypes.c_uint32
        return lib
    except Exception as e:
        log(f"nativeLoader: libpacklight load error: {e}")
        return None


def loadPackitDb() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libpackitdb"))
        vp   = ctypes.c_void_p
        cp   = ctypes.c_char_p
        i64  = ctypes.c_int64
        u32  = ctypes.c_uint32
        sz   = ctypes.c_size_t
        ci   = ctypes.c_int
        u8p  = ctypes.POINTER(ctypes.c_uint8)
        u32p = ctypes.POINTER(ctypes.c_uint32)
        lib.packdb_write_raw.restype = ci
        lib.packdb_write_raw.argtypes = [cp, cp, u8p, u32]
        lib.packdb_read_raw.restype = ci
        lib.packdb_read_raw.argtypes = [cp, cp, u8p, u32p]
        lib.packdb_delete_key.restype = ci
        lib.packdb_delete_key.argtypes = [cp, cp]
        lib.packdb_list_keys.restype = vp
        lib.packdb_list_keys.argtypes = [cp, u32p]
        lib.packdb_free_keys.restype = None
        lib.packdb_free_keys.argtypes = [vp, u32]
        lib.packdb_vacuum.restype = ci
        lib.packdb_vacuum.argtypes = [cp]
        lib.packdb_open_from_payload.restype = vp
        lib.packdb_open_from_payload.argtypes = [cp, cp, u8p, u32]
        lib.packdb_serialize_to.restype = ci
        lib.packdb_serialize_to.argtypes = [vp, u8p, u32p]
        lib.packdb_open.restype = vp
        lib.packdb_open.argtypes = [cp, cp]
        lib.packdb_close.restype = ci
        lib.packdb_close.argtypes = [vp]
        lib.packdb_get.restype = i64
        lib.packdb_get.argtypes = [vp, cp, i64]
        lib.packdb_set.restype = ci
        lib.packdb_set.argtypes = [vp, cp, i64]
        lib.packdb_increment.restype = i64
        lib.packdb_increment.argtypes = [vp, cp, i64]
        lib.packdb_award_has.restype = ci
        lib.packdb_award_has.argtypes = [vp, cp]
        lib.packdb_award_add.restype = ci
        lib.packdb_award_add.argtypes = [vp, cp]
        lib.packdb_award_list.restype = ci
        lib.packdb_award_list.argtypes = [vp, cp, sz]
        lib.packdb_award_count.restype = ci
        lib.packdb_award_count.argtypes = [vp]
        lib.packdb_entry_count.restype = ci
        lib.packdb_entry_count.argtypes = [vp]
        return lib
    except Exception as e:
        log(f"nativeLoader: libpackitdb load error: {e}")
        return None


def loadExport() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libexport"))
        lib.packit_write_file.restype = ctypes.c_int
        lib.packit_write_file.argtypes = [
            ctypes.c_int64, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
        ]
        lib.packit_read_file.restype = ctypes.c_int
        lib.packit_read_file.argtypes = [
            ctypes.c_char_p, ctypes.c_int64, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_uint32),
        ]
        lib.packit_free_buf.restype = None
        lib.packit_free_buf.argtypes = [ctypes.c_char_p]
        lib.packit_last_error.restype = ctypes.c_char_p
        lib.packit_last_error.argtypes = []
        return lib
    except Exception as e:
        log(f"nativeLoader: libexport load error: {e}")
        return None

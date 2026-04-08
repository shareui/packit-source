import ctypes
import platform

def _soPath() -> str:
    from ..utils.paths import _filesDir
    return _filesDir() + "/plugins/ElyxPlugins/shareui_packit/packit/native/libscl.so"

_lib = ctypes.CDLL(_soPath())

_libc = ctypes.CDLL("msvcrt" if platform.system() == "Windows" else None)
_libc.free.argtypes = [ctypes.c_void_p]
_libc.free.restype  = None

class SclStr(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_char_p),
        ("len",  ctypes.c_size_t),
    ]

class SclResult(ctypes.Structure):
    _fields_ = [
        ("ok",           ctypes.c_bool),
        ("doc",          ctypes.c_void_p),
        ("error",        ctypes.c_char_p),
        ("warnings",     ctypes.POINTER(ctypes.c_char_p)),
        ("warningCount", ctypes.c_size_t),
    ]

class SclStrResult(ctypes.Structure):
    _fields_ = [
        ("ok",    ctypes.c_bool),
        ("str",   SclStr),
        ("error", ctypes.c_char_p),
    ]

class SclParseOpts(ctypes.Structure):
    _fields_ = [
        ("allowUnknownAnnotations", ctypes.c_bool),
        ("strictDatetime",          ctypes.c_bool),
        ("maxDepth",                ctypes.c_int),
        ("includeRoot",             ctypes.c_bool),
    ]

# signatures

_lib.scl_version.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
_lib.scl_version.restype  = None

_lib.scl_parse_str.argtypes = [ctypes.c_char_p]
_lib.scl_parse_str.restype  = SclResult

_lib.scl_parse_file.argtypes = [ctypes.c_char_p]
_lib.scl_parse_file.restype  = SclResult

_lib.scl_parse_str_opts.argtypes = [ctypes.c_char_p, SclParseOpts]
_lib.scl_parse_str_opts.restype  = SclResult

_lib.scl_parse_file_opts.argtypes = [ctypes.c_char_p, SclParseOpts]
_lib.scl_parse_file_opts.restype  = SclResult

_lib.scl_result_free_warnings.argtypes = [ctypes.POINTER(SclResult)]
_lib.scl_result_free_warnings.restype  = None

_lib.scl_doc_free.argtypes = [ctypes.c_void_p]
_lib.scl_doc_free.restype  = None

_lib.scl_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_lib.scl_get.restype  = ctypes.c_void_p

_lib.scl_get_path.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_lib.scl_get_path.restype  = ctypes.c_void_p

_cbType = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)

_lib.scl_each_key.argtypes = [ctypes.c_void_p, _cbType, ctypes.c_void_p]
_lib.scl_each_key.restype  = None

_lib.scl_value_type.argtypes = [ctypes.c_void_p]
_lib.scl_value_type.restype  = ctypes.c_int

_lib.scl_value_string.argtypes   = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
_lib.scl_value_string.restype    = ctypes.c_bool
_lib.scl_value_int.argtypes      = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
_lib.scl_value_int.restype       = ctypes.c_bool
_lib.scl_value_uint.argtypes     = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
_lib.scl_value_uint.restype      = ctypes.c_bool
_lib.scl_value_float.argtypes    = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
_lib.scl_value_float.restype     = ctypes.c_bool
_lib.scl_value_bool.argtypes     = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_bool)]
_lib.scl_value_bool.restype      = ctypes.c_bool
_lib.scl_value_date.argtypes     = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
_lib.scl_value_date.restype      = ctypes.c_bool
_lib.scl_value_datetime.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
_lib.scl_value_datetime.restype  = ctypes.c_bool
_lib.scl_value_duration.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
_lib.scl_value_duration.restype  = ctypes.c_bool
_lib.scl_value_is_null.argtypes  = [ctypes.c_void_p]
_lib.scl_value_is_null.restype   = ctypes.c_bool

_lib.scl_value_bytes.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
    ctypes.POINTER(ctypes.c_size_t),
]
_lib.scl_value_bytes.restype = ctypes.c_bool

_lib.scl_list_len.argtypes = [ctypes.c_void_p]
_lib.scl_list_len.restype  = ctypes.c_size_t
_lib.scl_list_get.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
_lib.scl_list_get.restype  = ctypes.c_void_p

_lib.scl_struct_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_lib.scl_struct_get.restype  = ctypes.c_void_p

_lib.scl_struct_each.argtypes = [ctypes.c_void_p, _cbType, ctypes.c_void_p]
_lib.scl_struct_each.restype  = None

_lib.scl_doc_new.argtypes    = []
_lib.scl_doc_new.restype     = ctypes.c_void_p
_lib.scl_val_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_lib.scl_val_string.restype  = ctypes.c_void_p
_lib.scl_val_int.argtypes    = [ctypes.c_void_p, ctypes.c_int64]
_lib.scl_val_int.restype     = ctypes.c_void_p
_lib.scl_val_uint.argtypes   = [ctypes.c_void_p, ctypes.c_uint64]
_lib.scl_val_uint.restype    = ctypes.c_void_p
_lib.scl_val_float.argtypes  = [ctypes.c_void_p, ctypes.c_double]
_lib.scl_val_float.restype   = ctypes.c_void_p
_lib.scl_val_bool.argtypes   = [ctypes.c_void_p, ctypes.c_bool]
_lib.scl_val_bool.restype    = ctypes.c_void_p
_lib.scl_val_null.argtypes   = [ctypes.c_void_p]
_lib.scl_val_null.restype    = ctypes.c_void_p
_lib.scl_val_bytes.argtypes  = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
_lib.scl_val_bytes.restype   = ctypes.c_void_p

_lib.scl_val_list_new.argtypes   = [ctypes.c_void_p]
_lib.scl_val_list_new.restype    = ctypes.c_void_p
_lib.scl_val_struct_new.argtypes = [ctypes.c_void_p]
_lib.scl_val_struct_new.restype  = ctypes.c_void_p

_lib.scl_doc_list_push.argtypes  = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_lib.scl_doc_list_push.restype   = None
_lib.scl_doc_struct_set.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
_lib.scl_doc_struct_set.restype  = None
_lib.scl_doc_set.argtypes        = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
_lib.scl_doc_set.restype         = None

_lib.scl_serialize.argtypes       = [ctypes.c_void_p]
_lib.scl_serialize.restype        = SclStr
_lib.scl_to_json.argtypes         = [ctypes.c_void_p]
_lib.scl_to_json.restype          = SclStr
_lib.scl_to_toml.argtypes         = [ctypes.c_void_p]
_lib.scl_to_toml.restype          = SclStrResult
_lib.scl_str_free.argtypes        = [SclStr]
_lib.scl_str_free.restype         = None
_lib.scl_str_result_free.argtypes = [ctypes.POINTER(SclStrResult)]
_lib.scl_str_result_free.restype  = None

# types

NULL     = 0
STRING   = 1
INT      = 2
UINT     = 3
FLOAT    = 4
BOOL     = 5
BYTES    = 6
DATE     = 7
DATETIME = 8
DURATION = 9
LIST     = 10
MAP      = 11
STRUCT   = 12
UNION    = 13

# public api

def version():
    major = ctypes.c_int(0)
    minor = ctypes.c_int(0)
    _lib.scl_version(ctypes.byref(major), ctypes.byref(minor))
    return (major.value, minor.value)

def parseStr(src, opts=None):
    # precondition: src is str or bytes
    if isinstance(src, str):
        src = src.encode()
    if opts is not None:
        return _lib.scl_parse_str_opts(src, opts)
    return _lib.scl_parse_str(src)

def parseFile(path, opts=None):
    # precondition: path is str or bytes
    if isinstance(path, str):
        path = path.encode()
    if opts is not None:
        return _lib.scl_parse_file_opts(path, opts)
    return _lib.scl_parse_file(path)

def freeResult(result):
    if result.error:
        _libc.free(ctypes.cast(result.error, ctypes.c_void_p))
        result.error = None
    _lib.scl_result_free_warnings(ctypes.byref(result))

def freeDoc(doc):
    _lib.scl_doc_free(doc)

def get(doc, key):
    if isinstance(key, str):
        key = key.encode()
    return _lib.scl_get(doc, key)

def getPath(doc, path):
    # dot-separated path
    if isinstance(path, str):
        path = path.encode()
    return _lib.scl_get_path(doc, path)

def eachKey(doc, cb):
    def wrapper(key, val, _userdata):
        return cb(key.decode(), val)
    cbRef = _cbType(wrapper)
    _lib.scl_each_key(doc, cbRef, None)

def valueType(val):
    return _lib.scl_value_type(val)

def valueString(val):
    out = ctypes.c_char_p()
    if _lib.scl_value_string(val, ctypes.byref(out)):
        return out.value.decode()
    return None

def valueInt(val):
    out = ctypes.c_int64(0)
    if _lib.scl_value_int(val, ctypes.byref(out)):
        return out.value
    return None

def valueUint(val):
    out = ctypes.c_uint64(0)
    if _lib.scl_value_uint(val, ctypes.byref(out)):
        return out.value
    return None

def valueFloat(val):
    out = ctypes.c_double(0.0)
    if _lib.scl_value_float(val, ctypes.byref(out)):
        return out.value
    return None

def valueBool(val):
    out = ctypes.c_bool(False)
    if _lib.scl_value_bool(val, ctypes.byref(out)):
        return out.value
    return None

def valueBytes(val):
    ptr  = ctypes.POINTER(ctypes.c_uint8)()
    size = ctypes.c_size_t(0)
    if _lib.scl_value_bytes(val, ctypes.byref(ptr), ctypes.byref(size)):
        return bytes(ptr[:size.value])
    return None

def valueDate(val):
    out = ctypes.c_char_p()
    if _lib.scl_value_date(val, ctypes.byref(out)):
        return out.value.decode()
    return None

def valueDatetime(val):
    out = ctypes.c_char_p()
    if _lib.scl_value_datetime(val, ctypes.byref(out)):
        return out.value.decode()
    return None

def valueDuration(val):
    out = ctypes.c_char_p()
    if _lib.scl_value_duration(val, ctypes.byref(out)):
        return out.value.decode()
    return None

def valueIsNull(val):
    return _lib.scl_value_is_null(val)

def listLen(val):
    return _lib.scl_list_len(val)

def listGet(val, index):
    return _lib.scl_list_get(val, index)

def structGet(val, key):
    if isinstance(key, str):
        key = key.encode()
    return _lib.scl_struct_get(val, key)

def structEach(val, cb):
    def wrapper(key, v, _userdata):
        return cb(key.decode(), v)
    cbRef = _cbType(wrapper)
    _lib.scl_struct_each(val, cbRef, None)

def docNew():
    return _lib.scl_doc_new()

def valString(doc, s):
    if isinstance(s, str):
        s = s.encode()
    return _lib.scl_val_string(doc, s)

def valInt(doc, v):
    return _lib.scl_val_int(doc, v)

def valUint(doc, v):
    return _lib.scl_val_uint(doc, v)

def valFloat(doc, v):
    return _lib.scl_val_float(doc, v)

def valBool(doc, v):
    return _lib.scl_val_bool(doc, v)

def valNull(doc):
    return _lib.scl_val_null(doc)

def valBytes(doc, data):
    arr = (ctypes.c_uint8 * len(data))(*data)
    return _lib.scl_val_bytes(doc, arr, len(data))

def valListNew(doc):
    return _lib.scl_val_list_new(doc)

def valStructNew(doc):
    return _lib.scl_val_struct_new(doc)

def docListPush(doc, lst, val):
    _lib.scl_doc_list_push(doc, lst, val)

def docStructSet(doc, strct, key, val):
    if isinstance(key, str):
        key = key.encode()
    _lib.scl_doc_struct_set(doc, strct, key, val)

def docSet(doc, key, val):
    if isinstance(key, str):
        key = key.encode()
    _lib.scl_doc_set(doc, key, val)

def serialize(doc):
    s = _lib.scl_serialize(doc)
    result = s.data[:s.len].decode()
    _lib.scl_str_free(s)
    return result

def toJson(doc):
    s = _lib.scl_to_json(doc)
    result = s.data[:s.len].decode()
    _lib.scl_str_free(s)
    return result

def toToml(doc):
    r = _lib.scl_to_toml(doc)
    if not r.ok:
        msg = r.error.decode() if r.error else "toml serialization failed"
        _lib.scl_str_result_free(ctypes.byref(r))
        raise RuntimeError(msg)
    result = r.str.data[:r.str.len].decode()
    _lib.scl_str_result_free(ctypes.byref(r))
    return result

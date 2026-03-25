import ctypes
import os

from android_utils import log

# token types — must match packlight.h
_TK_KEYWORD   = 1
_TK_STRING    = 2
_TK_NUMBER    = 3
_TK_COMMENT   = 4
_TK_FUNCTION  = 5
_TK_CALL      = 6
_TK_BUILTIN   = 7
_TK_CONSTANT  = 8
_TK_DECORATOR = 9
_TK_OPERATOR  = 10
_TK_JSON_KEY  = 11

_MAX_TOKENS = 65536

_lib = None


class _CToken(ctypes.Structure):
    _fields_ = [
        ("start",  ctypes.c_uint32),
        ("length", ctypes.c_uint32),
        ("type",   ctypes.c_uint8),
    ]

_TokenBuf = _CToken * _MAX_TOKENS


def _loadLib():
    global _lib
    if _lib is not None:
        return _lib
    soPath = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "res", "native", "libpacklight.so"
    )
    soPath = os.path.normpath(soPath)
    try:
        _lib = ctypes.CDLL(soPath)
        _lib.packlight_json.argtypes   = [ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(_CToken), ctypes.c_uint32]
        _lib.packlight_json.restype    = ctypes.c_uint32
        _lib.packlight_python.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(_CToken), ctypes.c_uint32]
        _lib.packlight_python.restype  = ctypes.c_uint32
        log("packlight: libpacklight.so loaded")
    except Exception as e:
        log(f"packlight: load error: {e}")
        _lib = None
    return _lib


def _resolveColors():
    try:
        from org.telegram.ui.ActionBar import Theme
        return {
            _TK_JSON_KEY:  Theme.getColor(Theme.key_code_keyword),
            _TK_KEYWORD:   Theme.getColor(Theme.key_code_keyword),
            _TK_STRING:    Theme.getColor(Theme.key_code_string),
            _TK_NUMBER:    Theme.getColor(Theme.key_code_number),
            _TK_COMMENT:   Theme.getColor(Theme.key_code_comment),
            _TK_FUNCTION:  Theme.getColor(Theme.key_code_function),
            _TK_CONSTANT:  Theme.getColor(Theme.key_code_constant),
            _TK_OPERATOR:  Theme.getColor(Theme.key_code_operator),
            _TK_BUILTIN:   Theme.getColor(Theme.key_color_cyan),
            _TK_CALL:      Theme.getColor(Theme.key_color_lightblue),
            _TK_DECORATOR: Theme.getColor(Theme.key_color_orange),
        }
    except Exception as e:
        log(f"packlight: _resolveColors error: {e}")
        return {}


def _applySpans(spannable, srcBytes: bytes, buf, cnt: int, colors: dict):
    try:
        from android.text.style import ForegroundColorSpan

        # build byte→char map in one pass for only needed offsets
        needed = set()
        for k in range(cnt):
            needed.add(buf[k].start)
            needed.add(buf[k].start + buf[k].length)

        byteToChar = {}
        charIdx = 0
        byteIdx = 0
        n = len(srcBytes)
        while byteIdx <= n:
            if byteIdx in needed:
                byteToChar[byteIdx] = charIdx
            if byteIdx == n:
                break
            b = srcBytes[byteIdx]
            if b < 0x80:   byteIdx += 1
            elif b < 0xE0: byteIdx += 2
            elif b < 0xF0: byteIdx += 3
            else:           byteIdx += 4
            charIdx += 1

        EXCL_EXCL = 0x11
        for k in range(cnt):
            tk = buf[k]
            color = colors.get(tk.type)
            if color is None:
                continue
            cs = byteToChar.get(tk.start)
            ce = byteToChar.get(tk.start + tk.length)
            if cs is None or ce is None or cs >= ce:
                continue
            spannable.setSpan(ForegroundColorSpan(color), cs, ce, EXCL_EXCL)
    except Exception as e:
        log(f"packlight: _applySpans error: {e}")


def _highlight(text: str, tokenizeFn) -> object:
    try:
        lib = _loadLib()
        if lib is None:
            return text
        encoded = text.encode("utf-8")
        buf = _TokenBuf()
        cnt = tokenizeFn(encoded, len(encoded), buf, _MAX_TOKENS)
        if cnt == 0:
            return text
        colors = _resolveColors()
        if not colors:
            return text
        from android.text import SpannableString
        spannable = SpannableString(text)
        _applySpans(spannable, encoded, buf, cnt, colors)
        return spannable
    except Exception as e:
        log(f"packlight: _highlight error: {e}")
        return text


def highlightJson(text: str) -> object:
    lib = _loadLib()
    if lib is None:
        return text
    return _highlight(text, lib.packlight_json)


def highlightPython(text: str) -> object:
    lib = _loadLib()
    if lib is None:
        return text
    return _highlight(text, lib.packlight_python)

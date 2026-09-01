# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import ctypes
import os



# token types
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


class _CCharRange(ctypes.Structure):
    _fields_ = [
        ("byte_start", ctypes.c_uint32),
        ("byte_end",   ctypes.c_uint32),
        ("char_start", ctypes.c_uint32),
        ("char_end",   ctypes.c_uint32),
    ]


_TokenBuf     = _CToken     * _MAX_TOKENS
_CharRangeBuf = _CCharRange * _MAX_TOKENS


def _setupArgtypes(lib):
    tokenizeSig = [
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(_CToken),
        ctypes.c_uint32,
    ]
    for name in ("packlight_json", "packlight_python", "packlight_java", "packlight_kotlin"):
        fn = getattr(lib, name)
        fn.argtypes = tokenizeSig
        fn.restype = ctypes.c_uint32
    lib.packlight_tokens_to_chars.argtypes = [
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(_CToken),
        ctypes.c_uint32,
        ctypes.POINTER(_CCharRange),
        ctypes.c_uint32,
    ]
    lib.packlight_tokens_to_chars.restype = ctypes.c_uint32


def _loadLib():
    global _lib
    if _lib is not None:
        return _lib
    from ...core.NativeLoader import loadPackLight
    _lib = loadPackLight()
    if _lib is not None:
        _setupArgtypes(_lib)
        logx("packlight: libpacklight.so loaded", True)
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
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"packlight: _resolveColors error: {e}", False)
        return {}


def _applySpans(spannable, tokBuf, ranges, cnt, colors, offset=0):
    try:
        from android.text.style import ForegroundColorSpan
        EXCL_EXCL = 0x11
        for k in range(cnt):
            color = colors.get(tokBuf[offset + k].type)
            if color is None:
                continue
            cs = ranges[offset + k].char_start
            ce = ranges[offset + k].char_end
            if cs == 0xFFFFFFFF or ce == 0xFFFFFFFF or cs >= ce:
                continue
            spannable.setSpan(ForegroundColorSpan(color), cs, ce, EXCL_EXCL)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"packlight: _applySpans error: {e}", False)


def tokenize(text: str, tokenizeFn):
    try:
        lib = _loadLib()
        if lib is None:
            return None
        encoded = text.encode("utf-8")
        srcLen = len(encoded)
        tokBuf = _TokenBuf()
        cnt = tokenizeFn(encoded, srcLen, tokBuf, _MAX_TOKENS)
        if cnt == 0:
            return None
        ranges = _CharRangeBuf()
        lib.packlight_tokens_to_chars(encoded, srcLen, tokBuf, cnt, ranges, _MAX_TOKENS)
        return tokBuf, ranges, cnt
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"packlight: tokenize error: {e}", False)
        return None


def tokenizeJson(text: str):
    lib = _loadLib()
    if lib is None:
        return None
    return tokenize(text, lib.packlight_json)


def tokenizePython(text: str):
    lib = _loadLib()
    if lib is None:
        return None
    return tokenize(text, lib.packlight_python)


def tokenizeJava(text: str):
    lib = _loadLib()
    if lib is None:
        return None
    return tokenize(text, lib.packlight_java)


def tokenizeKotlin(text: str):
    lib = _loadLib()
    if lib is None:
        return None
    return tokenize(text, lib.packlight_kotlin)
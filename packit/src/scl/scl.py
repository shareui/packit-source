from . import native as _native
from .errors import ParseError, TomlError
from .opts import ParseOpts
from .doc import Doc
from .value import Value

NULL     = _native.NULL
STRING   = _native.STRING
INT      = _native.INT
UINT     = _native.UINT
FLOAT    = _native.FLOAT
BOOL     = _native.BOOL
BYTES    = _native.BYTES
DATE     = _native.DATE
DATETIME = _native.DATETIME
DURATION = _native.DURATION
LIST     = _native.LIST
MAP      = _native.MAP
STRUCT   = _native.STRUCT
UNION    = _native.UNION

def version():
    return _native.version()

def parse(src, opts=None):
    # precondition: src is str or bytes
    nativeOpts = opts.toNative() if opts is not None else None
    r = _native.parseStr(src, nativeOpts)

    ok  = r.ok
    doc = r.doc
    msg = r.error.decode() if (not r.ok and r.error) else None

    warnings = []
    if r.warningCount > 0 and r.warnings:
        for i in range(r.warningCount):
            w = r.warnings[i]
            if w:
                warnings.append(w.decode())

    _native.freeResult(r)

    if not ok:
        raise ParseError(msg or "parse failed")

    return Doc(doc, warnings)

def parseFile(path, opts=None):
    # precondition: path is str
    nativeOpts = opts.toNative() if opts is not None else None
    r = _native.parseFile(path, nativeOpts)

    ok  = r.ok
    doc = r.doc
    msg = r.error.decode() if (not r.ok and r.error) else None

    warnings = []
    if r.warningCount > 0 and r.warnings:
        for i in range(r.warningCount):
            w = r.warnings[i]
            if w:
                warnings.append(w.decode())

    _native.freeResult(r)

    if not ok:
        raise ParseError(msg or "parse failed")

    return Doc(doc, warnings)

import ctypes
from dataclasses import dataclass, field

from . import native as _native

@dataclass
class ParseOpts:
    allowUnknownAnnotations: bool = False
    strictDatetime: bool = False
    maxDepth: int = 0

    def toNative(self):
        opts = _native.SclParseOpts()
        opts.allowUnknownAnnotations = self.allowUnknownAnnotations
        opts.strictDatetime = self.strictDatetime
        opts.maxDepth = self.maxDepth
        opts.includeRoot = False
        return opts

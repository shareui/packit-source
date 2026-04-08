from . import native as _native
from .errors import TomlError
from .value import Value, ListBuilder, StructBuilder, _makeVal

class Doc:
    # precondition: ptr is a valid doc pointer from the native layer, or None for empty
    def __init__(self, ptr, warnings=None):
        self._ptr = ptr
        self.warnings = warnings or []

    def __del__(self):
        self._free()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._free()

    def _free(self):
        if self._ptr is not None:
            _native.freeDoc(self._ptr)
            self._ptr = None

    def get(self, key):
        ptr = _native.get(self._ptr, key)
        if ptr is None:
            return None
        return Value(ptr, self)

    def getPath(self, path):
        ptr = _native.getPath(self._ptr, path)
        if ptr is None:
            return None
        return Value(ptr, self)

    def __getitem__(self, key):
        return self.get(key)

    def keys(self):
        result = []
        def cb(k, _v):
            result.append(k)
            return True
        _native.eachKey(self._ptr, cb)
        return result

    def items(self):
        result = []
        def cb(k, v):
            result.append((k, Value(v, self)))
            return True
        _native.eachKey(self._ptr, cb)
        return result

    def serialize(self):
        return _native.serialize(self._ptr)

    def toJson(self):
        return _native.toJson(self._ptr)

    def toToml(self):
        try:
            return _native.toToml(self._ptr)
        except RuntimeError as e:
            raise TomlError(str(e)) from e

    @staticmethod
    def new():
        ptr = _native.docNew()
        return Doc(ptr)

    def set(self, key, value):
        ptr = _makeVal(self._ptr, value)
        _native.docSet(self._ptr, key, ptr)

    def val(self, value):
        ptr = _makeVal(self._ptr, value)
        return Value(ptr, self)

    def newList(self):
        listPtr = _native.valListNew(self._ptr)
        return ListBuilder(self._ptr, listPtr, self)

    def newStruct(self):
        structPtr = _native.valStructNew(self._ptr)
        return StructBuilder(self._ptr, structPtr, self)

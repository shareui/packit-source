from . import native as _native

class Value:
    def __init__(self, ptr, doc):
        self._ptr = ptr
        self._doc = doc

    @property
    def type(self):
        return _native.valueType(self._ptr)

    def asString(self):
        return _native.valueString(self._ptr)

    def asInt(self):
        return _native.valueInt(self._ptr)

    def asUint(self):
        return _native.valueUint(self._ptr)

    def asFloat(self):
        return _native.valueFloat(self._ptr)

    def asBool(self):
        return _native.valueBool(self._ptr)

    def asBytes(self):
        return _native.valueBytes(self._ptr)

    def asDate(self):
        return _native.valueDate(self._ptr)

    def asDatetime(self):
        return _native.valueDatetime(self._ptr)

    def asDuration(self):
        return _native.valueDuration(self._ptr)

    def isNull(self):
        return _native.valueIsNull(self._ptr)

    def __len__(self):
        t = self.type
        if t == _native.LIST:
            return _native.listLen(self._ptr)
        if t in (_native.STRUCT, _native.MAP):
            return len(self.keys())
        return 0

    def __iter__(self):
        t = self.type
        if t == _native.LIST:
            n = _native.listLen(self._ptr)
            for i in range(n):
                ptr = _native.listGet(self._ptr, i)
                if ptr is not None:
                    yield Value(ptr, self._doc)
        elif t in (_native.STRUCT, _native.MAP):
            for _, v in self.items():
                yield v

    def __getitem__(self, key):
        if isinstance(key, int):
            ptr = _native.listGet(self._ptr, key)
            if ptr is None:
                return None
            return Value(ptr, self._doc)
        t = self.type
        if t in (_native.STRUCT, _native.MAP):
            ptr = _native.structGet(self._ptr, key)
            if ptr is None:
                return None
            return Value(ptr, self._doc)
        return None

    def keys(self):
        result = []
        def cb(k, _v):
            result.append(k)
            return True
        t = self.type
        if t in (_native.STRUCT, _native.MAP):
            _native.structEach(self._ptr, cb)
        return result

    def items(self):
        result = []
        def cb(k, v):
            result.append((k, Value(v, self._doc)))
            return True
        t = self.type
        if t in (_native.STRUCT, _native.MAP):
            _native.structEach(self._ptr, cb)
        return result


class ListBuilder:
    def __init__(self, docPtr, listPtr, docObj):
        self._doc = docPtr
        self._list = listPtr
        self._docObj = docObj

    def append(self, value):
        ptr = _makeVal(self._doc, value)
        _native.docListPush(self._doc, self._list, ptr)
        return self

    def build(self):
        return Value(self._list, self._docObj)


class StructBuilder:
    def __init__(self, docPtr, structPtr, docObj):
        self._doc = docPtr
        self._struct = structPtr
        self._docObj = docObj

    def set(self, key, value):
        ptr = _makeVal(self._doc, value)
        _native.docStructSet(self._doc, self._struct, key, ptr)
        return self

    def build(self):
        return Value(self._struct, self._docObj)


def _makeVal(docPtr, value):
    if isinstance(value, Value):
        return value._ptr
    if value is None:
        return _native.valNull(docPtr)
    if isinstance(value, bool):
        return _native.valBool(docPtr, value)
    if isinstance(value, int):
        return _native.valInt(docPtr, value)
    if isinstance(value, float):
        return _native.valFloat(docPtr, value)
    if isinstance(value, str):
        return _native.valString(docPtr, value)
    if isinstance(value, bytes):
        return _native.valBytes(docPtr, value)
    raise TypeError(f"unsupported value type: {type(value)}")

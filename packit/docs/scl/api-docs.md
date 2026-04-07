# pyscl API Reference

Python bindings for SCL (Structured Configuration Language) via native C library.

```sh
pip install pyscl
```

[Language documentation](https://github.com/shareui/scl-c/blob/main/docs/scl-lang.md)

---

## Module

```python
import scl
from scl import Doc, Value
from errors import ParseError, TomlError
from opts import ParseOpts
```

---

## Parsing

### `scl.parse(src, opts=None) -> Doc`

Parse SCL source string. Raises `ParseError` on failure.

```python
doc = scl.parse('@scl 1\nport: int = 8080\n')
```

### `scl.parseFile(path, opts=None) -> Doc`

Parse SCL file by path. Raises `ParseError` on failure.

```python
doc = scl.parseFile('config.scl')
```

### `scl.version() -> tuple[int, int]`

Returns `(major, minor)` of the native library.

---

## ParseOpts

```python
opts = ParseOpts(
    allowUnknownAnnotations=False,  # do not error on unknown @annotations
    strictDatetime=False,           # require explicit timezone in datetime values
    maxDepth=0,                     # max nesting depth, 0 = unlimited
)
doc = scl.parse(src, opts)
```

---

## Doc

Parsed document. Owns all value memory. Use as a context manager for deterministic release.

```python
with scl.parse(src) as doc:
    val = doc['port']
```

### Access

```python
doc['key']              # -> Value | None, top-level field by name
doc.get('key')          # same as above
doc.getPath('a.b.c')    # -> Value | None, dot-separated path
doc.keys()              # -> list[str], top-level keys in document order
doc.items()             # -> list[tuple[str, Value]]
```

### Serialization

```python
doc.serialize()  # -> str, SCL format
doc.toJson()     # -> str, JSON
doc.toToml()     # -> str, TOML — raises TomlError if doc contains bytes or union values
```

### Building

Create a document programmatically without parsing:

```python
doc = Doc.new()

doc.set('host', 'localhost')   # str
doc.set('port', 8080)          # int
doc.set('debug', False)        # bool
doc.set('ratio', 0.5)          # float
doc.set('data', b'\x01\x02')   # bytes
doc.set('nothing', None)       # null

ports = doc.newList().append(8080).append(8081).build()
doc.set('ports', ports)

server = doc.newStruct().set('host', 'localhost').set('port', 8080).build()
doc.set('server', server)

out = doc.serialize()
```

`doc.val(value) -> Value` — wrap a Python value as a `Value` without setting it on the doc.

Accepted Python types in `set` / `append` / `val`: `str`, `int`, `float`, `bool`, `bytes`, `None`, or an existing `Value`.

---

## Value

Read-only handle to a value node inside a `Doc`. Invalid after the owning doc is freed.

### Type

```python
val.type  # int constant: scl.NULL, scl.STRING, scl.INT, etc.
```

Type constants: `NULL STRING INT UINT FLOAT BOOL BYTES DATE DATETIME DURATION LIST MAP STRUCT UNION`

### Primitive readers

All return `None` on type mismatch, never coerce.

```python
val.asString()    # -> str | None
val.asInt()       # -> int | None
val.asUint()      # -> int | None
val.asFloat()     # -> float | None
val.asBool()      # -> bool | None
val.asBytes()     # -> bytes | None
val.asDate()      # -> str | None   e.g. "2024-01-15"
val.asDatetime()  # -> str | None   e.g. "2024-01-15T10:00:00Z"
val.asDuration()  # -> str | None   e.g. "3h30m"
val.isNull()      # -> bool
```

`asString()` returns `None` for `DATE`, `DATETIME`, and `DURATION` — use the specific reader.

### Collections

```python
len(val)          # list length, or struct/map key count
val[0]            # -> Value | None, list index
val['key']        # -> Value | None, struct/map field
val.keys()        # -> list[str], struct/map keys in document order
val.items()       # -> list[tuple[str, Value]]

for item in val:  # iterates list elements, or struct/map values
    ...
```

Out-of-bounds list access returns `None`.

---

## Errors

```python
from errors import ParseError, TomlError

try:
    doc = scl.parse(bad_src)
except ParseError as e:
    print(e)  # includes line, col, and source excerpt

try:
    toml = doc.toToml()
except TomlError as e:
    print(e)
```

---

## Warnings

`doc.warnings` is a `list[str]`. Non-empty when `@deprecated` fields are present or other non-fatal issues are found.

```python
doc = scl.parse(src)
for w in doc.warnings:
    print('warning:', w)
```

---

## Full example

```python
import scl

src = '''
@scl 1

host: string = "localhost"
port: int @range(1, 65535) = 8080
tags: [string] = ["prod", "v2"]

db: struct {
    url: string
    pool: int
} = {
    url = "postgres://localhost/app"
    pool = 10
}
'''

with scl.parse(src) as doc:
    print(doc['host'].asString())        # localhost
    print(doc['port'].asInt())           # 8080
    print([v.asString() for v in doc['tags']])   # ['prod', 'v2']
    print(doc.getPath('db.url').asString())       # postgres://localhost/app
    print(doc.toJson())
```
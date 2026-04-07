# SCL Language Reference

SCL (Structured Configuration Language) is a typed, explicit key-value configuration format.  
Every document has one valid parse result. Ambiguous input is always a parse error.

## File structure

Every SCL file starts with a version directive, followed by field declarations.

```scl
@scl 1

name: string = "Alice"
age: int = 30
active: bool = true
```

`@scl 1` is required. The parser rejects unknown version numbers.  
Fields are declared as `name: type = value`. The type annotation is always required.

---

## Primitive types

| Type | Example | Description |
|---|---|---|
| `string` | `"hello"` | UTF-8 string |
| `int` | `42`, `-7` | 64-bit signed integer |
| `uint` | `42u` | 64-bit unsigned integer |
| `float` | `3.14`, `-0.5` | IEEE 754 double |
| `bool` | `true`, `false` | Boolean |
| `bytes` | `b64"aGVsbG8="` | Base64-encoded binary |
| `date` | `2024-01-15` | ISO 8601 date |
| `datetime` | `2024-01-15T10:00:00Z` | ISO 8601 datetime, timezone required |
| `duration` | `3h30m`, `90s`, `500ms` | Human-readable duration |
| `null` | `null` | Explicit null — only valid in optional fields |

---

## Strings

Standard strings use double quotes with C-style escape sequences.

```scl
greeting: string = "hello world"
tab: string = "col1\tcol2"
unicode: string = "emoji \u{1F600}"
```

Multiline strings use triple quotes. Leading newline is stripped. Content is dedented based on the indentation of the first non-empty line.

```scl
query: string = """
    SELECT *
    FROM users
    WHERE active = true
"""
```

There is only one multiline syntax.

---

## Optional fields

Appending `?` to a type marks the field as optional. Optional fields may be assigned `null`.  
Assigning `null` to a non-optional field is a parse error.

```scl
nickname: string? = null
timeout: int? = 30
```

---

## Lists

Lists are typed. The element type is explicit.

```scl
ports: [int] = [8080, 8081, 8082]

tags: [string] = [
    "production",
    "v2",
    "eu-west",
]
```

Trailing commas are always allowed. `[any]` does not exist.

---

## Maps

Maps have explicit key and value types.

```scl
env: {string: string} = {
    "DATABASE_URL" = "postgres://localhost/app"
    "PORT" = "8080"
}
```

---

## Structs

Structs are inline schema + value. Fields are declared in the type and assigned in the value.

```scl
server: struct {
    host: string
    port: int
    tls: bool
} = {
    host = "localhost"
    port = 8080
    tls = false
}
```

Structs are closed by default — unknown fields in the value are a parse error.

`struct open` allows extra fields beyond the declared schema.

```scl
metadata: struct open {
    version: string
} = {
    version = "1.0"
    author = "team-a"
}
```

---

## Enums

Enums are declared at file scope with `@enum`. Variants are uppercase identifiers.

```scl
@enum LogLevel = DEBUG | INFO | WARN | ERROR

level: LogLevel = INFO
```

The enum name is used as the field type. Assigning an undeclared variant is a parse error.

---

## Unions

Union types combine two or more types with `|`. The value must satisfy exactly one of the listed types.

```scl
id: string | int = "user-42"
result: string | null = null
```

`null` in a union is explicit and must appear in the type declaration.

---

## Constants and references

`@const` defines a reusable named value. References use `$name`.

```scl
@const defaultTimeout: int = 30

read: int = $defaultTimeout
write: int = $defaultTimeout
```

Constants are resolved at parse time. Forward references are not allowed.

---

## Struct merging

Two struct values can be merged with `&`. The right side wins on conflicting keys.  
Types of both sides must be compatible.

```scl
@const base: struct {
    timeout: int
    retries: int
} = {
    timeout = 30
    retries = 3
}

production: struct {
    timeout: int
    retries: int
    region: string
} = $base & {
    timeout = 60
    region = "eu-west"
}
```

Merging is explicit. There is no hidden inheritance.

---

## Annotations

Annotations constrain field values and are validated at parse time. A violation is a parse error.

```scl
port: int @range(1, 65535) = 8080
name: string @minlen(1) @maxlen(64) = "alice"
ratio: float @range(0.0, 1.0) = 0.5
email: string @pattern("[^@]+@[^@]+") = "a@b.com"
items: [string] @minlen(1) = ["x"]
outdated: string @deprecated = "old"
```

| Annotation | Applies to | Description |
|---|---|---|
| `@range(min, max)` | `int`, `uint`, `float` | Inclusive bounds check |
| `@minlen(n)` | `string`, `[T]` | Minimum length |
| `@maxlen(n)` | `string`, `[T]` | Maximum length |
| `@pattern(regex)` | `string` | Must match the given regular expression |
| `@deprecated` | any field | Emits a parse warning |

Multiple annotations on the same field are allowed.

---

## Includes

`@include` inserts the contents of another SCL file into the current scope.

```scl
@include "base.scl"
@include "secrets.scl" as secrets
```

Without `as`, all top-level keys from the included file are merged into the current scope.  
With `as name`, included keys are accessible as `name.key`.  
Circular includes are detected and reported as a parse error.  
The included file must be a valid SCL document.

---

## Comments

Only line comments are supported. Block comments do not exist.

```scl
// standalone comment

server: struct {
    // port the service listens on
    port: int // inline comment
} = {
    port = 8080
}
```

Comments are parsed and attached to the following field in the AST.

---

## Error format

All parse and type errors follow a consistent format.

```
scl error at line 4, col 12
  field "port": expected int, got string
  |  port: int = "8080"
  |              ^^^^^^
```

Every error includes: file position, field name when applicable, a description, and a source excerpt with caret annotation.

---

## File extensions

| Extension | Use |
|---|---|
| `.scl` | Standard SCL document |
| `.scls` | Schema-only file — type definitions and annotations, no values |

---

## Non-goals

SCL is not a programming language — no loops, functions, or conditionals.  
SCL is not a query language.  
SCL is not a binary format — use Protobuf or BARE for that.  
SCL is not a full schema language — for complex contracts, use Protobuf or JSON Schema.

# Building PackIt

## Requirements

Install **ElyxBuilder** from the [releases page](https://github.com/shareui/ElyxBuilder/releases).

Documentation:
- [English](https://github.com/shareui/ElyxBuilder/blob/main/docs/en.md)
- [Russian](https://github.com/shareui/ElyxBuilder/blob/main/docs/ru.md)

Compiled builds require **Python 3.11**.

## Build commands

All commands are run from the repository root.

### Compiled

**Universal** — use when all obfuscated classes are present in the build:

```bash
elyb build -c -v -nf -sv 12.6.4 true
```

**exteraGram** — use when the build does not contain obfuscated classes for AyuGram, or they are outdated:

```bash
elyb build -c -v -nf -sv 12.6.4 true -sc com.exteragram.messenger exteraGram
```

**AyuGram** — use when the build does not contain obfuscated classes for exteraGram, or they are outdated:

```bash
elyb build -c -v -nf -sv 12.6.4 true -sc com.radolyn.ayugram AyuGram
```

### Uncompiled

**Universal:**

```bash
elyb build -v -nf -sv 12.6.4 true
```

**exteraGram:**

```bash
elyb build -v -nf -sv 12.6.4 true -sc com.exteragram.messenger exteraGram
```

**AyuGram:**

```bash
elyb build -v -nf -sv 12.6.4 true -sc com.radolyn.ayugram AyuGram
```

## Native libraries

Prebuilt `.so` files are located in `packit/native/`. Rebuilding them is not required for standard plugin builds.

Sources:
- `libscl` → [shareui/scl-c](https://github.com/shareui/scl-c)
- `libbithash` → [shareui/bithash](https://github.com/shareui/bithash)
- Other libs → `libs/` directory in this repository

# Building PackIt

## Requirements

Install **ElyxBuilder** from PyPI:

```bash
pip install ElyxBuilder
```

Documentation:
- [English](https://github.com/shareui/ElyxBuilder/blob/main/docs/en.md)
- [Russian](https://github.com/shareui/ElyxBuilder/blob/main/docs/ru.md)

Compiled builds require **Python 3.11**.

## Build commands

All commands are run from the repository root. The output archive is written to `builds/`.

### Compiled

```bash
elyb build -c 2 -v -nf
```

`-c 2` compiles sources to `.pyc` with optimization level 2, `-v` prints the build log, `-nf` excludes the elyxbuilder directory from the archive.

### Uncompiled

```bash
elyb build -v -nf
```

### Client-specific builds

By default the build is **Universal** (works for both exteraGram and AyuGram). To mark a build for a specific client, add `-sc`:

```bash
# exteraGram
elyb build -c 2 -v -nf -sc com.exteragram.messenger exteraGram

# AyuGram
elyb build -c 2 -v -nf -sc com.radolyn.ayugram AyuGram
```

The client version the build was made against can be recorded with `-sv <version> true` (the version is appended to the archive name). Run `elyb build --help` or see the ElyxBuilder docs for all flags.

## CI builds

Every push that touches `packit/**` runs the [build workflow](.github/workflows/build.yml). The compiled `.eaf` is available as a downloadable artifact on the workflow run page (Actions → run → Artifacts).

## Native libraries

Prebuilt `.so` files are located in `packit/native/`. Rebuilding them is not required for standard plugin builds.

Sources:
- `libscl` → [shareui/scl-c](https://github.com/shareui/scl-c)
- `libbithash` → [shareui/bithash](https://github.com/shareui/bithash)
- Other libs → `libs/` directory in this repository

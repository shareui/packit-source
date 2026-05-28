# PackIt Versions Archive

This file contains all versions of PackIt.

## Build types

Each version may have up to three build variants:

**Universal**: built against a client that contains obfuscated classes for all supported forks. Works for both exteraGram and AyuGram.

**exteraGram**: built against a client that only contains obfuscated classes for exteraGram. Used when AyuGram classes are absent or outdated.

**AyuGram**: built against a client that only contains obfuscated classes for AyuGram. Used when exteraGram classes are absent or outdated.

## Version notation

Versions marked with **PB** are built against a private beta of the client.
Versions marked with **REL** are built against a public release of the client.

The suffix **-{number}** (e.g. `12.6.4-2`) indicates which client build of that version this was compiled against.

## Cross-installing

Installing a build on an unintended client is allowed. If you install a non-Universal build on a different client of the same version, it will most likely work... but some things may behave incorrectly or not work at all.

Installing a build across different versions is also possible, but may produce incorrect behavior in the same way.

---

## Stable builds

**Universal**

| PackIt | Client | Type | Builder |
|---|---|---|---|
| None | None | None | None |

**exteraGram**

| PackIt | Client | Type | Builder |
|---|---|---|---|
| 0.0.0 | 12.6.4 | PB | @shareui |

**AyuGram**

| PackIt | Client | Type | Builder |
|---|---|---|---|
| None | None | None | None |

## Unstable builds
None

---
All builds are created using ElyxBuilder


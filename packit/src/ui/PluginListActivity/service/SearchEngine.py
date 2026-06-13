# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import ctypes
import json
import os


# native loader

_lib = None
_lib_load_attempted = False

def _load_native() -> bool:
    global _lib, _lib_load_attempted
    if _lib_load_attempted:
        return _lib is not None
    _lib_load_attempted = True

    # 0 = native, 1 = python only
    try:
        from elyx import settings
        if settings.get("search_engine", 0) == 1:
            logx("search: python engine selected in settings, skipping native load", True)
            return False
    except Exception:
        pass

    from ....nativeLoader import loadSearch
    lib = loadSearch()
    if lib is None:
        logx("search: failed to load libsearch.so, using python fallback", True)
        return False
    _lib = lib
    logx("search: native libsearch.so loaded successfully", True)
    return True

# native index wrapper

class _NativeIndex:
    def __init__(self, handle: int):
        self.handle = handle

    def free(self):
        if _lib and self.handle >= 0:
            _lib.search_free_index(self.handle)
            self.handle = -1

# python fallback implementation

_RU_TO_EN = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y',
    'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h',
    'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n',
    'ь': 'm', 'б': ',', 'ю': '.',
}

def _translit(text: str) -> str:
    return ''.join(_RU_TO_EN.get(c, c) for c in text)

def _trigrams(text: str) -> set:
    padded = f" {text} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}

def _words(text: str) -> list:
    return [w for w in text.replace('_', ' ').split() if w]

def _edit_distance_1(a: str, b: str) -> bool:
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        return diffs == 1
    shorter, longer = (a, b) if la < lb else (b, a)
    i = j = diffs = 0
    while i < len(shorter) and j < len(longer):
        if shorter[i] != longer[j]:
            diffs += 1
            if diffs > 1:
                return False
            j += 1
        else:
            i += 1
            j += 1
    return True

def _py_build_index(plugins: list) -> dict:
    index = {}
    skipped = 0
    for p in plugins:
        pid = str(p.get("id") or "")
        if not pid:
            skipped += 1
            continue
        name = str(p.get("name") or "").lower()
        author = str(p.get("author") or "").lower()
        about = p.get("about", [])
        if isinstance(about, list):
            descEn = str(about[0]).lower() if len(about) > 0 else ""
            descRu = str(about[1]).lower() if len(about) > 1 else ""
        else:
            descEn = str(p.get("description") or "").lower()
            descRu = descEn
        index[pid] = {
            "name": _trigrams(name),
            "author": _trigrams(author),
            "desc_en": _trigrams(descEn),
            "desc_ru": _trigrams(descRu),
            "name_raw": name,
            "author_raw": author,
            "desc_en_raw": descEn,
            "desc_ru_raw": descRu,
            "id_raw": pid.lower(),
            "name_words": _words(name),
            "id_words": _words(pid.lower()),
        }
    if skipped:
        logx(f"search: build_index skipped {skipped} plugins with no id", True)
    return index

def _trigram_similarity(queryTrigrams: set, fieldTrigrams: set) -> float:
    if not queryTrigrams or not fieldTrigrams:
        return 0.0
    intersection = len(queryTrigrams & fieldTrigrams)
    union = len(queryTrigrams | fieldTrigrams)
    return intersection / union if union > 0 else 0.0

def _all_tokens_match(tokens: list, field: str) -> bool:
    return all(t in field for t in tokens)

def _prefix_word_match(query: str, words: list) -> bool:
    return any(w.startswith(query) for w in words)

_MIN_SIMILARITY = 0.15

def _py_score(plugin: dict, query: str, index: dict, isRussian: bool, fuzzy: bool = False) -> tuple:
    if not query:
        return (0, 0, 0.0)

    ql = query.lower().strip()

    translitQ = _translit(ql)
    if translitQ != ql and translitQ.replace(' ', '').isalpha():
        ql = translitQ

    pid = str(plugin.get("id") or "")
    entry = index.get(pid)
    if not entry:
        logx(f"search: score() called for '{pid}' not in index — index may be stale", True)
        return (6, 0, 0.0)

    nameRaw = entry["name_raw"]
    idRaw = entry["id_raw"]
    authorRaw = entry["author_raw"]
    descPrimary = entry["desc_ru_raw"] if isRussian else entry["desc_en_raw"]
    descSecondary = entry["desc_en_raw"] if isRussian else entry["desc_ru_raw"]
    nameWords = entry["name_words"]
    idWords = entry["id_words"]

    tokens = _words(ql)

    if ql in nameRaw:
        return (1, 0 if nameRaw.startswith(ql) else 1, 0.0)
    if ql in descPrimary:
        return (2, 0 if descPrimary.startswith(ql) else 1, 0.0)
    if ql in descSecondary:
        return (3, 0 if descSecondary.startswith(ql) else 1, 0.0)
    if ql in idRaw:
        return (4, 0 if idRaw.startswith(ql) else 1, 0.0)
    if ql in authorRaw:
        return (5, 0 if authorRaw.startswith(ql) else 1, 0.0)

    if _prefix_word_match(ql, nameWords):
        return (1, 2, 0.0)
    if _prefix_word_match(ql, idWords):
        return (4, 2, 0.0)

    if len(tokens) > 1:
        if _all_tokens_match(tokens, nameRaw):
            return (1, 3, 0.0)
        if _all_tokens_match(tokens, descPrimary):
            return (2, 3, 0.0)
        if _all_tokens_match(tokens, descSecondary):
            return (3, 3, 0.0)
        if _all_tokens_match(tokens, idRaw):
            return (4, 3, 0.0)
        if _all_tokens_match(tokens, authorRaw):
            return (5, 3, 0.0)

    queryTri = _trigrams(ql)
    nameSim = _trigram_similarity(queryTri, entry["name"])
    if nameSim >= _MIN_SIMILARITY:
        return (1, 4, -nameSim)

    descPrimaryField = "desc_ru" if isRussian else "desc_en"
    descSecondaryField = "desc_en" if isRussian else "desc_ru"
    descPrimarySim = _trigram_similarity(queryTri, entry[descPrimaryField])
    if descPrimarySim >= _MIN_SIMILARITY:
        return (2, 4, -descPrimarySim)

    descSecondarySim = _trigram_similarity(queryTri, entry[descSecondaryField])
    if descSecondarySim >= _MIN_SIMILARITY:
        return (3, 4, -descSecondarySim)

    idSim = _trigram_similarity(queryTri, _trigrams(idRaw))
    if idSim >= _MIN_SIMILARITY:
        return (4, 4, -idSim)

    authorSim = _trigram_similarity(queryTri, entry["author"])
    if authorSim >= _MIN_SIMILARITY:
        return (5, 4, -authorSim)

    if fuzzy:
        for w in nameWords:
            if _edit_distance_1(ql, w):
                return (1, 5, 0.0)
        for w in idWords:
            if _edit_distance_1(ql, w):
                return (4, 5, 0.0)

    return (6, 0, 0.0)

# public API

def build_index(plugins: list):
    if _load_native():
        try:
            raw = json.dumps(plugins, ensure_ascii=False)
            handle = _lib.search_build_index(raw.encode('utf-8'))
            if handle >= 0:
                logx(f"search: native index built for {len(plugins)} plugins (handle={handle})", True)
                return _NativeIndex(handle)
            logx("search: native build_index returned invalid handle, falling back to python", True)
        except Exception as e:
            logx(f"search: native build_index failed, falling back to python: {e}", False)

    logx(f"search: python index built for {len(plugins)} plugins", True)
    return _py_build_index(plugins)


def score(plugin: dict, query: str, index, isRussian: bool, fuzzy: bool = False) -> tuple:
    if isinstance(index, _NativeIndex) and index.handle >= 0:
        try:
            pid = str(plugin.get("id") or "")
            ptr = _lib.search_score(
                index.handle,
                pid.encode('utf-8'),
                query.encode('utf-8'),
                int(isRussian),
                int(fuzzy)
            )
            if ptr:
                try:
                    raw = ctypes.string_at(ptr).decode('utf-8')
                    parsed = json.loads(raw)
                    return (parsed[0], parsed[1], parsed[2])
                finally:
                    _lib.search_free_str(ptr)
            logx("search: native score returned null, falling back to python", True)
        except Exception as e:
            logx(f"search: native score failed, falling back to python: {e}", False)
        return (6, 0, 0.0)

    return _py_score(plugin, query, index, isRussian, fuzzy)
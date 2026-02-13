from android_utils import log


def _trigrams(text: str) -> set:
    # pad with spaces so short strings still produce trigrams
    padded = f" {text} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def build_index(plugins: list) -> dict:
    index = {}
    for p in plugins:
        pid = str(p.get("id") or "")
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
            # raw strings for exact-substring fast path
            "name_raw": name,
            "author_raw": author,
            "desc_en_raw": descEn,
            "desc_ru_raw": descRu,
            "id_raw": pid.lower(),
        }
    return index


def _trigram_similarity(queryTrigrams: set, fieldTrigrams: set) -> float:
    """jaccard similarity between two trigram sets"""
    if not queryTrigrams or not fieldTrigrams:
        return 0.0
    intersection = len(queryTrigrams & fieldTrigrams)
    union = len(queryTrigrams | fieldTrigrams)
    return intersection / union if union > 0 else 0.0


# minimum jaccard similarity to consider a match
_MIN_SIMILARITY = 0.15


def score(plugin: dict, query: str, index: dict, isRussian: bool) -> tuple:
    if not query:
        return (0, 0, 0.0)

    ql = query.lower()
    pid = str(plugin.get("id") or "")
    entry = index.get(pid)
    if not entry:
        return (6, 0, 0.0)

    nameRaw = entry["name_raw"]
    idRaw = entry["id_raw"]
    authorRaw = entry["author_raw"]
    descPrimary = entry["desc_ru_raw"] if isRussian else entry["desc_en_raw"]
    descSecondary = entry["desc_en_raw"] if isRussian else entry["desc_ru_raw"]

    # exact substring fast path — same priority as before
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

    # trigram fuzzy path
    queryTri = _trigrams(ql)
    nameSim = _trigram_similarity(queryTri, entry["name"])
    if nameSim >= _MIN_SIMILARITY:
        return (1, 2, -nameSim)

    descPrimaryField = "desc_ru" if isRussian else "desc_en"
    descSecondaryField = "desc_en" if isRussian else "desc_ru"
    descPrimarySim = _trigram_similarity(queryTri, entry[descPrimaryField])
    if descPrimarySim >= _MIN_SIMILARITY:
        return (2, 2, -descPrimarySim)

    descSecondarySim = _trigram_similarity(queryTri, entry[descSecondaryField])
    if descSecondarySim >= _MIN_SIMILARITY:
        return (3, 2, -descSecondarySim)

    idSim = _trigram_similarity(queryTri, _trigrams(idRaw))
    if idSim >= _MIN_SIMILARITY:
        return (4, 2, -idSim)

    authorSim = _trigram_similarity(queryTri, entry["author"])
    if authorSim >= _MIN_SIMILARITY:
        return (5, 2, -authorSim)

    return (6, 0, 0.0)

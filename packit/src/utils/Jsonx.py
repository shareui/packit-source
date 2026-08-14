# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Forgiving parser for repository files.
#
# A repomap.json is written by hand, and a trailing comma before a closing
# brace is the mistake people make — javascript and python both accept it,
# json does not. The official repository shipped one and every client then
# refused to add or refresh it, reporting "no metadata" for a file that was
# otherwise perfectly fine.
#
# So: parse strictly, and only if that fails strip trailing commas and try
# once more. The stripping walks the text instead of running a regex over it,
# because a naive pattern also eats the comma in a string like "a, }" and
# would quietly change data.

from packutil import logx
import json


def _strip_trailing_commas(text: str) -> str:
    out = []
    in_string = False
    escaped = False
    pending = -1  # index in `out` of a comma waiting to see what follows

    for ch in text:
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            pending = -1
            in_string = True
            out.append(ch)
            continue

        if ch == ",":
            pending = len(out)
            out.append(ch)
            continue

        if ch in " \t\r\n":
            out.append(ch)
            continue

        if ch in "}]" and pending >= 0:
            out[pending] = ""  # the comma was trailing after all
        pending = -1
        out.append(ch)

    return "".join(out)


def loads(text):
    """json.loads that tolerates trailing commas. Raises like json.loads does."""
    try:
        return json.loads(text)
    except ValueError as strict_error:
        repaired = _strip_trailing_commas(text)
        if repaired == text:
            raise
        value = json.loads(repaired)
        logx(f"jsonx: accepted a file with trailing commas ({strict_error})", False)
        return value


def loads_response(response):
    """Same, for a requests response."""
    return loads(response.text)

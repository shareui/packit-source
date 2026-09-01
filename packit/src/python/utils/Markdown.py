# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Markdown handling for plugin descriptions.
#
# The SDK parser (markdown_utils.parse_markdown) marks bold with a SINGLE
# asterisk — it has doubled forms for underline (__) and spoiler (||), but none
# for bold. Plugin authors write the usual **bold**, which the parser reads as
# two empty bold pairs: the markers vanish and nothing ends up bold. Everything
# that renders a description goes through here so both spellings work.

from packutil import logx
import re

# **bold** -> *bold* (non-greedy, may span lines); leaves single * alone
_DOUBLE_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)


def normalize(text) -> str:
    s = str(text or "")
    try:
        return _DOUBLE_BOLD.sub(r"*\1*", s)
    except Exception:
        return s


def parse(text):
    # returns the SDK ParsedMessage (.text + .entities) for normalized markdown,
    # or None when the parser is unavailable or the markdown is malformed
    try:
        from markdown_utils import parse_markdown
        return parse_markdown(normalize(text))
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"markdown: parse failed: {e}", False)
        return None


def to_plain(text) -> str:
    # text with every marker removed, for places that cannot render entities
    parsed = parse(text)
    if parsed is not None:
        return parsed.text
    return str(text or "")

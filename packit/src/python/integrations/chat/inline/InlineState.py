# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

try:
    from elyx import settings
    _is_enabled = settings.get("inline_search_enabled", True)
except Exception:
    _is_enabled = True

def update_state(val):
    global _is_enabled
    _is_enabled = val

def get_state():
    return _is_enabled

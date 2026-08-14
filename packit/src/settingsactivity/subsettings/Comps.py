# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.settings import Header, Divider
from elyx import strings


def build_comps_page(other_settings, ctx):
    items = [
        Header(text=strings.components_header),
        other_settings._build_search_engine_item(ctx),
        other_settings._build_hash_function_item(ctx),
        Divider(),
    ]
    return [item for item in items if item is not None]
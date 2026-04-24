from ui.settings import Header, Divider
from elyx import strings

def build_sfx_page(other_settings, ctx):
    items = [
        Header(text=strings.sfx_header),
        other_settings._make_expandable_switch("sfx_enabled", strings.sfx_header, [
            ("sfx_install", False),
            ("sfx_copy_link", False),
            ("sfx_search", False),
            ("sfx_clear_search", False),
            ("sfx_achievement", True),
        ]),
        other_settings._make_es_child("sfx_install", strings.sfx_install, False) if other_settings._es_is_expanded("sfx_enabled") else None,
        other_settings._make_es_child("sfx_copy_link", strings.sfx_copy_link, False) if other_settings._es_is_expanded("sfx_enabled") else None,
        other_settings._make_es_child("sfx_search", strings.sfx_search, False) if other_settings._es_is_expanded("sfx_enabled") else None,
        other_settings._make_es_child("sfx_clear_search", strings.sfx_clear_search, False) if other_settings._es_is_expanded("sfx_enabled") else None,
        other_settings._make_es_child("sfx_achievement", strings.sfx_achievement, True) if other_settings._es_is_expanded("sfx_enabled") else None,
        other_settings._build_sfx_volume_slider(ctx),
        Divider(text=strings.sfx_header_desc),
    ]
    return [item for item in items if item is not None]

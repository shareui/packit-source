# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Divider, Custom
from elyx import strings, settings

_SFX_CHILDREN = [
    ("sfx_install", "sfx_install", False),
    ("sfx_copy_link", "sfx_copy_link", False),
    ("sfx_search", "sfx_search", False),
    ("sfx_clear_search", "sfx_clear_search", False),
    ("sfx_achievement", "sfx_achievement", True),
    ("sfx_available_updates", "sfx_available_updates", False),
]


def _item_id(key):
    return hash(key) & 0x7FFFFFFF


def _reload():
    settings.set("_es_dummy", not settings.get("_es_dummy", False), reload_settings=True)


def _make_expandable(other_settings, ctx):
    try:
        from android_utils import OnClickListener
        from ...dexLoader import sfxExpandableCreate

        checked_count = sum(
            1 for key, _, default in _SFX_CHILDREN if settings.get(key, default)
        )

        def switch_click(view):
            new_value = not any(
                settings.get(key, default)
                for key, _, default in _SFX_CHILDREN
            )
            for key, _, _ in _SFX_CHILDREN:
                settings.set(key, new_value, reload_settings=False)
            _reload()

        listener = OnClickListener(switch_click)
        item = sfxExpandableCreate(
            ctx,
            _item_id("sfx_enabled"),
            strings.sfx_header,
            f"{checked_count}/{len(_SFX_CHILDREN)}",
            checked_count > 0,
            not other_settings._es_is_expanded("sfx_enabled"),
            listener,
        )
        if item is None:
            from org.telegram.ui.Components import UItem
            item = UItem.asExteraExpandableSwitch(
                _item_id("sfx_enabled"),
                strings.sfx_header,
                f"{checked_count}/{len(_SFX_CHILDREN)}",
                listener,
            )
            item.setChecked(checked_count > 0)
            item.setCollapsed(not other_settings._es_is_expanded("sfx_enabled"))
        return Custom(
            item=item,
            on_click=lambda view: other_settings._es_toggle_and_reload("sfx_enabled"),
        )
    except Exception as e:
        logx(f"sfx: expandable create error: {e}", False)
        return None


def _make_child(ctx, key, text, default):
    try:
        from ...dexLoader import sfxChildCreate

        item = sfxChildCreate(
            ctx,
            _item_id(key),
            text,
            settings.get(key, default),
        )
        if item is None:
            from org.telegram.ui.Components import UItem
            item = UItem.asRoundCheckbox(_item_id(key), text)
            item.setChecked(settings.get(key, default))
            item.pad()

        def on_click(view):
            settings.set(key, not settings.get(key, default), reload_settings=False)
            _reload()

        return Custom(item=item, on_click=on_click)
    except Exception as e:
        logx(f"sfx: child {key} create error: {e}", False)
        return None


def _make_volume_slider(ctx):
    try:
        from java import dynamic_proxy
        from java.lang.reflect import InvocationHandler
        from ...dexLoader import sfxVolumeSliderCreate

        class _VolumeChange(dynamic_proxy(InvocationHandler)):
            def invoke(self, proxy, method, args):
                if args:
                    settings.set("sfx_volume", int(args[0]), reload_settings=False)
                return None

        initial = int(settings.get("sfx_volume", 100))
        off_label = strings["sfx_volume_off"]
        maximum_label = strings["sfx_volume_maximum"]
        view = sfxVolumeSliderCreate(
            ctx,
            initial,
            strings.sfx_volume,
            off_label,
            maximum_label,
            _VolumeChange(),
        )
        if view is None:
            from ...ui.md3Slider import createMd3Slider

            def on_change(value):
                settings.set("sfx_volume", int(value), reload_settings=False)

            def format_value(label_type, value):
                if label_type != 0:
                    return f"{value}%"
                if value == 0:
                    return off_label
                if value == 100:
                    return maximum_label
                return f"{value}%"

            slider = createMd3Slider(
                ctx, 0, 100, initial, on_change, format_value
            )
            view = slider.view if slider is not None else None
        return Custom(view=view) if view is not None else None
    except Exception as e:
        logx(f"sfx: volume slider create error: {e}", False)
        return None

def build_sfx_page(other_settings, ctx):
    expanded = other_settings._es_is_expanded("sfx_enabled")
    items = [
        Header(text=strings.sfx_header),
        _make_expandable(other_settings, ctx),
        *(
            [
                _make_child(ctx, key, getattr(strings, label), default)
                for key, label, default in _SFX_CHILDREN
            ]
            if expanded else []
        ),
        _make_volume_slider(ctx),
        Divider(text=strings.sfx_header_desc),
    ]
    return [item for item in items if item is not None]

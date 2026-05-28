# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

_UNSORTED_KEY = "__unsorted__"


def collect_tags(plugins: list) -> dict:
    tags_summary = {}
    has_unsorted = False
    for plugin in plugins:
        plugin_tags = plugin.get("tags", [])
        if isinstance(plugin_tags, list) and plugin_tags:
            for tag_info in plugin_tags:
                if isinstance(tag_info, list) and len(tag_info) >= 1:
                    tag_name = tag_info[0]
                    if tag_name not in tags_summary:
                        tags_summary[tag_name] = 0
                    tags_summary[tag_name] += 1
        else:
            has_unsorted = True
    if has_unsorted:
        tags_summary[_UNSORTED_KEY] = sum(
            1 for p in plugins
            if not (isinstance(p.get("tags", []), list) and p.get("tags", []))
        )
    return tags_summary


def filter_by_tags(plugins: list, selected_tags: set) -> list:
    if not selected_tags:
        return list(plugins)

    all_tags = collect_tags(plugins)
    # all tags selected == no filter
    if selected_tags >= set(all_tags.keys()):
        return list(plugins)

    include_unsorted = _UNSORTED_KEY in selected_tags
    filtered = []
    for plugin in plugins:
        plugin_tags = plugin.get("tags", [])
        has_tags = isinstance(plugin_tags, list) and bool(plugin_tags)
        if not has_tags:
            if include_unsorted:
                filtered.append(plugin)
            continue
        for tag_info in plugin_tags:
            if isinstance(tag_info, list) and len(tag_info) >= 1:
                if tag_info[0] in selected_tags:
                    filtered.append(plugin)
                    break
    return filtered
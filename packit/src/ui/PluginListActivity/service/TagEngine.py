def collect_tags(plugins: list) -> dict:
    tags_summary = {}
    for plugin in plugins:
        plugin_tags = plugin.get("tags", [])
        if isinstance(plugin_tags, list):
            for tag_info in plugin_tags:
                if isinstance(tag_info, list) and len(tag_info) >= 1:
                    tag_name = tag_info[0]
                    if tag_name not in tags_summary:
                        tags_summary[tag_name] = 0
                    tags_summary[tag_name] += 1
    return tags_summary


def filter_by_tags(plugins: list, selected_tags: set) -> list:
    if not selected_tags:
        return list(plugins)

    filtered = []
    for plugin in plugins:
        plugin_tags = plugin.get("tags", [])
        if isinstance(plugin_tags, list):
            for tag_info in plugin_tags:
                if isinstance(tag_info, list) and len(tag_info) >= 1:
                    tag_name = tag_info[0]
                    if tag_name in selected_tags:
                        filtered.append(plugin)
                        break
    return filtered
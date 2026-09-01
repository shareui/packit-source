# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"utils: import elyx import strings failed: {e}")

def _count_active_repos(repo_manager) -> int:
    try:
        repos = repo_manager.getRepositories() or []
        return sum(1 for r in repos if r and r.get("enabled", True) and str(r.get("url") or "").strip())
    except Exception:
        return 0

def _plural_form(n: int, plural_type: str) -> str:
    # returns "one", "few", or "many" based on count and language plural rule
    if plural_type == "ru":
        # slavic rule: 1->one, 2-4->few, 5+->many (also handles 11-19 edge case)
        mod10 = n % 10
        mod100 = n % 100
        if mod10 == 1 and mod100 != 11:
            return "one"
        if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
            return "few"
        return "many"
    if plural_type == "pl":
        # polish rule
        mod10 = n % 10
        mod100 = n % 100
        if n == 1:
            return "one"
        if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
            return "few"
        return "many"
    # default "en" rule: 1→one, else→many
    return "one" if n == 1 else "many"

def _format_plural(n: int, key_one: str, key_few: str, key_many: str, plural_type: str) -> str:
    form = _plural_form(n, plural_type)
    template = key_many
    if form == "one":
        template = key_one
    elif form == "few":
        template = key_few
    return template.replace("{0}", str(n))

def _build_stats_label(repo_count: int, plugin_count: int) -> str:
    try:
        plural_type = strings["plural_type"]
        repo_str = _format_plural(
            repo_count,
            strings["repo_one"], strings["repo_few"], strings["repo_many"],
            plural_type
        )
        plugin_str = _format_plural(
            plugin_count,
            strings["plugin_one"], strings["plugin_few"], strings["plugin_many"],
            plural_type
        )
        return f"{repo_str} · {plugin_str}"
    except Exception:
        return strings("total_plugins", repo_count, plugin_count)

def _build_plugin_count_label(plugin_count: int) -> str:
    try:
        plural_type = strings["plural_type"]
        plugin_str = _format_plural(
            plugin_count,
            strings["plugin_one"], strings["plugin_few"], strings["plugin_many"],
            plural_type
        )
        return plugin_str
    except Exception:
        return strings("plugin_many", plugin_count)

def _parse_version(v_str):
    try:
        return tuple(int(x) for x in str(v_str).strip().split("."))
    except Exception:
        return (0,)

def _check_app_version(app_version_expr):
    from ....utils.AppVersion import check_app_version
    return check_app_version(app_version_expr)

def _filter_unavailable(plugins):
    try:
        from elyx import settings as _s
        if not _s.get("hide_unavailable_plugins", False):
            return plugins
    except Exception:
        return plugins
    result = []
    for p in plugins:
        av = p.get("app_version")
        if not av or _check_app_version(av):
            result.append(p)
    return result

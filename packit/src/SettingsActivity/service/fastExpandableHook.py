# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from android_utils import run_on_ui_thread
from hook_utils import find_class, get_private_field
from base_plugin import MethodHook
from client_utils import get_last_fragment

# expandable groups defined in OtherSettings.build()
# key -> [(child_key, child_default), ...]
_ES_GROUPS = {
    "sfx_enabled": [
        ("sfx_install", False),
        ("sfx_copy_link", False),
        ("sfx_search", False),
        ("sfx_clear_search", False),
        ("sfx_achievement", True),
    ],
    "inline_send_enabled": [
        ("inline_send_name", True),
        ("inline_send_version", True),
        ("inline_send_author", True),
        ("inline_send_description", True),
        ("inline_send_install", True),
    ],
}

# set of all child keys across all groups
_ALL_CHILD_KEYS = {ck for children in _ES_GROUPS.values() for ck, _ in children}


def setup_fast_expandable_hook(plugin, other_settings):
    try:
        PythonEngineClass = find_class("com.exteragram.messenger.plugins.PythonPluginsEngine")
        if PythonEngineClass is None:
            logx("fastExpandableHook: PythonPluginsEngine not found", True)
            return None

        logx(f"fastExpandableHook: PythonPluginsEngine found: {PythonEngineClass}", True)

        plugin_id = plugin.id

        class LoadPluginSettingsHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    requested_id = str(param.args[0]) if param.args[0] is not None else None
                    if requested_id != plugin_id:
                        return
                    result = _fast_reload(param, plugin_id, other_settings)
                    if result is not None:
                        param.setResult(result)
                except Exception as e:
                    logx(f"fastExpandableHook: hook error: {e}", False)

        refs = plugin.hook_all_methods(PythonEngineClass, "loadPluginSettings", LoadPluginSettingsHook())
        return refs[0] if refs else None

    except Exception as e:
        logx(f"fastExpandableHook: setup error: {e}", False)
        return None


def _fast_reload(param, plugin_id, other_settings):
    # returns a replacement result only when the fast path applies; None keeps
    # the original method's result. Never re-invoke the original from an
    # after-hook (it has already run) and never hand the engine an empty page:
    # an empty list gets cached as "plugin has no settings" and the settings
    # screen stays blank until reinstall.
    try:
        from elyx import settings as _s
        from android_utils import OnClickListener as _OCL

        # get settingItems from the open PluginSettingsActivity
        frag = get_last_fragment()
        if frag is None:
            logx("fastExpandableHook: frag is None -> keep original result", True)
            return None

        frag_class = frag.getClass().getName()
        if "PluginSettingsActivity" not in frag_class:
            logx(f"fastExpandableHook: frag is {frag_class} -> keep original result", True)
            return None

        setting_items = get_private_field(frag, "settingItems")
        if setting_items is None or setting_items.size() == 0:
            logx("fastExpandableHook: settingItems missing/empty -> keep original result", True)
            return None

        logx(f"fastExpandableHook: fast path, patching {setting_items.size()} items in-place", True)

        # patch expandable CustomSetting items in-place
        size = setting_items.size()
        for i in range(size):
            si = setting_items.get(i)
            if si is None:
                continue
            try:
                uitem = si.item
            except Exception:
                continue
            if uitem is None:
                continue

            item_id = int(uitem.id)

            # check if it's an expandable header
            for key, children in _ES_GROUPS.items():
                if item_id == (hash(key) & 0x7FFFFFFF):
                    _patch_expandable(si, uitem, key, children, other_settings, _s, _OCL)
                    break
            else:
                # check if it's a child checkbox
                for ck, cd in ((ck, cd) for children in _ES_GROUPS.values() for ck, cd in children):
                    if item_id == (hash(ck) & 0x7FFFFFFF):
                        uitem.setChecked(_s.get(ck, cd))
                        break

        # update adapter on UI thread
        def _update():
            try:
                frag2 = get_last_fragment()
                if frag2 is not None:
                    frag2.listView.adapter.update(True)
                    logx("fastExpandableHook: adapter.update(True) done", True)
            except Exception as e:
                logx(f"fastExpandableHook: adapter update error: {e}", False)

        run_on_ui_thread(_update)

        # return the mutated list so PluginsController.settings cache stays consistent
        return setting_items

    except Exception as e:
        logx(f"fastExpandableHook: _fast_reload error: {e}", False)
        return None


def _patch_expandable(si, uitem, key, children, other_settings, _s, _OCL):
    try:
        from elyx import strings
        checked_count = sum(1 for ck, cd in children if _s.get(ck, cd))
        total_count = len(children)
        uitem.animatedText = f"{checked_count}/{total_count}"
        uitem.setChecked(checked_count > 0)
        uitem.setCollapsed(not other_settings._es_is_expanded(key))

        def switch_click(view, ch=children):
            currently_any = any(_s.get(ck, cd) for ck, cd in ch)
            new_val = not currently_any
            for ck, _ in ch:
                _s.set(ck, new_val, reload_settings=False)
            _s.set("_es_dummy", not _s.get("_es_dummy", False), reload_settings=True)

        uitem.clickCallback = _OCL(switch_click)
    except Exception as e:
        logx(f"fastExpandableHook: _patch_expandable error: {e}", False)

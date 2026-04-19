import traceback
from android_utils import log, run_on_ui_thread
from hook_utils import find_class, get_private_field
from base_plugin import MethodReplacement
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
            log("fastExpandableHook: PythonPluginsEngine not found")
            return None

        log(f"fastExpandableHook: PythonPluginsEngine found: {PythonEngineClass}")

        plugin_id = plugin.id

        class LoadPluginSettingsHook(MethodReplacement):
            def replace_hooked_method(self, param):
                try:
                    requested_id = str(param.args[0]) if param.args[0] is not None else None
                    caller = "".join(traceback.format_stack()[-4:-1]).strip().replace("\n", " | ")
                    log(f"fastExpandableHook: loadPluginSettings called id={requested_id} | {caller}")
                    if requested_id != plugin_id:
                        return param.method.invoke(param.thisObject, param.args)
                    return _fast_reload(param, plugin_id, other_settings)
                except Exception as e:
                    log(f"fastExpandableHook: replace error: {e}")
                    try:
                        return param.method.invoke(param.thisObject, param.args)
                    except Exception:
                        return None

        try:
            StringClass = find_class("java.lang.String")
            method = PythonEngineClass.getDeclaredMethod("loadPluginSettings", StringClass)
            method.setAccessible(True)
            log(f"fastExpandableHook: method found: {method}")
            ref = plugin.hook_method(method, LoadPluginSettingsHook(plugin))
            log(f"fastExpandableHook: hook installed: {ref}")
            return ref
        except Exception as e:
            log(f"fastExpandableHook: getDeclaredMethod failed: {e}, trying hook_all_methods")
            refs = plugin.hook_all_methods(PythonEngineClass, "loadPluginSettings", LoadPluginSettingsHook(plugin))
            log(f"fastExpandableHook: hook_all_methods result: {refs}")
            return refs[0] if refs else None

    except Exception as e:
        log(f"fastExpandableHook: setup error: {e}")
        return None


def _fast_reload(param, plugin_id, other_settings):
    try:
        from elyx import settings as _s
        from org.telegram.ui.Components import UItem
        from android_utils import OnClickListener as _OCL
        from com.exteragram.messenger.plugins import PluginsController

        # get settingItems from the open PluginSettingsActivity
        frag = get_last_fragment()
        if frag is None:
            log("fastExpandableHook: frag is None -> fallback full reload")
            return _original_call(param)

        frag_class = frag.getClass().getName()
        if "PluginSettingsActivity" not in frag_class:
            log(f"fastExpandableHook: frag is {frag_class} -> fallback full reload")
            return _original_call(param)

        setting_items = get_private_field(frag, "settingItems")
        if setting_items is None:
            log("fastExpandableHook: settingItems is None -> fallback full reload")
            return _original_call(param)

        log(f"fastExpandableHook: fast path, patching {setting_items.size()} items in-place")

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
                    log("fastExpandableHook: adapter.update(True) done")
            except Exception as e:
                log(f"fastExpandableHook: adapter update error: {e}")

        run_on_ui_thread(_update)

        # return the mutated list so PluginsController.settings cache stays consistent
        return setting_items

    except Exception as e:
        log(f"fastExpandableHook: _fast_reload error: {e}")
        return _original_call(param)


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
        log(f"fastExpandableHook: _patch_expandable error: {e}")


def _original_call(param):
    try:
        return param.method.invoke(param.thisObject, param.args)
    except Exception as e:
        log(f"fastExpandableHook: _original_call error: {e}")
        return None

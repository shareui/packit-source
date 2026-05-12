from android_utils import log, run_on_ui_thread
from client_utils import get_last_fragment


def report_plugin(plugin_info: dict, activity, repo_id: str = ""):
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else activity
        if not act:
            log("report_plugin: no activity")
            return
        name = str(plugin_info.get("name") or plugin_info.get("id") or "")
        rid = repo_id or str(plugin_info.get("repo_id") or "")
        from ....ui.reportDialog import show_report_dialog
        _name = name
        _rid = rid
        run_on_ui_thread(lambda: show_report_dialog(act, _name, _rid))
    except Exception as e:
        log(f"report_plugin: error: {e}")

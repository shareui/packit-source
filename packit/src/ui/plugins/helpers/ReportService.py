# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ....utils.Bulletins import factory as _pbf
from android_utils import run_on_ui_thread
from client_utils import get_last_fragment


def report_plugin(plugin_info: dict, activity, repo_id: str = ""):
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else activity
        if not act:
            logx("report_plugin: no activity", True)
            return
        name = str(plugin_info.get("name") or plugin_info.get("id") or "")
        # aggregated listings ("all repos") tag each plugin with _repo_id and
        # leave the fragment's own repo_id empty; without that fallback the
        # report settings lookup got an empty id and bailed out with
        # "missing field: forum_username"
        rid = repo_id or str(plugin_info.get("repo_id") or plugin_info.get("_repo_id") or "")
        pid = str(plugin_info.get("id") or "")

        from ...dialogs.ReportDialog import _load_report_settings
        from elyx import strings
        forum_username, topic_msg_id = _load_report_settings(rid)

        def _show_missing(field):
            try:
                from org.telegram.ui.Components import BulletinFactory
                decor = act.getWindow().getDecorView()
                msg = str(strings["report_dialog_missing_field"]).replace("{field}", field)
                _pbf(decor, None).createErrorBulletin(msg).show()
            except Exception as e:
                logx(f"report_plugin: bulletin error: {e}", False)

        if not forum_username:
            run_on_ui_thread(lambda: _show_missing("forum_username"))
            return

        if not topic_msg_id:
            run_on_ui_thread(lambda: _show_missing("topic_msg_id"))
            return

        from ...dialogs.ReportDialog import show_report_dialog
        _name = name
        _rid = rid
        _pid = pid
        run_on_ui_thread(lambda: show_report_dialog(act, _name, _rid, _pid))
    except Exception as e:
        logx(f"report_plugin: error: {e}", False)
# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ..utils.Bulletins import factory as _pbf
from android.view import View, MotionEvent
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics import Color
from android_utils import run_on_ui_thread
from android_utils import OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class
from java import dynamic_proxy
try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import BottomSheet, Theme failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


DEEPLINKS_DATA = {
    "dl_plugins_menu": {
        "title": strings.deeplinks_plugins_menu,
        "link": "tg://packit?install",
        "description": strings.deeplinks_plugins_menu_desc,
        "params": []
    },
    "dl_all_repos": {
        "title": strings.deeplinks_all_repositories,
        "link": "tg://packit?install",
        "description": strings.deeplinks_all_repositories_desc,
        "params": []
    },
    "dl_add_repo": {
        "title": strings.deeplinks_add_repository,
        "link": "tg://packit?repo=add",
        "description": strings.deeplinks_add_repository_desc,
        "params": [
            {"name": "name", "required": False, "desc": strings.param_name_desc},
            {"name": "link", "required": True, "desc": strings.param_link_desc},
            {"name": "icon", "required": False, "desc": strings.param_icon_desc}
        ]
    },
    "dl_specific_repo": {
        "title": strings.deeplinks_specific_repository,
        "link": "tg://packit?install&repo=<rm_rid>",
        "description": strings.deeplinks_specific_repository_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc}
        ]
    },
    "dl_plugin_profile": {
        "title": strings.get("deeplinks_plugin_profile", "Open plugin profile"),
        "link": "tg://packit?plugin=<plugin_id>&repo=<rm_rid>",
        "description": strings.get("deeplinks_plugin_profile_desc", "Opens the profile page of a specific plugin"),
        "params": [
            {"name": "plugin_id", "required": True, "desc": strings.param_plugin_id_desc},
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc}
        ]
    },
    "dl_specific_plugin": {
        "title": strings.deeplinks_install_plugin,
        "link": "tg://packit?install&repo=<rm_rid>&plugin=<plugin_id>",
        "description": strings.deeplinks_install_plugin_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc},
            {"name": "plugin_id", "required": True, "desc": strings.param_plugin_id_desc},
            {"name": "version", "required": False, "desc": strings.param_version_desc}
        ]
    },
    "dl_suggest_plugin": {
        "title": strings.deeplinks_suggest_plugin,
        "link": "tg://packit?suggestion=<rm_rid>",
        "description": strings.deeplinks_suggest_plugin_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc}
        ]
    },
    "dl_specific_icon_pack": {
        "title": strings.deeplinks_install_icon_pack,
        "link": "tg://packit?install&repo=<rm_rid>&icon=<icon_id>",
        "description": strings.deeplinks_install_icon_pack_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc},
            {"name": "icon_id", "required": True, "desc": strings.param_icon_id_desc}
        ]
    },
    "dl_update_all": {
        "title": strings.deeplinks_check_updates,
        "link": "tg://packit?update",
        "description": strings.deeplinks_update_all_desc,
        "params": []
    },
    "dl_update_repo": {
        "title": strings.deeplinks_check_updates_repo,
        "link": "tg://packit?update&repo=<rm_rid>",
        "description": strings.deeplinks_update_repository_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc}
        ]
    },
    "dl_settings": {
        "title": strings.deeplinks_settings,
        "link": "tg://packit?settings",
        "description": strings.deeplinks_settings_desc,
        "params": []
    },
    "dl_forum": {
        "title": strings.deeplinks_forum,
        "link": "tg://packit?forum",
        "description": strings.deeplinks_forum_desc,
        "params": []
    },
    "dl_problems": {
        "title": strings.deeplinks_possible_problems,
        "link": "tg://packit?problems",
        "description": strings.deeplinks_possible_problems_desc,
        "params": []
    },
    "dl_restart": {
        "title": strings.deeplinks_restart,
        "link": "tg://packit?pkill",
        "description": strings.deeplinks_restart_desc,
        "params": []
    },
    "dl_check": {
        "title": strings.get("deeplinks_check", "Check Status"),
        "link": "tg://packit",
        "description": strings.deeplinks_check_desc,
        "params": []
    },
    "dl_install_plugin": {
        "title": strings.deeplinks_install_plugin,
        "link": "tg://packit?install&repo=<rm_rid>&plugin=<plugin_id>",
        "description": strings.deeplinks_install_plugin_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc},
            {"name": "plugin_id", "required": True, "desc": strings.param_plugin_id_desc},
            {"name": "version", "required": False, "desc": strings.param_version_desc}
        ]
    },
    "dl_check_updates": {
        "title": strings.deeplinks_check_updates,
        "link": "tg://packit?update",
        "description": strings.deeplinks_update_all_desc,
        "params": []
    },
    "dl_check_updates_repo": {
        "title": strings.deeplinks_check_updates_repo,
        "link": "tg://packit?update&repo=<rm_rid>",
        "description": strings.deeplinks_check_updates_repo_desc,
        "params": [
            {"name": "rm_rid", "required": True, "desc": strings.param_rm_id_desc}
        ]
    },
    "dl_possible_problems": {
        "title": strings.deeplinks_possible_problems,
        "link": "tg://packit?problems",
        "description": strings.deeplinks_possible_problems_desc,
        "params": []
    }
}


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self, fn):
                super().__init__()
                self._fn = fn
            def onTouch(self, v, event):
                return self._fn(v, event)
        def _on_touch(v, event):
            try:
                action = event.getActionMasked()
                if action == MotionEvent.ACTION_DOWN:
                    v.animate().scaleX(0.94).scaleY(0.94).setDuration(100).start()
                elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
            except Exception:
                pass
            return False
        view.setOnTouchListener(_TouchListener(_on_touch))
    except Exception:
        pass


def show_deeplink_sheet(link_alias):
    fragment = get_last_fragment()
    if not fragment:
        return
    act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
    if not act:
        return

    def _show():
        try:
            is_dark_theme = False
            try:
                is_dark_theme = Theme.isCurrentThemeDark()
            except Exception:
                try:
                    bg_color = Theme.getColor(Theme.key_dialogBackground)
                    is_dark_theme = (bg_color & 0x00FFFFFF) < 0x00808080
                except Exception:
                    pass

            sheet = BottomSheet(act, False, fragment.getResourceProvider())

            for attr in ('setAllowNestedScroll', 'setResizeKeyboardArea', 'setUseSmoothKeyboard',
                         'setUseSmoothKeyboardTransition', 'setAnimateKeyboard'):
                try:
                    m = getattr(sheet, attr, None)
                    if m and attr in ('setUseSmoothKeyboard', 'setUseSmoothKeyboardTransition', 'setAnimateKeyboard'):
                        if hasattr(sheet, attr):
                            m(True)
                    elif m:
                        m(True)
                except Exception:
                    pass
            sheet.setApplyBottomPadding(False)
            sheet.setApplyTopPadding(False)

            root = LinearLayout(act)
            root.setOrientation(LinearLayout.VERTICAL)
            root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
            try:
                from android.graphics.drawable import GradientDrawable
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadius(AndroidUtilities.dp(20))
                bg.setColor(Theme.getColor(Theme.key_dialogBackground))
                root.setBackground(bg)
            except Exception:
                try:
                    root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                except Exception:
                    pass

            deeplink_info = DEEPLINKS_DATA.get(link_alias, {})
            title_text = deeplink_info.get("title", "Unknown Deeplink")
            link_text = deeplink_info.get("link", "")
            description_text = deeplink_info.get("description", "")
            params = deeplink_info.get("params", [])

            title = TextView(act)
            title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
            try:
                title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                title.setTypeface(AndroidUtilities.bold())
            title.setText(title_text)
            title.setGravity(Gravity.CENTER)
            root.addView(title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 8))

            link_container = LinearLayout(act)
            link_container.setBaselineAligned(False)
            link_container.setGravity(Gravity.CENTER_VERTICAL)
            link_container.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))

            try:
                base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
            except Exception:
                base_color = Theme.getColor(Theme.key_dialogTextBlue)
            
            try:
                link_bg = GradientDrawable()
                link_bg.setShape(GradientDrawable.RECTANGLE)
                link_bg.setCornerRadius(AndroidUtilities.dp(12))
                link_bg.setColor(0x00000000)
                link_bg.setStroke(AndroidUtilities.dp(2), base_color)
                link_container.setBackground(link_bg)
            except Exception:
                try:
                    link_container.setBackgroundColor(base_color)
                except Exception:
                    pass

            link_text_view = TextView(act)
            link_text_view.setText(link_text)
            link_text_view.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            link_text_view.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            link_text_view.setTypeface(AndroidUtilities.getTypeface("fonts/rttc.ttf"))

            copy_icon = ImageView(act)
            try:
                R_tg = find_class("org.telegram.messenger.R")
                icon_id = getattr(R_tg.drawable, "msg_copy", 0)
                copy_icon.setImageResource(icon_id)
                try:
                    copy_icon.setColorFilter(base_color)
                except Exception:
                    pass
            except Exception:
                pass

            def copy_link(v):
                try:
                    AndroidUtilities.addToClipboard(link_text)
                    try:
                        BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                        container = act.getWindow().getDecorView()
                        resource_provider = fragment.getResourceProvider()
                        R_tg = find_class("org.telegram.messenger.R")
                        _pbf(container, resource_provider).createSimpleBulletin(
                            getattr(R_tg.raw, "voip_invite", 0), 
                            strings.link_copied
                        ).show()
                    except Exception as e:
                        logx(f"Failed to show bulletin: {e}", False)
                except Exception as e:
                    logx(f"Failed to copy link: {e}", False)
            
            copy_icon.setOnClickListener(OnClickListener(copy_link))
            copy_icon.setClickable(True)
            copy_icon.setFocusable(True)
            _apply_press_scale(copy_icon)
            
            link_container.addView(link_text_view, LayoutHelper.createLinear(-2, -2, 1.0))
            link_container.addView(copy_icon, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 16, 0, 0, 0))
            
            root.addView(link_container, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 8))

            if description_text:
                desc = TextView(act)
                desc.setText(description_text)
                desc.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                desc.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                desc.setPadding(AndroidUtilities.dp(4), 0, AndroidUtilities.dp(4), 0)
                root.addView(desc, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 16))

            if params:
                params_title = TextView(act)
                params_title.setText(strings.get("deeplinks_parameters", "Parameters"))
                params_title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                params_title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                try:
                    params_title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    params_title.setTypeface(AndroidUtilities.bold())
                root.addView(params_title, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

                param_icons = {
                    "rm_rid": "msg_folders",
                    "plugin_id": "msg_saved",
                    "name": "msg_edit",
                    "link": "msg_link",
                    "icon": "msg_folders",
                    "icon_id": "msg_sticker",
                    "version": "menu_premium_clock_remix"
                }

                for param in params:
                    param_container = LinearLayout(act)
                    param_container.setOrientation(LinearLayout.HORIZONTAL)
                    param_container.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(8), AndroidUtilities.dp(16), AndroidUtilities.dp(8))
                    
                    try:
                        param_bg = GradientDrawable()
                        param_bg.setShape(GradientDrawable.RECTANGLE)
                        param_bg.setCornerRadius(AndroidUtilities.dp(12))
                        param_bg.setColor(0x00000000)
                        param_bg.setStroke(AndroidUtilities.dp(2), Theme.getColor(Theme.key_windowBackgroundGray))
                        param_container.setBackground(param_bg)
                    except Exception:
                        try:
                            param_container.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                        except Exception:
                            pass

                    param_icon = ImageView(act)
                    icon_name = param_icons.get(param["name"], "msg_folder")
                    try:
                        R_tg = find_class("org.telegram.messenger.R")
                        icon_id = getattr(R_tg.drawable, icon_name, 0)
                        param_icon.setImageResource(icon_id)
                        try:
                            param_icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                        except Exception:
                            pass
                    except Exception:
                        pass
                    
                    param_container.addView(param_icon, LayoutHelper.createLinear(32, 32, Gravity.CENTER_VERTICAL, 0, 0, 16, 0))
                    param_text_container = LinearLayout(act)
                    param_text_container.setOrientation(LinearLayout.VERTICAL)

                    param_name_container = LinearLayout(act)
                    param_name_container.setOrientation(LinearLayout.HORIZONTAL)
                    param_name_container.setGravity(Gravity.CENTER_VERTICAL)
                    
                    param_name = TextView(act)
                    param_name.setText(param["name"])
                    param_name.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                    param_name.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                    param_name.setTypeface(AndroidUtilities.bold())
                    
                    if param.get("required", False):
                        required_tag = TextView(act)
                        required_tag.setText(strings.get("required", "Required"))
                        required_tag.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
                        required_tag.setTextColor(Color.WHITE)
                        try:
                            required_bg = GradientDrawable()
                            required_bg.setShape(GradientDrawable.RECTANGLE)
                            required_bg.setCornerRadius(AndroidUtilities.dp(4))
                            required_bg.setColor(Theme.getColor(Theme.key_text_RedRegular))
                            required_tag.setBackground(required_bg)
                        except Exception:
                            pass
                        required_tag.setPadding(AndroidUtilities.dp(6), AndroidUtilities.dp(2), AndroidUtilities.dp(6), AndroidUtilities.dp(2))
                        param_name_container.addView(param_name, LayoutHelper.createLinear(-2, -2, 0, 0, 8, 0))
                        param_name_container.addView(required_tag, LayoutHelper.createLinear(-2, -2))
                    else:
                        param_name_container.addView(param_name, LayoutHelper.createLinear(-2, -2))
                    
                    param_text_container.addView(param_name_container, LayoutHelper.createLinear(-1, -2))
                    param_desc = TextView(act)
                    param_desc.setText(param["desc"])
                    param_desc.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    param_desc.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                    param_text_container.addView(param_desc, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))
                    param_container.addView(param_text_container, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))
                    
                    root.addView(param_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

            close_btn = FrameLayout(act)
            try:
                base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
            except Exception:
                base_color = Theme.getColor(Theme.key_dialogTextBlue)
            try:
                pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            except Exception:
                pressed_color = base_color
            close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(28), base_color, pressed_color
            ))
            close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
            close_btn.setClickable(True)
            close_btn.setFocusable(True)
            close_text = TextView(act)
            close_text.setText(strings.close_button)
            close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            close_text.setTypeface(AndroidUtilities.bold())
            close_text.setGravity(Gravity.CENTER)
            try:
                close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                close_text.setTextColor(Theme.getColor(Theme.key_dialogTextBlue))
            
            close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))
            close_btn.setOnClickListener(OnClickListener(lambda v: sheet.dismiss()))
            _apply_press_scale(close_btn)
            
            root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))
            sheet.setCustomView(root)
            try:
                from .ViewUtils import applyFontToTree
                applyFontToTree(root)
            except Exception:
                pass
            sheet.show()
            
        except Exception as e:
            logx(f"Error showing deeplink sheet: {e}", False)

    run_on_ui_thread(_show)
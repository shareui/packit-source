# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from android.view import View
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics import Color
from android_utils import run_on_ui_thread
from android_utils import OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class
try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import BottomSheet, Theme failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


def show_icon_repo_sheet(install_ui, repos, on_select=None):
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
            install_ui._setup_bottom_sheet(sheet)

            root = LinearLayout(act)
            root.setOrientation(LinearLayout.VERTICAL)
            root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
            try:
                root.setBackground(install_ui._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
            except Exception:
                try:
                    root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                except Exception:
                    pass

            title = TextView(act)
            title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
            try:
                title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                title.setTypeface(AndroidUtilities.bold())
            title.setText(strings["select_repository"])
            title.setGravity(Gravity.CENTER)
            root.addView(title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 8))

            content_frame = FrameLayout(act)
            root.addView(content_frame, LayoutHelper.createLinear(-1, 0, 1.0))

            scroll = ScrollView(act)
            scroll.setFillViewport(True)
            scroll.setVerticalScrollBarEnabled(False)
            try:
                scroll.setNestedScrollingEnabled(True)
            except Exception:
                pass

            items = LinearLayout(act)
            items.setOrientation(LinearLayout.VERTICAL)
            scroll.addView(items)

            divider_color = Theme.getColor(Theme.key_divider)

            def add_divider():
                d = View(act)
                d.setBackgroundColor(divider_color)
                items.addView(d, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 0, 16, 0))

            def make_repo_button(repo):
                btn = LinearLayout(act)
                btn.setOrientation(LinearLayout.HORIZONTAL)
                btn.setClickable(True)
                btn.setFocusable(True)
                btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(16), AndroidUtilities.dp(8))
                try:
                    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(8),
                        Theme.getColor(Theme.key_dialogBackground),
                        Theme.getColor(Theme.key_dialogBackgroundGray)
                    ))
                except Exception:
                    pass

                icon_iv = ImageView(act)
                icon_name = repo.get("icon", "msg_smile_status")
                try:
                    R = find_class("org.telegram.messenger.R")
                    icon_iv.setImageResource(getattr(R.drawable, icon_name))
                    icon_iv.setColorFilter(Color.BLACK if not is_dark_theme else Color.WHITE)
                except Exception:
                    pass
                icon_iv.setScaleType(ImageView.ScaleType.CENTER)
                icon_iv.setLayoutParams(LayoutHelper.createLinear(AndroidUtilities.dp(24), AndroidUtilities.dp(24), Gravity.CENTER_VERTICAL, 0, 0, 16, 0))

                text_container = LinearLayout(act)
                text_container.setOrientation(LinearLayout.VERTICAL)
                text_container.setLayoutParams(LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))

                name_tv = TextView(act)
                try:
                    name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    name_tv.setTypeface(AndroidUtilities.bold())
                name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                name_tv.setText(repo.get("name") or strings["unnamed"])
                name_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))

                url_tv = TextView(act)
                url_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                raw_url = str(repo.get("url", ""))
                owner, repo_name_str = install_ui._parse_github_url(raw_url) if hasattr(install_ui, "_parse_github_url") else (None, None)
                url_tv.setText(f"{owner} • {repo_name_str}" if owner and repo_name_str else raw_url)
                url_tv.setTextColor(Theme.getColor(Theme.key_dialogTextGray2))

                text_container.addView(name_tv)
                text_container.addView(url_tv, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))
                btn.addView(icon_iv)
                btn.addView(text_container)

                def on_click(v):
                    try:
                        sheet.dismiss()
                    except Exception:
                        pass
                    if on_select:
                        on_select(repo)
                    else:
                        install_ui._open_repo_icons(repo)

                btn.setOnClickListener(OnClickListener(lambda v: on_click(v)))
                install_ui._apply_press_scale(btn)
                return btn

            # all repos button
            all_btn = LinearLayout(act)
            all_btn.setOrientation(LinearLayout.HORIZONTAL)
            all_btn.setClickable(True)
            all_btn.setFocusable(True)
            all_btn.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(8), AndroidUtilities.dp(16), AndroidUtilities.dp(8))
            try:
                all_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(8),
                    Theme.getColor(Theme.key_dialogBackground),
                    Theme.getColor(Theme.key_dialogBackgroundGray)
                ))
            except Exception:
                pass

            all_icon = ImageView(act)
            try:
                R = find_class("org.telegram.messenger.R")
                all_icon.setImageResource(getattr(R.drawable, "msg_smile_status"))
                all_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
            except Exception:
                pass
            all_icon.setScaleType(ImageView.ScaleType.CENTER)
            all_icon.setLayoutParams(LayoutHelper.createLinear(AndroidUtilities.dp(24), AndroidUtilities.dp(24), Gravity.CENTER_VERTICAL, 0, 0, 16, 0))

            all_text_container = LinearLayout(act)
            all_text_container.setOrientation(LinearLayout.VERTICAL)
            all_text_container.setLayoutParams(LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))

            all_name = TextView(act)
            all_name.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            all_name.setText(strings["all_repositories"])
            all_name.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            all_name.setTypeface(AndroidUtilities.bold())

            all_url = TextView(act)
            all_url.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            all_url.setText(strings["search_all_repositories"])
            all_url.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))

            all_text_container.addView(all_name)
            all_text_container.addView(all_url, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))
            all_btn.addView(all_icon)
            all_btn.addView(all_text_container)

            def on_all_click(v):
                try:
                    sheet.dismiss()
                except Exception:
                    pass
                if on_select:
                    on_select("all")
                else:
                    install_ui._open_all_repos_icons()

            all_btn.setOnClickListener(OnClickListener(lambda v: on_all_click(v)))
            install_ui._apply_press_scale(all_btn)
            items.addView(all_btn, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 16, 2, 16, 2))
            add_divider()

            for i, repo in enumerate(repos):
                if i != 0:
                    add_divider()
                items.addView(make_repo_button(repo), LayoutHelper.createFrame(-1, -2, Gravity.TOP, 16, 2, 16, 2))

            content_frame.addView(scroll, FrameLayout.LayoutParams(-1, -1))

            close_btn = install_ui._create_close_button(act)
            close_btn.setOnClickListener(OnClickListener(lambda v: sheet.dismiss()))
            install_ui._apply_press_scale(close_btn)
            root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

            sheet.setCustomView(root)
            try:
                from ..components.ViewUtils import applyFontToTree
                applyFontToTree(root)
            except Exception:
                pass
            sheet.show()
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"icon repo sheet error: {e}", False)

    run_on_ui_thread(_show)
# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android.view import View
from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics import Color
from android.graphics.drawable import GradientDrawable
from android_utils import log
from android_utils import OnClickListener
from client_utils import get_last_fragment
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import BottomSheet, Theme failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()

_SORT_ICONS = {
    "alpha_az": "msg_archive",
    "alpha_za": "msg_unarchive",
    "authors": "msg_online",
}


def show_icon_sort_menu(install_ui, act, current_sort_type, on_sort_selected):
    try:
        sort_sheet = BottomSheet(act, False, get_last_fragment().getResourceProvider())
        sort_sheet.setApplyBottomPadding(False)
        sort_sheet.setApplyTopPadding(False)

        sort_root = LinearLayout(act)
        sort_root.setOrientation(LinearLayout.VERTICAL)
        sort_root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            sort_root.setBackground(install_ui._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                sort_root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass

        sort_title = TextView(act)
        sort_title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        sort_title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            sort_title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            sort_title.setTypeface(AndroidUtilities.bold())
        sort_title.setText(strings["sort_title_icons"])
        sort_title.setGravity(Gravity.CENTER)
        sort_root.addView(sort_title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 16))

        def create_sort_option(text, sort_type):
            option = LinearLayout(act)
            option.setOrientation(LinearLayout.HORIZONTAL)
            option.setGravity(Gravity.CENTER_VERTICAL)
            option.setClickable(True)
            option.setFocusable(True)
            option.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
            is_current = (sort_type == current_sort_type)
            use_classic_design = settings.get("old_sort_menu_design", False)

            try:
                if is_current and use_classic_design:
                    option.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(8),
                        Theme.getColor(Theme.key_featuredStickers_addButton),
                        Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
                    ))
                else:
                    option.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(8),
                        Theme.getColor(Theme.key_dialogBackground),
                        Theme.getColor(Theme.key_dialogBackgroundGray)
                    ))
            except Exception:
                try:
                    option.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector)))
                except Exception:
                    pass

            option_text = TextView(act)
            option_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            option_text.setText(text)
            if is_current and use_classic_design:
                option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            elif is_current and not use_classic_design:
                option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            else:
                option_text.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))

            option_layout = LinearLayout(act)
            option_layout.setOrientation(LinearLayout.HORIZONTAL)
            option_layout.setGravity(Gravity.CENTER_VERTICAL)

            if not use_classic_design:
                radio_circle = FrameLayout(act)
                radio_size = AndroidUtilities.dp(20)
                radio_params = LinearLayout.LayoutParams(radio_size, radio_size)
                radio_params.rightMargin = AndroidUtilities.dp(12)

                accent_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                bg_color = Theme.getColor(Theme.key_dialogBackground)
                gray_color = Theme.getColor(Theme.key_dialogTextGray2)

                if is_current:
                    outer_ring = GradientDrawable()
                    outer_ring.setShape(GradientDrawable.OVAL)
                    outer_ring.setColor(accent_color)
                    radio_circle.setBackground(outer_ring)

                    middle_ring = View(act)
                    middle_size = AndroidUtilities.dp(16)
                    middle_bg = GradientDrawable()
                    middle_bg.setShape(GradientDrawable.OVAL)
                    middle_bg.setColor(bg_color)
                    middle_ring.setBackground(middle_bg)
                    radio_circle.addView(middle_ring, FrameLayout.LayoutParams(middle_size, middle_size, Gravity.CENTER))

                    inner_dot = View(act)
                    inner_size = AndroidUtilities.dp(10)
                    inner_bg = GradientDrawable()
                    inner_bg.setShape(GradientDrawable.OVAL)
                    inner_bg.setColor(accent_color)
                    inner_dot.setBackground(inner_bg)
                    radio_circle.addView(inner_dot, FrameLayout.LayoutParams(inner_size, inner_size, Gravity.CENTER))
                else:
                    circle_bg = GradientDrawable()
                    circle_bg.setShape(GradientDrawable.OVAL)
                    circle_bg.setColor(bg_color)
                    circle_bg.setStroke(AndroidUtilities.dp(2), gray_color)
                    radio_circle.setBackground(circle_bg)

                option_layout.addView(radio_circle, radio_params)

            icon = ImageView(act)
            icon_name = _SORT_ICONS.get(sort_type)
            icon_id = install_ui._resolve_icon(icon_name) if icon_name else None
            if icon_id:
                icon.setImageResource(icon_id)
                try:
                    if is_current and use_classic_design:
                        icon.setColorFilter(Color.WHITE)
                    elif is_current and not use_classic_design:
                        icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                    else:
                        icon.setColorFilter(Theme.getColor(Theme.key_dialogTextGray2))
                except Exception:
                    pass
                icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                icon_lp.rightMargin = AndroidUtilities.dp(16)
                option_layout.addView(icon, icon_lp)

            option_layout.addView(option_text, LayoutHelper.createLinear(-1, -2))
            option.addView(option_layout, LayoutHelper.createLinear(-1, -2))

            def on_option_click(v, st=sort_type):
                try:
                    sort_sheet.dismiss()
                    on_sort_selected(st)
                except Exception:
                    pass

            option.setOnClickListener(OnClickListener(on_option_click))
            install_ui._apply_press_scale(option)
            return option

        def add_divider():
            d = View(act)
            d.setBackgroundColor(Theme.getColor(Theme.key_divider))
            sort_root.addView(d, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))

        sort_root.addView(create_sort_option(strings["sort_alpha_az"], "alpha_az"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
        add_divider()
        sort_root.addView(create_sort_option(strings["sort_alpha_za"], "alpha_za"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
        add_divider()
        sort_root.addView(create_sort_option(strings["sort_by_authors"], "authors"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))

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
        close_text.setText(strings["close_button"])
        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_text.setTypeface(AndroidUtilities.bold())
        close_text.setGravity(Gravity.CENTER)
        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))
        close_btn.setOnClickListener(OnClickListener(lambda v: sort_sheet.dismiss()))
        install_ui._apply_press_scale(close_btn)
        sort_root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        sort_sheet.setCustomView(sort_root)
        sort_sheet.show()
    except Exception as e:
        log(f"icon sort menu error: {e}")
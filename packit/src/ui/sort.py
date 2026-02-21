from android.view import View
from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics import Color
from android.graphics.drawable import GradientDrawable
from android_utils import log
from android_utils import OnClickListener
from client_utils import get_last_fragment
from elyx import settings
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper
from org.telegram.messenger import AndroidUtilities


def show_sort_menu(install_ui, act, current_sort_type, build_list_with_sort):
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
        sort_title.setText("Sort Plugins")
        sort_title.setGravity(Gravity.CENTER)
        sort_root.addView(sort_title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 16))

        def resolve_icon(name):
            return install_ui._resolve_icon(name)

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
            if is_current and not use_classic_design:
                check_circle = FrameLayout(act)
                check_circle_size = AndroidUtilities.dp(20)
                check_circle_params = LinearLayout.LayoutParams(check_circle_size, check_circle_size)
                check_circle_params.rightMargin = AndroidUtilities.dp(12)
                circle_bg = GradientDrawable()
                circle_bg.setShape(GradientDrawable.OVAL)
                circle_bg.setColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                circle_bg.setStroke(AndroidUtilities.dp(1), Color.WHITE)
                check_circle.setBackground(circle_bg)
                dot = View(act)
                dot_size = AndroidUtilities.dp(8)
                dot_bg = GradientDrawable()
                dot_bg.setShape(GradientDrawable.OVAL)
                dot_bg.setColor(Color.WHITE)
                dot.setBackground(dot_bg)
                check_circle.addView(dot, FrameLayout.LayoutParams(dot_size, dot_size, Gravity.CENTER))
                option_layout.addView(check_circle, check_circle_params)
            elif not use_classic_design:
                empty_space = View(act)
                empty_space_params = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                empty_space_params.rightMargin = AndroidUtilities.dp(12)
                option_layout.addView(empty_space, empty_space_params)

            icon = ImageView(act)
            icon_id = None
            if "A-Z" in text:
                icon_id = resolve_icon("msg_archive")
            elif "Z-A" in text:
                icon_id = resolve_icon("msg_unarchive")
            elif "Authors" in text:
                icon_id = resolve_icon("msg_online")
            elif "Repository" in text:
                icon_id = resolve_icon("menu_album_add")

            if icon_id:
                icon.setImageResource(icon_id)
                try:
                    if is_current and not use_classic_design:
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

            def on_option_click(v):
                try:
                    sort_sheet.dismiss()
                    build_list_with_sort(sort_type)
                except Exception:
                    pass

            option.setOnClickListener(OnClickListener(lambda v: on_option_click(v)))
            install_ui._apply_press_scale(option)
            return option

        sort_root.addView(create_sort_option("Alphabetically A-Z", "alpha_az"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
        divider = View(act)
        divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
        sort_root.addView(divider, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
        sort_root.addView(create_sort_option("Alphabetically Z-A", "alpha_za"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
        divider3 = View(act)
        divider3.setBackgroundColor(Theme.getColor(Theme.key_divider))
        sort_root.addView(divider3, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
        sort_root.addView(create_sort_option("As in Repository", "repo_order"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
        divider2 = View(act)
        divider2.setBackgroundColor(Theme.getColor(Theme.key_divider))
        sort_root.addView(divider2, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
        sort_root.addView(create_sort_option("By Authors (A-Z)", "authors"), LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))
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
            AndroidUtilities.dp(28),
            base_color,
            pressed_color
        ))
        close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_text = TextView(act)
        close_text.setText("Close")
        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_text.setTypeface(AndroidUtilities.bold())
        close_text.setGravity(Gravity.CENTER)
        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))

        def on_close_sort(v):
            try:
                sort_sheet.dismiss()
            except Exception:
                pass

        close_btn.setOnClickListener(OnClickListener(lambda v: on_close_sort(v)))
        install_ui._apply_press_scale(close_btn)
        sort_root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        sort_sheet.setCustomView(sort_root)
        sort_sheet.show()
    except Exception as e:
        log(f"sort: sort menu error: {e}")
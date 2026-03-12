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
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import BottomSheet, Theme failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities failed: {e}")
    from ...other.importFailed import showImportFailedAlert as _sifa; _sifa()


def show_tag_filter_menu(install_ui, act, plugins, selected_tags, on_tags_selected, on_save):
    try:
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

        if not tags_summary:
            log("No tags found in plugins")
            return

        tag_sheet = BottomSheet(act, False, get_last_fragment().getResourceProvider())
        tag_sheet.setApplyBottomPadding(False)
        tag_sheet.setApplyTopPadding(False)
        tag_root = LinearLayout(act)
        tag_root.setOrientation(LinearLayout.VERTICAL)
        tag_root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            tag_root.setBackground(install_ui._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                tag_root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass
        tag_title = TextView(act)
        tag_title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        tag_title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            tag_title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            tag_title.setTypeface(AndroidUtilities.bold())
        tag_title.setText(strings["plugin_tags"])
        tag_title.setGravity(Gravity.CENTER)
        tag_root.addView(tag_title, LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 16))

        tag_options = {}
        current_selected = set(selected_tags) if selected_tags else set()

        if not current_selected:
            current_selected = set(tags_summary.keys())

        show_tag_filter_menu.current_selected = current_selected
        tag_items = list(tags_summary.items())
        for i, (tag_name, count) in enumerate(tag_items):
            tag_option = create_tag_option(install_ui, act, tag_name, count, tag_name in current_selected)
            tag_options[tag_name] = tag_option
            tag_root.addView(tag_option, LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))

            if i < len(tag_items) - 1:
                divider = View(act)
                divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
                tag_root.addView(divider, LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))

        save_btn = FrameLayout(act)
        try:
            base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception:
            base_color = Theme.getColor(Theme.key_dialogTextBlue)
        try:
            pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            pressed_color = base_color
        save_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28),
            base_color,
            pressed_color
        ))
        save_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        save_btn.setClickable(True)
        save_btn.setFocusable(True)
        save_text = TextView(act)
        save_text.setText(strings.get("save_button", "Save"))
        save_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        save_text.setTypeface(AndroidUtilities.bold())
        save_text.setGravity(Gravity.CENTER)
        save_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        save_btn.addView(save_text, FrameLayout.LayoutParams(-1, -2))

        def on_save_click(v):
            try:
                on_tags_selected(show_tag_filter_menu.current_selected)
                tag_sheet.dismiss()
                on_save()
            except Exception:
                pass

        def on_tag_click(tag_name):
            def handler(v):
                try:
                    if tag_name in show_tag_filter_menu.current_selected:
                        show_tag_filter_menu.current_selected.remove(tag_name)
                    else:
                        show_tag_filter_menu.current_selected.add(tag_name)
                    tag_option = tag_options[tag_name]
                    update_tag_option(install_ui, tag_option, tag_name, count, tag_name in show_tag_filter_menu.current_selected)
                except Exception as e:
                    log(f"Tag click error: {e}")
            return handler

        for tag_name, tag_option in tag_options.items():
            tag_option.setOnClickListener(OnClickListener(on_tag_click(tag_name)))
            install_ui._apply_press_scale(tag_option)

        save_btn.setOnClickListener(OnClickListener(lambda v: on_save_click(v)))
        install_ui._apply_press_scale(save_btn)
        tag_root.addView(save_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        tag_sheet.setCustomView(tag_root)
        tag_sheet.show()
    except Exception as e:
        log(f"tag filter menu error: {e}")


def create_tag_option(install_ui, act, tag_name, count, is_selected):
    try:
        option = LinearLayout(act)
        option.setOrientation(LinearLayout.HORIZONTAL)
        option.setGravity(Gravity.CENTER_VERTICAL)
        option.setClickable(True)
        option.setFocusable(True)
        option.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
        
        use_classic_design = settings.get("old_sort_menu_design", False)

        try:
            if is_selected and use_classic_design:
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
        option_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        option_text.setText(tag_name)
        if is_selected and use_classic_design:
            option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        elif is_selected and not use_classic_design:
            option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
        else:
            option_text.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        
        option_layout = LinearLayout(act)
        option_layout.setOrientation(LinearLayout.HORIZONTAL)
        option_layout.setGravity(Gravity.CENTER_VERTICAL)
        
        if is_selected and not use_classic_design:
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

        count_circle = FrameLayout(act)
        count_circle_size = AndroidUtilities.dp(24) if use_classic_design else AndroidUtilities.dp(20)
        count_circle_params = LinearLayout.LayoutParams(count_circle_size, count_circle_size)
        count_circle_params.rightMargin = AndroidUtilities.dp(20) if use_classic_design else AndroidUtilities.dp(16)
        
        if is_selected and use_classic_design:
            count_bg = GradientDrawable()
            count_bg.setShape(GradientDrawable.OVAL)
            count_bg.setColor(Color.WHITE)
            count_bg.setStroke(AndroidUtilities.dp(1), Theme.getColor(Theme.key_dialogTextGray2))
            count_circle.setBackground(count_bg)
            count_text = TextView(act)
            count_text.setText(str(count))
            count_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            count_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            count_text.setGravity(Gravity.CENTER)
        else:
            count_bg = GradientDrawable()
            count_bg.setShape(GradientDrawable.OVAL)
            count_bg.setColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            count_circle.setBackground(count_bg)
            count_text = TextView(act)
            count_text.setText(str(count))
            count_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            count_text.setTextColor(Color.WHITE)
            count_text.setGravity(Gravity.CENTER)
        
        count_circle.addView(count_text, FrameLayout.LayoutParams(-1, -1, Gravity.CENTER))
        option_layout.addView(count_circle, count_circle_params)

        option_layout.addView(option_text, LayoutHelper.createLinear(-1, -2))
        option.addView(option_layout, LayoutHelper.createLinear(-1, -2))

        return option
    except Exception as e:
        log(f"create_tag_option error: {e}")
        return View(act)


def update_tag_option(install_ui, option, tag_name, count, is_selected):
    try:
        use_classic_design = settings.get("old_sort_menu_design", False)

        try:
            if is_selected and use_classic_design:
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
            pass

        if option.getChildCount() > 0:
            option_layout = option.getChildAt(0)
            if isinstance(option_layout, LinearLayout):
                if not use_classic_design:

                    if option_layout.getChildCount() > 0:
                        option_layout.removeViewAt(0)

                    if is_selected:
                        check_circle = FrameLayout(option.getContext())
                        check_circle_size = AndroidUtilities.dp(20)
                        check_circle_params = LinearLayout.LayoutParams(check_circle_size, check_circle_size)
                        check_circle_params.rightMargin = AndroidUtilities.dp(12)
                        circle_bg = GradientDrawable()
                        circle_bg.setShape(GradientDrawable.OVAL)
                        circle_bg.setColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                        circle_bg.setStroke(AndroidUtilities.dp(1), Color.WHITE)
                        check_circle.setBackground(circle_bg)
                        dot = View(option.getContext())
                        dot_size = AndroidUtilities.dp(8)
                        dot_bg = GradientDrawable()
                        dot_bg.setShape(GradientDrawable.OVAL)
                        dot_bg.setColor(Color.WHITE)
                        dot.setBackground(dot_bg)
                        check_circle.addView(dot, FrameLayout.LayoutParams(dot_size, dot_size, Gravity.CENTER))
                        option_layout.addView(check_circle, 0, check_circle_params)
                    else:
                        empty_space = View(option.getContext())
                        empty_space_params = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                        empty_space_params.rightMargin = AndroidUtilities.dp(12)
                        option_layout.addView(empty_space, 0, empty_space_params)

                count_circle_index = 1 if not use_classic_design else 0
                if option_layout.getChildCount() > count_circle_index:
                    count_circle = option_layout.getChildAt(count_circle_index)
                    if isinstance(count_circle, FrameLayout) and count_circle.getChildCount() > 0:
                        count_text = count_circle.getChildAt(0)
                        if isinstance(count_text, TextView):
                            count_text.setText(str(count))

                            if is_selected and use_classic_design:
                                count_bg = GradientDrawable()
                                count_bg.setShape(GradientDrawable.OVAL)
                                count_bg.setColor(Color.WHITE)
                                count_bg.setStroke(AndroidUtilities.dp(1), Theme.getColor(Theme.key_dialogTextGray2))
                                count_circle.setBackground(count_bg)
                                count_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))

                                count_circle_size = AndroidUtilities.dp(24)
                                count_circle_params = LinearLayout.LayoutParams(count_circle_size, count_circle_size)
                                count_circle_params.rightMargin = AndroidUtilities.dp(20)
                                count_circle.setLayoutParams(count_circle_params)
                            else:
                                count_bg = GradientDrawable()
                                count_bg.setShape(GradientDrawable.OVAL)
                                count_bg.setColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                                count_circle.setBackground(count_bg)
                                count_text.setTextColor(Color.WHITE)

                                count_circle_size = AndroidUtilities.dp(20)
                                count_circle_params = LinearLayout.LayoutParams(count_circle_size, count_circle_size)
                                count_circle_params.rightMargin = AndroidUtilities.dp(16)
                                count_circle.setLayoutParams(count_circle_params)

                text_index = 2 if not use_classic_design else 1
                if option_layout.getChildCount() > text_index:
                    option_text = option_layout.getChildAt(text_index)
                    if isinstance(option_text, TextView):
                        option_text.setText(tag_name)
                        if is_selected and use_classic_design:
                            option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
                        elif is_selected and not use_classic_design:
                            option_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                        else:
                            option_text.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception as e:
        log(f"update_tag_option error: {e}")
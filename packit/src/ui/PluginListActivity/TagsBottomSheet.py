# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android.view import View
from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics import Color
from android.graphics.drawable import GradientDrawable
from android.text import TextUtils
from android_utils import log
from android_utils import OnClickListener
from client_utils import get_last_fragment
from .service import filterEngine
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


def show_tag_filter_menu(install_ui, act, plugins, selected_tags, on_tags_selected, on_save):
    try:
        tags_summary = filterEngine.collect_tags(plugins)

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
        
        tags_container = LinearLayout(act)
        tags_container.setOrientation(LinearLayout.VERTICAL)
        tags_container.setPadding(AndroidUtilities.dp(0), AndroidUtilities.dp(8), AndroidUtilities.dp(0), AndroidUtilities.dp(8))
        
        tag_items = list(tags_summary.items())
        current_row = None
        current_row_items = []
        
        def create_new_row():
            nonlocal current_row, current_row_items
            current_row = LinearLayout(act)
            current_row.setOrientation(LinearLayout.HORIZONTAL)
            current_row.setGravity(Gravity.CENTER)
            tags_container.addView(current_row, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 4))
            current_row_items = []
        
        def check_row_space(tag_name):
            if not current_row or len(current_row_items) >= 3:
                return True
            if len(current_row_items) == 2:
                return False
            return True
        
        create_new_row()
        
        for tag_name, count in tag_items:
            if not check_row_space(tag_name):
                create_new_row()
            
            tag_option = create_tag_tile(install_ui, act, tag_name, count, tag_name in current_selected)
            tag_options[tag_name] = tag_option
            current_row.addView(tag_option, LayoutHelper.createLinear(-2, -2, 1.0, 0, 8, 0))
            current_row_items.append(tag_name)
        
        tag_root.addView(tags_container, LayoutHelper.createLinear(-1, -2))

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
        save_text.setText(strings["save_button"])
        save_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        save_text.setTypeface(AndroidUtilities.bold())
        save_text.setGravity(Gravity.CENTER)
        save_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        save_btn.addView(save_text, FrameLayout.LayoutParams(-1, -2))

        def on_save_click(v):
            try:
                if not show_tag_filter_menu.current_selected:
                    return
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
                    update_tag_tile(install_ui, tag_option, tag_name, tags_summary[tag_name], tag_name in show_tag_filter_menu.current_selected)
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
        try:
            from ..viewUtils import applyFontToTree
            applyFontToTree(tag_root)
        except Exception:
            pass
        tag_sheet.show()
    except Exception as e:
        log(f"tag filter menu error: {e}")


def create_tag_tile(install_ui, act, tag_name, count, is_selected):
    try:
        tile = FrameLayout(act)
        tile.setClickable(True)
        tile.setFocusable(True)
        tile.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))
        
        main_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        
        if is_selected:
            tile_bg = GradientDrawable()
            tile_bg.setShape(GradientDrawable.RECTANGLE)
            tile_bg.setCornerRadius(AndroidUtilities.dp(16))
            tile_bg.setColor(main_color)
            tile.setBackground(tile_bg)
            
            text_color = Color.WHITE
            count_bg_color = Color.WHITE
            count_text_color = main_color
        else:
            import ctypes
            r = (main_color >> 16) & 0xFF
            g = (main_color >> 8) & 0xFF
            b = main_color & 0xFF
            transparent_color = ctypes.c_int32((0x15 << 24) | (r << 16) | (g << 8) | b).value
            
            tile_bg = GradientDrawable()
            tile_bg.setShape(GradientDrawable.RECTANGLE)
            tile_bg.setCornerRadius(AndroidUtilities.dp(16))
            tile_bg.setColor(transparent_color)
            tile_bg.setStroke(AndroidUtilities.dp(1), main_color)
            tile.setBackground(tile_bg)
            
            text_color = main_color
            count_bg_color = main_color
            count_text_color = Color.WHITE
        
        content_layout = LinearLayout(act)
        content_layout.setOrientation(LinearLayout.HORIZONTAL)
        content_layout.setGravity(Gravity.CENTER_VERTICAL)
        content_layout.setPadding(AndroidUtilities.dp(0), AndroidUtilities.dp(0), AndroidUtilities.dp(0), AndroidUtilities.dp(0))
        
        tag_text = TextView(act)
        tag_text.setText(tag_name)
        tag_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        tag_text.setTypeface(AndroidUtilities.bold())
        tag_text.setTextColor(text_color)
        tag_text.setGravity(Gravity.CENTER_VERTICAL)
        tag_text.setSingleLine(True)
        tag_text.setEllipsize(TextUtils.TruncateAt.END)
        
        count_circle = FrameLayout(act)
        count_size = AndroidUtilities.dp(22)
        count_params = LinearLayout.LayoutParams(count_size, count_size)
        count_params.setMargins(AndroidUtilities.dp(8), 0, 0, 0)
        
        count_bg = GradientDrawable()
        count_bg.setShape(GradientDrawable.OVAL)
        count_bg.setColor(count_bg_color)
        count_circle.setBackground(count_bg)
        
        count_text = TextView(act)
        count_text.setText(str(count))
        count_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        count_text.setTextColor(count_text_color)
        count_text.setGravity(Gravity.CENTER)
        count_text.setTypeface(AndroidUtilities.bold())
        
        count_circle.addView(count_text, FrameLayout.LayoutParams(-1, -1, Gravity.CENTER))
        
        content_layout.addView(tag_text, LayoutHelper.createLinear(-2, -2, 1.0))
        content_layout.addView(count_circle, count_params)
        
        tile.addView(content_layout, FrameLayout.LayoutParams(-2, -2))
        
        return tile
    except Exception as e:
        log(f"create_tag_tile error: {e}")
        return View(act)


def update_tag_tile(install_ui, tile, tag_name, count, is_selected):
    try:
        main_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        
        if is_selected:
            tile_bg = GradientDrawable()
            tile_bg.setShape(GradientDrawable.RECTANGLE)
            tile_bg.setCornerRadius(AndroidUtilities.dp(16))
            tile_bg.setColor(main_color)
            tile.setBackground(tile_bg)
            
            text_color = Color.WHITE
            count_bg_color = Color.WHITE
            count_text_color = main_color
        else:
            import ctypes
            r = (main_color >> 16) & 0xFF
            g = (main_color >> 8) & 0xFF
            b = main_color & 0xFF
            transparent_color = ctypes.c_int32((0x15 << 24) | (r << 16) | (g << 8) | b).value
            
            tile_bg = GradientDrawable()
            tile_bg.setShape(GradientDrawable.RECTANGLE)
            tile_bg.setCornerRadius(AndroidUtilities.dp(16))
            tile_bg.setColor(transparent_color)
            tile_bg.setStroke(AndroidUtilities.dp(1), main_color)
            tile.setBackground(tile_bg)
            
            text_color = main_color
            count_bg_color = main_color
            count_text_color = Color.WHITE
        
        if tile.getChildCount() > 0:
            content_layout = tile.getChildAt(0)
            if isinstance(content_layout, LinearLayout) and content_layout.getChildCount() >= 2:
                tag_text = content_layout.getChildAt(0)
                count_circle = content_layout.getChildAt(1)
                
                if isinstance(tag_text, TextView):
                    tag_text.setText(tag_name)
                    tag_text.setTextColor(text_color)
                    tag_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
                
                if isinstance(count_circle, FrameLayout) and count_circle.getChildCount() > 0:
                    count_text = count_circle.getChildAt(0)
                    if isinstance(count_text, TextView):
                        count_text.setText(str(count))
                        count_text.setTextColor(count_text_color)
                        count_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
                    
                    count_bg = GradientDrawable()
                    count_bg.setShape(GradientDrawable.OVAL)
                    count_bg.setColor(count_bg_color)
                    count_circle.setBackground(count_bg)
                    
                    count_params = LinearLayout.LayoutParams(AndroidUtilities.dp(22), AndroidUtilities.dp(22))
                    count_params.setMargins(AndroidUtilities.dp(8), 0, 0, 0)
                    count_circle.setLayoutParams(count_params)
    except Exception as e:
        log(f"update_tag_tile error: {e}")
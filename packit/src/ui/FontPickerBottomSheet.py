import ctypes
from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.view import View, Gravity
from android.graphics import Color
from android.graphics.drawable import GradientDrawable
from android.util import TypedValue
from android_utils import log, OnClickListener

try:
    from elyx import strings
except Exception as e:
    log(f"FontPickerBottomSheet: import elyx failed: {e}")
    strings = None

try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    log(f"FontPickerBottomSheet: import BottomSheet/Theme failed: {e}")
    BottomSheet = None
    Theme = None

try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    log(f"FontPickerBottomSheet: import LayoutHelper failed: {e}")
    LayoutHelper = None

try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    log(f"FontPickerBottomSheet: import AndroidUtilities failed: {e}")
    AndroidUtilities = None

from .FontManager import listFontFiles, setFont, getSelectedFilename
from java import dynamic_proxy
from android.view import MotionEvent

_COLOR_WHITE = ctypes.c_int32(0xFFFFFFFF).value


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self):
                super().__init__()
            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.93).scaleY(0.93).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                except Exception:
                    pass
                return False
        view.setOnTouchListener(_TouchListener())
    except Exception:
        pass


def _str(key, fallback):
    try:
        return str(strings[key])
    except Exception:
        return fallback


def _groupFonts(filenames):
    # groups ["Quicksand-Bold.ttf", ...] -> {"Quicksand": [("Bold", "Quicksand-Bold.ttf"), ...]}
    # files with no dash: family=name, style="Regular"
    groups = {}
    for filename in filenames:
        name = filename
        if name.lower().endswith(".ttf"):
            name = name[:-4]
        if "-" in name:
            parts = name.split("-", 1)
            family = parts[0]
            style = parts[1].replace("-", " ")
        else:
            family = name
            style = "Regular"
        if family not in groups:
            groups[family] = []
        groups[family].append((style, filename))
    return groups


def _createRoundedBg(color):
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadii([
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        0, 0, 0, 0
    ])
    bg.setColor(color)
    return bg


def _createDivider(act):
    divider = View(act)
    try:
        divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
    except Exception:
        pass
    return divider


def _createCloseButton(act, on_click):
    btn = FrameLayout(act)
    try:
        base = Theme.getColor(Theme.key_featuredStickers_addButton)
        pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
    except Exception:
        base = ctypes.c_int32(0xFF2AABEE).value
        pressed = base
    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
        AndroidUtilities.dp(28), base, pressed
    ))
    btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
    btn.setClickable(True)
    btn.setFocusable(True)
    tv = TextView(act)
    tv.setText(_str("close_button", "Close"))
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    tv.setGravity(Gravity.CENTER)
    try:
        tv.setTypeface(AndroidUtilities.bold())
        tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    except Exception:
        pass
    btn.addView(tv, FrameLayout.LayoutParams(-1, -2))
    _apply_press_scale(btn)
    btn.setOnClickListener(OnClickListener(lambda v: on_click()))
    return btn


def _createSheetRoot(act):
    root = LinearLayout(act)
    root.setOrientation(LinearLayout.VERTICAL)
    root.setPadding(
        AndroidUtilities.dp(20), AndroidUtilities.dp(16),
        AndroidUtilities.dp(20), AndroidUtilities.dp(8)
    )
    try:
        root.setBackground(_createRoundedBg(Theme.getColor(Theme.key_dialogBackground)))
    except Exception:
        pass
    return root


def _createTitleBlock(act, title, subtitle=None):
    # returns a vertical LinearLayout with title + optional subtitle
    block = LinearLayout(act)
    block.setOrientation(LinearLayout.VERTICAL)
    block.setGravity(Gravity.CENTER)

    title_tv = TextView(act)
    title_tv.setText(title)
    title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
    title_tv.setGravity(Gravity.CENTER)
    try:
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title_tv.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    block.addView(title_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER))

    if subtitle:
        sub_tv = TextView(act)
        sub_tv.setText(subtitle)
        sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        sub_tv.setGravity(Gravity.CENTER)
        try:
            sub_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        block.addView(sub_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER, 0, 2, 0, 0))

    return block


def _resolveIcon(name):
    try:
        from hook_utils import find_class
        R = find_class("org.telegram.messenger.R")
        return getattr(R.drawable, name)
    except Exception:
        return None


def _createRadioIndicator(act, is_selected):
    indicator = FrameLayout(act)
    circle = GradientDrawable()
    circle.setShape(GradientDrawable.OVAL)
    if is_selected:
        try:
            circle.setColor(Theme.getColor(Theme.key_featuredStickers_addButton))
        except Exception:
            circle.setColor(ctypes.c_int32(0xFF2AABEE).value)
        dot = View(act)
        dot_bg = GradientDrawable()
        dot_bg.setShape(GradientDrawable.OVAL)
        dot_bg.setColor(_COLOR_WHITE)
        dot.setBackground(dot_bg)
        indicator.addView(dot, FrameLayout.LayoutParams(
            AndroidUtilities.dp(8), AndroidUtilities.dp(8), Gravity.CENTER
        ))
    else:
        circle.setColor(Color.TRANSPARENT)
        try:
            circle.setStroke(AndroidUtilities.dp(2), Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            circle.setStroke(AndroidUtilities.dp(2), ctypes.c_int32(0xFF888888).value)
    indicator.setBackground(circle)
    return indicator


def _loadTypefaceForFile(filename):
    # loads Typeface from res/fonts/filename, returns None on failure
    try:
        from .FontManager import getFontPath
        from android.graphics import Typeface
        path = getFontPath(filename)
        if path:
            return Typeface.createFromFile(path)
    except Exception as e:
        log(f"FontPickerBottomSheet: _loadTypefaceForFile error: {e}")
    return None


def _createFamilyRow(act, family, subtext, is_selected, on_click, show_arrow=True, typeface=None):
    # row with radio, title+subtext, arrow
    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setClickable(True)
    row.setFocusable(True)
    row.setPadding(
        AndroidUtilities.dp(8), AndroidUtilities.dp(12),
        AndroidUtilities.dp(8), AndroidUtilities.dp(12)
    )
    try:
        row.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(8),
            Theme.getColor(Theme.key_dialogBackground),
            Theme.getColor(Theme.key_dialogBackgroundGray)
        ))
    except Exception:
        pass

    ind_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
    ind_lp.rightMargin = AndroidUtilities.dp(14)
    row.addView(_createRadioIndicator(act, is_selected), ind_lp)

    textBlock = LinearLayout(act)
    textBlock.setOrientation(LinearLayout.VERTICAL)

    title_tv = TextView(act)
    title_tv.setText(family)
    title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    try:
        if is_selected:
            title_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            title_tv.setTypeface(AndroidUtilities.bold())
        else:
            title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception:
        pass
    if typeface is not None:
        title_tv.setTypeface(typeface)
    textBlock.addView(title_tv, LayoutHelper.createLinear(-2, -2))

    if subtext:
        sub_tv = TextView(act)
        sub_tv.setText(subtext)
        sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        try:
            sub_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        textBlock.addView(sub_tv, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

    row.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    arrow_id = _resolveIcon("msg_arrow_forward")
    if show_arrow and arrow_id is not None:
        arrow = ImageView(act)
        arrow.setImageResource(arrow_id)
        try:
            arrow.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        arrow_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
        arrow_lp.leftMargin = AndroidUtilities.dp(8)
        row.addView(arrow, arrow_lp)

    _apply_press_scale(row)
    row.setOnClickListener(OnClickListener(lambda v: on_click()))
    return row


def _createStyleRow(act, style_label, is_selected, on_click, typeface=None):
    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setClickable(True)
    row.setFocusable(True)
    row.setPadding(
        AndroidUtilities.dp(8), AndroidUtilities.dp(13),
        AndroidUtilities.dp(8), AndroidUtilities.dp(13)
    )
    try:
        row.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(8),
            Theme.getColor(Theme.key_dialogBackground),
            Theme.getColor(Theme.key_dialogBackgroundGray)
        ))
    except Exception:
        pass

    ind_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
    ind_lp.rightMargin = AndroidUtilities.dp(14)
    row.addView(_createRadioIndicator(act, is_selected), ind_lp)

    label_tv = TextView(act)
    label_tv.setText(style_label)
    label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    try:
        if is_selected:
            label_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            label_tv.setTypeface(AndroidUtilities.bold())
        else:
            label_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception:
        pass
    if typeface is not None:
        label_tv.setTypeface(typeface)
    row.addView(label_tv, LayoutHelper.createLinear(-1, -2))

    _apply_press_scale(row)
    row.setOnClickListener(OnClickListener(lambda v: on_click()))
    return row


def _onStylePicked(filename, style_sheet, parent_sheet, act, on_select):
    try:
        setFont(filename)
        style_sheet.dismiss()
        parent_sheet.dismiss()
        # reopen with updated selection
        showFontPicker(act, on_select)
        if on_select:
            on_select(filename)
    except Exception as e:
        log(f"FontPickerBottomSheet: _onStylePicked error: {e}")


def _showStyleSheet(act, family, styles, selected_filename, parent_sheet, on_select):
    if BottomSheet is None:
        return
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        rp = frag.getResourceProvider() if frag else None
        sheet = BottomSheet(act, False, rp)
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)

        root = _createSheetRoot(act)
        root.addView(
            _createTitleBlock(act, family),
            LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 16)
        )

        first = True
        for style_label, filename in styles:
            if not first:
                root.addView(_createDivider(act), LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
            first = False
            is_sel = (selected_filename == filename)
            fn = filename
            tf = _loadTypefaceForFile(filename)
            style_row = _createStyleRow(
                act, style_label, is_sel,
                lambda f=fn: _onStylePicked(f, sheet, parent_sheet, act, on_select),
                typeface=tf
            )
            root.addView(style_row, LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))

        root.addView(_createCloseButton(act, sheet.dismiss), LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        try:
            from .viewUtils import applyFontToTree
            applyFontToTree(root)
        except Exception:
            pass

        sheet.setCustomView(root)
        sheet.show()
    except Exception as e:
        log(f"FontPickerBottomSheet: _showStyleSheet error: {e}")


def _onDefaultPicked(sheet, act, on_select):
    try:
        setFont("")
        sheet.dismiss()
        showFontPicker(act, on_select)
        if on_select:
            on_select("")
    except Exception as e:
        log(f"FontPickerBottomSheet: _onDefaultPicked error: {e}")


def showFontPicker(act, on_select=None):
    if BottomSheet is None or act is None:
        return
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        rp = frag.getResourceProvider() if frag else None
        sheet = BottomSheet(act, False, rp)
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)

        root = _createSheetRoot(act)
        root.addView(
            _createTitleBlock(
                act,
                _str("font_picker_title", "Select Font"),
                _str("font_picker_experimental", "Experimental")
            ),
            LayoutHelper.createFrame(-1, -2, Gravity.TOP, 0, 16, 0, 16)
        )

        selected = getSelectedFilename()
        font_files = listFontFiles()
        groups = _groupFonts(font_files)

        is_default = (selected == "")
        default_row = _createFamilyRow(
            act, _str("font_default", "Default (System)"), None, is_default,
            lambda: _onDefaultPicked(sheet, act, on_select),
            show_arrow=False
        )
        root.addView(default_row, LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))

        for family, styles in groups.items():
            root.addView(_createDivider(act), LayoutHelper.createFrame(-1, 1, Gravity.TOP, 16, 4, 16, 4))
            is_family_selected = any(selected == fn for _, fn in styles)
            fam = family
            sty = list(styles)
            sel = selected
            # use Regular if available, otherwise first style for preview
            preview_file = next((fn for sl, fn in styles if "Regular" in sl), styles[0][1])
            tf = _loadTypefaceForFile(preview_file)
            family_row = _createFamilyRow(
                act, fam, None, is_family_selected,
                lambda f=fam, s=sty, c=sel: _showStyleSheet(act, f, s, c, sheet, on_select),
                typeface=tf
            )
            root.addView(family_row, LayoutHelper.createLinear(-1, -2, 0, 1, 0, 1))

        root.addView(_createCloseButton(act, sheet.dismiss), LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        try:
            from .viewUtils import applyFontToTree
            applyFontToTree(root)
        except Exception:
            pass

        sheet.setCustomView(root)
        sheet.show()
    except Exception as e:
        log(f"FontPickerBottomSheet: showFontPicker error: {e}")

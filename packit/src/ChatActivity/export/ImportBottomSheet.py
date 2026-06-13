# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import traceback

from android.view import Gravity, View, MotionEvent
from android.widget import FrameLayout, LinearLayout, ScrollView, TextView
from java import dynamic_proxy
from org.telegram.messenger import AndroidUtilities, R
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper, StickerImageView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable


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


def show_import_bottom_sheet(fragment, num_blocks: int, on_confirm, import_level=None, import_xp=None):
    try:
        from elyx import strings
        if import_level is not None and import_xp is not None:
            level = import_level
            xp_into = import_xp
        else:
            from ...ui.AchievementsActivity.service.AchivementsEngine import get_level_info, _load_account
            data, _ = _load_account()
            level, xp_into, _ = get_level_info(data)

        activity = fragment.getParentActivity()
        resource_provider = fragment.getResourceProvider()

        sheet = BottomSheet(activity, False, resource_provider)
        sheet.fixNavigationBar()

        frame = FrameLayout(activity)
        linear = LinearLayout(activity)
        linear.setOrientation(LinearLayout.VERTICAL)
        frame.addView(linear)

        sticker = StickerImageView(activity, sheet.currentAccount)
        sticker.setStickerPackName("exteraGramPlaceholders")
        sticker.setStickerNum(6)
        sticker.getImageReceiver().setAutoRepeat(1)
        sticker.getImageReceiver().setAutoRepeatCount(1)
        linear.addView(sticker, LayoutHelper.createLinear(144, 144, Gravity.CENTER_HORIZONTAL, 0, 16, 0, 0))

        title = TextView(activity)
        title.setGravity(Gravity.CENTER_HORIZONTAL)
        title.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
        title.setTextSize(1, 20.0)
        title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        title.setText(strings["import_db_title"])
        linear.addView(title, LayoutHelper.createFrame(-1, -2.0, 0, 40.0, 20.0, 40.0, 0.0))

        subtitle = TextView(activity)
        subtitle.setGravity(Gravity.CENTER_HORIZONTAL)
        subtitle.setTextSize(1, 14.0)
        subtitle.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteGrayText))
        subtitle.setText(strings("import_db_subtitle", level=level, xp=xp_into))
        linear.addView(subtitle, LayoutHelper.createFrame(-1, -2.0, 0, 21.0, 15.0, 21.0, 8.0))

        confirm_btn = FrameLayout(activity)
        base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        confirm_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base_color, pressed_color
        ))
        confirm_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        confirm_btn.setClickable(True)
        confirm_btn.setFocusable(True)

        confirm_text = TextView(activity)
        confirm_text.setText(strings["import_db_confirm"])
        confirm_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        confirm_text.setTypeface(AndroidUtilities.bold())
        confirm_text.setGravity(Gravity.CENTER)
        confirm_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        confirm_btn.addView(confirm_text, FrameLayout.LayoutParams(-1, -2))

        _apply_press_scale(confirm_btn)

        class _ConfirmClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                try:
                    on_confirm()
                except Exception:
                    logx(f"importBottomSheet: on_confirm error: {traceback.format_exc()}", True)

        confirm_btn.setOnClickListener(_ConfirmClick())
        linear.addView(confirm_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 15.0, 16.0, 16.0))

        scroll = ScrollView(activity)
        scroll.addView(frame)
        sheet.setCustomView(scroll)
        sheet.show()
    except Exception:
        logx(f"importBottomSheet: show error: {traceback.format_exc()}", True)
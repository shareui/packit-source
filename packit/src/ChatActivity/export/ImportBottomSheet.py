import traceback
from android_utils import log
from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, ScrollView, TextView
from java import dynamic_proxy
from org.telegram.messenger import AndroidUtilities, R
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper, StickerImageView
from org.telegram.ui.Stories.recorder import ButtonWithCounterView


def show_import_bottom_sheet(fragment, num_blocks: int, on_confirm, import_level=None, import_xp=None):
    try:
        from elyx import strings
        if import_level is not None and import_xp is not None:
            level = import_level
            xp_into = import_xp
        else:
            from ...ui.AchievementsActivity.service.AchivementsEngine import get_level_info, _load_account
            data = _load_account()
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

        confirmBtn = ButtonWithCounterView(activity, True, resource_provider)
        confirmBtn.setRound()
        confirmBtn.setText(strings["import_db_confirm"], False)

        class _ConfirmClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                try:
                    on_confirm()
                except Exception:
                    log(f"importBottomSheet: on_confirm error: {traceback.format_exc()}")

        confirmBtn.setOnClickListener(_ConfirmClick())
        linear.addView(confirmBtn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 15.0, 16.0, 8.0))

        cancelBtn = ButtonWithCounterView(activity, False, resource_provider)
        cancelBtn.setRound()
        cancelBtn.setNeutral()
        cancelBtn.setText(strings["import_db_cancel"], False)

        class _CancelClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()

        cancelBtn.setOnClickListener(_CancelClick())
        linear.addView(cancelBtn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 0.0, 16.0, 0.0))

        scroll = ScrollView(activity)
        scroll.addView(frame)
        sheet.setCustomView(scroll)
        sheet.show()
    except Exception:
        log(f"importBottomSheet: show error: {traceback.format_exc()}")

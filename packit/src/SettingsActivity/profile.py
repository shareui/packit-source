# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Text, Divider, Custom
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment

from ..ui.AchievementsActivity.fragment import show_achievements
import threading
import time
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from ..ui.AchievementsActivity.service.AchivementsEngine import get_all_with_progress, get_stats


def _get_greeting(first_name: str) -> str:
    t = time.localtime()
    h = t.tm_hour
    m = t.tm_min

    if 5 <= h < 7:
        key = "greeting_0500"
    elif h == 7 or (h == 8 and m < 30):
        key = "greeting_0700"
    elif (h == 8 and m >= 30) or h == 9:
        key = "greeting_0830"
    elif h == 10:
        key = "greeting_1000"
    elif h == 11:
        key = "greeting_1100"
    elif h == 12:
        key = "greeting_1200"
    elif h == 13:
        key = "greeting_1300"
    elif h == 14:
        key = "greeting_1400"
    elif h == 15:
        key = "greeting_1500"
    elif h == 16:
        key = "greeting_1600"
    elif h == 17:
        key = "greeting_1700"
    elif h == 18:
        key = "greeting_1800"
    elif h == 19:
        key = "greeting_1900"
    elif h == 20:
        key = "greeting_2000"
    elif h == 21:
        key = "greeting_2100"
    elif h == 22:
        key = "greeting_2200"
    elif h == 23 and m < 30:
        key = "greeting_2300"
    elif h == 23:
        key = "greeting_2330"
    elif 0 <= h < 2:
        key = "greeting_0000"
    else:
        key = "greeting_0200"

    try:
        return str(strings[key]).format(first_name=first_name)
    except Exception:
        return ""


def _make_profile_header(context):
    try:
        from android.widget import FrameLayout, LinearLayout, TextView
        from android.view import Gravity
        from android.util import TypedValue
        from org.telegram.messenger import AndroidUtilities, UserConfig, MessagesController
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import LayoutHelper, BackupImageView, AvatarDrawable

        container = FrameLayout(context)

        content = LinearLayout(context)
        content.setOrientation(LinearLayout.VERTICAL)

        user = None
        try:
            account = getattr(UserConfig, 'selectedAccount', 0)
            mc = MessagesController.getInstance(account)
            uc = UserConfig.getInstance(account)
            if mc and uc:
                user = mc.getUser(uc.getClientUserId())
        except Exception:
            pass

        if user:
            img = BackupImageView(context)
            try:
                from hook_utils import find_class
                ExteraConfig = find_class("com.exteragram.messenger.ExteraConfig")
                # avatar size is 100dp; getAvatarCorners returns px radius matching user setting
                avatarRadius = ExteraConfig.getAvatarCorners(100.0)
            except Exception:
                avatarRadius = AndroidUtilities.dp(40)
            img.setRoundRadius(avatarRadius)
            avatar_drawable = AvatarDrawable(user)
            img.setForUserOrChat(user, avatar_drawable)
            content.addView(img, LayoutHelper.createLinear(100, 100, Gravity.CENTER_HORIZONTAL, 0, 24, 0, 16))

        title = TextView(context)
        title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        first_name = str(user.first_name) if user and user.first_name else "User"
        first_name = first_name[0].upper() + first_name[1:] if first_name else "User"
        title.setText(strings("profile_title", first_name=first_name))
        title.setGravity(Gravity.CENTER)
        content.addView(title, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 16, 0, 16, 4))

        subtitle = TextView(context)
        subtitle.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        if settings.get("static_online_status", False):
            subtitle.setText(str(strings["static_online_label"]))
        else:
            subtitle.setText(_get_greeting(first_name))
        subtitle.setGravity(Gravity.CENTER)
        content.addView(subtitle, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 24, 0, 24, 24))

        container.addView(content, LayoutHelper.createFrame(-1, -2, Gravity.CENTER))
        return container
    except Exception as e:
        logx(f"profile._make_profile_header: error: {e}", False)
        return None


class ProfileSettings:
    def _get_act(self):
        frag = get_last_fragment()
        return frag.getParentActivity() if frag else None

    def _make_header_item(self):
        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if not ctx:
                return None
            view = _make_profile_header(ctx)
            if view is None:
                return None
            item = Custom(view=view)
            try:
                item.setTransparent(True)
            except Exception:
                pass
            return item
        except Exception as e:
            logx(f"profile._make_header_item: error: {e}", False)
            return None

    def _show_achievements(self, view):
        try:
            items = get_all_with_progress()

            categories = {}
            for a in items:
                cat = a.get("category_key", a["category"])
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(a)

            cat_names = list(categories.keys())
            show_achievements(categories, cat_names)
        except Exception as e:
            logx(f"profile._show_achievements: error: {e}", False)

    def _do_export(self, include_local_config: bool, include_achievements: bool, include_saved_plugins: bool):
        try:
            from ..ChatActivity.export.bin.writer import build_binary, _rand_suffix
            from android_utils import run_on_ui_thread
            from java import jclass, dynamic_proxy
            from java.io import File, FileOutputStream
            import os

            data = build_binary(
                include_local_config=include_local_config,
                include_achievements=include_achievements,
                include_saved_plugins=include_saved_plugins,
            )

            try:
                from elyx import settings as elyxSettings
                download_path = elyxSettings.get("download_path", "/storage/emulated/0/Download")
            except Exception:
                download_path = "/storage/emulated/0/Download"

            os.makedirs(download_path, exist_ok=True)
            file_path = os.path.join(download_path, f"backup-{_rand_suffix(4)}.packit")
            logx(f"profile._do_export: writing to {file_path}", True)
            temp_file = File(file_path)
            if temp_file.exists():
                temp_file.delete()
            fos = FileOutputStream(temp_file)
            fos.write(data)
            fos.close()

            def open_share():
                try:
                    from hook_utils import find_class
                    ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                    fragment = get_last_fragment()
                    if not fragment:
                        return

                    ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")
                    _fragment = fragment

                    class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                        def __init__(self):
                            super().__init__()

                        def didShare(self):
                            # didShare is called before dismiss() - post to UI thread so bulletin shows after dialog closes
                            def _show_bulletin():
                                try:
                                    from org.telegram.messenger import R as R_tg
                                    BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                                    container = _fragment.getParentActivity().getWindow().getDecorView()
                                    rp = _fragment.getResourceProvider()
                                    BulletinFactory.of(container, rp).createSimpleBulletin(R_tg.raw.voip_invite, strings["export_db_done_share"]).show()
                                except Exception as _be:
                                    logx(f"profile.ShareDelegate.didShare: {_be}", True)
                            run_on_ui_thread(_show_bulletin)

                        def didCopy(self):
                            return False

                    share_alert = ShareAlert(
                        fragment.getParentActivity(),
                        None, None,
                        temp_file.getAbsolutePath(),
                        None, None,
                        False, None, None,
                        False, False, False,
                        None, None
                    )
                    share_alert.setDelegate(ShareDelegate())
                    logx("profile.open_share: delegate set, showing dialog", True)
                    fragment.showDialog(share_alert)
                    logx("profile.open_share: showDialog returned", True)
                except Exception as e:
                    logx(f"profile._do_export.open_share: {e}", False)
                    BulletinHelper.show_error(strings["export_db_error"])

            run_on_ui_thread(open_share)
        except Exception as e:
            logx(f"profile._do_export: {e}", False)
            from android_utils import run_on_ui_thread
            run_on_ui_thread(lambda: BulletinHelper.show_error(strings["export_db_error"]))

    def _show_export_db(self, view):
        try:
            from android_utils import run_on_ui_thread
            run_on_ui_thread(self._open_export_sheet)
        except Exception as e:
            logx(f"profile._show_export_db: error: {e}", False)

    def _open_export_sheet(self):
        try:
            from android.widget import LinearLayout, TextView, FrameLayout
            from android.view import Gravity, View, MotionEvent
            from android.util import TypedValue
            from android.graphics import Color
            from android.graphics.drawable import GradientDrawable
            from org.telegram.messenger import AndroidUtilities
            from org.telegram.ui.ActionBar import Theme, BottomSheet
            from org.telegram.ui.Components import LayoutHelper, CheckBox2
            from android_utils import OnClickListener
            from java import dynamic_proxy

            frag = get_last_fragment()
            if not frag:
                return
            ctx = frag.getParentActivity()
            if not ctx:
                return

            dp = AndroidUtilities.dp

            sheet = BottomSheet(ctx, False, frag.getResourceProvider())
            sheet.setApplyBottomPadding(False)
            sheet.setApplyTopPadding(False)
            sheet.setCanDismissWithSwipe(False)

            outer = LinearLayout(ctx)
            outer.setOrientation(LinearLayout.VERTICAL)
            try:
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadii([
                    dp(20), dp(20),
                    dp(20), dp(20),
                    0, 0, 0, 0,
                ])
                bg.setColor(Theme.getColor(Theme.key_dialogBackground))
                outer.setBackground(bg)
            except Exception:
                try:
                    outer.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                except Exception:
                    pass

            pad_h = 20

            title_tv = TextView(ctx)
            title_tv.setText(str(strings["export_bs_title"]))
            title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
            try:
                title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            except Exception:
                pass

            subtitle_tv = TextView(ctx)
            subtitle_tv.setText(str(strings["export_bs_subtitle"]))
            subtitle_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            try:
                subtitle_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass

            title_col = LinearLayout(ctx)
            title_col.setOrientation(LinearLayout.VERTICAL)
            title_col.setGravity(Gravity.CENTER_HORIZONTAL)
            title_tv.setGravity(Gravity.CENTER)
            subtitle_tv.setGravity(Gravity.CENTER)
            title_col.addView(title_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL))
            title_col.addView(subtitle_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 0, 4, 0, 0))

            outer.addView(title_col, LayoutHelper.createLinear(-1, -2, pad_h, 16, pad_h, 16))

            checkboxStates = [True, True, True]
            checkboxLabels = [
                strings["export_bs_local_config"],
                strings["export_bs_achievements"],
                strings["export_bs_plugins"],
            ]
            checkboxViews = []

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

            def makeCheckRow(i, labelText):
                row = LinearLayout(ctx)
                row.setOrientation(LinearLayout.HORIZONTAL)
                row.setGravity(Gravity.CENTER_VERTICAL)
                row.setPadding(dp(12), dp(6), dp(12), dp(6))
                row.setClickable(True)
                row.setFocusable(True)
                try:
                    row_bg = GradientDrawable()
                    row_bg.setShape(GradientDrawable.RECTANGLE)
                    row_bg.setCornerRadius(dp(12))
                    row_bg.setColor(Theme.getColor(Theme.key_dialogBackground))
                    row.setBackground(row_bg)
                except Exception:
                    pass

                cb = CheckBox2(ctx, 21, frag.getResourceProvider())
                cb.setColor(Theme.key_radioBackgroundChecked, Theme.key_radioBackground, Theme.key_checkboxCheck)
                cb.setDrawUnchecked(True)
                cb.setDrawBackgroundAsArc(14)
                cb.setChecked(True, False)
                checkboxViews.append(cb)

                label = TextView(ctx)
                label.setText(str(labelText))
                label.setMaxLines(1)
                label.setSingleLine(True)
                try:
                    label.setAutoSizeTextTypeWithDefaults(TextView.AUTO_SIZE_TEXT_TYPE_UNIFORM)
                    label.setAutoSizeTextTypeUniformWithConfiguration(8, 15, 1, TypedValue.COMPLEX_UNIT_DIP)
                except Exception:
                    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                try:
                    label.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                except Exception:
                    pass

                row.addView(cb, LayoutHelper.createLinear(dp(21), dp(21), Gravity.CENTER_VERTICAL, 0, 0, dp(8), 0))
                row.addView(label, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                def makeToggle(idx, checkbox):
                    def onClick(v):
                        checkboxStates[idx] = not checkboxStates[idx]
                        checkbox.setChecked(checkboxStates[idx], True)
                    return onClick

                row.setOnClickListener(OnClickListener(makeToggle(i, cb)))
                _apply_press_scale(row)
                return row

            checkboxes_list = LinearLayout(ctx)
            checkboxes_list.setOrientation(LinearLayout.VERTICAL)

            for i, label in enumerate(checkboxLabels):
                rowView = makeCheckRow(i, label)
                row_lp = LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8 if i < len(checkboxLabels) - 1 else 0)
                checkboxes_list.addView(rowView, row_lp)

            dark_container = FrameLayout(ctx)
            dark_field_color = Theme.getColor(Theme.key_windowBackgroundGray)
            dark_bg = GradientDrawable()
            dark_bg.setShape(GradientDrawable.RECTANGLE)
            dark_bg.setCornerRadius(dp(18))
            dark_bg.setColor(dark_field_color)
            dark_container.setBackground(dark_bg)

            checkboxes_list.setPadding(dp(12), dp(16), dp(12), dp(16))
            dark_container.addView(checkboxes_list, FrameLayout.LayoutParams(-1, -2))

            dark_lp = LinearLayout.LayoutParams(-1, -2)
            dark_lp.leftMargin = dp(pad_h)
            dark_lp.rightMargin = dp(pad_h)
            outer.addView(dark_container, dark_lp)

            def onShare():
                try:
                    sheet.dismiss()
                except Exception:
                    pass
                t = threading.Thread(
                    target=self._do_export,
                    args=(checkboxStates[0], checkboxStates[1], checkboxStates[2]),
                    daemon=True,
                )
                t.start()

            export_btn = FrameLayout(ctx)
            base = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            export_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(28), base, pressed))
            export_btn.setPadding(0, dp(14), 0, dp(14))
            export_btn.setClickable(True)
            export_btn.setFocusable(True)

            btn_tv = TextView(ctx)
            btn_tv.setText(str(strings["export_bs_share"]))
            btn_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            btn_tv.setGravity(Gravity.CENTER)
            try:
                btn_tv.setTypeface(AndroidUtilities.bold())
                btn_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            export_btn.addView(btn_tv, FrameLayout.LayoutParams(-1, -2))
            export_btn.setOnClickListener(OnClickListener(lambda v: onShare()))
            _apply_press_scale(export_btn)
            outer.addView(export_btn, LayoutHelper.createLinear(-1, -2, pad_h, 24, pad_h, 16))

            sheet.setCustomView(outer)
            sheet.show()
        except Exception as e:
            logx(f"profile._open_export_sheet: error: {e}", False)

    def _make_stats_card(self, context):
        logx("profile: _make_stats_card start", True)
        try:
            import re as _re
            from android.widget import FrameLayout, LinearLayout, TextView
            from android.view import Gravity
            from android.util import TypedValue
            from android.graphics import Color
            from android.graphics.drawable import GradientDrawable
            from org.telegram.messenger import AndroidUtilities
            from org.telegram.ui.ActionBar import Theme
            from org.telegram.ui.Components import LayoutHelper
            from java import dynamic_proxy, jclass
            from android_utils import OnClickListener
            OnGlobalLayoutListener = jclass("android.view.ViewTreeObserver$OnGlobalLayoutListener")

            dp = AndroidUtilities.dp

            s = get_stats()
            level, xp_a, xp_b = s["level_info"]

            try:
                from ..utils.localConfig import days_since_install
                days = days_since_install()
            except Exception:
                days = 0

            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
            textPrimary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
            textSecondary = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            bgColor = Theme.getColor(Theme.key_windowBackgroundWhite)

            root = LinearLayout(context)
            root.setOrientation(LinearLayout.VERTICAL)
            root.setBackgroundColor(bgColor)
            root.setPadding(dp(16), dp(12), dp(16), dp(16))
            root.setClipChildren(False)
            root.setClipToPadding(False)

            # level row: label left, xp right
            levelRow = LinearLayout(context)
            levelRow.setOrientation(LinearLayout.HORIZONTAL)
            levelRow.setGravity(Gravity.CENTER_VERTICAL)

            levelLabel = TextView(context)
            levelLabel.setTextColor(textPrimary)
            levelLabel.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            try:
                levelLabel.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
            except Exception:
                pass
            if level >= 100:
                levelLabel.setText(str(strings["stat_account_level_max"]))
            else:
                levelLabel.setText(str(strings("stat_account_level", level=level)))
            levelRow.addView(levelLabel, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            root.addView(levelRow, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

            # progress bar background
            barBg = FrameLayout(context)
            barBgDrawable = GradientDrawable()
            barBgDrawable.setShape(GradientDrawable.RECTANGLE)
            barBgDrawable.setCornerRadius(dp(4))
            try:
                barBgDrawable.setColor(Theme.multAlpha(accent, 0.15))
            except Exception:
                barBgDrawable.setColor(Color.argb(38, Color.red(accent), Color.green(accent), Color.blue(accent)))
            barBg.setBackground(barBgDrawable)

            # progress bar fill
            fill = FrameLayout(context)
            fillDrawable = GradientDrawable()
            fillDrawable.setShape(GradientDrawable.RECTANGLE)
            fillDrawable.setCornerRadius(dp(4))
            fillDrawable.setColor(accent)
            fill.setBackground(fillDrawable)

            progress = min(1.0, max(0.0, xp_a / xp_b if xp_b > 0 else 1.0))
            barBg.addView(fill, LayoutHelper.createFrame(-1, -1, Gravity.START | Gravity.TOP))

            root.addView(barBg, LayoutHelper.createLinear(-1, 9, 0, 0, 0, 8))

            # resize fill to correct width after layout
            _progress = progress
            _fill = fill
            _dp4 = dp(4)

            class _LayoutListener(dynamic_proxy(OnGlobalLayoutListener)):
                def onGlobalLayout(self):
                    w = barBg.getWidth()
                    if w > 0:
                        lp = _fill.getLayoutParams()
                        lp.width = max(_dp4, int(w * _progress))
                        _fill.setLayoutParams(lp)
                    try:
                        barBg.getViewTreeObserver().removeOnGlobalLayoutListener(self)
                    except Exception:
                        pass

            barBg.getViewTreeObserver().addOnGlobalLayoutListener(_LayoutListener())

            xpLabel = TextView(context)
            xpLabel.setTextColor(textSecondary)
            xpLabel.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            if level >= 100:
                xpLabel.setText(str(strings("stat_xp_total", xp_a=xp_a, xp_b=xp_b)))
            else:
                xpLabel.setText(str(strings("stat_xp_to_next", xp_a=xp_a, xp_b=xp_b)))
            root.addView(xpLabel, LayoutHelper.createLinear(-2, -2, 0, 4, 0, 12))

            # counters: value on top (accent, bold), label below (secondary, small)
            # (text, icon_drawable_name)
            COUNTERS = [
                (str(strings("stat_achievements",       completed=s["completed"], total=s["total"])), "msg_fave",     strings["stat_hint_achievements"]),
                (str(strings("stat_days_of_use",        days=days)),                                  "msg_calendar2",strings["stat_hint_days_of_use"]),
                (str(strings("stat_installed_plugins",  count=s["installed_plugins"])),               "msg_plugins",  strings["stat_hint_installed_plugins"]),
                (str(strings("stat_links_copied",       count=s["links_copied"])),                    "msg_link",     strings["stat_hint_links_copied"]),
                (str(strings("stat_plugins_downloaded", count=s["plugins_downloaded"])),              "msg_download", strings["stat_hint_plugins_downloaded"]),
                (str(strings("stat_plugins_shared",     count=s["plugins_shared"])),                  "msg_share",    strings["stat_hint_plugins_shared"]),
                (str(strings("stat_code_views",         count=s["code_views"])),                      "msg_stats",    strings["stat_hint_code_views"]),
                (str(strings("stat_reports_sent",       count=s["reports_sent"])),                    "msg_report",   strings["stat_hint_reports_sent"]),
            ]

            logx(f"profile: stats card built ok, counters={len(COUNTERS)}", True)
            _active_hint = [None]

            def makeCell(text, iconName, hintText):
                # horizontal: icon | (value + label stacked)
                cell = LinearLayout(context)
                cell.setOrientation(LinearLayout.HORIZONTAL)
                cell.setGravity(Gravity.CENTER_VERTICAL)

                try:
                    from android.widget import ImageView
                    iconView = ImageView(context)
                    resId = context.getResources().getIdentifier(iconName, "drawable", context.getPackageName())
                    if resId != 0:
                        iconView.setImageResource(resId)
                    else:
                        iconView.setImageResource(R.drawable.msg_stats)
                    iconView.setColorFilter(textSecondary)
                    cell.addView(iconView, LayoutHelper.createLinear(18, 18, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))
                except Exception:
                    pass

                textBlock = LinearLayout(context)
                textBlock.setOrientation(LinearLayout.VERTICAL)

                m = _re.match(r"^(\S+)\s+(.*)", text)
                valStr = m.group(1) if m else text
                lblStr = m.group(2) if m else ""

                valView = TextView(context)
                valView.setTextColor(accent)
                valView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                try:
                    valView.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
                except Exception:
                    pass
                valView.setText(valStr)
                textBlock.addView(valView, LayoutHelper.createLinear(-2, -2))

                if lblStr:
                    lblView = TextView(context)
                    lblView.setTextColor(textSecondary)
                    lblView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
                    lblView.setText(lblStr)
                    textBlock.addView(lblView, LayoutHelper.createLinear(-2, -2, 0, 1, 0, 0))

                cell.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                def makeClickHandler(c, ht):
                    def onClick(v):
                        try:
                            from org.telegram.ui.Stories.recorder import HintView2
                            from android.text import Layout
                            from android_utils import run_on_ui_thread
                            from android.widget import FrameLayout as FL

                            prev = _active_hint[0]
                            if prev is not None:
                                try:
                                    prev.hide()
                                    prev.getParent().removeView(prev)
                                except Exception:
                                    pass
                                _active_hint[0] = None

                            frag = get_last_fragment()
                            decorView = frag.getParentActivity().getWindow().getDecorView()

                            hint = (
                                HintView2(c.getContext(), 3)
                                .setMultilineText(True)
                                .setBgColor(Theme.getColor(Theme.key_undo_background))
                                .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                                .setText(str(ht))
                                .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                                .allowBlur(True)
                                .setRounding(AndroidUtilities.dp(12))
                            )
                            try:
                                hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                            except Exception:
                                pass

                            decorView.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                            _active_hint[0] = hint

                            def _show():
                                try:
                                    c_loc = [0, 0]
                                    c.getLocationInWindow(c_loc)
                                    decor_loc = [0, 0]
                                    decorView.getLocationInWindow(decor_loc)
                                    cell_x = c_loc[0] - decor_loc[0]
                                    cell_y = c_loc[1] - decor_loc[1]
                                    center_x = float(cell_x) + float(c.getMeasuredWidth()) / 2.0
                                    ty = float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6))
                                    jx = float(-AndroidUtilities.dp(32)) + center_x
                                    hint.setTranslationY(ty)
                                    hint.setJointPx(0.0, jx)
                                    hint.setDuration(5500)
                                    hint.show()
                                except Exception as e:
                                    logx(f"profile: stat hint position error: {e}", False)

                            run_on_ui_thread(_show)
                        except Exception as e:
                            logx(f"profile: stat hint error: {e}", False)
                    return onClick

                cell.setOnClickListener(OnClickListener(makeClickHandler(cell, hintText)))
                return cell

            for rowStart in range(0, len(COUNTERS), 2):
                # FrameLayout wraps the row so HintView2 overlays without pushing content
                rowFrame = FrameLayout(context)
                rowFrame.setClipChildren(False)
                rowFrame.setClipToPadding(False)

                _current_row = LinearLayout(context)
                _current_row.setOrientation(LinearLayout.HORIZONTAL)
                chunk = COUNTERS[rowStart:rowStart + 2]
                for i, (text, icon, hint) in enumerate(chunk):
                    cell = makeCell(text, icon, hint)
                    leftM = 0 if i == 0 else dp(16)
                    _current_row.addView(cell, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, leftM, 0, 0, 0))
                rowFrame.addView(_current_row, LayoutHelper.createFrame(-1, -2))
                bottomM = 10 if rowStart + 2 < len(COUNTERS) else 0
                root.addView(rowFrame, LayoutHelper.createLinear(-1, -2, 0, 0, 0, bottomM))

            return root
        except Exception as e:
            logx(f"profile._make_stats_card: error: {e}", False)
            return None

    def build(self):
        items = []

        header = self._make_header_item()
        if header is not None:
            items.append(header)

        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if ctx:
                statsCard = self._make_stats_card(ctx)
                if statsCard is not None:
                    items.append(Custom(view=statsCard))
        except Exception as e:
            logx(f"profile.build: stats card error: {e}", False)

        items += [
            Text(
                text=strings["profile_achievements"],
                icon="msg_fave",
                on_click=self._show_achievements
            ),
            Text(
                text=strings["profile_export_db"],
                icon="msg_unarchive",
                on_click=self._show_export_db
            ),
            Divider(),
        ]

        return items
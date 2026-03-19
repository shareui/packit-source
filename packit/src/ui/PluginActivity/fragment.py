import ctypes
import threading
from android.view import Gravity, View
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, ProgressBar, HorizontalScrollView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class
from java import dynamic_proxy
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import elyx failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import AndroidUtilities failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import UniversalFragment failed: {e}")

try:
    from org.telegram.messenger.browser import Browser
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import Browser failed: {e}")
    Browser = None
    Uri = None

try:
    from org.telegram.ui.ActionBar import ActionBarPopupWindow
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import ActionBarPopupWindow failed: {e}")
    ActionBarPopupWindow = None

try:
    from androidx.core.content import ContextCompat
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import ContextCompat failed: {e}")
    ContextCompat = None

try:
    from android.graphics.drawable import RippleDrawable
except Exception:
    RippleDrawable = None

try:
    from android.graphics import Color as AColor, PorterDuff
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import AColor failed: {e}")
    AColor = None
    PorterDuff = None

try:
    from android.content.res import ColorStateList as AColorStateList
except Exception:
    AColorStateList = None




_STICKER_RETRY_DELAY = 1.5


def _resolve_icon(name):
    try:
        R_tg = find_class("org.telegram.messenger.R")
        return getattr(R_tg.drawable, name)
    except Exception:
        return 0


def _try_load_sticker(iv, icon_str, size_dp):
    try:
        if not icon_str or "/" not in str(icon_str):
            return False
        pack_name, index_str = str(icon_str).split("/", 1)
        sticker_index = int(index_str)
        mdc = MediaDataController.getInstance(0)
        ss = None
        try:
            ss = mdc.getStickerSetByName(pack_name)
        except Exception:
            pass
        if not ss:
            try:
                ss = mdc.getStickerSetByEmojiOrName(pack_name)
            except Exception:
                pass
        if ss and getattr(ss, "documents", None) and ss.documents.size() > sticker_index:
            doc = ss.documents.get(sticker_index)
            iv.setImage(
                ImageLocation.getForDocument(doc),
                f"{size_dp}_{size_dp}",
                None, None, 0, 1
            )
            return True
        return False
    except Exception as e:
        log(f"pluginProfile: _try_load_sticker error: {e}")
        return False


def _schedule_sticker_retry(iv, icon_str, size_dp, alive_ref):
    # alive_ref is a list[bool] shared with the fragment; set to False on destroy
    def _retry():
        if alive_ref[0]:
            _try_load_sticker(iv, icon_str, size_dp)
    threading.Timer(_STICKER_RETRY_DELAY, lambda: run_on_ui_thread(_retry)).start()


def _make_chip(act, text, color_key):
    try:
        color = Theme.getColor(getattr(Theme, color_key))
    except Exception:
        color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
    text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(AndroidUtilities.dp(6))
    bg.setColor(fill)
    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(text_color)
    tv.setBackground(bg)
    tv.setPadding(
        AndroidUtilities.dp(7), AndroidUtilities.dp(3),
        AndroidUtilities.dp(7), AndroidUtilities.dp(3)
    )
    return tv


def _make_section_header(act, text):
    tv = TextView(act)
    tv.setText(text.upper())
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    tv.setLetterSpacing(0.08)
    try:
        tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        tv.setTypeface(AndroidUtilities.bold())
    return tv


def _make_divider(act):
    v = View(act)
    v.setBackgroundColor(Theme.getColor(Theme.key_divider))
    lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
    lp.topMargin = AndroidUtilities.dp(16)
    lp.bottomMargin = AndroidUtilities.dp(14)
    return v, lp


def _make_card_bg(act, corner=14):
    try:
        base = Theme.getColor(Theme.key_windowBackgroundWhite)
        r = (base >> 16) & 0xFF
        g = (base >> 8) & 0xFF
        b = base & 0xFF
        fill = ctypes.c_int32((0xDD << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(corner))
        bg.setColor(fill)
        return bg
    except Exception:
        return None



from .versionPicker import _show_version_picker


def _show_plugin_menu(act, p, anchor_view, repo_id: str = ""):
    try:
        from ..PluginListActivity.service.PluginActions import copy_plugin_link, share_plugin_file, view_plugin_code, download_plugin_file, translate_plugin
        from ..PluginListActivity.service.ReportService import report_plugin
        from org.telegram.messenger import R as R_tg

        popup_layout = ActionBarPopupWindow.ActionBarPopupWindowLayout(act)
        popup_layout.setBackgroundColor(Theme.getColor(Theme.key_actionBarDefaultSubmenuBackground))
        popup_layout.setFitItems(True)
        popup_window_ref = [None]

        def create_menu_item(icon_res, title, action, is_red=False):
            item_frame = FrameLayout(act)
            item_frame.setMinimumWidth(AndroidUtilities.dp(160))
            item_frame.setClickable(True)
            item_frame.setFocusable(True)
            try:
                try:
                    bg_color = Theme.getColor(Theme.key_dialogBackgroundGray) & 0x20FFFFFF | 0x10000000
                except Exception:
                    bg_color = Theme.getColor(Theme.key_windowBackgroundGray) & 0x20FFFFFF | 0x10000000
                try:
                    pressed_color = Theme.getColor(Theme.key_listSelector) & 0x40FFFFFF | 0x30000000
                except Exception:
                    pressed_color = AColor.parseColor("#D0D0D0") if AColor else 0x30000000
                btn_bg = GradientDrawable()
                btn_bg.setCornerRadius(AndroidUtilities.dp(10))
                btn_bg.setColor(bg_color)
                try:
                    ripple_color = AColorStateList.valueOf(AColor.parseColor("#40000000"))
                    pressed_bg = GradientDrawable()
                    pressed_bg.setCornerRadius(AndroidUtilities.dp(10))
                    pressed_bg.setColor(pressed_color)
                    item_frame.setBackground(RippleDrawable(ripple_color, btn_bg, pressed_bg))
                except Exception:
                    item_frame.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(10), bg_color, pressed_color
                    ))
            except Exception:
                item_frame.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))

            item_content = LinearLayout(act)
            item_content.setOrientation(LinearLayout.HORIZONTAL)
            item_content.setGravity(Gravity.CENTER_VERTICAL)
            item_content.setPadding(AndroidUtilities.dp(16), AndroidUtilities.dp(12), AndroidUtilities.dp(16), AndroidUtilities.dp(12))

            icon = ImageView(act)
            icon.setScaleType(ImageView.ScaleType.CENTER)
            try:
                icon_drawable = ContextCompat.getDrawable(act, icon_res)
                if is_red:
                    try:
                        red_color = Theme.getColor(Theme.key_text_RedRegular)
                    except Exception:
                        red_color = AColor.parseColor("#FF3B30")
                    icon_drawable.setColorFilter(red_color, PorterDuff.Mode.SRC_IN)
                else:
                    try:
                        gray_color = Theme.getColor(Theme.key_dialogTextGray)
                    except Exception:
                        gray_color = AColor.parseColor("#808080")
                    icon_drawable.setColorFilter(gray_color, PorterDuff.Mode.SRC_IN)
                icon.setImageDrawable(icon_drawable)
            except Exception:
                icon.setImageResource(icon_res)
            item_content.addView(icon, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

            title_tv = TextView(act)
            title_tv.setText(title)
            title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            try:
                if is_red:
                    try:
                        red_color = Theme.getColor(Theme.key_text_RedRegular)
                    except Exception:
                        red_color = AColor.parseColor("#FF3B30")
                    title_tv.setTextColor(red_color)
                else:
                    title_tv.setTextColor(Theme.getColor(Theme.key_actionBarDefaultSubmenuItem))
            except Exception:
                pass
            item_content.addView(title_tv, LayoutHelper.createLinear(-1, -2, 1.0, Gravity.CENTER_VERTICAL))
            item_frame.addView(item_content)

            def _on_click(*_):
                try:
                    if popup_window_ref[0]:
                        popup_window_ref[0].dismiss()
                except Exception:
                    pass
                try:
                    action()
                except Exception:
                    pass

            item_frame.setOnClickListener(OnClickListener(_on_click))
            popup_layout.addView(item_frame, LayoutHelper.createLinear(-1, -2))

        icon_copy      = getattr(R_tg.drawable, 'msg_copy',      getattr(R_tg.drawable, 'msg_copy_filled', 0))
        icon_share     = getattr(R_tg.drawable, 'msg_share',     0)
        icon_code      = getattr(R_tg.drawable, 'msg_view_file', 0)
        icon_download  = getattr(R_tg.drawable, 'msg_download',  0)
        icon_translate = getattr(R_tg.drawable, 'msg_replace',   0)
        icon_report    = getattr(R_tg.drawable, 'msg_report',    0)

        create_menu_item(icon_copy,      str(strings["copy_link"]), lambda: copy_plugin_link(p, repo_id or str(p.get("id") or ""), None))
        create_menu_item(icon_share,     str(strings["share"]),     lambda: share_plugin_file(p, str(p.get("name") or p.get("id") or ""), act))
        create_menu_item(icon_code,      str(strings["code"]),      lambda: view_plugin_code(p, act))
        create_menu_item(icon_download,  str(strings["download"]),  lambda: download_plugin_file(p))
        create_menu_item(icon_report,    str(strings["report"]),    lambda: report_plugin(p, act), is_red=True)

        popup_window = ActionBarPopupWindow(popup_layout, -2, -2)
        popup_window_ref[0] = popup_window
        popup_window.setOutsideTouchable(True)
        popup_window.setClippingEnabled(True)
        popup_window.setAnimationStyle(R_tg.style.PopupContextAnimation)
        popup_window.setFocusable(True)
        popup_layout.measure(
            View.MeasureSpec.makeMeasureSpec(AndroidUtilities.dp(1000), View.MeasureSpec.AT_MOST),
            View.MeasureSpec.makeMeasureSpec(AndroidUtilities.dp(1000), View.MeasureSpec.AT_MOST)
        )
        location = [0, 0]
        anchor_view.getLocationInWindow(location)
        popup_x = location[0] + anchor_view.getWidth() - popup_layout.getMeasuredWidth()
        popup_y = location[1] - popup_layout.getMeasuredHeight()
        popup_window.showAtLocation(anchor_view, Gravity.TOP | Gravity.LEFT, popup_x, popup_y)
        popup_window.dimBehind()
        log("pluginProfile: _show_plugin_menu shown")
    except Exception as e:
        log(f"pluginProfile: _show_plugin_menu error: {e}")


class PluginProfileFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    _MENU_ID = 1001

    def __init__(self, plugin: dict, install_ui, all_plugins: list, repo_id: str = ""):
        super().__init__()
        self.plugin = plugin
        self.install_ui = install_ui
        self.all_plugins = all_plugins or []
        self.repo_id = repo_id
        self.content_view = None
        self._alive = [True]  # shared ref for sticker retry timers
        self._fragment_ref = [None]  # filled after presentFragment
        self._anchor_ref = [None]   # filled after menu button is created
        log(f"pluginProfile: init plugin={plugin.get('id')}")

    def onFragmentCreate(self, *_):
        log(f"pluginProfile: onFragmentCreate plugin={self.plugin.get('id')}")

    def onFragmentDestroy(self, *_):
        log(f"pluginProfile: onFragmentDestroy plugin={self.plugin.get('id')}")
        self._alive[0] = False
        try:
            spinner = getattr(self, '_changelog_spinner', None)
            if spinner:
                try:
                    spinner.stop()
                except Exception:
                    pass
                self._changelog_spinner = None
        except Exception:
            pass
        try:
            if self.content_view is not None:
                parent = self.content_view.getParent()
                log(f"pluginProfile: removeView parent={parent}")
                if parent is not None:
                    parent.removeView(self.content_view)
                self.content_view = None
                log("pluginProfile: content_view removed and nulled")
        except Exception as e:
            log(f"pluginProfile: onFragmentDestroy removeView error: {e}")

    def getTitle(self):
        return str(self.plugin.get("name") or self.plugin.get("id") or strings.pp_unknown_plugin)

    def onBackPressed(self):
        log(f"pluginProfile: onBackPressed plugin={self.plugin.get('id')}")
        return False

    def afterCreateView(self, v):
        log(f"pluginProfile: afterCreateView v={v}")
        return None

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, mid):
        log(f"pluginProfile: onMenuItemClick mid={mid} MENU_ID={self._MENU_ID}")
        if mid != self._MENU_ID:
            return
        try:
            frag = self._fragment_ref[0]
            anchor = self._anchor_ref[0]
            if not frag or not anchor:
                log("pluginProfile: onMenuItemClick missing frag or anchor")
                return
            act = frag.getParentActivity()
            _show_plugin_menu(act, self.plugin, anchor, repo_id=self.repo_id)
        except Exception as e:
            log(f"pluginProfile: onMenuItemClick error: {e}")

    def beforeCreateView(self):
        log(f"pluginProfile: beforeCreateView plugin={self.plugin.get('id')}")
        if self.content_view is not None:
            try:
                parent = self.content_view.getParent()
                if parent is not None:
                    parent.removeView(self.content_view)
                    log("pluginProfile: beforeCreateView removed stale content_view")
            except Exception as e:
                log(f"pluginProfile: beforeCreateView stale cleanup error: {e}")
            self.content_view = None
        frag = get_last_fragment()
        if not frag:
            log("pluginProfile: beforeCreateView no fragment, aborting")
            return None
        act = frag.getParentActivity()
        if not act:
            log("pluginProfile: beforeCreateView no activity, aborting")
            return None
        p = self.plugin

        bg_color = Theme.getColor(Theme.key_windowBackgroundGray)
        text_color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

        self.content_view = FrameLayout(act)
        self.content_view.setBackgroundColor(bg_color)

        scroll = ScrollView(act)
        scroll.setFillViewport(True)
        scroll.setVerticalScrollBarEnabled(False)
        self.content_view.addView(scroll, FrameLayout.LayoutParams(-1, -1))

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), AndroidUtilities.dp(24)
        )
        scroll.addView(root)

        # hero card: [icon | name + meta] / [release_date | install_btn | menu_btn]
        hero = LinearLayout(act)
        hero.setOrientation(LinearLayout.VERTICAL)
        hero.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), AndroidUtilities.dp(16)
        )
        bg = _make_card_bg(act, 18)
        if bg:
            hero.setBackground(bg)

        # top row: icon + name/meta
        top_row = LinearLayout(act)
        top_row.setOrientation(LinearLayout.HORIZONTAL)
        top_row.setGravity(Gravity.CENTER_VERTICAL)

        icon_str = p.get("icon")
        sticker_size = 72
        if icon_str and "/" in str(icon_str):
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(16))
            try:
                iv.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            iv_lp = LinearLayout.LayoutParams(
                AndroidUtilities.dp(sticker_size), AndroidUtilities.dp(sticker_size)
            )
            iv_lp.rightMargin = AndroidUtilities.dp(14)
            top_row.addView(iv, iv_lp)
            if not _try_load_sticker(iv, icon_str, sticker_size):
                _schedule_sticker_retry(iv, icon_str, sticker_size, self._alive)

        info_col = LinearLayout(act)
        info_col.setOrientation(LinearLayout.VERTICAL)
        info_col.setGravity(Gravity.TOP)

        name_tv = TextView(act)
        name_tv.setText(str(p.get("name") or p.get("id") or strings.pp_unknown_name))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        name_tv.setTextColor(text_color)
        name_tv.setSingleLine(True)
        name_tv.setHorizontalFadingEdgeEnabled(True)
        name_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        info_col.addView(name_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 3))

        meta_parts = []
        if p.get("author"):
            meta_parts.append(str(p["author"]))
        if p.get("version"):
            meta_parts.append(f"v{p['version']}")
        if meta_parts:
            meta_tv = TextView(act)
            meta_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            meta_tv.setTextColor(gray_color)
            meta_tv.setSingleLine(True)
            meta_tv.setHorizontalFadingEdgeEnabled(True)
            meta_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                meta_tv.setText(LocaleUtils.fullyFormatText("  ·  ".join(meta_parts)))
                meta_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                meta_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                meta_tv.setText("  ·  ".join(meta_parts))
            info_col.addView(meta_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        # chips: state + size + min_version
        chips_row = LinearLayout(act)
        chips_row.setOrientation(LinearLayout.HORIZONTAL)
        chips_row.setGravity(Gravity.CENTER_VERTICAL)

        _STATE_COLOR_KEYS = {
            "release": "key_color_green",
            "beta":    "key_color_orange",
            "alpha":   "key_color_red",
        }
        state = str(p.get("state") or "").strip().lower()
        if state:
            color_key = _STATE_COLOR_KEYS.get(state, "key_windowBackgroundWhiteGrayText")
            chip = _make_chip(act, state, color_key)
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(4)
            chips_row.addView(chip, chip_lp)

        if p.get("size"):
            chip = _make_chip(act, str(p["size"]), "key_color_cyan")
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(4)
            chips_row.addView(chip, chip_lp)

        if p.get("min_version"):
            chip = _make_chip(act, str(p["min_version"]), "key_avatar_background2Blue")
            chips_row.addView(chip, LinearLayout.LayoutParams(-2, -2))

        if chips_row.getChildCount() > 0:
            info_col.addView(chips_row, LayoutHelper.createLinear(-2, -2))

        top_row.addView(info_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))
        hero.addView(top_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 14))

        # bottom row: release_date chip | spacer | install circle btn | menu circle btn
        bottom_row = LinearLayout(act)
        bottom_row.setOrientation(LinearLayout.HORIZONTAL)
        bottom_row.setGravity(Gravity.TOP)

        # dates column (left) — release date + last updated
        release_date = str(p.get("release_date") or "").strip()
        update_date = str(p.get("update_date") or "").strip()

        def _format_date(raw, prefix):
            # parses DD.MM.YY or DD.MM.YYYY, returns "Prefix: N ago"
            try:
                parts = raw.split(".")
                if len(parts) != 3:
                    return f"{prefix}: {raw}"
                day, month, year_raw = int(parts[0]), int(parts[1]), int(parts[2])
                year = (2000 + year_raw) if year_raw < 100 else year_raw
                from java.util import Calendar
                rel = Calendar.getInstance()
                rel.set(year, month - 1, day, 0, 0, 0)
                rel.set(Calendar.MILLISECOND, 0)
                now = Calendar.getInstance()
                now.set(Calendar.HOUR_OF_DAY, 0)
                now.set(Calendar.MINUTE, 0)
                now.set(Calendar.SECOND, 0)
                now.set(Calendar.MILLISECOND, 0)
                diff_ms = now.getTimeInMillis() - rel.getTimeInMillis()
                diff_days = int(diff_ms // (1000 * 60 * 60 * 24))
                if diff_days < 0:
                    return f"{prefix}: {raw}"
                if diff_days == 0:
                    ago = "Today"
                elif diff_days == 1:
                    ago = "Yesterday"
                elif diff_days < 30:
                    ago = f"{diff_days} days ago"
                elif diff_days < 365:
                    months = diff_days // 30
                    ago = f"{months} month ago" if months == 1 else f"{months} months ago"
                else:
                    years = diff_days // 365
                    ago = f"{years} year ago" if years == 1 else f"{years} years ago"
                return f"{prefix}: {ago}"
            except Exception:
                return f"{prefix}: {raw}"

        if release_date or update_date:
            dates_col = LinearLayout(act)
            dates_col.setOrientation(LinearLayout.VERTICAL)
            dates_col.setGravity(Gravity.TOP)

            if release_date:
                date_tv = TextView(act)
                date_tv.setText(_format_date(release_date, "Release date"))
                date_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                date_tv.setTextColor(text_color)
                date_tv.setSingleLine(True)
                date_tv.setHorizontalFadingEdgeEnabled(True)
                date_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
                try:
                    date_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    date_tv.setTypeface(AndroidUtilities.bold())
                dates_col.addView(date_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 2))

            effective_update = update_date if update_date else release_date
            if effective_update:
                update_tv = TextView(act)
                update_tv.setText(_format_date(effective_update, "Last updated"))
                update_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                update_tv.setTextColor(text_color)
                update_tv.setSingleLine(True)
                update_tv.setHorizontalFadingEdgeEnabled(True)
                update_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
                try:
                    update_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    update_tv.setTypeface(AndroidUtilities.bold())
                dates_col.addView(update_tv, LayoutHelper.createLinear(-1, -2))

            bottom_row.addView(dates_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP))
        else:
            spacer = View(act)
            bottom_row.addView(spacer, LayoutHelper.createLinear(0, 1, 1.0))

        # install circle button
        has_link = bool(p.get("link") or p.get("raw"))
        deps = p.get("deps") or []

        if has_link:
            from ..PluginListActivity.fragment import _is_min_version_satisfied
            plugin_min_ver = p.get("min_version")
            is_available = (not plugin_min_ver) or _is_min_version_satisfied(plugin_min_ver)

            try:
                btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
                btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            except Exception:
                from android.graphics import Color
                btn_base = Color.parseColor("#2196F3")
                btn_pressed = Color.parseColor("#1976D2")

            circle_size = AndroidUtilities.dp(44)

            install_btn = FrameLayout(act)
            install_btn.setClickable(True)
            install_btn.setFocusable(True)

            if is_available:
                btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                try:
                    from android.graphics.drawable import GradientDrawable as _GD
                    circle_bg = _GD()
                    circle_bg.setShape(_GD.OVAL)
                    circle_bg.setColor(btn_base)
                    install_btn.setBackground(circle_bg)
                except Exception:
                    pass
            else:
                gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                r = (gray >> 16) & 0xFF
                g = (gray >> 8) & 0xFF
                b = gray & 0xFF
                bg_gray = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                try:
                    from android.graphics.drawable import GradientDrawable as _GD
                    circle_bg = _GD()
                    circle_bg.setShape(_GD.OVAL)
                    circle_bg.setColor(bg_gray)
                    install_btn.setBackground(circle_bg)
                except Exception:
                    pass
                btn_text_color = gray
                install_btn.setEnabled(False)

            install_label_container = LinearLayout(act)
            install_label_container.setOrientation(LinearLayout.HORIZONTAL)
            install_label_container.setGravity(Gravity.CENTER)
            install_icon = ImageView(act)
            install_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                install_icon.setImageResource(_resolve_icon("msg_download_remix"))
                install_icon.setColorFilter(btn_text_color)
            except Exception:
                pass
            install_label_container.addView(install_icon, LayoutHelper.createLinear(22, 22, Gravity.CENTER))
            install_btn.addView(install_label_container, FrameLayout.LayoutParams(circle_size, circle_size))

            if is_available:
                _install_ui_ref = self.install_ui
                _all_plugins_ref = self.all_plugins

                def _set_loading(_btn, _label, _btn_text_color, _act, isLoading):
                    try:
                        _btn.setEnabled(not isLoading)
                        _btn.removeAllViews()
                        if isLoading:
                            try:
                                from org.telegram.ui.Components import CircularProgressDrawable
                                d = CircularProgressDrawable(_btn_text_color)
                                try:
                                    d.size = float(AndroidUtilities.dp(20))
                                    d.thickness = float(AndroidUtilities.dp(2))
                                except Exception:
                                    pass
                                spinner = ImageView(_act)
                                spinner.setImageDrawable(d)
                                spinner.setScaleType(ImageView.ScaleType.CENTER)
                                spin_lp = FrameLayout.LayoutParams(circle_size, circle_size)
                                spin_lp.gravity = Gravity.CENTER
                                _btn.addView(spinner, spin_lp)
                            except Exception:
                                pb = ProgressBar(_act)
                                try:
                                    pb.setIndeterminate(True)
                                    from android.content.res import ColorStateList
                                    pb.setIndeterminateTintList(ColorStateList.valueOf(_btn_text_color))
                                except Exception:
                                    pass
                                pb_lp = FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                                pb_lp.gravity = Gravity.CENTER
                                _btn.addView(pb, pb_lp)
                        else:
                            _btn.addView(_label, FrameLayout.LayoutParams(circle_size, circle_size))
                    except Exception as e:
                        log(f"pluginProfile: _set_loading error: {e}")

                def _do_install(_p, _install_ui, _all, _btn, _label, _btn_text_color, _act,
                               on_finish_override=None):
                    from ...core import install_plugin
                    if not on_finish_override:
                        _set_loading(_btn, _label, _btn_text_color, _act, True)

                    # check if cached so we can delay the spinner removal
                    cached = False
                    try:
                        from org.telegram.messenger import ApplicationLoader as _AL
                        import os as _os
                        from ...core import _get_plugin_cache_path, _sha256_file
                        _pkg = _AL.applicationContext.getPackageName()
                        _url = _p.get("link") or _p.get("raw") or ""
                        _fname = _url.split("/")[-1] or f"{_p.get('id')}.plugin"
                        _cp = _get_plugin_cache_path(_pkg, _fname)
                        _eh = _p.get("hash") or ""
                        if _eh and _os.path.exists(_cp):
                            cached = _eh == _sha256_file(_cp)
                    except Exception:
                        pass

                    def _finish(ok):
                        if on_finish_override:
                            run_on_ui_thread(lambda: on_finish_override(ok))
                        else:
                            delay = 1.0 if cached else 0.0
                            if delay:
                                import threading as _t
                                _t.Timer(delay, lambda: run_on_ui_thread(
                                    lambda: _set_loading(_btn, _label, _btn_text_color, _act, False)
                                )).start()
                            else:
                                run_on_ui_thread(lambda: _set_loading(_btn, _label, _btn_text_color, _act, False))

                    install_plugin(_p, on_finish=_finish, install_ui=_install_ui, all_plugins=_all)

                _unavail_hint_ref = [None]

                def _show_all_unavail_hint(_btn, _act):
                    try:
                        from org.telegram.ui.Stories.recorder import HintView2
                        from android.text import Layout
                        prev = _unavail_hint_ref[0]
                        if prev is not None:
                            try:
                                prev.hide()
                                prev.getParent().removeView(prev)
                            except Exception:
                                pass
                            _unavail_hint_ref[0] = None
                        dv = _act.getWindow().getDecorView()
                        hint = (
                            HintView2(_btn.getContext(), 3)
                            .setMultilineText(True)
                            .setBgColor(Theme.getColor(Theme.key_undo_background))
                            .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                            .setText(str(strings["plugin_version_below_min"]))
                            .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                            .allowBlur(True)
                            .setRounding(AndroidUtilities.dp(12))
                        )
                        try:
                            hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                        except Exception:
                            pass
                        dv.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                        _unavail_hint_ref[0] = hint
                        def _position():
                            try:
                                btn_loc = [0, 0]
                                _btn.getLocationInWindow(btn_loc)
                                dv_loc = [0, 0]
                                dv.getLocationInWindow(dv_loc)
                                cell_y = btn_loc[1] - dv_loc[1]
                                center_x = float(btn_loc[0] - dv_loc[0]) + float(_btn.getMeasuredWidth()) / 2.0
                                hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                                hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                                hint.setDuration(3500)
                                hint.show()
                            except Exception as e:
                                log(f"pluginProfile: unavail hint position error: {e}")
                        run_on_ui_thread(_position)
                    except Exception as e:
                        log(f"pluginProfile: unavail hint error: {e}")

                def onInstallClick(v, _p=p, _install_ui=_install_ui_ref, _all=_all_plugins_ref,
                                   _btn=install_btn, _label=install_label_container,
                                   _btn_text_color=btn_text_color, _act=act):
                    versions = _p.get("versions") or {}
                    if not versions:
                        _do_install(_p, _install_ui, _all, _btn, _label, _btn_text_color, _act)
                        return
                    from ..PluginListActivity.fragment import _is_min_version_satisfied
                    from .versionPicker import _build_version_entries
                    all_entries = _build_version_entries(_p)
                    hide_unavail = False
                    try:
                        from elyx import settings as _s
                        hide_unavail = _s.get("hide_unavailable_plugins", False)
                    except Exception:
                        pass
                    avail = [e for e in all_entries if not e["min_version"] or _is_min_version_satisfied(e["min_version"])]
                    if hide_unavail and not avail:
                        _show_all_unavail_hint(_btn, _act)
                        return
                    if len(avail) == 1 and (hide_unavail or len(all_entries) == 1):
                        e = avail[0]
                        versioned = dict(_p)
                        versioned["link"] = e["link"]
                        if e["min_version"]:
                            versioned["min_version"] = e["min_version"]
                        _do_install(versioned, _install_ui, _all, _btn, _label, _btn_text_color, _act)
                        return
                    _show_version_picker(_act, _p, _install_ui, _all, _btn, _label, _btn_text_color, _do_install)

                install_btn.setOnClickListener(OnClickListener(onInstallClick))

            install_lp = LinearLayout.LayoutParams(circle_size, circle_size)
            install_lp.rightMargin = AndroidUtilities.dp(8)
            bottom_row.addView(install_btn, install_lp)

        # save circle button (msg_saved icon, yellow when active)
        _save_size = AndroidUtilities.dp(44)
        save_btn_hero = FrameLayout(act)
        save_btn_hero.setClickable(True)
        save_btn_hero.setFocusable(True)

        _plugin_id = str(p.get("id") or "")
        _repo_id_save = self.repo_id or ""

        def _is_saved():
            try:
                from ...utils.localConfig import LocalConfig
                saved = LocalConfig.get("saved_plugins", {})
                return isinstance(saved, dict) and _plugin_id in saved
            except Exception:
                return False

        def _make_circle_bg(color):
            try:
                from android.graphics.drawable import GradientDrawable as _GD3
                bg = _GD3()
                bg.setShape(_GD3.OVAL)
                bg.setColor(color)
                return bg
            except Exception:
                return None

        def _gray_fill():
            ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            r = (ic_color >> 16) & 0xFF
            g = (ic_color >> 8) & 0xFF
            b = ic_color & 0xFF
            return ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value

        def _yellow_fill():
            try:
                yc = Theme.getColor(Theme.key_avatar_nameInMessagePink)
                r = (yc >> 16) & 0xFF
                g = (yc >> 8) & 0xFF
                b = yc & 0xFF
                return ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
            except Exception:
                return ctypes.c_int32((0x33 << 24) | (0xFF << 16) | (0xCC << 8) | 0x00).value

        def _apply_save_state(active):
            try:
                fill = _yellow_fill() if active else _gray_fill()
                bg = _make_circle_bg(fill)
                if bg:
                    save_btn_hero.setBackground(bg)
            except Exception as e:
                log(f"pluginProfile: _apply_save_state error: {e}")

        # use RLottieImageView for msg_stories_saved animation
        save_iv_ref = [None]
        try:
            from org.telegram.ui.Components import RLottieImageView
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            anim_id = int(getattr(R_tg.raw, "msg_stories_saved", 0))
            if anim_id:
                lottie_iv = RLottieImageView(act)
                lottie_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                lottie_iv.setAnimation(anim_id, 28, 28)
                lottie_iv.setAutoRepeat(False)
                save_iv_ref[0] = lottie_iv
                save_btn_hero.addView(lottie_iv, FrameLayout.LayoutParams(_save_size, _save_size))
            else:
                raise Exception("anim not found")
        except Exception:
            # fallback to static icon
            save_iv = ImageView(act)
            save_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                save_iv.setImageResource(_resolve_icon("msg_saved"))
            except Exception:
                pass
            save_iv_ref[0] = save_iv
            save_btn_hero.addView(save_iv, FrameLayout.LayoutParams(_save_size, _save_size))

        def _apply_save_color(active):
            try:
                color = Theme.getColor(Theme.key_avatar_nameInMessagePink) if active else Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                iv = save_iv_ref[0]
                if iv is not None:
                    iv.setColorFilter(color)
            except Exception:
                pass

        _apply_save_state(_is_saved())
        _apply_save_color(_is_saved())

        def onSaveClick(v):
            try:
                from ...utils.localConfig import LocalConfig
                saved = LocalConfig.get("saved_plugins", {})
                if not isinstance(saved, dict):
                    saved = {}
                if _plugin_id in saved:
                    del saved[_plugin_id]
                    active = False
                else:
                    saved[_plugin_id] = _repo_id_save
                    active = True
                LocalConfig.set("saved_plugins", saved)
                _apply_save_state(active)
                _apply_save_color(active)
                if active:
                    try:
                        iv = save_iv_ref[0]
                        iv.setProgress(0)
                        iv.playAnimation()
                    except Exception:
                        pass
            except Exception as e:
                log(f"pluginProfile: onSaveClick error: {e}")
        save_btn_hero.setOnClickListener(OnClickListener(onSaveClick))

        save_lp = LinearLayout.LayoutParams(_save_size, _save_size)
        save_lp.rightMargin = AndroidUtilities.dp(8)
        bottom_row.addView(save_btn_hero, save_lp)

        # menu circle button (three dots)
        menu_size = AndroidUtilities.dp(44)
        menu_btn_hero = FrameLayout(act)
        menu_btn_hero.setClickable(True)
        menu_btn_hero.setFocusable(True)
        try:
            ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            r = (ic_color >> 16) & 0xFF
            g = (ic_color >> 8) & 0xFF
            b = ic_color & 0xFF
            ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
            ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
            try:
                from android.graphics.drawable import GradientDrawable as _GD2
                circle_menu_bg = _GD2()
                circle_menu_bg.setShape(_GD2.OVAL)
                circle_menu_bg.setColor(ic_fill)
                menu_btn_hero.setBackground(circle_menu_bg)
            except Exception:
                menu_btn_hero.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(22), ic_fill, ic_pressed
                ))
        except Exception:
            pass
        menu_iv = ImageView(act)
        menu_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        try:
            menu_iv.setImageResource(_resolve_icon("ic_ab_other"))
            menu_iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        menu_btn_hero.addView(menu_iv, FrameLayout.LayoutParams(menu_size, menu_size))

        def onHeroMenuClick(v):
            _show_plugin_menu(act, p, menu_btn_hero, repo_id=self.repo_id)
        menu_btn_hero.setOnClickListener(OnClickListener(onHeroMenuClick))
        bottom_row.addView(menu_btn_hero, LinearLayout.LayoutParams(menu_size, menu_size))

        hero.addView(bottom_row, LayoutHelper.createLinear(-1, -2))

        # archived banner
        archived_raw = str(p.get("archived") or "").strip()
        if archived_raw:
            def _parse_archived_date(raw):
                try:
                    parts = raw.split(".")
                    if len(parts) != 3:
                        return raw
                    day, month, year_raw = int(parts[0]), int(parts[1]), int(parts[2])
                    year = (2000 + year_raw) if year_raw < 100 else year_raw
                    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    return f"{month_names[month - 1]} {day}, {year}"
                except Exception:
                    return raw

            try:
                archived_color = Theme.getColor(Theme.key_color_yellow)
            except Exception:
                archived_color = 0xFFFFAA00

            ar = (archived_color >> 16) & 0xFF
            ag = (archived_color >> 8) & 0xFF
            ab = archived_color & 0xFF
            archived_bg_color = ctypes.c_int32((0x22 << 24) | (ar << 16) | (ag << 8) | ab).value

            archived_banner = LinearLayout(act)
            archived_banner.setOrientation(LinearLayout.HORIZONTAL)
            archived_banner.setGravity(Gravity.CENTER_VERTICAL)
            archived_banner.setPadding(
                AndroidUtilities.dp(12), AndroidUtilities.dp(10),
                AndroidUtilities.dp(12), AndroidUtilities.dp(10)
            )
            try:
                from android.graphics.drawable import GradientDrawable as _GDA
                arc_bg = _GDA()
                arc_bg.setShape(_GDA.RECTANGLE)
                arc_bg.setCornerRadius(AndroidUtilities.dp(10))
                arc_bg.setColor(archived_bg_color)
                archived_banner.setBackground(arc_bg)
            except Exception:
                pass

            arc_icon = ImageView(act)
            arc_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                arc_icon.setImageResource(_resolve_icon("msg_archive"))
                arc_icon.setColorFilter(archived_color)
            except Exception:
                pass
            archived_banner.addView(arc_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 10, 0))

            arc_tv = TextView(act)
            arc_tv.setText(f"This plugin was archived by the owner on {_parse_archived_date(archived_raw)}. The plugin will no longer be updated.")
            arc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            arc_tv.setTextColor(archived_color)
            try:
                arc_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                arc_tv.setTypeface(AndroidUtilities.bold())
            arc_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
            archived_banner.addView(arc_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            _unavail_archived_hint_ref = [None]

            def onArchivedClick(v):
                try:
                    from org.telegram.ui.Stories.recorder import HintView2
                    from android.text import Layout
                    prev = _unavail_archived_hint_ref[0]
                    if prev is not None:
                        try:
                            prev.hide()
                            prev.getParent().removeView(prev)
                        except Exception:
                            pass
                        _unavail_archived_hint_ref[0] = None
                    dv = act.getWindow().getDecorView()
                    hint = (
                        HintView2(v.getContext(), 3)
                        .setMultilineText(True)
                        .setBgColor(Theme.getColor(Theme.key_undo_background))
                        .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                        .setText("The plugin will no longer be updated. But it might still work.")
                        .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                        .allowBlur(True)
                        .setRounding(AndroidUtilities.dp(12))
                    )
                    try:
                        hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                    except Exception:
                        pass
                    dv.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                    _unavail_archived_hint_ref[0] = hint
                    def _position():
                        try:
                            loc = [0, 0]
                            v.getLocationInWindow(loc)
                            dv_loc = [0, 0]
                            dv.getLocationInWindow(dv_loc)
                            cell_y = loc[1] - dv_loc[1]
                            center_x = float(loc[0] - dv_loc[0]) + float(v.getMeasuredWidth()) / 2.0
                            hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                            hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                            hint.setDuration(3500)
                            hint.show()
                        except Exception as e:
                            log(f"pluginProfile: archived hint position error: {e}")
                    run_on_ui_thread(_position)
                except Exception as e:
                    log(f"pluginProfile: archived hint error: {e}")

            archived_banner.setClickable(True)
            archived_banner.setFocusable(True)
            archived_banner.setOnClickListener(OnClickListener(onArchivedClick))

            hero.addView(archived_banner, LayoutHelper.createLinear(-1, -2, 0, 12, 0, 0))

        root.addView(hero, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # tab bar + tab content
        tab_names = [
            str(strings.pp_tab_description),
            str(strings.pp_tab_gallery),
            str(strings.pp_tab_changes),
        ]
        selected_tab = [0]

        # tab bar: FrameLayout with sliding indicator behind tab text
        tab_bar_frame = FrameLayout(act)
        tab_bar_bg = GradientDrawable()
        tab_bar_bg.setShape(GradientDrawable.RECTANGLE)
        tab_bar_bg.setCornerRadius(AndroidUtilities.dp(20))
        try:
            base = Theme.getColor(Theme.key_windowBackgroundWhite)
            r_c = (base >> 16) & 0xFF
            g_c = (base >> 8) & 0xFF
            b_c = base & 0xFF
            tab_bar_fill = ctypes.c_int32((0xDD << 24) | (r_c << 16) | (g_c << 8) | b_c).value
        except Exception:
            tab_bar_fill = 0xDD2A2A2A
        tab_bar_bg.setColor(tab_bar_fill)
        tab_bar_frame.setBackground(tab_bar_bg)
        tab_bar_frame.setPadding(
            AndroidUtilities.dp(4), AndroidUtilities.dp(4),
            AndroidUtilities.dp(4), AndroidUtilities.dp(4)
        )

        # sliding indicator
        accent_c = Theme.getColor(Theme.key_featuredStickers_addButton)
        r_a = (accent_c >> 16) & 0xFF
        g_a = (accent_c >> 8) & 0xFF
        b_a = accent_c & 0xFF
        ind_fill = ctypes.c_int32((0x33 << 24) | (r_a << 16) | (g_a << 8) | b_a).value
        ind_bg = GradientDrawable()
        ind_bg.setShape(GradientDrawable.RECTANGLE)
        ind_bg.setCornerRadius(AndroidUtilities.dp(16))
        ind_bg.setColor(ind_fill)
        indicator = View(act)
        indicator.setBackground(ind_bg)
        # height = tab text height: padding top+bottom + ~14sp text
        _ind_h = AndroidUtilities.dp(8 + 8) + AndroidUtilities.dp(14) + AndroidUtilities.dp(4)
        indicator_lp = FrameLayout.LayoutParams(0, _ind_h)
        indicator_lp.gravity = Gravity.CENTER_VERTICAL
        tab_bar_frame.addView(indicator, indicator_lp)

        tab_bar = LinearLayout(act)
        tab_bar.setOrientation(LinearLayout.HORIZONTAL)
        tab_bar_frame.addView(tab_bar, FrameLayout.LayoutParams(-1, -2))

        # tab content card (swapped on tab click)
        tab_content = LinearLayout(act)
        tab_content.setOrientation(LinearLayout.VERTICAL)
        tab_content_bg = _make_card_bg(act)
        if tab_content_bg:
            tab_content.setBackground(tab_content_bg)
        tab_content.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(14),
            AndroidUtilities.dp(16), AndroidUtilities.dp(14)
        )

        desc = self._get_localized_description(p)
        readme_url = str(p.get("readme") or "").strip()

        def _make_icon_btn(icon_name):
            btn = FrameLayout(act)
            btn.setClickable(True)
            btn.setFocusable(True)
            try:
                ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                r = (ic_color >> 16) & 0xFF
                g = (ic_color >> 8) & 0xFF
                b = ic_color & 0xFF
                ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(8), ic_fill, ic_pressed
                ))
            except Exception:
                pass
            btn.setPadding(
                AndroidUtilities.dp(6), AndroidUtilities.dp(4),
                AndroidUtilities.dp(6), AndroidUtilities.dp(4)
            )
            iv = ImageView(act)
            iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                iv.setImageResource(_resolve_icon(icon_name))
                iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass
            btn.addView(iv, FrameLayout.LayoutParams(
                AndroidUtilities.dp(16), AndroidUtilities.dp(16)
            ))
            return btn

        def _build_desc_content():
            wrap = LinearLayout(act)
            wrap.setOrientation(LinearLayout.VERTICAL)

            show_extended = False
            try:
                from elyx import settings as _s
                show_extended = _s.get("show_extended_desc", False)
            except Exception:
                pass

            use_extended = show_extended and bool(readme_url)

            desc_header_row = LinearLayout(act)
            desc_header_row.setOrientation(LinearLayout.HORIZONTAL)
            desc_header_row.setGravity(Gravity.CENTER_VERTICAL)
            header_label = str(strings.pp_section_extended_description) if use_extended else str(strings.pp_section_description)
            desc_header_row.addView(
                _make_section_header(act, header_label),
                LayoutHelper.createLinear(0, -2, 1.0)
            )

            wrap.addView(desc_header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))

            if use_extended:
                # show spinner + async loaded readme content
                spinner_frame = FrameLayout(act)
                try:
                    from org.telegram.ui.Components import CircularProgressDrawable
                    spin_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                    d = CircularProgressDrawable(spin_color)
                    try:
                        d.size = float(AndroidUtilities.dp(24))
                        d.thickness = float(AndroidUtilities.dp(2))
                    except Exception:
                        pass
                    self._changelog_spinner = d
                    spin_iv = ImageView(act)
                    spin_iv.setImageDrawable(d)
                    spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                    spinner_frame.addView(spin_iv, LayoutHelper.createFrame(32, 32, Gravity.CENTER, 0, 8, 0, 8))
                except Exception:
                    pass
                wrap.addView(spinner_frame, LayoutHelper.createLinear(-1, -2))

                content_tv = TextView(act)
                content_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                content_tv.setVisibility(View.GONE)
                wrap.addView(content_tv, LayoutHelper.createLinear(-1, -2))

                # shared ref: filled after fetch completes, used by translate button
                fetched_readme = [""]

                def _show_readme_text(text, centered=False):
                    spinner_frame.setVisibility(View.GONE)
                    content_tv.setVisibility(View.VISIBLE)
                    if centered:
                        content_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                        content_tv.setTextColor(gray_color)
                        content_tv.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
                        content_tv.setText(text)
                    else:
                        fetched_readme[0] = text
                        content_tv.setGravity(Gravity.LEFT)
                        content_tv.setTextColor(text_color)
                        content_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
                        try:
                            from com.exteragram.messenger.utils.text import LocaleUtils
                            from android.text.method import LinkMovementMethod
                            content_tv.setText(LocaleUtils.fullyFormatText(text))
                            content_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                            content_tv.setMovementMethod(LinkMovementMethod.getInstance())
                        except Exception:
                            content_tv.setText(text)

                import threading as _threading
                import requests as _req

                def _fetch_readme():
                    try:
                        r = _req.get(readme_url, timeout=10)
                        if r.status_code != 200:
                            # readme not available — fall back to standard desc
                            def _fallback():
                                spinner_frame.setVisibility(View.GONE)
                                content_tv.setVisibility(View.VISIBLE)
                                content_tv.setGravity(Gravity.LEFT)
                                content_tv.setTextColor(text_color)
                                content_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
                                if desc:
                                    try:
                                        from com.exteragram.messenger.utils.text import LocaleUtils
                                        from android.text.method import LinkMovementMethod
                                        content_tv.setText(LocaleUtils.fullyFormatText(desc))
                                        content_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                                        content_tv.setMovementMethod(LinkMovementMethod.getInstance())
                                    except Exception:
                                        content_tv.setText(desc)
                                else:
                                    _show_readme_text(str(strings.pp_changelog_empty), centered=True)
                            run_on_ui_thread(_fallback)
                            return
                        md = r.text
                        run_on_ui_thread(lambda t=md: _show_readme_text(t))
                    except Exception as e:
                        log(f"pluginProfile: readme fetch error: {e}")
                        run_on_ui_thread(lambda: _show_readme_text(desc if desc else str(strings.pp_changelog_empty), centered=not bool(desc)))

                _threading.Thread(target=_fetch_readme, daemon=True).start()

                buttons_row_ext = LinearLayout(act)
                buttons_row_ext.setOrientation(LinearLayout.HORIZONTAL)
                buttons_row_ext.setGravity(Gravity.CENTER_VERTICAL | Gravity.FILL_HORIZONTAL)

                def _make_text_btn_ext(icon_name, text):
                    btn = LinearLayout(act)
                    btn.setOrientation(LinearLayout.HORIZONTAL)
                    btn.setGravity(Gravity.CENTER)
                    btn.setClickable(True)
                    btn.setFocusable(True)
                    try:
                        ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                        r = (ic_color >> 16) & 0xFF
                        g = (ic_color >> 8) & 0xFF
                        b = ic_color & 0xFF
                        ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                        ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                            AndroidUtilities.dp(16), ic_fill, ic_pressed
                        ))
                    except Exception:
                        pass
                    btn.setPadding(
                        AndroidUtilities.dp(10), AndroidUtilities.dp(8),
                        AndroidUtilities.dp(10), AndroidUtilities.dp(8)
                    )
                    iv = ImageView(act)
                    iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    try:
                        iv.setImageResource(_resolve_icon(icon_name))
                        iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                    except Exception:
                        pass
                    btn.addView(iv, LayoutHelper.createLinear(16, 16, Gravity.CENTER_VERTICAL, 0, 0, 4, 0))
                    tv = TextView(act)
                    tv.setText(text)
                    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                    try:
                        tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        tv.setTypeface(AndroidUtilities.bold())
                    btn.addView(tv, LayoutHelper.createLinear(-2, -2))
                    return btn

                translate_btn_ext = _make_text_btn_ext("msg_replace", str(strings["translate"]))

                def onTranslateClickExt(v, _p=p, _readme=fetched_readme):
                    from ..PluginListActivity.translation import translate_plugin
                    text = _readme[0] if _readme[0] else None
                    translate_plugin(_p, text_override=text)
                translate_btn_ext.setOnClickListener(OnClickListener(onTranslateClickExt))

                copy_btn_ext = _make_text_btn_ext("msg_copy", str(strings["copy"]))

                def onCopyClickExt(v, _desc=desc):
                    try:
                        from android.content import ClipData
                        clipboard_manager = act.getSystemService(act.CLIPBOARD_SERVICE)
                        clip = ClipData.newPlainText("Plugin description", _desc)
                        clipboard_manager.setPrimaryClip(clip)
                        from ui.bulletin import BulletinHelper
                        BulletinHelper.show_success(strings.get("copied_to_clipboard", "Скопировано в буфер обмена"))
                    except Exception as e:
                        log(f"pluginProfile: copy description error: {e}")
                copy_btn_ext.setOnClickListener(OnClickListener(onCopyClickExt))

                ext_btns = [translate_btn_ext, copy_btn_ext]
                gap_ext = AndroidUtilities.dp(6)
                for i, btn in enumerate(ext_btns):
                    lp = LinearLayout.LayoutParams(0, -2, 1.0)
                    if i < len(ext_btns) - 1:
                        lp.rightMargin = gap_ext
                    buttons_row_ext.addView(btn, lp)

                wrap.addView(buttons_row_ext, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))
                return wrap

            # standard description
            desc_tv = TextView(act)
            desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            desc_tv.setTextColor(text_color)
            desc_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
            if desc:
                try:
                    from com.exteragram.messenger.utils.text import LocaleUtils
                    from android.text.method import LinkMovementMethod
                    desc_tv.setText(LocaleUtils.fullyFormatText(desc))
                    desc_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                    desc_tv.setMovementMethod(LinkMovementMethod.getInstance())
                except Exception:
                    desc_tv.setText(desc)
            wrap.addView(desc_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 12))

            buttons_row = LinearLayout(act)
            buttons_row.setOrientation(LinearLayout.HORIZONTAL)
            buttons_row.setGravity(Gravity.CENTER_VERTICAL)

            def _make_icon_only_btn(icon_name):
                # square icon-only button
                btn = FrameLayout(act)
                btn.setClickable(True)
                btn.setFocusable(True)
                size = AndroidUtilities.dp(36)
                try:
                    ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                    r = (ic_color >> 16) & 0xFF
                    g = (ic_color >> 8) & 0xFF
                    b = ic_color & 0xFF
                    ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                    ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(12), ic_fill, ic_pressed
                    ))
                except Exception:
                    pass
                iv = ImageView(act)
                iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                try:
                    iv.setImageResource(_resolve_icon(icon_name))
                    iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    pass
                btn.addView(iv, FrameLayout.LayoutParams(size, size))
                return btn

            def _make_text_btn(icon_name, text):
                btn = LinearLayout(act)
                btn.setOrientation(LinearLayout.HORIZONTAL)
                btn.setGravity(Gravity.CENTER)
                btn.setClickable(True)
                btn.setFocusable(True)
                try:
                    ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                    r = (ic_color >> 16) & 0xFF
                    g = (ic_color >> 8) & 0xFF
                    b = ic_color & 0xFF
                    ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                    ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(16), ic_fill, ic_pressed
                    ))
                except Exception:
                    pass
                btn.setPadding(
                    AndroidUtilities.dp(10), AndroidUtilities.dp(8),
                    AndroidUtilities.dp(10), AndroidUtilities.dp(8)
                )
                iv = ImageView(act)
                iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                try:
                    iv.setImageResource(_resolve_icon(icon_name))
                    iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    pass
                btn.addView(iv, LayoutHelper.createLinear(16, 16, Gravity.CENTER_VERTICAL, 0, 0, 4, 0))
                tv = TextView(act)
                tv.setText(text)
                tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                try:
                    tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    tv.setTypeface(AndroidUtilities.bold())
                btn.addView(tv, LayoutHelper.createLinear(-2, -2))
                return btn

            gap = AndroidUtilities.dp(6)

            translate_btn = _make_icon_only_btn("msg_replace")

            def onTranslateClick(v, _p=p):
                from ..PluginListActivity.translation import translate_plugin
                translate_plugin(_p)
            translate_btn.setOnClickListener(OnClickListener(onTranslateClick))

            copy_btn = _make_icon_only_btn("msg_copy")

            def onCopyClick(v, _desc=desc):
                try:
                    from android.content import ClipData
                    clipboard_manager = act.getSystemService(act.CLIPBOARD_SERVICE)
                    clip = ClipData.newPlainText("Plugin description", _desc)
                    clipboard_manager.setPrimaryClip(clip)
                    from ui.bulletin import BulletinHelper
                    BulletinHelper.show_success(strings.get("copied_to_clipboard", "Скопировано в буфер обмена"))
                except Exception as e:
                    log(f"pluginProfile: copy description error: {e}")
            copy_btn.setOnClickListener(OnClickListener(onCopyClick))

            tr_lp = LinearLayout.LayoutParams(-2, -2)
            tr_lp.rightMargin = gap
            buttons_row.addView(translate_btn, tr_lp)

            cp_lp = LinearLayout.LayoutParams(-2, -2)
            cp_lp.rightMargin = gap
            buttons_row.addView(copy_btn, cp_lp)

            if readme_url:
                extended_btn = _make_text_btn("msg_info", str(strings["plugin_view_button"]))

                def _raw_to_github(url):
                    # https://raw.githubusercontent.com/user/repo/refs/heads/branch/path
                    # → https://github.com/user/repo/blob/branch/path
                    try:
                        prefix = "https://raw.githubusercontent.com/"
                        if not url.startswith(prefix):
                            return url
                        rest = url[len(prefix):]
                        parts = rest.split("/")
                        # parts: [user, repo, "refs", "heads", branch, ...path]
                        if len(parts) >= 6 and parts[2] == "refs" and parts[3] == "heads":
                            user, repo, _, _, branch = parts[:5]
                            path = "/".join(parts[5:])
                            return f"https://github.com/{user}/{repo}/blob/{branch}/{path}"
                        # fallback: user/repo/branch/path (no refs/heads)
                        if len(parts) >= 4:
                            user, repo, branch = parts[:3]
                            path = "/".join(parts[3:])
                            return f"https://github.com/{user}/{repo}/blob/{branch}/{path}"
                    except Exception:
                        pass
                    return url

                def onExtendedClick(v, _url=readme_url, _act=act):
                    try:
                        if Browser and Uri:
                            Browser.openUrl(_act, Uri.parse(_raw_to_github(_url)), True, True, True, None, None, False, False, False)
                    except Exception as ex:
                        log(f"pluginProfile: extended_btn openUrl error: {ex}")
                extended_btn.setOnClickListener(OnClickListener(onExtendedClick))
                buttons_row.addView(extended_btn, LinearLayout.LayoutParams(0, -2, 1.0))

            wrap.addView(buttons_row, LayoutHelper.createLinear(-1, -2))
            return wrap

        def _build_stub_content():
            tv = TextView(act)
            tv.setText("It's not ready yet.")
            tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            tv.setTextColor(gray_color)
            tv.setGravity(Gravity.CENTER_HORIZONTAL)
            tv.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
            return tv

        changelog_url = str(p.get("changelog") or "").strip()

        fetched_changelog = [""]  # shared ref for translate button

        def _build_changelog_content():
            wrap = LinearLayout(act)
            wrap.setOrientation(LinearLayout.VERTICAL)

            spinner_frame = FrameLayout(act)
            try:
                from org.telegram.ui.Components import CircularProgressDrawable
                spin_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                d = CircularProgressDrawable(spin_color)
                try:
                    d.size = float(AndroidUtilities.dp(24))
                    d.thickness = float(AndroidUtilities.dp(2))
                except Exception:
                    pass
                self._changelog_spinner = d
                spin_iv = ImageView(act)
                spin_iv.setImageDrawable(d)
                spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                spinner_frame.addView(spin_iv, LayoutHelper.createFrame(32, 32, Gravity.CENTER, 0, 8, 0, 8))
            except Exception:
                pass
            wrap.addView(spinner_frame, LayoutHelper.createLinear(-1, -2))

            content_tv = TextView(act)
            content_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            content_tv.setVisibility(View.GONE)
            wrap.addView(content_tv, LayoutHelper.createLinear(-1, -2))

            def _show_text(text, centered=True):
                spinner_frame.setVisibility(View.GONE)
                content_tv.setVisibility(View.VISIBLE)
                if centered:
                    content_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                    content_tv.setTextColor(gray_color)
                    content_tv.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
                content_tv.setText(text)

            if not changelog_url:
                _show_text(str(strings.pp_changelog_empty))
                return wrap

            import threading
            import requests as _req

            def _fetch():
                try:
                    r = _req.get(changelog_url, timeout=10)
                    if r.status_code != 200:
                        run_on_ui_thread(lambda: _show_text(str(strings.pp_changelog_empty)))
                        return
                    md = r.text
                    fetched_changelog[0] = md
                    def _apply(t=md):
                        try:
                            spinner_frame.setVisibility(View.GONE)
                            content_tv.setVisibility(View.VISIBLE)
                            content_tv.setGravity(Gravity.LEFT)
                            content_tv.setTextColor(text_color)
                            content_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
                            from com.exteragram.messenger.utils.text import LocaleUtils
                            from android.text.method import LinkMovementMethod
                            content_tv.setText(LocaleUtils.fullyFormatText(t))
                            content_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                            content_tv.setMovementMethod(LinkMovementMethod.getInstance())
                        except Exception:
                            _show_text(t, centered=False)
                    run_on_ui_thread(_apply)
                except Exception as e:
                    log(f"pluginProfile: changelog fetch error: {e}")
                    run_on_ui_thread(lambda: _show_text(str(strings.pp_changelog_empty)))

            threading.Thread(target=_fetch, daemon=True).start()
            return wrap

        _tab_builders = [_build_desc_content, _build_stub_content, _build_changelog_content]

        def _move_indicator(tb, animate):
            try:
                w = tb.getWidth()
                x = float(tb.getLeft())
                pad = AndroidUtilities.dp(4)
                lp = indicator.getLayoutParams()
                lp.width = w
                indicator.setLayoutParams(lp)
                if animate:
                    indicator.animate().translationX(x).setDuration(200).start()
                else:
                    indicator.setTranslationX(x)
            except Exception as e:
                log(f"pluginProfile: _move_indicator error: {e}")

        def _switch_tab(idx, tab_btns):
            selected_tab[0] = idx
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
            for i, tb in enumerate(tab_btns):
                if i == idx:
                    tb.setTextColor(accent)
                    try:
                        tb.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        tb.setTypeface(AndroidUtilities.bold())
                else:
                    tb.setTextColor(gray_color)
                    try:
                        tb.setTypeface(AndroidUtilities.getTypeface("fonts/r.ttf"))
                    except Exception:
                        pass
            # move indicator to selected tab
            _move_indicator(tab_btns[idx], animate=True)
            # rebuild content
            tab_content.removeAllViews()
            try:
                tab_content.addView(_tab_builders[idx](), LayoutHelper.createLinear(-1, -2))
            except Exception as e:
                log(f"pluginProfile: tab content build error: {e}")

        tab_btns = []
        for i, name in enumerate(tab_names):
            tb = TextView(act)
            tb.setText(name)
            tb.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            tb.setGravity(Gravity.CENTER)
            tb.setClickable(True)
            tb.setFocusable(True)
            tb.setPadding(
                AndroidUtilities.dp(14), AndroidUtilities.dp(8),
                AndroidUtilities.dp(14), AndroidUtilities.dp(8)
            )
            tab_btns.append(tb)
            tab_bar.addView(tb, LayoutHelper.createLinear(0, -2, 1.0))

        _switch_tab(0, tab_btns)

        # reposition indicator after first layout pass (sizes are 0 before)
        def _init_indicator_on_layout():
            try:
                from android.view import ViewTreeObserver
                vto = tab_bar.getViewTreeObserver()

                class _LayoutListener(dynamic_proxy(ViewTreeObserver.OnGlobalLayoutListener)):
                    def onGlobalLayout(self):
                        try:
                            _move_indicator(tab_btns[selected_tab[0]], animate=False)
                            tab_bar.getViewTreeObserver().removeOnGlobalLayoutListener(self)
                        except Exception:
                            pass
                vto.addOnGlobalLayoutListener(_LayoutListener())
            except Exception as e:
                log(f"pluginProfile: layout listener error: {e}")
        _init_indicator_on_layout()

        desc_extra = LinearLayout(act)
        desc_extra.setOrientation(LinearLayout.VERTICAL)

        _orig_switch_tab = _switch_tab

        def _switch_tab(idx, tab_btns):
            _orig_switch_tab(idx, tab_btns)
            desc_extra.setVisibility(View.VISIBLE if idx == 0 else View.GONE)
            translate_bar.setVisibility(View.VISIBLE if idx == 2 and changelog_url else View.GONE)

        for i, tb in enumerate(tab_btns):
            def _on_tab_click(v, _i=i, _btns=tab_btns):
                _switch_tab(_i, _btns)
            tb.setOnClickListener(OnClickListener(_on_tab_click))

        root.addView(tab_bar_frame, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))
        root.addView(tab_content, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))

        # translate button shown only on changelog tab
        translate_bar = LinearLayout(act)
        translate_bar.setOrientation(LinearLayout.HORIZONTAL)
        translate_bar.setGravity(Gravity.CENTER)
        translate_bar.setVisibility(View.GONE)

        try:
            btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
            btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            from android.graphics import Color as _C
            btn_base = _C.parseColor("#2196F3")
            btn_pressed = _C.parseColor("#1976D2")

        translate_bar_btn = LinearLayout(act)
        translate_bar_btn.setOrientation(LinearLayout.HORIZONTAL)
        translate_bar_btn.setGravity(Gravity.CENTER)
        translate_bar_btn.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(12),
            AndroidUtilities.dp(20), AndroidUtilities.dp(12)
        )
        translate_bar_btn.setClickable(True)
        translate_bar_btn.setFocusable(True)
        translate_bar_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(14), btn_base, btn_pressed
        ))

        translate_bar_label = TextView(act)
        translate_bar_label.setText(str(strings["translate"]))
        translate_bar_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        try:
            translate_bar_label.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        except Exception:
            translate_bar_label.setTextColor(0xFFFFFFFF)
        try:
            translate_bar_label.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            translate_bar_label.setTypeface(AndroidUtilities.bold())
        translate_bar_btn.addView(translate_bar_label)

        def onTranslateBarClick(v, _p=p):
            text = fetched_changelog[0]
            if not text.strip():
                return
            import threading
            import requests as _req
            from ..PluginListActivity.translation import _show_translate_sheet
            from java.util import Locale

            def _set_loading(loading):
                try:
                    translate_bar_btn.setEnabled(not loading)
                    translate_bar_btn.removeAllViews()
                    if loading:
                        try:
                            from org.telegram.ui.Components import CircularProgressDrawable
                            spin_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                            d = CircularProgressDrawable(spin_color)
                            try:
                                d.size = float(AndroidUtilities.dp(20))
                                d.thickness = float(AndroidUtilities.dp(2))
                            except Exception:
                                pass
                            spin_iv = ImageView(act)
                            spin_iv.setImageDrawable(d)
                            spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                            translate_bar_btn.addView(spin_iv, LayoutHelper.createLinear(20, 20, Gravity.CENTER))
                        except Exception:
                            translate_bar_btn.addView(translate_bar_label)
                    else:
                        translate_bar_btn.addView(translate_bar_label)
                except Exception as e:
                    log(f"pluginProfile: translate _set_loading error: {e}")

            def _do_translate():
                try:
                    target_lang = Locale.getDefault().getLanguage() or "en"
                    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={_req.utils.quote(text)}"
                    response = _req.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        # collect all translation chunks
                        translated = "".join(
                            chunk[0] for chunk in data[0] if chunk and chunk[0]
                        ) if data and data[0] else text
                    else:
                        translated = text
                    def _done():
                        _show_translate_sheet(act, _p, target_lang, translated)
                        threading.Timer(1.0, lambda: run_on_ui_thread(lambda: _set_loading(False))).start()
                    run_on_ui_thread(_done)
                except Exception as e:
                    log(f"pluginProfile: changelog translate error: {e}")
                    run_on_ui_thread(lambda: _set_loading(False))

            run_on_ui_thread(lambda: _set_loading(True))
            threading.Thread(target=_do_translate, daemon=True).start()
        translate_bar_btn.setOnClickListener(OnClickListener(onTranslateBarClick))

        translate_bar.addView(translate_bar_btn, LayoutHelper.createLinear(-1, -2))
        root.addView(translate_bar, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # social links card
        social = p.get("social") or []
        if social:
            social_card = LinearLayout(act)
            social_card.setOrientation(LinearLayout.VERTICAL)
            social_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg_social = _make_card_bg(act)
            if bg_social:
                social_card.setBackground(bg_social)

            social_card.addView(
                _make_section_header(act, str(strings.pp_section_social)),
                LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0, 10)
            )

            for i, entry in enumerate(social):
                if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                    continue
                icon_name = str(entry[0])
                link_label = str(entry[1])
                link_url = str(entry[2])

                row = LinearLayout(act)
                row.setOrientation(LinearLayout.HORIZONTAL)
                row.setGravity(Gravity.CENTER_VERTICAL)
                row.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
                row.setClickable(True)
                row.setFocusable(True)
                row.setBackground(Theme.createSelectorDrawable(
                    Theme.getColor(Theme.key_listSelector), 2
                ))

                icon_iv = ImageView(act)
                icon_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                try:
                    icon_iv.setImageResource(_resolve_icon(icon_name))
                    icon_iv.setColorFilter(gray_color)
                except Exception:
                    pass
                row.addView(icon_iv, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

                label_tv = TextView(act)
                label_tv.setText(link_label)
                label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                label_tv.setTextColor(text_color)
                row.addView(label_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                if link_url:
                    def _on_social_click(v, _url=link_url):
                        try:
                            if Browser and Uri:
                                Browser.openUrl(act, Uri.parse(_url), True, True, True, None, None, False, False, False)
                        except Exception as e:
                            log(f"pluginProfile: social link error: {e}")
                    row.setOnClickListener(OnClickListener(_on_social_click))

                social_card.addView(row, LayoutHelper.createLinear(-1, -2))

                if i < len(social) - 1:
                    dv = View(act)
                    dv.setBackgroundColor(Theme.getColor(Theme.key_divider))
                    dv_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
                    dv_lp.leftMargin = AndroidUtilities.dp(32)
                    social_card.addView(dv, dv_lp)

            desc_extra.addView(social_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # tags card
        tags = p.get("tags") or []
        if tags:
            tags_card = LinearLayout(act)
            tags_card.setOrientation(LinearLayout.VERTICAL)
            tags_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg_tags = _make_card_bg(act)
            if bg_tags:
                tags_card.setBackground(bg_tags)

            tags_card.addView(
                _make_section_header(act, str(strings.pp_section_tags)),
                LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0, 8)
            )

            chips_row_tags = LinearLayout(act)
            chips_row_tags.setOrientation(LinearLayout.HORIZONTAL)

            for tag in tags:
                if not isinstance(tag, (list, tuple)) or len(tag) < 2:
                    continue
                chip = _make_chip(act, str(tag[0]), str(tag[1]))
                chip_lp = LinearLayout.LayoutParams(-2, -2)
                chip_lp.rightMargin = AndroidUtilities.dp(5)
                chips_row_tags.addView(chip, chip_lp)

            if chips_row_tags.getChildCount() > 0:
                tags_card.addView(chips_row_tags, LayoutHelper.createLinear(-2, -2))
                desc_extra.addView(tags_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # dependencies
        if deps:
            deps_card = LinearLayout(act)
            deps_card.setOrientation(LinearLayout.VERTICAL)
            deps_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg3 = _make_card_bg(act)
            if bg3:
                deps_card.setBackground(bg3)

            # header row: "DEPENDENCIES" label + count pill on the right
            deps_header_row = LinearLayout(act)
            deps_header_row.setOrientation(LinearLayout.HORIZONTAL)
            deps_header_row.setGravity(Gravity.CENTER_VERTICAL)
            deps_header_row.addView(
                _make_section_header(act, str(strings.pp_section_dependencies)),
                LayoutHelper.createLinear(0, -2, 1.0)
            )
            dep_count_str = str(strings.pp_dep_library_one) if len(deps) == 1 else str(strings.pp_dep_library_other).format(len(deps))
            count_chip = _make_chip(act, dep_count_str, "key_color_purple")
            deps_header_row.addView(count_chip, LinearLayout.LayoutParams(-2, -2))
            deps_card.addView(deps_header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

            deps_meta = {
                dp["id"]: dp for dp in self.all_plugins
                if isinstance(dp, dict) and dp.get("id")
            }

            try:
                from com.exteragram.messenger.plugins import PluginsController
                controller = PluginsController.getInstance()
            except Exception:
                controller = None

            try:
                red_color = Theme.getColor(Theme.key_avatar_backgroundRed)
            except Exception:
                from android.graphics import Color
                red_color = Color.parseColor("#FF5252")
            try:
                green_color = Theme.getColor(Theme.key_avatar_backgroundGreen)
            except Exception:
                from android.graphics import Color
                green_color = Color.parseColor("#4CAF50")

            for i, dep_id in enumerate(deps):
                if not isinstance(dep_id, str):
                    continue
                dep_plugin = deps_meta.get(dep_id)

                dep_row = LinearLayout(act)
                dep_row.setOrientation(LinearLayout.HORIZONTAL)
                dep_row.setGravity(Gravity.CENTER_VERTICAL)
                dep_row.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))

                # sticker icon (same size as depsSheet: 36dp)
                dep_icon_str = (dep_plugin.get("icon") if dep_plugin else None) or ""
                icon_size_dp = 36
                if dep_icon_str and "/" in dep_icon_str:
                    dep_iv = BackupImageView(act)
                    dep_iv.setRoundRadius(AndroidUtilities.dp(8))
                    try:
                        dep_iv.getImageReceiver().setCrossfadeWithOldImage(True)
                    except Exception:
                        pass
                    iv_lp = LinearLayout.LayoutParams(
                        AndroidUtilities.dp(icon_size_dp), AndroidUtilities.dp(icon_size_dp)
                    )
                    iv_lp.rightMargin = AndroidUtilities.dp(10)
                    dep_row.addView(dep_iv, iv_lp)
                    if not _try_load_sticker(dep_iv, dep_icon_str, icon_size_dp):
                        _schedule_sticker_retry(dep_iv, dep_icon_str, icon_size_dp, self._alive)

                # status icon: msg_select green / msg_cancel red
                installed = False
                if controller:
                    try:
                        installed = controller.getPluginEngine(dep_id) is not None
                    except Exception:
                        pass
                status_iv = ImageView(act)
                status_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                if installed:
                    status_iv.setImageResource(_resolve_icon("msg_select"))
                    status_iv.setColorFilter(green_color)
                else:
                    status_iv.setImageResource(_resolve_icon("msg_cancel"))
                    status_iv.setColorFilter(red_color)
                dep_row.addView(status_iv, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

                # name + version inline
                name_row = LinearLayout(act)
                name_row.setOrientation(LinearLayout.HORIZONTAL)
                name_row.setGravity(Gravity.CENTER_VERTICAL)

                dep_name = (dep_plugin.get("name") if dep_plugin else None) or dep_id
                dep_name_tv = TextView(act)
                dep_name_tv.setText(str(dep_name))
                dep_name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                dep_name_tv.setTextColor(text_color)
                try:
                    dep_name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    dep_name_tv.setTypeface(AndroidUtilities.bold())
                name_row.addView(dep_name_tv, LayoutHelper.createLinear(-2, -2))

                dep_ver = (dep_plugin.get("version") if dep_plugin else None) or ""
                if dep_ver:
                    ver_tv = TextView(act)
                    ver_tv.setText(f"  v{dep_ver}")
                    ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    ver_tv.setTextColor(gray_color)
                    name_row.addView(ver_tv, LayoutHelper.createLinear(-2, -2))

                dep_row.addView(name_row, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                if dep_plugin:
                    dep_row.setClickable(True)
                    dep_row.setFocusable(True)
                    dep_row.setBackground(Theme.createSelectorDrawable(
                        Theme.getColor(Theme.key_listSelector), 2
                    ))

                    def onDepClick(v, target=dep_plugin):
                        show_plugin_profile(target, self.install_ui, self.all_plugins)
                    dep_row.setOnClickListener(OnClickListener(onDepClick))

                deps_card.addView(dep_row, LayoutHelper.createLinear(-1, -2))

                if i < len(deps) - 1:
                    dv = View(act)
                    dv.setBackgroundColor(Theme.getColor(Theme.key_divider))
                    dv_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
                    dv_lp.leftMargin = AndroidUtilities.dp(46)
                    deps_card.addView(dv, dv_lp)

            desc_extra.addView(deps_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # other plugins by author
        author = str(p.get("author") or "").strip()
        plugin_id = p.get("id")
        others = [
            op for op in self.all_plugins
            if isinstance(op, dict)
            and str(op.get("author") or "").strip() == author
            and op.get("id") != plugin_id
        ] if author else []

        if others:
            others_card = LinearLayout(act)
            others_card.setOrientation(LinearLayout.VERTICAL)
            others_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg4 = _make_card_bg(act)
            if bg4:
                others_card.setBackground(bg4)

            others_header_row = LinearLayout(act)
            others_header_row.setOrientation(LinearLayout.HORIZONTAL)
            others_header_row.setGravity(Gravity.CENTER_VERTICAL)

            more_from_raw = str(strings.pp_section_more_from).format(author)
            more_from_tv = TextView(act)
            more_from_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            more_from_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            more_from_tv.setLetterSpacing(0.08)
            try:
                more_from_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                more_from_tv.setTypeface(AndroidUtilities.bold())
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                more_from_tv.setText(LocaleUtils.fullyFormatText(more_from_raw.upper()))
                more_from_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                more_from_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                more_from_tv.setText(more_from_raw.upper())
            others_header_row.addView(more_from_tv, LayoutHelper.createLinear(0, -2, 1.0))

            others_count_str = str(strings.pp_other_plugin_one) if len(others) == 1 else str(strings.pp_other_plugin_other).format(len(others))
            others_chip = _make_chip(act, others_count_str, "key_color_green")
            others_header_row.addView(others_chip, LinearLayout.LayoutParams(-2, -2))
            others_card.addView(others_header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

            for i, other in enumerate(others):
                mini = self._make_mini_card(act, other, text_color, gray_color)
                others_card.addView(mini, LayoutHelper.createLinear(-1, -2))
                if i < len(others) - 1:
                    dv = View(act)
                    dv.setBackgroundColor(Theme.getColor(Theme.key_divider))
                    dv_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
                    dv_lp.leftMargin = AndroidUtilities.dp(58)
                    others_card.addView(dv, dv_lp)

            desc_extra.addView(others_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        root.addView(desc_extra, LayoutHelper.createLinear(-1, -2))

        log(f"pluginProfile: beforeCreateView done, content_view={self.content_view}")
        try:
            from ..viewUtils import applyFontToTree
            applyFontToTree(self.content_view)
        except Exception:
            pass
        return self.content_view

    def _get_localized_description(self, plugin):
        about = plugin.get("about", [])
        if isinstance(about, list) and len(about) >= 1:
            try:
                from java.util import Locale
                lang = Locale.getDefault().getLanguage()
                if lang == "ru" and len(about) > 1:
                    return str(about[1])
                return str(about[0])
            except Exception:
                return str(about[0])
        return str(plugin.get("description") or "")

    def _make_mini_card(self, act, plugin, text_color, gray_color):
        row = LinearLayout(act)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
        row.setClickable(True)
        row.setFocusable(True)
        row.setBackground(Theme.createSelectorDrawable(
            Theme.getColor(Theme.key_listSelector), 2
        ))

        icon_str = plugin.get("icon")
        size_dp = 42
        show_default_sticker = settings.get("show_default_sticker", False)
        show_icon = icon_str and icon_str != "Unknown"
        if not show_icon and show_default_sticker:
            icon_str = "Plugins_Stickers/0"
            show_icon = True
        if show_icon:
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(10))
            iv_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp))
            iv_lp.rightMargin = AndroidUtilities.dp(12)
            row.addView(iv, iv_lp)
            if not _try_load_sticker(iv, icon_str, size_dp):
                _schedule_sticker_retry(iv, icon_str, size_dp, self._alive)

        info = LinearLayout(act)
        info.setOrientation(LinearLayout.VERTICAL)
        info.setGravity(Gravity.CENTER_VERTICAL)

        name_tv = TextView(act)
        name_tv.setText(str(plugin.get("name") or plugin.get("id") or "?"))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        name_tv.setTextColor(text_color)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        info.addView(name_tv, LayoutHelper.createLinear(-2, -2))

        sub_parts = []
        if plugin.get("version"):
            sub_parts.append(f"v{plugin['version']}")
        desc = str(plugin.get("description") or "")
        if desc:
            sub_parts.append(desc[:40] + ("…" if len(desc) > 40 else ""))
        if sub_parts:
            sub_tv = TextView(act)
            sub_tv.setText("  ·  ".join(sub_parts))
            sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            sub_tv.setTextColor(gray_color)
            sub_tv.setSingleLine(True)
            sub_tv.setHorizontalFadingEdgeEnabled(True)
            sub_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            info.addView(sub_tv, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        row.addView(info, LayoutHelper.createLinear(0, -2, 1.0))

        def onRowClick(v, target=plugin):
            show_plugin_profile(target, self.install_ui, self.all_plugins)
        row.setOnClickListener(OnClickListener(onRowClick))
        return row


def show_plugin_profile(plugin: dict, install_ui, all_plugins: list = None, repo_id: str = ""):
    try:
        fragment = get_last_fragment()
        if not fragment:
            log("pluginProfile: no fragment")
            return
        log(f"pluginProfile: show_plugin_profile plugin={plugin.get('id')}")
        delegate = PluginProfileFragment(plugin, install_ui, all_plugins or [], repo_id=repo_id)
        new_fragment = UniversalFragment(delegate)
        fragment.presentFragment(new_fragment)
        log(f"pluginProfile: presentFragment done")
        try:
            new_fragment.setTitle(str(plugin.get("name") or plugin.get("id") or strings.pp_unknown_plugin), False, 0)
            action_bar = new_fragment.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                delegate._fragment_ref[0] = new_fragment
        except Exception as e:
            log(f"pluginProfile: actionBar setup error: {e}")
    except Exception as e:
        log(f"pluginProfile: show_plugin_profile error: {e}")

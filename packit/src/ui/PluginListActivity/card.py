# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import ctypes
from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ImageView, HorizontalScrollView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy
from hook_utils import find_class
from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from packutil import logx
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"card: import strings failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"card: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    import android_utils as _au; _au.log(f"card: import LayoutHelper, BackupImageView failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"card: import AndroidUtilities etc failed: {e}")
try:
    from com.exteragram.messenger.utils.text import LocaleUtils
except Exception as e:
    import android_utils as _au; _au.log(f"card: import LocaleUtils failed: {e}")
try:
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"card: import Uri failed: {e}")
try:
    from org.telegram.messenger.browser import Browser
except Exception:
    Browser = None

from .helpers.PluginActions import copy_plugin_link, share_plugin_file, view_plugin_code, report_plugin, download_plugin_file, translate_plugin
from .helpers.utils import _check_app_version
from ..viewUtils import highlightQuery as _highlight_query


def make_plugin_card(self, p):
    act = get_last_fragment().getContext()
    fragment = get_last_fragment()
    row = FrameLayout(act)
    container = LinearLayout(act)
    container.setOrientation(LinearLayout.VERTICAL)
    container.setGravity(Gravity.TOP)
    _card_padding = AndroidUtilities.dp(self._s_card_padding)
    container.setPadding(_card_padding, _card_padding, _card_padding, _card_padding)
    try:
        container.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(self._s_card_radius), self.card_bg_color, self.card_bg_color
        ))
    except Exception:
        pass

    def create_icon_pill(icon_name, handler):
        try:
            surface_color = self.card_bg_color
            pressed_color = self.card_pressed_color
        except Exception:
            surface_color = self.card_bg_color
            pressed_color = self.card_pressed_color
        pill = self.install_ui._create_pill(
            act,
            surface_color,
            pressed_color,
            padding_h=8,
            padding_v=8
        )
        icon = ImageView(act)
        icon_id = self.install_ui._resolve_icon(icon_name)
        icon.setImageResource(icon_id)
        try:
            icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        pill.addView(icon, LinearLayout.LayoutParams(AndroidUtilities.dp(23), AndroidUtilities.dp(23)))
        pill.setOnClickListener(OnClickListener(lambda v: handler()))
        self.install_ui._apply_press_scale(pill)
        return pill

    icon_str = p.get("icon")
    show_icon = (icon_str and icon_str != "Unknown") and self._s_card_show_icon
    show_stub = not show_icon and self._s_show_default_sticker and self._s_card_show_icon
    icon_size_dp = self._s_icon_size_dp
    top_row = LinearLayout(act)
    top_row.setOrientation(LinearLayout.HORIZONTAL)
    top_row.setGravity(Gravity.TOP)
    container.addView(top_row, LayoutHelper.createLinear(-1, -2))
    if show_stub:
        try:
            from android.graphics import PorterDuffColorFilter, PorterDuff
            stub_view = ImageView(act)
            stub_view.setScaleType(ImageView.ScaleType.FIT_CENTER)
            stub_view.setImageResource(R_tg.drawable.plugins_filled)
            stub_view.setColorFilter(PorterDuffColorFilter(
                Theme.getColor(Theme.key_featuredStickers_buttonText),
                PorterDuff.Mode.SRC_IN
            ))
            p_stub = AndroidUtilities.dp(16)
            stub_view.setPadding(p_stub, p_stub, p_stub, p_stub)
            stub_view.setBackground(Theme.createCircleDrawable(
                AndroidUtilities.dp(icon_size_dp),
                Theme.getColor(Theme.key_featuredStickers_addButton)
            ))
            stub_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(icon_size_dp), AndroidUtilities.dp(icon_size_dp))
            stub_lp.rightMargin = AndroidUtilities.dp(12)
            stub_lp.topMargin = AndroidUtilities.dp(5)
            top_row.addView(stub_view, stub_lp)
        except Exception as e:
            logx(f"PluginList: stub icon error: {e}", False)
    if show_icon:
        try:
            icon_view = BackupImageView(act)
            icon_view.setRoundRadius(AndroidUtilities.dp(self._s_sticker_radius))
            try:
                icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            icon_size_px = AndroidUtilities.dp(icon_size_dp)
            icon_lp = LinearLayout.LayoutParams(icon_size_px, icon_size_px)
            icon_lp.rightMargin = AndroidUtilities.dp(12)
            icon_lp.topMargin = AndroidUtilities.dp(5)
            top_row.addView(icon_view, icon_lp)

            def onIconClick(v, plugin=p):
                try:
                    from ..PluginActivity.fragment import show_plugin_profile
                    show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id or str(plugin.get("_repo_id") or ""))
                except Exception as e:
                    pass

            icon_view.setClickable(True)
            icon_view.setFocusable(True)
            icon_view.setOnClickListener(OnClickListener(onIconClick))
            if self._s_show_details_button:
                self.install_ui._apply_press_scale(icon_view)
            else:
                self.install_ui._apply_press_scale_on_target(icon_view, row)

            # make_plugin_card runs off the UI thread (_load_initial_batch worker),
            # MediaDataController and BackupImageView.setImage must run on the UI thread
            from ...utils.stickers import load_sticker
            run_on_ui_thread(lambda: load_sticker(icon_view, icon_str, icon_size_dp))
        except Exception as e:
            pass

    col = LinearLayout(act)
    col.setOrientation(LinearLayout.VERTICAL)

    name_scroll = HorizontalScrollView(act)
    name_scroll.setHorizontalScrollBarEnabled(False)
    name_scroll.setFillViewport(True)
    name_scroll.setHorizontalFadingEdgeEnabled(True)
    name_scroll.setFadingEdgeLength(AndroidUtilities.dp(24))

    name_container = LinearLayout(act)
    name_container.setOrientation(LinearLayout.VERTICAL)

    name_tv = TextView(act)
    try:
        name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        name_tv.setTypeface(AndroidUtilities.bold())
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, self._s_card_name_size)
    display_name = str(p.get("name") or p.get("id") or "Unknown")
    # highlight search matches in the name with the accent color
    highlighted = None
    try:
        _q = getattr(self, "last_search_query", None)
        if _q:
            highlighted = _highlight_query(
                display_name, str(_q),
                Theme.getColor(Theme.key_featuredStickers_addButton),
            )
    except Exception:
        highlighted = None
    name_tv.setText(highlighted if highlighted is not None else display_name)
    name_tv.setTextColor(self.text_color)
    name_tv.setSingleLine(True)
    name_tv.setHorizontalFadingEdgeEnabled(True)
    name_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
    id_tv = TextView(act)
    id_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, self._s_card_id_size)
    version_text = str(p.get("version") or "").strip()
    author_text = str(p.get("author") or "").strip()
    if version_text and author_text:
        formatted_text = LocaleUtils.fullyFormatText(f"v{version_text} • {author_text}")
        id_tv.setText(formatted_text)
    elif version_text:
        id_tv.setText(f"v{version_text}")
    else:
        formatted_author = LocaleUtils.fullyFormatText(author_text)
        id_tv.setText(formatted_author)
    if not self._s_card_show_id:
        id_tv.setVisibility(View.GONE)
    try:
        id_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        id_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
        from android.text.method import LinkMovementMethod
        id_tv.setMovementMethod(LinkMovementMethod.getInstance())
    except Exception:
        pass
    id_tv.setSingleLine(True)
    id_tv.setHorizontalFadingEdgeEnabled(True)
    id_tv.setFadingEdgeLength(AndroidUtilities.dp(24))

    name_container.addView(name_tv, LayoutHelper.createLinear(-1, -2))
    name_container.addView(id_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

    name_scroll.addView(name_container, FrameLayout.LayoutParams(
        FrameLayout.LayoutParams.WRAP_CONTENT,
        FrameLayout.LayoutParams.WRAP_CONTENT
    ))
    col.addView(name_scroll, LayoutHelper.createLinear(-1, -2))

    tags = p.get("tags") or []
    if tags and self._s_show_plugin_tags:
        tags_row = LinearLayout(act)
        tags_row.setOrientation(LinearLayout.HORIZONTAL)
        tags_row.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL)
        tags_row.setPadding(0, AndroidUtilities.dp(6), 0, 0)
        tags_row.setClipChildren(True)
        for tag in tags:
            if not isinstance(tag, (list, tuple)) or len(tag) < 2:
                continue
            tag_name = str(tag[0])
            tag_color_key = str(tag[1])
            tag_url = str(tag[2]) if len(tag) > 2 else None
            try:
                tag_color = Theme.getColor(getattr(Theme, tag_color_key))
            except Exception:
                continue
            r = (tag_color >> 16) & 0xFF
            g = (tag_color >> 8) & 0xFF
            b = tag_color & 0xFF
            fill_color = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
            text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
            tag_bg = GradientDrawable()
            tag_bg.setShape(GradientDrawable.RECTANGLE)
            tag_bg.setCornerRadius(AndroidUtilities.dp(6))
            tag_bg.setColor(fill_color)
            tag_tv = TextView(act)
            tag_tv.setText(tag_name)
            tag_tv.setSingleLine(True)
            tag_tv.setMaxLines(1)
            tag_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            tag_tv.setTextColor(text_color)
            tag_tv.setBackground(tag_bg)
            tag_tv.setPadding(
                AndroidUtilities.dp(7), AndroidUtilities.dp(2),
                AndroidUtilities.dp(7), AndroidUtilities.dp(2)
            )
            if tag_url:
                tag_tv.setClickable(True)
                tag_tv.setFocusable(True)
                def onTagClick(v, url=tag_url):
                    try:
                        if url.startswith("https://t.me/"):
                            frag = get_last_fragment()
                            act2 = frag.getParentActivity() if frag else None
                            if act2:
                                Browser.openUrl(act2, Uri.parse(url), True, True, True, None, None, False, False, False)
                        else:
                            from android.content import Intent
                            ctx = act
                            intent = Intent(Intent.ACTION_VIEW)
                            intent.setData(Uri.parse(url))
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            ctx.startActivity(intent)
                    except Exception as e:
                        pass
                tag_tv.setOnClickListener(OnClickListener(onTagClick))
                self.install_ui._apply_press_scale(tag_tv)
            tag_lp = LinearLayout.LayoutParams(-2, -2)
            tag_lp.rightMargin = AndroidUtilities.dp(5)
            tags_row.addView(tag_tv, tag_lp)

        # all tags on one horizontally-scrollable row: chips never split, none
        # are hidden, and the card height stays fixed — overflow reached by
        # swiping, with fading edges like the plugin-name row above
        tags_scroll = HorizontalScrollView(act)
        tags_scroll.setHorizontalScrollBarEnabled(False)
        tags_scroll.setHorizontalFadingEdgeEnabled(True)
        tags_scroll.setFadingEdgeLength(AndroidUtilities.dp(16))
        tags_scroll.addView(tags_row, FrameLayout.LayoutParams(-2, -2))
        col.addView(tags_scroll, LayoutHelper.createLinear(-1, -2))

    top_row.addView(col, LayoutHelper.createLinear(0, -2, 1.0))

    similarity = p.get("_search_similarity")
    show_similarity = isinstance(similarity, (int, float)) and similarity > 0
    show_size = self._s_show_size
    show_min_ver = self._s_show_min_ver
    show_deps = self._s_show_deps

    if show_similarity or show_size or show_min_ver or show_deps:
        chips_col = LinearLayout(act)
        chips_col.setOrientation(LinearLayout.VERTICAL)
        chips_col.setGravity(Gravity.TOP | Gravity.RIGHT)

        if show_similarity:
            chip = self.install_ui._make_info_chip(
                act, f"{int(round(similarity))}%", "key_featuredStickers_addButton", self._s_chip_ver_size
            )
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.bottomMargin = AndroidUtilities.dp(4)
            chips_col.addView(chip, chip_lp)

        if show_min_ver:
            min_ver = p.get("app_version")
            if min_ver:
                chip = self.install_ui._make_info_chip(act, str(min_ver), "key_avatar_background2Blue", self._s_chip_ver_size)
                chip_lp = LinearLayout.LayoutParams(-2, -2)
                chip_lp.bottomMargin = AndroidUtilities.dp(4)
                chips_col.addView(chip, chip_lp)

        if show_deps:
            deps = p.get("deps") or []
            dep_count = len(deps)
            if dep_count > 0:
                dep_label = "library" if dep_count == 1 else "libraries"
                chip = self.install_ui._make_info_chip(act, f"{dep_count} {dep_label}", "key_color_purple", self._s_chip_deps_size)
                chip_lp = LinearLayout.LayoutParams(-2, -2)
                chip_lp.bottomMargin = AndroidUtilities.dp(4)
                chips_col.addView(chip, chip_lp)

        if show_size:
            size_str = p.get("size")
            if size_str:
                chip = self.install_ui._make_info_chip(act, str(size_str), "key_color_cyan", self._s_chip_size_size)
                chips_col.addView(chip, LinearLayout.LayoutParams(-2, -2))

        chips_lp = LinearLayout.LayoutParams(-2, -2)
        chips_lp.leftMargin = AndroidUtilities.dp(8)
        top_row.addView(chips_col, chips_lp)

    desc_tv = TextView(act)
    desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, self._s_card_desc_size)
    description_text = self._get_localized_description(p)
    formatted_description = LocaleUtils.fullyFormatText(description_text)
    desc_tv.setText(formatted_description)
    try:
        desc_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        desc_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
        from android.text.method import LinkMovementMethod
        desc_tv.setMovementMethod(LinkMovementMethod.getInstance())
    except Exception:
        pass
    if self._s_card_show_desc:
        container.addView(desc_tv, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

    buttons = LinearLayout(act)
    buttons.setOrientation(LinearLayout.HORIZONTAL)
    buttons.setGravity(Gravity.LEFT)
    buttons.setPadding(0, AndroidUtilities.dp(8), 0, 0)
    base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
    pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)

    plugin_min_version = p.get("app_version")
    is_available = (not plugin_min_version) or _check_app_version(plugin_min_version)

    install_btn = self.install_ui._create_pill(act, base_color, pressed_color)
    install_icon = ImageView(act)
    icon_id = self.install_ui._resolve_icon("msg_view_file")
    install_icon.setImageResource(icon_id)
    try:
        install_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
    except Exception:
        pass
    icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
    icon_lp.rightMargin = AndroidUtilities.dp(6)
    install_btn.addView(install_icon, icon_lp)
    install_text = TextView(act)
    install_text.setText(strings["plugin_view_button"])
    install_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    install_text.setTypeface(AndroidUtilities.bold())
    install_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    install_btn.addView(install_text)

    current_hint_ref = [None]

    def onViewClick(v, plugin=p, btn=install_btn, row_ref=row, hint_ref=current_hint_ref, available=is_available):
        if not available:
            try:
                from org.telegram.ui.Stories.recorder import HintView2
                from android.text import Layout

                prev = hint_ref[0]
                if prev is not None:
                    try:
                        prev.hide()
                    except Exception:
                        pass
                    hint_ref[0] = None

                hint = (
                    HintView2(row_ref.getContext(), 3)
                    .setMultilineText(True)
                    .setBgColor(Theme.getColor(Theme.key_undo_background))
                    .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                    .setText(strings["plugin_version_below_min"])
                    .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                    .allowBlur(True)
                    .setRounding(AndroidUtilities.dp(12))
                )
                try:
                    hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                except Exception:
                    pass

                row_ref.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                hint_ref[0] = hint

                def _position_and_show():
                    try:
                        btn_loc = [0, 0]
                        btn.getLocationInWindow(btn_loc)
                        row_loc = [0, 0]
                        row_ref.getLocationInWindow(row_loc)
                        rel_x = btn_loc[0] - row_loc[0]
                        rel_y = btn_loc[1] - row_loc[1]
                        center_x = float(rel_x) + float(btn.getMeasuredWidth()) / 2.0
                        hint.setTranslationY(float(rel_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                        hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                        hint.setDuration(5500)
                        hint.show()
                    except Exception as e:
                        pass

                run_on_ui_thread(_position_and_show)
            except Exception as e:
                pass

        try:
            from ..PluginActivity.fragment import show_plugin_profile
            show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id or str(plugin.get("_repo_id") or ""))
        except Exception as e:
            pass

    def onCardClick(v, plugin=p, row_ref=row, hint_ref=current_hint_ref, available=is_available):
        if not self._s_show_view_button:
            try:
                from ..PluginActivity.fragment import show_plugin_profile
                show_plugin_profile(plugin, self.install_ui, self.plugins, repo_id=self.repo_id or str(plugin.get("_repo_id") or ""))
            except Exception as e:
                pass

    install_btn.setOnClickListener(OnClickListener(onViewClick))
    self.install_ui._apply_press_scale(install_btn)

    if not self._s_show_view_button:
        row.setOnClickListener(OnClickListener(onCardClick))
        self.install_ui._apply_press_scale_on_target(row, row)
        name_tv.setClickable(True)
        name_tv.setFocusable(True)
        name_tv.setOnClickListener(OnClickListener(onCardClick))
        self.install_ui._apply_press_scale_on_target(name_tv, row)
        if self._s_card_show_desc:
            desc_tv.setClickable(True)
            desc_tv.setFocusable(True)
            desc_tv.setOnClickListener(OnClickListener(onCardClick))
            self.install_ui._apply_press_scale_on_target(desc_tv, row)

    if self._s_show_view_button:
        buttons.addView(install_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 8, 0))

    def create_icon_pill(icon_name, handler):
        try:
            surface_color = self.card_bg_color
            pressed_color = self.card_pressed_color
        except Exception:
            surface_color = self.card_bg_color
            pressed_color = self.card_pressed_color
        pill = self.install_ui._create_pill(
            act,
            surface_color,
            pressed_color,
            padding_h=8,
            padding_v=8
        )
        icon = ImageView(act)
        icon_id = self.install_ui._resolve_icon(icon_name)
        icon.setImageResource(icon_id)
        try:
            icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        pill.addView(icon, LinearLayout.LayoutParams(AndroidUtilities.dp(23), AndroidUtilities.dp(23)))
        pill.setOnClickListener(OnClickListener(lambda v: handler()))
        self.install_ui._apply_press_scale(pill)
        return pill

    try:
        from elyx import assets
        copyLinkSoundPath = assets.sounds.copy_link.path_str
    except Exception as e:
        logx(f"card: copy-link sound asset unavailable: {e}", False)
        copyLinkSoundPath = None
    act_for_share = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None

    def do_install():
        # install straight from the catalog card; stat increments happen
        # inside the install pipeline, no manual bump here
        if not is_available:
            try:
                from ui.bulletin import BulletinHelper
                BulletinHelper.show_error(str(strings["plugin_version_below_min"]))
            except Exception:
                pass
            return
        try:
            from ...core import install_plugin
            install_plugin(
                p,
                install_ui=self.install_ui,
                all_plugins=self.plugins,
                rm_rid=self.repo_id or str(p.get("_repo_id") or ""),
            )
        except Exception as e:
            logx(f"card: install from card error: {e}", False)

    def do_download_relocated():
        download_plugin_file(p)
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
            increment_category("Downloading")
        except Exception as e:
            pass

    def do_copy_relocated():
        copy_plugin_link(p, self.repo_id or self.title, copyLinkSoundPath)
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
            increment_category("Copying links")
        except Exception as e:
            pass

    def do_share_relocated():
        share_plugin_file(p, str(display_name), act_for_share)
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
            increment_category("Sharing")
        except Exception as e:
            pass

    def do_code_relocated():
        view_plugin_code(p, act)
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
            increment_category("Viewing code")
        except Exception as e:
            pass

    def do_translate_relocated():
        translate_plugin(p)

    def do_report_relocated():
        report_plugin(p, act, repo_id=self.repo_id)
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
            increment_category("Reporting")
        except Exception as e:
            pass

    spacer = View(act)
    buttons.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))

    relocate_actions = [
        ("_s_relocate_install",   "msg_add",       do_install),
        ("_s_relocate_copy",      "msg_copy",      do_copy_relocated),
        ("_s_relocate_share",     "msg_share",     do_share_relocated),
        ("_s_relocate_code",      "msg_view_file", do_code_relocated),
        ("_s_relocate_download",  "msg_download",  do_download_relocated),
        ("_s_relocate_translate", "msg_replace",   do_translate_relocated),
        ("_s_relocate_report",    "msg_report",    do_report_relocated),
    ]
    for attr_key, icon_name, action in relocate_actions:
        if getattr(self, attr_key, False):
            relocated_btn = create_icon_pill(icon_name, action)
            buttons.addView(relocated_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 4, 0))

    def show_plugin_actions_menu(anchor_view):
        try:
            from ..contextMenu import show_plugin_context_menu

            def do_install():
                from ...core import install_plugin
                install_plugin(
                    p,
                    install_ui=self.install_ui,
                    all_plugins=self.plugins,
                    rm_rid=self.repo_id or str(p.get("_repo_id") or ""),
                )

            def do_download():
                download_plugin_file(p)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Downloading")
                except Exception:
                    pass

            def do_copy():
                copy_plugin_link(p, self.repo_id or self.title, copyLinkSoundPath)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Copying links")
                except Exception:
                    pass

            def do_share():
                share_plugin_file(p, str(display_name), act_for_share)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Sharing")
                except Exception:
                    pass

            def do_code():
                view_plugin_code(p, act)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Viewing code")
                except Exception:
                    pass

            def do_translate():
                translate_plugin(p)

            def do_report():
                report_plugin(p, act, repo_id=self.repo_id)
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                    increment_category("Reporting")
                except Exception:
                    pass

            show_plugin_context_menu(anchor_view.getRootView(), anchor_view, [
                {"icon": "msg_download_remix", "text": str(strings["pp_install"]), "action": do_install, "show": is_available},
                {"icon": "msg_copy",      "text": str(strings["copy_link"]), "action": do_copy,      "show": not getattr(self, "_s_relocate_copy",      False)},
                {"icon": "msg_share",     "text": str(strings["share"]),     "action": do_share,     "show": not getattr(self, "_s_relocate_share",     False)},
                {"icon": "msg_view_file", "text": str(strings["code"]),      "action": do_code,      "show": not getattr(self, "_s_relocate_code",      False)},
                {"icon": "msg_download",  "text": str(strings["download"]),  "action": do_download,  "show": not getattr(self, "_s_relocate_download",  False)},
                {"icon": "msg_replace",   "text": str(strings["translate"]), "action": do_translate, "show": not getattr(self, "_s_relocate_translate", False)},
                {"icon": "msg_report",    "text": str(strings["report"]),    "action": do_report,    "show": not getattr(self, "_s_relocate_report",    False), "red": True},
            ])
        except Exception as e:
            pass

    if self._s_show_details_button:
        menu_btn = create_icon_pill("ic_ab_other", lambda: show_plugin_actions_menu(menu_btn))
        buttons.addView(menu_btn, LayoutHelper.createLinear(-2, -2))
    container.addView(buttons, LayoutHelper.createLinear(-1, -2))

    row.addView(container)
    return row

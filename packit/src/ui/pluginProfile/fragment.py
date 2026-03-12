import ctypes
import threading
from android.view import Gravity, View
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, ProgressBar
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


class PluginProfileFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    def __init__(self, plugin: dict, install_ui, all_plugins: list):
        super().__init__()
        self.plugin = plugin
        self.install_ui = install_ui
        self.all_plugins = all_plugins or []
        self.content_view = None
        self._alive = [True]  # shared ref for sticker retry timers
        log(f"pluginProfile: init plugin={plugin.get('id')}")

    def onFragmentCreate(self, *_):
        log(f"pluginProfile: onFragmentCreate plugin={self.plugin.get('id')}")

    def onFragmentDestroy(self, *_):
        log(f"pluginProfile: onFragmentDestroy plugin={self.plugin.get('id')}")
        self._alive[0] = False
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
        return str(self.plugin.get("name") or self.plugin.get("id") or "Plugin")

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
        pass

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
        act = get_last_fragment().getContext()
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

        # hero card: sticker centered + name + meta────────────────────────
        hero = LinearLayout(act)
        hero.setOrientation(LinearLayout.VERTICAL)
        hero.setGravity(Gravity.CENTER_HORIZONTAL)
        hero.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(24),
            AndroidUtilities.dp(20), AndroidUtilities.dp(20)
        )
        bg = _make_card_bg(act, 18)
        if bg:
            hero.setBackground(bg)

        icon_str = p.get("icon")
        sticker_size = 96
        if icon_str and "/" in str(icon_str):
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(20))
            try:
                iv.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            iv_lp = LinearLayout.LayoutParams(
                AndroidUtilities.dp(sticker_size), AndroidUtilities.dp(sticker_size)
            )
            iv_lp.bottomMargin = AndroidUtilities.dp(14)
            hero.addView(iv, iv_lp)
            if not _try_load_sticker(iv, icon_str, sticker_size):
                _schedule_sticker_retry(iv, icon_str, sticker_size, self._alive)

        name_tv = TextView(act)
        name_tv.setText(str(p.get("name") or p.get("id") or "Unknown"))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
        name_tv.setTextColor(text_color)
        name_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        hero.addView(name_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 4))

        meta_parts = []
        if p.get("author"):
            meta_parts.append(str(p["author"]))
        if p.get("version"):
            meta_parts.append(f"v{p['version']}")
        if meta_parts:
            meta_tv = TextView(act)
            meta_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            meta_tv.setTextColor(gray_color)
            meta_tv.setGravity(Gravity.CENTER_HORIZONTAL)
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                meta_tv.setText(LocaleUtils.fullyFormatText("  ·  ".join(meta_parts)))
                meta_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                meta_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                meta_tv.setText("  ·  ".join(meta_parts))
            hero.addView(meta_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 12))

        # chips: tags + size + min_version + deps
        chips_row = LinearLayout(act)
        chips_row.setOrientation(LinearLayout.HORIZONTAL)
        chips_row.setGravity(Gravity.CENTER_HORIZONTAL)

        tags = p.get("tags") or []
        for tag in tags:
            if not isinstance(tag, (list, tuple)) or len(tag) < 2:
                continue
            chip = _make_chip(act, str(tag[0]), str(tag[1]))
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(5)
            chips_row.addView(chip, chip_lp)

        if p.get("size"):
            chip = _make_chip(act, str(p["size"]), "key_color_cyan")
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(5)
            chips_row.addView(chip, chip_lp)

        if p.get("min_version"):
            chip = _make_chip(act, str(p["min_version"]), "key_avatar_background2Blue")
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(5)
            chips_row.addView(chip, chip_lp)

        deps = p.get("deps") or []

        if chips_row.getChildCount() > 0:
            hero.addView(chips_row, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL))

        # install button
        has_link = bool(p.get("link") or p.get("raw"))
        if has_link:
            install_margin_lp = LayoutHelper.createLinear(-1, -2, Gravity.CENTER_HORIZONTAL, 0, 16, 0, 0)
            from ..installUi.uiMain import _is_min_version_satisfied
            plugin_min_ver = p.get("min_version")
            is_available = (not plugin_min_ver) or _is_min_version_satisfied(plugin_min_ver)

            try:
                btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
                btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            except Exception:
                from android.graphics import Color
                btn_base = Color.parseColor("#2196F3")
                btn_pressed = Color.parseColor("#1976D2")

            install_btn = LinearLayout(act)
            install_btn.setOrientation(LinearLayout.HORIZONTAL)
            install_btn.setGravity(Gravity.CENTER)
            install_btn.setPadding(
                AndroidUtilities.dp(20), AndroidUtilities.dp(13),
                AndroidUtilities.dp(20), AndroidUtilities.dp(13)
            )
            install_btn.setClickable(True)
            install_btn.setFocusable(True)

            if is_available:
                install_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(14), btn_base, btn_pressed
                ))
                btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
            else:
                import ctypes as _ct
                gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                r = (gray >> 16) & 0xFF
                g = (gray >> 8) & 0xFF
                b = gray & 0xFF
                bg_gray = _ct.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                bg_gray_d = GradientDrawable()
                bg_gray_d.setShape(GradientDrawable.RECTANGLE)
                bg_gray_d.setCornerRadius(AndroidUtilities.dp(14))
                bg_gray_d.setColor(bg_gray)
                install_btn.setBackground(bg_gray_d)
                btn_text_color = gray
                install_btn.setEnabled(False)

            install_label = TextView(act)
            install_label.setText(strings["install_plugin"] if is_available else (str(plugin_min_ver) + " required"))
            install_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            install_label.setTextColor(btn_text_color)
            try:
                install_label.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                install_label.setTypeface(AndroidUtilities.bold())
            install_btn.addView(install_label)

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
                                _btn.addView(spinner, LayoutHelper.createLinear(20, 20, Gravity.CENTER))
                            except Exception:
                                pb = ProgressBar(_act)
                                try:
                                    pb.setIndeterminate(True)
                                    from android.content.res import ColorStateList
                                    pb.setIndeterminateTintList(ColorStateList.valueOf(_btn_text_color))
                                except Exception:
                                    pass
                                _btn.addView(pb, LayoutHelper.createLinear(20, 20, Gravity.CENTER))
                        else:
                            _btn.addView(_label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER))
                    except Exception as e:
                        log(f"pluginProfile: _set_loading error: {e}")

                def onInstallClick(v, _p=p, _install_ui=_install_ui_ref, _all=_all_plugins_ref,
                                   _btn=install_btn, _label=install_label,
                                   _btn_text_color=btn_text_color, _act=act):
                    from ...core import install_plugin
                    _set_loading(_btn, _label, _btn_text_color, _act, True)

                    def _finish(ok):
                        run_on_ui_thread(lambda: _set_loading(_btn, _label, _btn_text_color, _act, False))

                    install_plugin(_p, on_finish=_finish, install_ui=_install_ui, all_plugins=_all)

                install_btn.setOnClickListener(OnClickListener(onInstallClick))

            hero.addView(install_btn, install_margin_lp)

        root.addView(hero, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 12))

        # description
        desc = self._get_localized_description(p)
        if desc:
            desc_card = LinearLayout(act)
            desc_card.setOrientation(LinearLayout.VERTICAL)
            desc_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg2 = _make_card_bg(act)
            if bg2:
                desc_card.setBackground(bg2)

            desc_card.addView(
                _make_section_header(act, "Description"),
                LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0, 8)
            )

            # FrameLayout: desc_tv full width with paddingEnd so text wraps before button,
            # translate_btn overlays top-right corner
            btn_size = AndroidUtilities.dp(32)  # 18dp icon + 7dp padding * 2
            desc_frame = FrameLayout(act)

            desc_tv = TextView(act)
            desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            desc_tv.setTextColor(text_color)
            desc_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
            desc_tv.setPadding(0, 0, btn_size + AndroidUtilities.dp(4), 0)
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                desc_tv.setText(LocaleUtils.fullyFormatText(desc))
                desc_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                desc_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                desc_tv.setText(desc)
            desc_frame.addView(desc_tv, FrameLayout.LayoutParams(-1, -2))

            translate_btn = FrameLayout(act)
            translate_btn.setClickable(True)
            translate_btn.setFocusable(True)
            try:
                tr_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                r = (tr_color >> 16) & 0xFF
                g = (tr_color >> 8) & 0xFF
                b = tr_color & 0xFF
                tr_fill = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                tr_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                translate_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(8), tr_fill, tr_pressed
                ))
            except Exception:
                pass
            translate_btn.setPadding(
                AndroidUtilities.dp(7), AndroidUtilities.dp(5),
                AndroidUtilities.dp(7), AndroidUtilities.dp(5)
            )
            tr_icon = ImageView(act)
            tr_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                tr_icon.setImageResource(_resolve_icon("msg_replace"))
                tr_icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass
            translate_btn.addView(tr_icon, FrameLayout.LayoutParams(
                AndroidUtilities.dp(18), AndroidUtilities.dp(18)
            ))

            def onTranslateClick(v, _p=p):
                from ..installUi.translation import translate_plugin
                translate_plugin(_p)
            translate_btn.setOnClickListener(OnClickListener(onTranslateClick))

            tr_lp = FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.END)
            desc_frame.addView(translate_btn, tr_lp)

            desc_card.addView(desc_frame, LayoutHelper.createLinear(-1, -2))
            root.addView(desc_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

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
                _make_section_header(act, "Dependencies"),
                LayoutHelper.createLinear(0, -2, 1.0)
            )
            dep_label = "library" if len(deps) == 1 else "libraries"
            count_chip = _make_chip(act, f"{len(deps)} {dep_label}", "key_color_purple")
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

            root.addView(deps_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

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
            others_header_row.addView(
                _make_section_header(act, f"More from {author}"),
                LayoutHelper.createLinear(0, -2, 1.0)
            )
            others_count_label = "plugin" if len(others) == 1 else "plugins"
            others_chip = _make_chip(act, f"{len(others)} {others_count_label}", "key_color_green")
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

            root.addView(others_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        log(f"pluginProfile: beforeCreateView done, content_view={self.content_view}")
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
        if icon_str and "/" in str(icon_str):
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(10))
            iv_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp))
            iv_lp.rightMargin = AndroidUtilities.dp(12)
            row.addView(iv, iv_lp)
            if not _try_load_sticker(iv, icon_str, size_dp):
                _schedule_sticker_retry(iv, icon_str, size_dp, self._alive)
        else:
            # placeholder when no icon
            placeholder = FrameLayout(act)
            ph_bg = GradientDrawable()
            ph_bg.setShape(GradientDrawable.RECTANGLE)
            ph_bg.setCornerRadius(AndroidUtilities.dp(10))
            ph_bg.setColor(Theme.getColor(Theme.key_windowBackgroundGray))
            placeholder.setBackground(ph_bg)
            ph_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp))
            ph_lp.rightMargin = AndroidUtilities.dp(12)
            row.addView(placeholder, ph_lp)

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
            info.addView(sub_tv, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        row.addView(info, LayoutHelper.createLinear(0, -2, 1.0))

        def onRowClick(v, target=plugin):
            show_plugin_profile(target, self.install_ui, self.all_plugins)
        row.setOnClickListener(OnClickListener(onRowClick))
        return row


def show_plugin_profile(plugin: dict, install_ui, all_plugins: list = None):
    try:
        fragment = get_last_fragment()
        if not fragment:
            log("pluginProfile: no fragment")
            return
        log(f"pluginProfile: show_plugin_profile plugin={plugin.get('id')}")
        delegate = PluginProfileFragment(plugin, install_ui, all_plugins or [])
        new_fragment = UniversalFragment(delegate)
        fragment.presentFragment(new_fragment)
        log(f"pluginProfile: presentFragment done")
        try:
            new_fragment.setTitle(str(plugin.get("name") or plugin.get("id") or "Plugin"), False, 0)
            action_bar = new_fragment.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
        except Exception as e:
            log(f"pluginProfile: actionBar setup error: {e}")
    except Exception as e:
        log(f"pluginProfile: show_plugin_profile error: {e}")

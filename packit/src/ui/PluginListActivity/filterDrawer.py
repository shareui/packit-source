# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from android.view import View, Gravity, ViewTreeObserver, MotionEvent
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView
from android.util import TypedValue
from android.graphics import Color
from android.graphics.drawable import GradientDrawable
from android.animation import ValueAnimator, Animator
from android.view.animation import DecelerateInterpolator
from java import dynamic_proxy
from hook_utils import find_class
from android_utils import OnClickListener
from .service import filterEngine
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    logx(f"SortDrawer: import Theme failed: {e}", False)
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    logx(f"SortDrawer: import AndroidUtilities failed: {e}", False)
try:
    from elyx import strings
except Exception as e:
    logx(f"SortDrawer: import strings failed: {e}", False)


_DRAWER_WIDTH_DP = 280
_ANIM_MS = 220


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.94).scaleY(0.94).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                except Exception:
                    pass
                return False
        view.setOnTouchListener(_TouchListener())
    except Exception:
        pass


def _accent():
    try:
        return Theme.getColor(Theme.key_featuredStickers_addButton)
    except Exception:
        return Color.parseColor("#2196F3")


def _accent_pressed():
    try:
        return Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
    except Exception:
        return _accent()


def _dialog_bg():
    try:
        return Theme.getColor(Theme.key_dialogBackground)
    except Exception:
        return Color.parseColor("#1E1E1E")


def _text_primary():
    try:
        return Theme.getColor(Theme.key_dialogTextBlack)
    except Exception:
        return Color.WHITE


def _text_secondary():
    try:
        return Theme.getColor(Theme.key_dialogTextGray3)
    except Exception:
        return Color.GRAY


def _section_bg(dialog_bg):
    # slightly darker than drawer bg
    r = (dialog_bg >> 16) & 0xFF
    g = (dialog_bg >> 8) & 0xFF
    b = dialog_bg & 0xFF
    r2 = max(0, r - 18)
    g2 = max(0, g - 18)
    b2 = max(0, b - 18)
    import ctypes
    return ctypes.c_int32((0xFF << 24) | (r2 << 16) | (g2 << 8) | b2).value


def _make_pill_bg(color, radius_dp, stroke_color=None, stroke_dp=1):
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(AndroidUtilities.dp(radius_dp))
    bg.setColor(color)
    if stroke_color is not None:
        bg.setStroke(AndroidUtilities.dp(stroke_dp), stroke_color)
    return bg


def _format_app_version(expr):
    # ">=1.2.3" -> "1.2.3 or higher", "<=1.2.3" -> "1.2.3 or lower", "==1.2.3" -> "1.2.3"
    if not expr:
        return str(expr)
    s = str(expr).strip()
    if s.startswith(">=") or s.startswith("=>"):
        v = s[2:].strip()
        try:
            return str(strings["filter_version_or_higher"]).replace("{version}", v)
        except Exception:
            return v + " or higher"
    if s.startswith("<=") or s.startswith("=<"):
        v = s[2:].strip()
        try:
            return str(strings["filter_version_or_lower"]).replace("{version}", v)
        except Exception:
            return v + " or lower"
    if s.startswith("=="):
        return s[2:].strip()
    return s


def _collect_authors(plugins):
    seen = {}
    for p in plugins:
        a = str(p.get("author") or "").strip()
        if a and a.lower() != "unknown":
            seen[a] = seen.get(a, 0) + 1
    return seen


def _collect_app_versions(plugins):
    seen = {}
    for p in plugins:
        v = str(p.get("app_version") or "").strip()
        if v and v.lower() != "unknown":
            seen[v] = seen.get(v, 0) + 1
    return seen


class SortDrawer:
    def __init__(self, act, content_view, plugins, selected_tags, on_apply,
                 selected_authors=None, selected_app_versions=None, selected_saved=None):
        self.act = act
        self.content_view = content_view
        self._decor_view = act.getWindow().getDecorView()
        self.plugins = plugins
        self.on_apply = on_apply

        self._is_open = False
        self._current_selected = set(selected_tags) if selected_tags else set()
        self._tags_summary = {}
        self._tag_rows = {}     # tag_name -> (row_view, border_drawable)
        self._tags_expanded = False

        self._authors_summary = {}
        self._author_rows = {}
        self._authors_expanded = False
        self._current_authors = set(selected_authors) if selected_authors else set()

        self._app_versions_summary = {}
        self._app_version_rows = {}
        self._app_versions_expanded = False
        self._current_app_versions = set(selected_app_versions) if selected_app_versions else set()

        # saved filter: set of "saved" and/or "unsaved", both active by default
        self._saved_rows = {}
        self._saved_expanded = False
        self._current_saved = set(selected_saved) if selected_saved else {"saved", "unsaved"}

        self._overlay = None
        self._drawer = None
        self._drawer_width = AndroidUtilities.dp(_DRAWER_WIDTH_DP)

        self._build()

    def _build(self):
        try:
            act = self.act
            bg = _dialog_bg()

            # dim overlay
            self._overlay = FrameLayout(act)
            self._overlay.setBackgroundColor(Color.argb(0, 0, 0, 0))
            self._overlay.setClickable(False)
            self._overlay.setFocusable(False)
            self._overlay.setVisibility(View.GONE)
            self._overlay.setOnClickListener(OnClickListener(lambda v: self.close()))

            # drawer panel
            self._drawer = LinearLayout(act)
            self._drawer.setOrientation(LinearLayout.VERTICAL)
            self._drawer.setClickable(True)
            self._drawer.setFocusable(True)
            self._drawer.setBackground(_make_pill_bg(
                bg, 16,
                # left corners rounded only — approximate with full radius, clipped by edge
            ))
            try:
                drawer_bg = GradientDrawable()
                drawer_bg.setShape(GradientDrawable.RECTANGLE)
                drawer_bg.setCornerRadii([
                    AndroidUtilities.dp(16), AndroidUtilities.dp(16),
                    0.0, 0.0,
                    0.0, 0.0,
                    AndroidUtilities.dp(16), AndroidUtilities.dp(16),
                ])
                drawer_bg.setColor(bg)
                self._drawer.setBackground(drawer_bg)
            except Exception:
                self._drawer.setBackgroundColor(bg)

            self._drawer.setTranslationX(self._drawer_width)

            # scroll area
            scroll = ScrollView(act)
            scroll.setFillViewport(True)
            scroll.setVerticalScrollBarEnabled(False)

            inner = LinearLayout(act)
            inner.setOrientation(LinearLayout.VERTICAL)
            inner.setPadding(
                AndroidUtilities.dp(12), AndroidUtilities.dp(16),
                AndroidUtilities.dp(12), AndroidUtilities.dp(8)
            )

            self._spacer = View(act)
            inner.addView(self._spacer, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

            self._tags_section_view = self._build_section(inner, bg)
            inner.addView(self._tags_section_view, LinearLayout.LayoutParams(-1, -2))

            authors_lp = LinearLayout.LayoutParams(-1, -2)
            authors_lp.setMargins(0, AndroidUtilities.dp(8), 0, 0)
            self._authors_section_view = self._build_generic_section(inner, bg, "authors")
            inner.addView(self._authors_section_view, authors_lp)

            appver_lp = LinearLayout.LayoutParams(-1, -2)
            appver_lp.setMargins(0, AndroidUtilities.dp(8), 0, 0)
            self._appver_section_view = self._build_generic_section(inner, bg, "app_versions")
            inner.addView(self._appver_section_view, appver_lp)

            saved_lp = LinearLayout.LayoutParams(-1, -2)
            saved_lp.setMargins(0, AndroidUtilities.dp(8), 0, 0)
            self._saved_section_view = self._build_generic_section(inner, bg, "saved")
            inner.addView(self._saved_section_view, saved_lp)

            scroll.addView(inner, FrameLayout.LayoutParams(-1, -2))

            scroll.setFadingEdgeLength(AndroidUtilities.dp(32))
            scroll.setVerticalFadingEdgeEnabled(True)

            # wrap scroll + bottom gradient in a FrameLayout
            scroll_container = FrameLayout(act)
            scroll_lp = LinearLayout.LayoutParams(-1, 0, 1.0)
            scroll_container.addView(scroll, FrameLayout.LayoutParams(-1, -1))

            fade_h = AndroidUtilities.dp(40)
            bottom_fade = View(act)
            try:
                from android.graphics import LinearGradient, Shader, Paint, Canvas
                fade_drawable = GradientDrawable(
                    GradientDrawable.Orientation.BOTTOM_TOP,
                    [bg, Color.TRANSPARENT]
                )
                bottom_fade.setBackground(fade_drawable)
            except Exception:
                bottom_fade.setBackgroundColor(Color.TRANSPARENT)
            fade_lp = FrameLayout.LayoutParams(-1, fade_h, Gravity.BOTTOM)
            scroll_container.addView(bottom_fade, fade_lp)

            self._drawer.addView(scroll_container, scroll_lp)
            self._drawer.addView(self._build_buttons(), LinearLayout.LayoutParams(-1, -2))

            self._decor_view.addView(self._overlay, FrameLayout.LayoutParams(-1, -1))
            self._decor_view.addView(
                self._drawer,
                FrameLayout.LayoutParams(self._drawer_width, -1, Gravity.RIGHT)
            )
        except Exception as e:
            logx(f"SortDrawer._build error: {e}", False)

    def _build_section(self, parent, drawer_bg):
        act = self.act
        try:
            sec_bg = Theme.getColor(Theme.key_dialogLineProgressBackground)
        except Exception:
            sec_bg = _section_bg(drawer_bg)

        section = LinearLayout(act)
        section.setOrientation(LinearLayout.VERTICAL)

        # section header row
        header = FrameLayout(act)
        header.setClickable(True)
        header.setFocusable(True)
        header.setPadding(
            AndroidUtilities.dp(14), AndroidUtilities.dp(12),
            AndroidUtilities.dp(14), AndroidUtilities.dp(12)
        )
        header.setBackground(_make_pill_bg(sec_bg, 10))

        header_inner = LinearLayout(act)
        header_inner.setOrientation(LinearLayout.HORIZONTAL)
        header_inner.setGravity(Gravity.CENTER_VERTICAL)

        title_tv = TextView(act)
        try:
            title_tv.setText(strings["tags_section_title"])
        except Exception:
            title_tv.setText(str(strings["filter_tags_title"]))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        try:
            title_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        title_tv.setTextColor(_text_primary())

        self._chevron_iv = ImageView(act)
        try:
            R_tg = find_class("org.telegram.messenger.R")
            self._chevron_iv.setImageResource(int(R_tg.drawable.arrow_more))
        except Exception:
            pass
        self._chevron_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        self._chevron_iv.setColorFilter(_text_secondary())
        # start collapsed → arrow pointing right (0°), expanded → down (90°)
        self._chevron_iv.setRotation(0.0)

        header_inner.addView(title_tv, LinearLayout.LayoutParams(0, -2, 1.0))
        header_inner.addView(self._chevron_iv, LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20)))
        header.addView(header_inner, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER_VERTICAL))

        # tags list — hidden by default
        self._tags_list = LinearLayout(act)
        self._tags_list.setOrientation(LinearLayout.VERTICAL)
        self._tags_list.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(2))
        self._tags_list.setVisibility(View.GONE)

        def on_header_click(v):
            self._tags_expanded = not self._tags_expanded
            try:
                self._chevron_iv.animate().rotation(180.0 if self._tags_expanded else 0.0).setDuration(200).start()
            except Exception:
                self._chevron_iv.setRotation(180.0 if self._tags_expanded else 0.0)

            tags_list_ref = self._tags_list

            if self._tags_expanded:
                tags_list_ref.setAlpha(0.0)
                tags_list_ref.setVisibility(View.VISIBLE)
                measure_w = tags_list_ref.getWidth()
                if measure_w <= 0:
                    try:
                        measure_w = tags_list_ref.getParent().getWidth()
                    except Exception:
                        measure_w = 0
                spec_w = (View.MeasureSpec.makeMeasureSpec(measure_w, View.MeasureSpec.EXACTLY)
                          if measure_w > 0
                          else View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
                tags_list_ref.measure(
                    spec_w,
                    View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
                )
                target_h = tags_list_ref.getMeasuredHeight()
                tags_list_ref.getLayoutParams().height = 0
                tags_list_ref.requestLayout()
                try:
                    class _UpdateExpand(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                        def onAnimationUpdate(self, a):
                            tags_list_ref.getLayoutParams().height = int(a.getAnimatedValue())
                            tags_list_ref.requestLayout()

                    class _EndExpand(dynamic_proxy(Animator.AnimatorListener)):
                        def onAnimationEnd(self, a, *args):
                            tags_list_ref.getLayoutParams().height = -2
                            tags_list_ref.requestLayout()
                        def onAnimationStart(self, a, *args): pass
                        def onAnimationCancel(self, a, *args): pass
                        def onAnimationRepeat(self, a, *args): pass

                    anim = ValueAnimator.ofInt(0, target_h)
                    anim.setDuration(220)
                    anim.addUpdateListener(_UpdateExpand())
                    anim.addListener(_EndExpand())
                    anim.start()
                    tags_list_ref.animate().alpha(1.0).setDuration(220).start()
                except Exception:
                    tags_list_ref.getLayoutParams().height = -2
                    tags_list_ref.setAlpha(1.0)
                    tags_list_ref.requestLayout()
            else:
                start_h = tags_list_ref.getMeasuredHeight()
                try:
                    class _UpdateCollapse(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                        def onAnimationUpdate(self, a):
                            tags_list_ref.getLayoutParams().height = int(a.getAnimatedValue())
                            tags_list_ref.requestLayout()

                    class _EndCollapse(dynamic_proxy(Animator.AnimatorListener)):
                        def onAnimationEnd(self, a, *args):
                            tags_list_ref.setVisibility(View.GONE)
                            tags_list_ref.getLayoutParams().height = -2
                            tags_list_ref.setAlpha(1.0)
                            tags_list_ref.requestLayout()
                        def onAnimationStart(self, a, *args): pass
                        def onAnimationCancel(self, a, *args): pass
                        def onAnimationRepeat(self, a, *args): pass

                    anim = ValueAnimator.ofInt(start_h, 0)
                    anim.setDuration(180)
                    anim.addUpdateListener(_UpdateCollapse())
                    anim.addListener(_EndCollapse())
                    anim.start()
                    tags_list_ref.animate().alpha(0.0).setDuration(180).start()
                except Exception:
                    tags_list_ref.setVisibility(View.GONE)

        header.setOnClickListener(OnClickListener(on_header_click))

        section.addView(header, LinearLayout.LayoutParams(-1, -2))
        section.addView(self._tags_list, LinearLayout.LayoutParams(-1, -2))

        return section

    def _build_tag_row(self, tag_name, count, is_selected):
        act = self.act

        accent = _accent()
        import ctypes
        ar = (accent >> 16) & 0xFF
        ag = (accent >> 8) & 0xFF
        ab = accent & 0xFF
        # active fill: accent@20% composited over drawer bg — opaque, no alpha lerp flash
        try:
            bg_c = _dialog_bg()
            bgr = (bg_c >> 16) & 0xFF
            bgg = (bg_c >> 8) & 0xFF
            bgb = bg_c & 0xFF
        except Exception:
            bgr = bgg = bgb = 30
        a_ratio = 0.20
        afr = int(bgr * (1 - a_ratio) + ar * a_ratio)
        afg = int(bgg * (1 - a_ratio) + ag * a_ratio)
        afb = int(bgb * (1 - a_ratio) + ab * a_ratio)
        active_fill = ctypes.c_int32((0xFF << 24) | (afr << 16) | (afg << 8) | afb).value
        # inactive: slightly lighter than drawer bg so it's visible against it
        inactive_fill = ctypes.c_int32((0xFF << 24) | (min(255, bgr + 22) << 16) | (min(255, bgg + 22) << 8) | min(255, bgb + 22)).value
        # active text: accent darkened by 20% for better readability on tinted bg
        ar = max(0, int(((accent >> 16) & 0xFF) * 0.80))
        ag = max(0, int(((accent >> 8) & 0xFF) * 0.80))
        ab = max(0, int((accent & 0xFF) * 0.80))
        active_text = ctypes.c_int32((0xFF << 24) | (ar << 16) | (ag << 8) | ab).value
        # inactive text: standard secondary gray
        inactive_text = _text_secondary()

        pill = GradientDrawable()
        pill.setShape(GradientDrawable.RECTANGLE)
        pill.setCornerRadius(AndroidUtilities.dp(10))
        pill.setColor(active_fill if is_selected else inactive_fill)

        row = FrameLayout(act)
        row.setClickable(True)
        row.setFocusable(True)
        row.setPadding(
            AndroidUtilities.dp(12), AndroidUtilities.dp(11),
            AndroidUtilities.dp(12), AndroidUtilities.dp(11)
        )
        row.setBackground(pill)

        inner = LinearLayout(act)
        inner.setOrientation(LinearLayout.HORIZONTAL)
        inner.setGravity(Gravity.CENTER_VERTICAL)

        name_tv = TextView(act)
        name_tv.setText(tag_name)
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        name_tv.setTextColor(active_text if is_selected else inactive_text)
        try:
            name_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass

        inner.addView(name_tv, LinearLayout.LayoutParams(-1, -2))
        row.addView(inner, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER_VERTICAL))
        _apply_press_scale(row)

        return row, pill, name_tv

    def _update_row_style(self, pill, name_tv, is_selected):
        try:
            accent = _accent()
            import ctypes
            r = (accent >> 16) & 0xFF
            g = (accent >> 8) & 0xFF
            b = accent & 0xFF
            try:
                bg_c = _dialog_bg()
                bgr = (bg_c >> 16) & 0xFF
                bgg = (bg_c >> 8) & 0xFF
                bgb = bg_c & 0xFF
            except Exception:
                bgr = bgg = bgb = 30
            a_ratio = 0.20
            afr = int(bgr * (1 - a_ratio) + r * a_ratio)
            afg = int(bgg * (1 - a_ratio) + g * a_ratio)
            afb = int(bgb * (1 - a_ratio) + b * a_ratio)
            active_fill = ctypes.c_int32((0xFF << 24) | (afr << 16) | (afg << 8) | afb).value
            try:
                ifr = min(255, bgr + 22)
                ifg = min(255, bgg + 22)
                ifb = min(255, bgb + 22)
                inactive_fill = ctypes.c_int32((0xFF << 24) | (ifr << 16) | (ifg << 8) | ifb).value
            except Exception:
                inactive_fill = Color.parseColor("#2A2A2A")
            active_text = ctypes.c_int32((0xFF << 24) | (max(0, int(r * 0.80)) << 16) | (max(0, int(g * 0.80)) << 8) | max(0, int(b * 0.80))).value
            inactive_text = _text_secondary()

            to_fill = active_fill if is_selected else inactive_fill
            to_text = active_text if is_selected else inactive_text

            # read current color from views so re-triggered animation starts from actual state
            try:
                from_fill = pill.getColor().getDefaultColor()
            except Exception:
                from_fill = inactive_fill if is_selected else active_fill
            try:
                from_text = name_tv.getCurrentTextColor()
            except Exception:
                from_text = inactive_text if is_selected else active_text

            def lerpColor(c1, c2, t):
                rv = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
                gv = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
                bv = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
                return Color.rgb(rv, gv, bv)

            pill_ref = pill
            tv_ref = name_tv

            class _Listener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self, anim):
                    t = float(anim.getAnimatedFraction())
                    pill_ref.setColor(lerpColor(from_fill, to_fill, t))
                    tv_ref.setTextColor(lerpColor(from_text, to_text, t))

            anim = ValueAnimator.ofFloat(0.0, 1.0)
            anim.setDuration(250)
            anim.setInterpolator(DecelerateInterpolator(2.0))
            anim.addUpdateListener(_Listener())
            anim.start()
        except Exception as e:
            logx(f"SortDrawer._update_row_style error: {e}", False)

    def _build_buttons(self):
        act = self.act
        accent = _accent()
        pressed = _accent_pressed()

        try:
            divider_color = Theme.getColor(Theme.key_divider)
        except Exception:
            divider_color = Color.argb(40, 127, 127, 127)

        outer = LinearLayout(act)
        outer.setOrientation(LinearLayout.VERTICAL)

        divider = View(act)
        divider.setBackgroundColor(divider_color)
        outer.addView(divider, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1)))

        bar = LinearLayout(act)
        bar.setOrientation(LinearLayout.HORIZONTAL)
        bar.setPadding(
            AndroidUtilities.dp(12), AndroidUtilities.dp(12),
            AndroidUtilities.dp(12), AndroidUtilities.dp(20)
        )
        bar.setGravity(Gravity.CENTER_VERTICAL)

        # Reset
        reset_btn = FrameLayout(act)
        reset_btn.setClickable(True)
        reset_btn.setFocusable(True)
        reset_btn.setPadding(0, AndroidUtilities.dp(12), 0, AndroidUtilities.dp(12))
        reset_bg = GradientDrawable()
        reset_bg.setShape(GradientDrawable.RECTANGLE)
        reset_bg.setCornerRadius(AndroidUtilities.dp(24))
        reset_bg.setColor(Color.TRANSPARENT)
        reset_bg.setStroke(AndroidUtilities.dp(1), accent)
        reset_btn.setBackground(reset_bg)

        reset_tv = TextView(act)
        try:
            reset_tv.setText(strings["reset_button"])
        except Exception:
            reset_tv.setText(str(strings["filter_reset"]))
        reset_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        reset_tv.setGravity(Gravity.CENTER)
        reset_tv.setTextColor(accent)
        try:
            reset_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        reset_btn.addView(reset_tv, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))

        # Apply
        apply_btn = FrameLayout(act)
        apply_btn.setClickable(True)
        apply_btn.setFocusable(True)
        apply_btn.setPadding(0, AndroidUtilities.dp(12), 0, AndroidUtilities.dp(12))
        apply_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(24), accent, pressed
        ))

        apply_tv = TextView(act)
        try:
            apply_tv.setText(strings["apply_button"])
        except Exception:
            apply_tv.setText(str(strings["apply_button"]))
        apply_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        apply_tv.setGravity(Gravity.CENTER)
        try:
            apply_tv.setTextColor(Theme.getColor(Theme.key_dialogScrollGlow))
        except Exception:
            apply_tv.setTextColor(_text_primary())
        try:
            apply_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        apply_btn.addView(apply_tv, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))

        reset_lp = LinearLayout.LayoutParams(0, -2, 1.0)
        reset_lp.setMargins(0, 0, AndroidUtilities.dp(8), 0)
        apply_lp = LinearLayout.LayoutParams(0, -2, 1.5)

        def on_reset(v):
            self._current_selected = set(self._tags_summary.keys())
            self._current_authors = set(self._authors_summary.keys())
            self._current_app_versions = set(self._app_versions_summary.keys())
            self._current_saved = {"saved", "unsaved"}
            self._refresh_rows()

        def on_apply(v):
            self.on_apply(
                set(self._current_selected),
                set(self._current_authors),
                set(self._current_app_versions),
                set(self._current_saved),
            )
            self.close()

        reset_btn.setOnClickListener(OnClickListener(on_reset))
        apply_btn.setOnClickListener(OnClickListener(on_apply))

        bar.addView(reset_btn, reset_lp)
        bar.addView(apply_btn, apply_lp)
        outer.addView(bar, LinearLayout.LayoutParams(-1, -2))

        return outer

    def _build_generic_section(self, parent, drawer_bg, section_key):
        # section_key: "authors" | "app_versions" | "saved"
        act = self.act
        try:
            sec_bg = Theme.getColor(Theme.key_dialogLineProgressBackground)
        except Exception:
            sec_bg = _section_bg(drawer_bg)

        section = LinearLayout(act)
        section.setOrientation(LinearLayout.VERTICAL)

        header = FrameLayout(act)
        header.setClickable(True)
        header.setFocusable(True)
        header.setPadding(
            AndroidUtilities.dp(14), AndroidUtilities.dp(12),
            AndroidUtilities.dp(14), AndroidUtilities.dp(12)
        )
        header.setBackground(_make_pill_bg(sec_bg, 10))

        header_inner = LinearLayout(act)
        header_inner.setOrientation(LinearLayout.HORIZONTAL)
        header_inner.setGravity(Gravity.CENTER_VERTICAL)

        title_tv = TextView(act)
        if section_key == "authors":
            try:
                title_tv.setText(strings["authors_section_title"])
            except Exception:
                title_tv.setText("Authors")
        elif section_key == "saved":
            try:
                title_tv.setText(strings["saved_section_title"])
            except Exception:
                title_tv.setText("Saved Plugins")
        else:
            try:
                title_tv.setText(strings["app_version_section_title"])
            except Exception:
                title_tv.setText("App Version")
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        try:
            title_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        title_tv.setTextColor(_text_primary())

        chevron = ImageView(act)
        try:
            R_tg = find_class("org.telegram.messenger.R")
            chevron.setImageResource(int(R_tg.drawable.arrow_more))
        except Exception:
            pass
        chevron.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        chevron.setColorFilter(_text_secondary())
        chevron.setRotation(0.0)

        header_inner.addView(title_tv, LinearLayout.LayoutParams(0, -2, 1.0))
        header_inner.addView(chevron, LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20)))
        header.addView(header_inner, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER_VERTICAL))

        items_list = LinearLayout(act)
        items_list.setOrientation(LinearLayout.VERTICAL)
        items_list.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(2))
        items_list.setVisibility(View.GONE)

        if section_key == "authors":
            self._authors_list = items_list
        elif section_key == "saved":
            self._saved_list = items_list
        else:
            self._app_versions_list = items_list

        def on_click(v):
            if section_key == "authors":
                self._authors_expanded = not self._authors_expanded
                expanded = self._authors_expanded
            elif section_key == "saved":
                self._saved_expanded = not self._saved_expanded
                expanded = self._saved_expanded
            else:
                self._app_versions_expanded = not self._app_versions_expanded
                expanded = self._app_versions_expanded

            try:
                chevron.animate().rotation(180.0 if expanded else 0.0).setDuration(200).start()
            except Exception:
                chevron.setRotation(180.0 if expanded else 0.0)

            list_ref = items_list
            if expanded:
                list_ref.setAlpha(0.0)
                list_ref.setVisibility(View.VISIBLE)
                measure_w = list_ref.getWidth()
                if measure_w <= 0:
                    try:
                        measure_w = list_ref.getParent().getWidth()
                    except Exception:
                        measure_w = 0
                spec_w = (View.MeasureSpec.makeMeasureSpec(measure_w, View.MeasureSpec.EXACTLY)
                          if measure_w > 0
                          else View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
                list_ref.measure(
                    spec_w,
                    View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
                )
                target_h = list_ref.getMeasuredHeight()
                list_ref.getLayoutParams().height = 0
                list_ref.requestLayout()
                try:
                    class _UE(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                        def onAnimationUpdate(self, a):
                            list_ref.getLayoutParams().height = int(a.getAnimatedValue())
                            list_ref.requestLayout()

                    class _EE(dynamic_proxy(Animator.AnimatorListener)):
                        def onAnimationEnd(self, a, *args):
                            list_ref.getLayoutParams().height = -2
                            list_ref.requestLayout()
                        def onAnimationStart(self, a, *args): pass
                        def onAnimationCancel(self, a, *args): pass
                        def onAnimationRepeat(self, a, *args): pass

                    anim = ValueAnimator.ofInt(0, target_h)
                    anim.setDuration(220)
                    anim.addUpdateListener(_UE())
                    anim.addListener(_EE())
                    anim.start()
                    list_ref.animate().alpha(1.0).setDuration(220).start()
                except Exception:
                    list_ref.getLayoutParams().height = -2
                    list_ref.setAlpha(1.0)
                    list_ref.requestLayout()
            else:
                start_h = list_ref.getMeasuredHeight()
                try:
                    class _UC(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                        def onAnimationUpdate(self, a):
                            list_ref.getLayoutParams().height = int(a.getAnimatedValue())
                            list_ref.requestLayout()

                    class _EC(dynamic_proxy(Animator.AnimatorListener)):
                        def onAnimationEnd(self, a, *args):
                            list_ref.setVisibility(View.GONE)
                            list_ref.getLayoutParams().height = -2
                            list_ref.setAlpha(1.0)
                            list_ref.requestLayout()
                        def onAnimationStart(self, a, *args): pass
                        def onAnimationCancel(self, a, *args): pass
                        def onAnimationRepeat(self, a, *args): pass

                    anim = ValueAnimator.ofInt(start_h, 0)
                    anim.setDuration(180)
                    anim.addUpdateListener(_UC())
                    anim.addListener(_EC())
                    anim.start()
                    list_ref.animate().alpha(0.0).setDuration(180).start()
                except Exception:
                    list_ref.setVisibility(View.GONE)

        header.setOnClickListener(OnClickListener(on_click))
        section.addView(header, LinearLayout.LayoutParams(-1, -2))
        section.addView(items_list, LinearLayout.LayoutParams(-1, -2))
        return section

    def _populate_generic(self, section_key):
        try:
            if section_key == "authors":
                self._authors_list.removeAllViews()
                self._author_rows.clear()
                self._authors_summary = _collect_authors(self.plugins)
                if not self._current_authors:
                    self._current_authors = set(self._authors_summary.keys())
                summary = self._authors_summary
                current_sel = self._current_authors
                rows_dict = self._author_rows
                list_view = self._authors_list
                label_fn = lambda k: k
            elif section_key == "saved":
                self._saved_list.removeAllViews()
                self._saved_rows.clear()
                saved_items = {
                    "saved": str(strings["saved_filter_saved"]) if "saved_filter_saved" in dir(strings) else "Saved plugins",
                    "unsaved": str(strings["saved_filter_unsaved"]) if "saved_filter_unsaved" in dir(strings) else "Unsaved plugins",
                }
                try:
                    saved_items = {
                        "saved": str(strings["saved_filter_saved"]),
                        "unsaved": str(strings["saved_filter_unsaved"]),
                    }
                except Exception:
                    pass
                if not self._current_saved:
                    self._current_saved = {"saved", "unsaved"}
                for key, label in saved_items.items():
                    is_sel = key in self._current_saved
                    row, border, name_tv = self._build_tag_row(label, 0, is_sel)

                    def make_saved_handler(k, bdr, ntv):
                        def handler(v):
                            if k in self._current_saved:
                                self._current_saved.discard(k)
                            else:
                                self._current_saved.add(k)
                            self._update_row_style(bdr, ntv, k in self._current_saved)
                        return handler

                    row.setOnClickListener(OnClickListener(make_saved_handler(key, border, name_tv)))
                    row_lp = LinearLayout.LayoutParams(-1, -2)
                    row_lp.setMargins(0, 0, 0, AndroidUtilities.dp(6))
                    self._saved_list.addView(row, row_lp)
                    self._saved_rows[key] = (row, border, name_tv)
                return
            else:
                self._app_versions_list.removeAllViews()
                self._app_version_rows.clear()
                self._app_versions_summary = _collect_app_versions(self.plugins)
                if not self._current_app_versions:
                    self._current_app_versions = set(self._app_versions_summary.keys())
                summary = self._app_versions_summary
                current_sel = self._current_app_versions
                rows_dict = self._app_version_rows
                list_view = self._app_versions_list
                label_fn = _format_app_version

            for key, count in summary.items():
                is_sel = key in current_sel
                row, border, name_tv = self._build_tag_row(label_fn(key), count, is_sel)

                def make_handler(k, bdr, ntv, sel_set):
                    def handler(v):
                        if k in sel_set:
                            sel_set.discard(k)
                        else:
                            sel_set.add(k)
                        self._update_row_style(bdr, ntv, k in sel_set)
                    return handler

                row.setOnClickListener(OnClickListener(make_handler(key, border, name_tv, current_sel)))
                row_lp = LinearLayout.LayoutParams(-1, -2)
                row_lp.setMargins(0, 0, 0, AndroidUtilities.dp(6))
                list_view.addView(row, row_lp)
                rows_dict[key] = (row, border, name_tv)
        except Exception as e:
            logx(f"SortDrawer._populate_generic({section_key}) error: {e}", False)

    def _populate_tags(self):
        try:
            self._tags_list.removeAllViews()
            self._tag_rows.clear()
            self._tags_summary = filterEngine.collect_tags(self.plugins)

            if not self._current_selected:
                self._current_selected = set(self._tags_summary.keys())

            for tag_name, count in self._tags_summary.items():
                # use localized label for unsorted, keep key internal
                if tag_name == filterEngine._UNSORTED_KEY:
                    try:
                        from elyx import strings as _s
                        display_name = str(_s["filter_tag_unsorted"])
                    except Exception:
                        display_name = "Unsorted"
                else:
                    display_name = tag_name
                is_sel = tag_name in self._current_selected
                row, border, name_tv = self._build_tag_row(display_name, count, is_sel)

                def make_handler(name, bdr, ntv):
                    def handler(v):
                        if name in self._current_selected:
                            self._current_selected.discard(name)
                        else:
                            self._current_selected.add(name)
                        self._update_row_style(bdr, ntv, name in self._current_selected)
                    return handler

                row.setOnClickListener(OnClickListener(make_handler(tag_name, border, name_tv)))

                row_lp = LinearLayout.LayoutParams(-1, -2)
                row_lp.setMargins(0, 0, 0, AndroidUtilities.dp(6))
                self._tags_list.addView(row, row_lp)
                self._tag_rows[tag_name] = (row, border, name_tv)
        except Exception as e:
            logx(f"SortDrawer._populate_tags error: {e}", False)

    def _refresh_rows(self):
        for tag_name, (row, border, name_tv) in self._tag_rows.items():
            self._update_row_style(border, name_tv, tag_name in self._current_selected)
        for key, (row, border, name_tv) in self._author_rows.items():
            self._update_row_style(border, name_tv, key in self._current_authors)
        for key, (row, border, name_tv) in self._app_version_rows.items():
            self._update_row_style(border, name_tv, key in self._current_app_versions)
        for key, (row, border, name_tv) in self._saved_rows.items():
            self._update_row_style(border, name_tv, key in self._current_saved)

    def _register_back_callback(self):
        try:
            from androidx.activity import OnBackPressedCallback
            from extera_utils.classes import Base, java_subclass, joverride
            drawer_ref = self

            @java_subclass(OnBackPressedCallback)
            class _BackCallback(Base):
                @joverride()
                def handleOnBackPressed(self):
                    drawer_ref.close()

            cb = _BackCallback.new_instance(True)
            self._back_callback = cb
            self.act.getOnBackPressedDispatcher().addCallback(self.act, cb.java)
        except Exception as e:
            logx(f"SortDrawer._register_back_callback error: {e}", False)
            self._back_callback = None

    def _unregister_back_callback(self):
        try:
            cb = getattr(self, '_back_callback', None)
            if cb is not None:
                cb.remove()
                self._back_callback = None
        except Exception as e:
            logx(f"SortDrawer._unregister_back_callback error: {e}", False)

    def open(self, selected_tags, selected_authors=None, selected_app_versions=None, selected_saved=None):
        try:
            self._current_selected = set(selected_tags) if selected_tags else set()
            if selected_authors is not None:
                self._current_authors = set(selected_authors)
            if selected_app_versions is not None:
                self._current_app_versions = set(selected_app_versions)
            if selected_saved is not None:
                self._current_saved = set(selected_saved)
            self._populate_tags()
            self._populate_generic("authors")
            self._populate_generic("app_versions")
            self._populate_generic("saved")
            self._overlay.setVisibility(View.VISIBLE)
            self._overlay.setClickable(True)
            self._is_open = True
            self._animate(True)
            self._adjust_spacer()
            self._register_back_callback()
        except Exception as e:
            logx(f"SortDrawer.open error: {e}", False)

    def _adjust_spacer(self):
        spacer_ref = self._spacer
        section_ref = self._tags_section_view

        class _LayoutListener(dynamic_proxy(ViewTreeObserver.OnGlobalLayoutListener)):
            def onGlobalLayout(self):
                try:
                    h = section_ref.getHeight()
                    if h > 0:
                        section_ref.getViewTreeObserver().removeOnGlobalLayoutListener(self)
                        spacer_ref.getLayoutParams().height = h
                        spacer_ref.requestLayout()
                except Exception as ex:
                    logx(f"SortDrawer._adjust_spacer error: {ex}", True)

        section_ref.getViewTreeObserver().addOnGlobalLayoutListener(_LayoutListener())

    def close(self):
        try:
            self._is_open = False
            self._unregister_back_callback()
            self._animate(False)
        except Exception as e:
            logx(f"SortDrawer.close error: {e}", False)

    def _animate(self, opening):
        try:
            target = 0.0 if opening else float(self._drawer_width)
            start = self._drawer.getTranslationX()

            animator = ValueAnimator.ofFloat(start, target)
            animator.setDuration(_ANIM_MS)

            drawer_ref = self._drawer
            overlay_ref = self._overlay
            width = float(self._drawer_width)

            class _UpdateListener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self, anim):
                    try:
                        val = float(anim.getAnimatedValue())
                        drawer_ref.setTranslationX(val)
                        progress = max(0.0, min(1.0, 1.0 - val / width)) if width > 0 else 0.0
                        overlay_ref.setBackgroundColor(Color.argb(int(progress * 110), 0, 0, 0))
                    except Exception:
                        pass

            decor_ref = self._decor_view
            drawer_ref2 = self._drawer

            class _EndListener(dynamic_proxy(Animator.AnimatorListener)):
                def onAnimationEnd(self, *args):
                    if not opening:
                        overlay_ref.setVisibility(View.GONE)
                        overlay_ref.setClickable(False)
                        try:
                            decor_ref.removeView(overlay_ref)
                            decor_ref.removeView(drawer_ref2)
                        except Exception:
                            pass
                def onAnimationStart(self, *args): pass
                def onAnimationCancel(self, *args): pass
                def onAnimationRepeat(self, *args): pass

            animator.addUpdateListener(_UpdateListener())
            animator.addListener(_EndListener())
            animator.start()
        except Exception as e:
            logx(f"SortDrawer._animate error: {e}", False)
            # snap fallback
            target = 0.0 if opening else float(self._drawer_width)
            self._drawer.setTranslationX(target)
            if not opening:
                self._overlay.setVisibility(View.GONE)
                self._overlay.setClickable(False)
                try:
                    self._decor_view.removeView(self._overlay)
                    self._decor_view.removeView(self._drawer)
                except Exception:
                    pass


def show_tag_drawer(act, content_view, plugins, selected_tags, on_apply,
                    selected_authors=None, selected_app_versions=None, selected_saved=None):
    try:
        drawer = SortDrawer(act, content_view, plugins, selected_tags, on_apply,
                            selected_authors, selected_app_versions, selected_saved)
        drawer.open(selected_tags, selected_authors, selected_app_versions, selected_saved)
        return drawer
    except Exception as e:
        logx(f"show_tag_drawer error: {e}", False)
        return None
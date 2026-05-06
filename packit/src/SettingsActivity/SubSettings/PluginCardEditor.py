import ctypes
from android.view import View, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, SeekBar
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.graphics import Canvas, Paint, RectF
from android.animation import ValueAnimator
from android_utils import OnClickListener, log, run_on_ui_thread
from client_utils import get_last_fragment
from java import dynamic_proxy, jarray, jfloat

try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"PluginCardEditor: import elyx failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"PluginCardEditor: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"PluginCardEditor: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"PluginCardEditor: import AndroidUtilities failed: {e}")
try:
    from org.telegram.ui.Components import BulletinFactory
except Exception as e:
    import android_utils as _au; _au.log(f"PluginCardEditor: import BulletinFactory failed: {e}")
    BulletinFactory = None

_KEY_SHOW_ICON    = "card_show_icon"
_KEY_ICON_SIZE    = "card_icon_size"
_KEY_SHOW_ID      = "card_show_id"
_KEY_ID_SIZE      = "card_id_size"
_KEY_NAME_SIZE    = "card_name_size"
_KEY_SHOW_DESC    = "card_show_desc"
_KEY_DESC_SIZE    = "card_desc_size"
_KEY_CARD_RADIUS  = "card_radius"
_KEY_CARD_PADDING = "card_padding"
_KEY_STICKER_RADIUS = "sticker_radius"

_DEFAULTS = {
    _KEY_SHOW_ICON:    True,
    _KEY_ICON_SIZE:    67,
    _KEY_SHOW_ID:      True,
    _KEY_ID_SIZE:      13,
    _KEY_NAME_SIZE:    20,
    _KEY_SHOW_DESC:    True,
    _KEY_DESC_SIZE:    15,
    _KEY_CARD_RADIUS:  18,
    _KEY_CARD_PADDING: 12,
    _KEY_STICKER_RADIUS: 18,
    "chip_gravity":    5,
    "chip_ver_size":   11,
    "chip_deps_size":  11,
    "chip_size_size":  11,
}

_EXTERNAL_DEFAULTS = {
    "show_default_sticker":    False,
    "show_plugin_tags":        True,
    "show_plugin_size":        False,
    "show_plugin_min_version": False,
    "show_plugin_deps_count":  False,
}

_BUTTON_DEFAULTS = {
    "relocate_copy_link": False,
    "relocate_share":      False,
    "relocate_code":       False,
    "relocate_download":   False,
    "relocate_translate":  False,
    "relocate_report":     False,
    "show_details_button":  False,
    "show_view_button":     False,
}


def _gs(key):
    return settings.get(key, _DEFAULTS.get(key, _EXTERNAL_DEFAULTS.get(key, _BUTTON_DEFAULTS.get(key, False))))


def _cs(key, val):
    settings.set(key, val)


def _card_color():
    base = Theme.getColor(Theme.key_windowBackgroundWhite)
    try:
        is_dark = Theme.isCurrentThemeDark()
    except Exception:
        r = (base >> 16) & 0xFF
        g = (base >> 8) & 0xFF
        b = base & 0xFF
        is_dark = (r * 299 + g * 587 + b * 114) < 128000
    if is_dark:
        r = min(255, ((base >> 16) & 0xFF) + 30)
        g = min(255, ((base >> 8) & 0xFF) + 26)
        b = min(255, (base & 0xFF) + 26)
        return ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
    return base


class _SeekTouchProxy(dynamic_proxy(View.OnTouchListener)):
    def onTouch(self, v, event):
        try:
            from android.view import MotionEvent
            action = event.getActionMasked()
            disallow = action == MotionEvent.ACTION_DOWN
            allow    = action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL)
            p = v.getParent()
            while p:
                try:
                    if disallow:
                        p.requestDisallowInterceptTouchEvent(True)
                    elif allow:
                        p.requestDisallowInterceptTouchEvent(False)
                    p = p.getParent()
                except Exception:
                    break
        except Exception:
            pass
        return False


class _SeekListener(dynamic_proxy(SeekBar.OnSeekBarChangeListener)):
    def __init__(self, cb):
        super().__init__()
        self.cb = cb

    def onProgressChanged(self, sb, progress, fromUser):
        self.cb(progress)

    def onStartTrackingTouch(self, sb):
        pass

    def onStopTrackingTouch(self, sb):
        pass


def _style_seekbar(sb):
    try:
        from android.content.res import ColorStateList
        accent   = ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader)).value
        inactive = ctypes.c_int32(Theme.getColor(Theme.key_switchTrack)).value
        sb.setProgressTintList(ColorStateList.valueOf(accent))
        sb.setThumbTintList(ColorStateList.valueOf(accent))
        sb.setProgressBackgroundTintList(ColorStateList.valueOf(inactive))
    except Exception:
        pass


class _HighlightDelegate:
    # draws animated rounded-rect highlight via UniversalView/UniversalViewDelegate
    def __init__(self):
        self._current_rect = RectF()
        self._target_rect  = RectF()
        self._radius = float(AndroidUtilities.dp(6))
        self._alpha  = 0.0
        self._anim   = None
        self.view    = None  # set after UniversalView is created

        accent = Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader)
        accent_int = ctypes.c_int32(accent).value
        from java import jint as _jint
        self._stroke = Paint(Paint.ANTI_ALIAS_FLAG)
        self._stroke.setStyle(Paint.Style.STROKE)
        self._stroke.setStrokeWidth(float(AndroidUtilities.dp(2)))
        self._stroke.setColor(_jint(accent_int))
        self._fill = Paint(Paint.ANTI_ALIAS_FLAG)
        self._fill.setStyle(Paint.Style.FILL)
        r = (accent_int >> 16) & 0xFF
        g = (accent_int >> 8)  & 0xFF
        b = accent_int & 0xFF
        fill_color = ctypes.c_int32((0x28 << 24) | (r << 16) | (g << 8) | b).value
        self._fill.setColor(_jint(fill_color))

    def _get_loc(self, v):
        try:
            # use jclass int[] to avoid Python int -> Integer[] mismatch
            IntArray = __import__('java').jclass('[I')
            arr = IntArray(2)
            v.getLocationOnScreen(arr)
            return int(arr[0]), int(arr[1])
        except Exception:
            try:
                arr = jarray(jfloat)(2)
                v.getLocationOnScreen(arr)
                return int(arr[0]), int(arr[1])
            except Exception:
                return 0, 0

    def setTarget(self, target_view, radius_dp=6):
        self._radius = float(AndroidUtilities.dp(radius_dp))
        if target_view is None:
            end = RectF()
        else:
            try:
                # coordinates relative to the overlay view itself
                sx, sy = self._get_loc(self.view)
                tx, ty = self._get_loc(target_view)
                x = tx - sx
                y = ty - sy
                w = target_view.getWidth()
                h = target_view.getHeight()
                log(f"highlight: self=({sx},{sy}) target=({tx},{ty}) -> ({x},{y}) {w}x{h}")
                end = RectF(float(x), float(y), float(x + w), float(y + h))
            except Exception as e:
                log(f"highlight: setTarget error: {e}")
                return
        self._start_anim(RectF(self._current_rect), end)

    def _start_anim(self, start, end):
        if self._anim:
            try: self._anim.cancel()
            except Exception: pass

        delegate = self

        class _Upd(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
            def __init__(self, s, e):
                super().__init__()
                self.s = s
                self.e = e

            def onAnimationUpdate(self, a):
                p = float(a.getAnimatedValue())
                delegate._current_rect.left   = self.s.left   + (self.e.left   - self.s.left)   * p
                delegate._current_rect.top    = self.s.top    + (self.e.top    - self.s.top)    * p
                delegate._current_rect.right  = self.s.right  + (self.e.right  - self.s.right)  * p
                delegate._current_rect.bottom = self.s.bottom + (self.e.bottom - self.s.bottom) * p
                delegate._alpha = p if not self.e.isEmpty() else 1.0 - p
                if delegate.view:
                    delegate.view.invalidate()

        try:
            from org.telegram.ui.Components import CubicBezierInterpolator
            anim = ValueAnimator.ofFloat(jarray(jfloat)([0.0, 1.0]))
            anim.setDuration(220)
            anim.setInterpolator(CubicBezierInterpolator.EASE_OUT_QUINT)
            anim.addUpdateListener(_Upd(start, end))
            anim.start()
            self._anim = anim
        except Exception as e:
            log(f"highlight: anim error: {e}")
            self._current_rect.set(end)
            self._alpha = 0.0 if end.isEmpty() else 1.0
            if self.view:
                self.view.invalidate()


def _make_highlight_view(context):
    # UniversalView + delegate — avoids dynamic_proxy(View) which requires interface
    try:
        from com.exteragram.messenger.plugins.ui.components.templates import UniversalView
        UniversalViewDelegate = UniversalView.UniversalViewDelegate

        delegate = _HighlightDelegate()

        class _Impl(dynamic_proxy(UniversalViewDelegate)):
            def __init__(self):
                super().__init__()

            def onDraw(self, canvas, callback):
                if not delegate._current_rect.isEmpty():
                    r = delegate._radius
                    delegate._fill.setAlpha(int(0x28 * delegate._alpha))
                    canvas.drawRoundRect(delegate._current_rect, r, r, delegate._fill)
                    delegate._stroke.setAlpha(int(0xFF * delegate._alpha))
                    canvas.drawRoundRect(delegate._current_rect, r, r, delegate._stroke)
                callback.run(canvas)

            def onAttachedToWindow(self): pass
            def onDetachedFromWindow(self): pass

            def onMeasure(self, w, h, callback):
                callback.run(__import__('java').jclass('java.lang.Integer')(w),
                             __import__('java').jclass('java.lang.Integer')(h))

            def onTouchEvent(self, event, callback):
                return __import__('java').jclass('java.lang.Boolean')(callback.run(event))

            def onInitializeAccessibilityNodeInfo(self, info, callback):
                callback.run(info)

        impl = _Impl()
        uv = UniversalView(context, impl)
        uv.setClickable(False)
        uv.setFocusable(False)
        delegate.view = uv
        return uv, delegate
    except Exception as e:
        log(f"highlight: _make_highlight_view error: {e}")
        return None, None


def _make_ghost_overlay(context, on_click, radius_dp=6):
    # semi-transparent overlay with dashed border — shown when element is hidden
    # uses UniversalView to draw, same pattern as highlight
    try:
        from com.exteragram.messenger.plugins.ui.components.templates import UniversalView
        from android.graphics import DashPathEffect, Path
        UniversalViewDelegate = UniversalView.UniversalViewDelegate
        from java import jint as _jint

        accent = ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)).value
        r = (accent >> 16) & 0xFF
        g = (accent >> 8)  & 0xFF
        b = accent & 0xFF

        stroke_paint = Paint(Paint.ANTI_ALIAS_FLAG)
        stroke_paint.setStyle(Paint.Style.STROKE)
        stroke_paint.setStrokeWidth(float(AndroidUtilities.dp(1)))
        stroke_paint.setColor(_jint(ctypes.c_int32((0x88 << 24) | (r << 16) | (g << 8) | b).value))
        stroke_paint.setPathEffect(DashPathEffect(
            jarray(jfloat)([float(AndroidUtilities.dp(4)), float(AndroidUtilities.dp(4))]), 0.0
        ))

        fill_paint = Paint(Paint.ANTI_ALIAS_FLAG)
        fill_paint.setStyle(Paint.Style.FILL)
        fill_paint.setColor(_jint(ctypes.c_int32((0x18 << 24) | (r << 16) | (g << 8) | b).value))

        rad = float(AndroidUtilities.dp(radius_dp))
        rect = RectF()

        class _GhostDelegate(dynamic_proxy(UniversalViewDelegate)):
            def __init__(self): super().__init__()
            def onDraw(self, canvas, callback):
                v = callback  # the view passed as Callback<Canvas>
                w = _view[0].getWidth() if _view[0] else 0
                h = _view[0].getHeight() if _view[0] else 0
                if w > 0 and h > 0:
                    rect.set(float(AndroidUtilities.dp(1)), float(AndroidUtilities.dp(1)),
                             float(w - AndroidUtilities.dp(1)), float(h - AndroidUtilities.dp(1)))
                    canvas.drawRoundRect(rect, rad, rad, fill_paint)
                    canvas.drawRoundRect(rect, rad, rad, stroke_paint)
                callback.run(canvas)
            def onAttachedToWindow(self): pass
            def onDetachedFromWindow(self): pass
            def onMeasure(self, w, h, cb):
                cb.run(__import__('java').jclass('java.lang.Integer')(w),
                       __import__('java').jclass('java.lang.Integer')(h))
            def onTouchEvent(self, ev, cb):
                return __import__('java').jclass('java.lang.Boolean')(cb.run(ev))
            def onInitializeAccessibilityNodeInfo(self, info, cb): cb.run(info)

        _view = [None]
        delegate = _GhostDelegate()
        uv = UniversalView(context, delegate)
        uv.setClickable(True)
        uv.setFocusable(True)
        uv.setOnClickListener(OnClickListener(on_click))
        _view[0] = uv
        return uv
    except Exception as e:
        log(f"ghost overlay error: {e}")
        return None


class PluginCardPreview:
    def __init__(self, context, on_select):
        self.context          = context
        self.on_select        = on_select
        self.elements         = {}
        self.highlight        = None
        self.currentSelection = None
        self.currentView      = None
        self.view             = self._build()

    def _build(self):
        outer = FrameLayout(self.context)
        outer.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))

        card = LinearLayout(self.context)
        card.setOrientation(LinearLayout.VERTICAL)
        card.setGravity(Gravity.TOP)
        self.elements['card'] = card

        top_row = LinearLayout(self.context)
        top_row.setOrientation(LinearLayout.HORIZONTAL)
        top_row.setGravity(Gravity.TOP)

        icon_frame = FrameLayout(self.context)
        icon_bg = GradientDrawable()
        icon_bg.setShape(GradientDrawable.RECTANGLE)
        icon_bg.setCornerRadius(float(AndroidUtilities.dp(12)))
        icon_bg.setColor(Theme.getColor(Theme.key_switchTrack))
        icon_frame.setBackground(icon_bg)
        try:
            from hook_utils import find_class
            plug_icon = ImageView(self.context)
            R_tg = find_class("org.telegram.messenger.R")
            plug_icon.setImageResource(getattr(R_tg.drawable, "msg_addbot", 0))
            plug_icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            plug_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            plug_icon.setPadding(
                AndroidUtilities.dp(14), AndroidUtilities.dp(14),
                AndroidUtilities.dp(14), AndroidUtilities.dp(14)
            )
            icon_frame.addView(plug_icon, FrameLayout.LayoutParams(-1, -1))
        except Exception:
            pass
        self.elements['icon_frame'] = icon_frame

        # ghost overlay for icon — shown when icon is hidden
        icon_wrapper = FrameLayout(self.context)
        icon_ghost = _make_ghost_overlay(self.context, lambda v: self.select(icon_wrapper, 'icon'), 12)
        icon_wrapper.addView(icon_frame, FrameLayout.LayoutParams(-1, -1))
        if icon_ghost:
            icon_wrapper.addView(icon_ghost, FrameLayout.LayoutParams(-1, -1))
        self.elements['icon_wrapper'] = icon_wrapper
        self.elements['icon_ghost']   = icon_ghost

        icon_lp = LinearLayout.LayoutParams(
            AndroidUtilities.dp(_gs(_KEY_ICON_SIZE)),
            AndroidUtilities.dp(_gs(_KEY_ICON_SIZE))
        )
        icon_lp.rightMargin = AndroidUtilities.dp(12)
        icon_lp.topMargin   = AndroidUtilities.dp(5)
        top_row.addView(icon_wrapper, icon_lp)
        self.elements['icon_lp'] = icon_lp

        col = LinearLayout(self.context)
        col.setOrientation(LinearLayout.VERTICAL)

        name_tv = TextView(self.context)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        name_tv.setText(str(strings["pce_plugin_name"]))
        name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        name_tv.setSingleLine(True)
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(_gs(_KEY_NAME_SIZE)))
        self.elements['name_tv'] = name_tv
        col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

        id_tv = TextView(self.context)
        id_tv.setText(str(strings["pce_version_author"]))
        id_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        id_tv.setSingleLine(True)
        id_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(_gs(_KEY_ID_SIZE)))
        id_tv.setClickable(False)
        id_tv.setFocusable(False)
        self.elements['id_tv'] = id_tv

        id_wrapper = FrameLayout(self.context)
        id_wrapper.addView(id_tv, FrameLayout.LayoutParams(-2, -2))
        id_ghost = _make_ghost_overlay(self.context, lambda v: self.select(id_wrapper, 'id'), 4)
        if id_ghost:
            id_wrapper.addView(id_ghost, FrameLayout.LayoutParams(-1, -1))
        self.elements['id_wrapper'] = id_wrapper
        self.elements['id_ghost']   = id_ghost
        col.addView(id_wrapper, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

        top_row.addView(col, LayoutHelper.createLinear(0, -2, 1.0))

        # chips column — right side of top_row, clickable element
        chips_col = LinearLayout(self.context)
        chips_col.setOrientation(LinearLayout.VERTICAL)
        chips_col.setGravity(Gravity.TOP | Gravity.RIGHT)
        self.elements['chips_col'] = chips_col

        chip_ver   = self._build_chip("12.5.1",   "chip_ver")
        chip_deps  = self._build_chip("1 library","chip_deps")
        chip_size  = self._build_chip("1.23 KB",  "chip_size")
        self.elements['chip_ver']  = chip_ver
        self.elements['chip_deps'] = chip_deps
        self.elements['chip_size'] = chip_size

        for i, chip in enumerate([chip_ver, chip_deps, chip_size]):
            lp = LinearLayout.LayoutParams(-2, -2)
            if i < 2:
                lp.bottomMargin = AndroidUtilities.dp(4)
            chips_col.addView(chip, lp)

        # chips placeholder — shown when all chips are off
        chips_ph = TextView(self.context)
        chips_ph.setText(str(strings["pce_chips_info"]))
        chips_ph.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        chips_ph.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)).value)
        chips_ph.setBackground(Theme.createRoundRectDrawable(
            AndroidUtilities.dp(6),
            ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundGray)).value
        ))
        chips_ph.setPadding(AndroidUtilities.dp(7), AndroidUtilities.dp(3), AndroidUtilities.dp(7), AndroidUtilities.dp(3))
        self.elements['chips_ph'] = chips_ph
        chips_col.addView(chips_ph, LinearLayout.LayoutParams(-2, -2))

        chips_lp = LinearLayout.LayoutParams(-2, -2)
        chips_lp.leftMargin = AndroidUtilities.dp(8)
        top_row.addView(chips_col, chips_lp)

        card.addView(top_row, LayoutHelper.createLinear(-1, -2))

        # tags row — clickable element
        tags_row = LinearLayout(self.context)
        tags_row.setOrientation(LinearLayout.HORIZONTAL)
        tags_row.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL)
        self.elements['tags_row'] = tags_row
        for tag_text, color_key in [("plugin", "key_avatar_background2Blue"), ("packit", "key_color_green")]:
            tag_bg = GradientDrawable()
            tag_bg.setShape(GradientDrawable.RECTANGLE)
            tag_bg.setCornerRadius(AndroidUtilities.dp(6))
            try:
                c = Theme.getColor(getattr(Theme, color_key))
            except Exception:
                c = Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader)
            r = (c >> 16) & 0xFF; g = (c >> 8) & 0xFF; b = c & 0xFF
            tag_bg.setColor(ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value)
            tag_tv = TextView(self.context)
            tag_tv.setText(tag_text)
            tag_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            tag_tv.setTextColor(ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value)
            tag_tv.setBackground(tag_bg)
            tag_tv.setPadding(AndroidUtilities.dp(7), AndroidUtilities.dp(2), AndroidUtilities.dp(7), AndroidUtilities.dp(2))
            tag_lp = LinearLayout.LayoutParams(-2, -2)
            tag_lp.rightMargin = AndroidUtilities.dp(5)
            tags_row.addView(tag_tv, tag_lp)
        # tags placeholder
        tags_ph = TextView(self.context)
        tags_ph.setText(str(strings["pce_tags_placeholder"]))
        tags_ph.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        tags_ph.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)).value)
        tags_ph.setBackground(Theme.createRoundRectDrawable(
            AndroidUtilities.dp(6),
            ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundGray)).value
        ))
        tags_ph.setPadding(AndroidUtilities.dp(7), AndroidUtilities.dp(3), AndroidUtilities.dp(7), AndroidUtilities.dp(3))
        self.elements['tags_ph'] = tags_ph
        tags_row.addView(tags_ph, LinearLayout.LayoutParams(-2, -2))

        tags_wrapper = FrameLayout(self.context)
        tags_wrapper.addView(tags_row, FrameLayout.LayoutParams(-2, -2))
        self.elements['tags_wrapper'] = tags_wrapper
        tags_wrapper_lp = LayoutHelper.createLinear(-2, -2)
        tags_wrapper_lp.topMargin = AndroidUtilities.dp(6)
        col.addView(tags_wrapper, tags_wrapper_lp)

        desc_tv = TextView(self.context)
        desc_tv.setText(str(strings["pce_desc_preview"]))
        desc_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(_gs(_KEY_DESC_SIZE)))
        self.elements['desc_tv'] = desc_tv
        desc_wrapper = FrameLayout(self.context)
        desc_wrapper.addView(desc_tv, FrameLayout.LayoutParams(-1, -2))
        desc_ghost = _make_ghost_overlay(self.context, lambda v: self.select(desc_wrapper, 'desc'), 4)
        if desc_ghost:
            desc_wrapper.addView(desc_ghost, FrameLayout.LayoutParams(-1, -1))
        self.elements['desc_ghost'] = desc_ghost
        card.addView(desc_wrapper, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

        actions_row = LinearLayout(self.context)
        actions_row.setOrientation(LinearLayout.HORIZONTAL)
        actions_row.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL)

        buttons_wrapper = LinearLayout(self.context)
        buttons_wrapper.setOrientation(LinearLayout.HORIZONTAL)
        buttons_wrapper.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL)

        icon_buttons_container = LinearLayout(self.context)
        icon_buttons_container.setOrientation(LinearLayout.HORIZONTAL)
        icon_buttons_container.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL)
        self.elements['icon_buttons_container'] = icon_buttons_container

        self._action_buttons = {}
        for setting_key, icon_name in [
            ("relocate_copy_link", "msg_copy"),
            ("relocate_share", "msg_share"),
            ("relocate_code", "msg_view_file"),
            ("relocate_download", "msg_download"),
            ("relocate_translate", "msg_replace"),
            ("relocate_report", "msg_report"),
        ]:
            icon_btn = self._create_icon_pill(icon_name)
            self._action_buttons[setting_key] = icon_btn
            icon_buttons_container.addView(icon_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 4, 0))
            self._wire(icon_btn, setting_key)

        details_btn = self._create_icon_pill("ic_ab_other")
        self.elements['details_btn'] = details_btn
        
        view_btn = self._create_pill_button(strings["plugin_view_button"], "msg_view_file")
        self.elements['view_btn'] = view_btn
        self._wire(view_btn, 'view_btn')

        more_btn = self._create_icon_pill("msg_addbot")
        self.elements['more_btn'] = more_btn
        self._wire(more_btn, 'more')

        buttons_wrapper.addView(icon_buttons_container, LayoutHelper.createLinear(-2, -2))
        buttons_wrapper.addView(details_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0))
        buttons_wrapper.addView(more_btn, LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0))
        
        self.elements['buttons_wrapper'] = buttons_wrapper
        self.elements['actions_row'] = actions_row
        actions_row.addView(view_btn, LayoutHelper.createLinear(-2, -2, Gravity.LEFT))
        spacer = View(self.context)
        actions_row.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))
        actions_row.addView(buttons_wrapper, LayoutHelper.createLinear(-2, -2, Gravity.RIGHT))
        card.addView(actions_row, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

        row = FrameLayout(self.context)
        try:
            from android.os import Build
            if Build.VERSION.SDK_INT >= 21:
                row.setElevation(float(AndroidUtilities.dp(2)))
        except Exception:
            pass
        row.addView(card, FrameLayout.LayoutParams(-1, -2))

        try:
            hl_view, hl_delegate = _make_highlight_view(self.context)
            if hl_view is not None:
                self.highlight = hl_delegate
                row.addView(hl_view, FrameLayout.LayoutParams(-1, -1))
        except Exception as e:
            log(f"PCE: highlight create error: {e}")

        outer.setPadding(
            AndroidUtilities.dp(8), AndroidUtilities.dp(8),
            AndroidUtilities.dp(8), AndroidUtilities.dp(8)
        )
        outer.addView(row, LayoutHelper.createFrame(-1, -2, Gravity.CENTER, 4, 4, 4, 4))

        class OuterClick(dynamic_proxy(View.OnClickListener)):
            def __init__(self, p): super().__init__(); self.p = p
            def onClick(self, v): self.p.on_select(None)
        outer.setOnClickListener(OuterClick(self))

        self._wire(icon_frame,    'icon')
        self._wire(name_tv,       'name')
        self._wire(id_wrapper,    'id')
        self._wire(desc_tv,       'desc')
        self._wire(card,          'card')
        self._wire(chips_col,     'chips')
        self._wire(tags_wrapper,  'tags')
        self._wire(view_btn,      'view_btn')
        self._wire(details_btn,   'details')

        self._apply_card_style()
        self._apply_icon_style()
        self._apply_visibility()
        return outer

    def _create_pill_button(self, text, icon_name):
        try:
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
            pill = FrameLayout(self.context)
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadius(float(AndroidUtilities.dp(18)))
            bg.setColor(accent)
            pill.setBackground(bg)
            
            content = LinearLayout(self.context)
            content.setOrientation(LinearLayout.HORIZONTAL)
            content.setGravity(Gravity.CENTER_VERTICAL)
            content.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(7), AndroidUtilities.dp(12), AndroidUtilities.dp(7))
            
            icon = ImageView(self.context)
            try:
                from hook_utils import find_class
                R_tg = find_class("org.telegram.messenger.R")
                icon_id = getattr(R_tg.drawable, icon_name, 0)
                icon.setImageResource(icon_id)
                icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            
            content.addView(icon, LayoutHelper.createLinear(18, 18, 0, 0, 5, 0))
            
            tv = TextView(self.context)
            tv.setText(text)
            tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            tv.setTypeface(AndroidUtilities.bold())
            tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            content.addView(tv)
            
            pill.addView(content, FrameLayout.LayoutParams(-2, -2))
            return pill
        except Exception as e:
            log(f"PCE: _create_pill_button error: {e}")
            return View(self.context)

    def _create_icon_pill(self, icon_name):
        try:
            pill = FrameLayout(self.context)
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadius(float(AndroidUtilities.dp(12)))
            bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
            pill.setBackground(bg)

            icon = ImageView(self.context)
            try:
                from hook_utils import find_class
                R_tg = find_class("org.telegram.messenger.R")
                icon_id = getattr(R_tg.drawable, icon_name, 0)
                icon.setImageResource(icon_id)
                icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass
            icon.setScaleType(ImageView.ScaleType.CENTER)
            
            pill.addView(icon, FrameLayout.LayoutParams(
                AndroidUtilities.dp(24), AndroidUtilities.dp(24),
                Gravity.CENTER
            ))
            
            pill.setPadding(AndroidUtilities.dp(6), AndroidUtilities.dp(6), AndroidUtilities.dp(6), AndroidUtilities.dp(6))
            pill.setLayoutParams(LinearLayout.LayoutParams(AndroidUtilities.dp(36), AndroidUtilities.dp(36)))
            return pill
        except Exception as e:
            log(f"PCE: _create_icon_pill error: {e}")

            pill = View(self.context)
            pill.setLayoutParams(LinearLayout.LayoutParams(AndroidUtilities.dp(40), AndroidUtilities.dp(40)))
            return pill

    # chip_key: "chip_ver" | "chip_deps" | "chip_size"
    # stored settings: {chip_key}_color (int ARGB), {chip_key}_size (int sp)
    _CHIP_DEFAULTS = {
        "chip_ver":  {"label": "12.5.1",    "color": None, "color_key": "key_avatar_background2Blue"},
        "chip_deps": {"label": "1 library", "color": None, "color_key": "key_color_purple"},
        "chip_size": {"label": "1.23 KB",   "color": None, "color_key": "key_color_cyan"},
    }

    def _chip_color(self, chip_key):
        saved = _gs(f"{chip_key}_color")
        if saved:
            return int(saved)
        info = self._CHIP_DEFAULTS.get(chip_key, {})
        try:
            return Theme.getColor(getattr(Theme, info.get("color_key", "key_windowBackgroundWhiteGrayText")))
        except Exception:
            return Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

    def _build_chip(self, text, chip_key):
        color = self._chip_color(chip_key)
        size  = int(_gs(f"{chip_key}_size") or 11)
        r = (color >> 16) & 0xFF
        g = (color >> 8)  & 0xFF
        b = color & 0xFF
        fill      = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
        text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(6))
        bg.setColor(fill)
        tv = TextView(self.context)
        tv.setText(text)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(size))
        tv.setTextColor(text_color)
        tv.setBackground(bg)
        tv.setPadding(AndroidUtilities.dp(7), AndroidUtilities.dp(2), AndroidUtilities.dp(7), AndroidUtilities.dp(2))
        return tv

    def _refresh_chip(self, chip_key):
        chip = self.elements.get(chip_key)
        if not chip:
            return
        color = self._chip_color(chip_key)
        size  = int(_gs(f"{chip_key}_size") or 11)
        r = (color >> 16) & 0xFF
        g = (color >> 8)  & 0xFF
        b = color & 0xFF
        fill      = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
        text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(6))
        bg.setColor(fill)
        chip.setBackground(bg)
        chip.setTextColor(text_color)
        chip.setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(size))

    def _make_chip(self, text, color_key):
        # legacy helper kept for compatibility
        try:
            color = Theme.getColor(getattr(Theme, color_key))
        except Exception:
            color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        r = (color >> 16) & 0xFF
        g = (color >> 8)  & 0xFF
        b = color & 0xFF
        fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
        text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(6))
        bg.setColor(fill)
        tv = TextView(self.context)
        tv.setText(text)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        tv.setTextColor(text_color)
        tv.setBackground(bg)
        tv.setPadding(
            AndroidUtilities.dp(7), AndroidUtilities.dp(2),
            AndroidUtilities.dp(7), AndroidUtilities.dp(2)
        )
        return tv

    def _wire(self, view, key):
        preview = self

        class Tap(dynamic_proxy(View.OnClickListener)):
            def __init__(self, k): super().__init__(); self.k = k
            def onClick(self, v):
                if self.k in ['details', 'more', 'relocate_copy_link', 'relocate_share', 'relocate_code', 
                              'relocate_download', 'relocate_translate', 'relocate_report']:
                    buttons_wrapper = preview.elements.get('buttons_wrapper')
                    if buttons_wrapper:
                        preview.select(buttons_wrapper, 'details')
                else:
                    preview.select(v, self.k)

        view.setClickable(True)
        view.setFocusable(True)
        view.setOnClickListener(Tap(key))

        if key == 'details':
            show_details = _gs("show_details_button")
            if not show_details:
                try:
                    details_btn = preview.elements.get('details_btn')
                    if details_btn:
                        icon = None
                        if details_btn.getChildCount() > 0:
                            icon = details_btn.getChildAt(0)
                        
                        if icon:
                            gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                            icon.setColorFilter(gray_color)
                except Exception as e:
                    log(f"PCE: Error setting gray state for details button: {e}")

        if key == 'more':
            try:
                more_btn = preview.elements.get('more_btn')
                if more_btn and more_btn.getChildCount() > 0:
                    icon = more_btn.getChildAt(0)
                    if icon:
                        normal_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                        icon.setColorFilter(normal_color)
            except Exception as e:
                log(f"PCE: Error setting more button color: {e}")

    def _refreshHighlight(self):
        if not self.highlight or not self.currentSelection or not self.currentView:
            return
        key    = self.currentSelection
        if key in ['details', 'more']:
            radius = int(_gs(_KEY_CARD_RADIUS)) if _gs(_KEY_CARD_RADIUS) else 6
        else:
            radius = 12 if key == 'icon' else (int(_gs(_KEY_CARD_RADIUS)) if key == 'card' else 6)
        try:
            self.highlight.setTarget(self.currentView, radius)
        except Exception as e:
            log(f"PCE: _refreshHighlight error: {e}")

    def select(self, view, key):
        self.currentSelection = key
        self.currentView      = view
        if self.highlight:
            try:
                if key in ['details', 'more']:
                    radius = int(_gs(_KEY_CARD_RADIUS)) if _gs(_KEY_CARD_RADIUS) else 6
                else:
                    radius = 12 if key == 'icon' else (int(_gs(_KEY_CARD_RADIUS)) if key == 'card' else 6)
                self.highlight.setTarget(view, radius)
            except Exception as e:
                log(f"PCE: select error: {e}")
        self.on_select(key)

    def deselect(self):
        self.currentSelection = None
        self.currentView      = None
        if self.highlight:
            try: self.highlight.setTarget(None)
            except Exception: pass

    def _apply_card_style(self):
        try:
            color = ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhite)).value
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadius(float(AndroidUtilities.dp(_gs(_KEY_CARD_RADIUS))))
            bg.setColor(color)
            card = self.elements['card']
            card.setBackground(bg)
            p = AndroidUtilities.dp(_gs(_KEY_CARD_PADDING))
            card.setPadding(p, p, p, p)
        except Exception as e:
            log(f"PCE: _apply_card_style error: {e}")

    def _apply_icon_style(self):
        try:
            icon_frame = self.elements['icon_frame']
            if icon_frame:
                bg = icon_frame.getBackground()
                if bg and hasattr(bg, 'setCornerRadius'):
                    bg.setCornerRadius(float(AndroidUtilities.dp(_gs(_KEY_STICKER_RADIUS))))
        except Exception as e:
            log(f"PCE: _apply_icon_style error: {e}")

    def _apply_visibility(self, animated=False):
        try:
            if animated:
                try:
                    from android.transition import TransitionManager, ChangeBounds, Fade, TransitionSet
                    card = self.elements['card']
                    ts = TransitionSet()
                    ts.setOrdering(TransitionSet.ORDERING_TOGETHER)
                    ts.addTransition(ChangeBounds())
                    ts.addTransition(Fade())
                    ts.setDuration(220)
                    try:
                        from org.telegram.ui.Components import CubicBezierInterpolator
                        ts.setInterpolator(CubicBezierInterpolator.EASE_OUT_QUINT)
                    except Exception:
                        pass
                    TransitionManager.beginDelayedTransition(card, ts)
                except Exception as e:
                    log(f"PCE: transition error: {e}")

            show_icon  = _gs(_KEY_SHOW_ICON)
            icon_frame = self.elements['icon_frame']
            icon_size  = AndroidUtilities.dp(_gs(_KEY_ICON_SIZE))

            # icon wrapper always visible — shows real icon or ghost
            icon_wrapper = self.elements.get('icon_wrapper')
            if icon_wrapper:
                lp = icon_wrapper.getLayoutParams()
                if lp:
                    lp.width       = icon_size
                    lp.height      = icon_size
                    lp.rightMargin = AndroidUtilities.dp(12)
                    icon_wrapper.setLayoutParams(lp)
                icon_frame.setVisibility(View.VISIBLE if show_icon else View.INVISIBLE)
                ghost = self.elements.get('icon_ghost')
                if ghost: ghost.setVisibility(View.GONE if show_icon else View.VISIBLE)
            else:
                lp = icon_frame.getLayoutParams()
                if lp:
                    lp.width  = icon_size if show_icon else 0
                    lp.height = icon_size if show_icon else 0
                    lp.rightMargin = AndroidUtilities.dp(12) if show_icon else 0
                    icon_frame.setLayoutParams(lp)
                icon_frame.setVisibility(View.VISIBLE if show_icon else View.GONE)

            # id_tv — stays VISIBLE always so wrapper keeps its height for ghost overlay
            # when hidden: show placeholder text with transparent color, ghost on top
            show_id = _gs(_KEY_SHOW_ID)
            id_tv = self.elements['id_tv']
            id_tv.setVisibility(View.VISIBLE)
            if show_id:
                id_tv.setText(str(strings["pce_version_author"]))
                id_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            else:
                id_tv.setText("v \u2022 @author")
                id_tv.setTextColor(ctypes.c_int32(
                    (0x44 << 24) | (Theme.getColor(Theme.key_windowBackgroundWhiteGrayText) & 0x00FFFFFF)
                ).value)
            id_ghost = self.elements.get('id_ghost')
            if id_ghost: id_ghost.setVisibility(View.GONE if show_id else View.VISIBLE)

            # desc_tv
            show_desc = _gs(_KEY_SHOW_DESC)
            self.elements['desc_tv'].setVisibility(View.VISIBLE if show_desc else View.INVISIBLE)
            desc_ghost = self.elements.get('desc_ghost')
            if desc_ghost: desc_ghost.setVisibility(View.GONE if show_desc else View.VISIBLE)

            self.elements['actions_row'].setVisibility(View.VISIBLE)
            for setting_key, icon_btn in self._action_buttons.items():
                should_show = _gs(setting_key)
                icon_btn.setVisibility(View.VISIBLE if should_show else View.GONE)

            show_details = _gs("show_details_button")
            details_btn = self.elements.get('details_btn')
            if details_btn:
                details_btn.setVisibility(View.VISIBLE if show_details else View.GONE)

            show_view = _gs("show_view_button")
            view_btn = self.elements.get('view_btn')
            if view_btn:
                if show_view:
                    view_btn.setVisibility(View.VISIBLE)
                    view_btn.setAlpha(1.0)
                else:
                    view_btn.setVisibility(View.VISIBLE)
                    view_btn.setAlpha(0.5)

            relocate_keys = [
                "relocate_copy_link", "relocate_share", "relocate_code",
                "relocate_download", "relocate_translate", "relocate_report"
            ]
            enabled_relocate_count = sum(1 for key in relocate_keys if _gs(key))
            
            show_more_button = not show_details and enabled_relocate_count == 0
            more_btn = self.elements.get('more_btn')
            if more_btn:
                more_btn.setVisibility(View.VISIBLE if show_more_button else View.GONE)
            # chips
            show_ver  = _gs("show_plugin_min_version")
            show_deps = _gs("show_plugin_deps_count")
            show_size = _gs("show_plugin_size")
            self.elements['chip_ver'].setVisibility(View.VISIBLE if show_ver else View.GONE)
            self.elements['chip_deps'].setVisibility(View.VISIBLE if show_deps else View.GONE)
            self.elements['chip_size'].setVisibility(View.VISIBLE if show_size else View.GONE)
            chips_any = show_ver or show_deps or show_size
            self.elements['chips_ph'].setVisibility(View.GONE if chips_any else View.VISIBLE)
            self.elements['chips_col'].setVisibility(View.VISIBLE)
            # tags
            show_tags = _gs("show_plugin_tags")
            self.elements['tags_row'].setVisibility(View.VISIBLE)
            for i in range(self.elements['tags_row'].getChildCount() - 1):
                self.elements['tags_row'].getChildAt(i).setVisibility(View.VISIBLE if show_tags else View.GONE)
            self.elements['tags_ph'].setVisibility(View.GONE if show_tags else View.VISIBLE)
        except Exception as e:
            log(f"PCE: _apply_visibility error: {e}")

    def refresh(self):
        try:
            # text size changes — animate via property animator for smooth scaling
            self.elements['name_tv'].setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(_gs(_KEY_NAME_SIZE)))
            self.elements['id_tv'].setTextSize(TypedValue.COMPLEX_UNIT_DIP,   float(_gs(_KEY_ID_SIZE)))
            self.elements['desc_tv'].setTextSize(TypedValue.COMPLEX_UNIT_DIP, float(_gs(_KEY_DESC_SIZE)))
            icon_wrapper = self.elements.get('icon_wrapper')
            target = icon_wrapper if icon_wrapper else self.elements['icon_frame']
            icon_size = AndroidUtilities.dp(_gs(_KEY_ICON_SIZE))
            lp = target.getLayoutParams()
            if lp:
                lp.width       = icon_size
                lp.height      = icon_size
                lp.rightMargin = AndroidUtilities.dp(12)
                target.setLayoutParams(lp)
            self._apply_card_style()
            self._apply_icon_style()
            self._apply_visibility(animated=True)
            for ck in ("chip_ver", "chip_deps", "chip_size"):
                self._refresh_chip(ck)
            show_details = _gs("show_details_button")
            details_btn = self.elements.get('details_btn')
            if details_btn:
                try:
                    icon = None
                    if details_btn.getChildCount() > 0:
                        icon = details_btn.getChildAt(0)
                    
                    if icon:
                        if show_details:
                            normal_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                            icon.setColorFilter(normal_color)
                        else:
                            gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                            icon.setColorFilter(gray_color)
                except Exception as e:
                    log(f"PCE: Error updating details button color: {e}")

            relocate_keys = [
                "relocate_copy_link", "relocate_share", "relocate_code",
                "relocate_download", "relocate_translate", "relocate_report"
            ]
            enabled_relocate_count = sum(1 for key in relocate_keys if _gs(key))
            show_more_button = not show_details and enabled_relocate_count == 0
            
            more_btn = self.elements.get('more_btn')
            if more_btn:
                try:
                    icon = None
                    if more_btn.getChildCount() > 0:
                        icon = more_btn.getChildAt(0)
                    
                    if icon:
                        if show_more_button:
                            more_btn.setVisibility(View.VISIBLE)
                            normal_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                            icon.setColorFilter(normal_color)
                        else:
                            more_btn.setVisibility(View.GONE)
                except Exception as e:
                    log(f"PCE: Error updating more button: {e}")
            
            # recalculate highlight after transition (220ms) settles
            try:
                from android_utils import R as _R
                self.view.postDelayed(_R(self._refreshHighlight), 240)
            except Exception:
                pass
        except Exception as e:
            log(f"PCE: refresh error: {e}")


class PluginCardEditorPage:
    def __init__(self):
        self.preview           = None
        self.settings_root     = None
        self.settings_scroll   = None
        self.current_selection = None

    def _get_context(self):
        try:
            frag = get_last_fragment()
            return frag.getParentActivity() if frag else None
        except Exception:
            return None

    def build(self):
        ctx = self._get_context()
        if not ctx:
            return []
        try:
            from ui.settings import Custom

            def on_select(key):
                run_on_ui_thread(lambda: self._show_settings_for(key))

            self.preview = PluginCardPreview(ctx, on_select)

            self.settings_scroll = ScrollView(ctx)
            self.settings_scroll.setFillViewport(True)
            self.settings_scroll.setClipToPadding(False)
            self.settings_scroll.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))

            self.settings_root = LinearLayout(ctx)
            self.settings_root.setOrientation(LinearLayout.VERTICAL)
            self.settings_root.setPadding(0, AndroidUtilities.dp(4), 0, AndroidUtilities.dp(24))
            self.settings_scroll.addView(self.settings_root, LayoutHelper.createScroll(-1, -2, 0))

            self._show_settings_for(None)

            settings_bg = GradientDrawable()
            settings_bg.setShape(GradientDrawable.RECTANGLE)
            settings_bg.setCornerRadii(jarray(jfloat)([
                float(AndroidUtilities.dp(14)), float(AndroidUtilities.dp(14)),
                float(AndroidUtilities.dp(14)), float(AndroidUtilities.dp(14)),
                0.0, 0.0,
                0.0, 0.0,
            ]))
            settings_bg.setColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhite)).value)
            self.settings_scroll.setBackground(settings_bg)

            container = LinearLayout(ctx)
            container.setOrientation(LinearLayout.VERTICAL)

            container.addView(self.preview.view, LayoutHelper.createLinear(-1, -2))

            spacer = View(ctx)
            spacer.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
            container.addView(spacer, LayoutHelper.createLinear(-1, 16))

            container.addView(self.settings_scroll, LayoutHelper.createLinear(-1, -2))

            return [Custom(view=container)]
        except Exception as e:
            log(f"PluginCardEditor: build error: {e}")
            return []

    def _show_settings_for(self, key):
        if self.settings_root is None:
            return
        # second tap on same element — deselect
        if key is not None and key == self.current_selection:
            key = None
            self.preview.deselect()

        self.current_selection = key
        ctx = self._get_context()
        if not ctx:
            return

        # _fill_settings must always run on UI thread
        run_on_ui_thread(lambda: self._fill_settings(key, ctx))

    def _fill_settings(self, key, ctx):
        self.settings_root.removeAllViews()
        self.settings_root.setAlpha(0.0)
        try:
            self.settings_root.animate().alpha(1.0).setDuration(150).start()
        except Exception:
            self.settings_root.setAlpha(1.0)

        if key is None:
            self._header(ctx, strings.card_section_shape)
            self._slider(ctx, strings.card_radius,  _KEY_CARD_RADIUS,  0, 28, 18)
            self._slider(ctx, strings.card_padding, _KEY_CARD_PADDING, 4, 24, 12)
            self._hint_divider(ctx)

        elif key == 'icon':
            self._header(ctx, strings.card_section_icon)
            self._check(ctx, _KEY_SHOW_ICON, strings.card_show_icon)
            self._slider(ctx, strings.card_icon_size, _KEY_ICON_SIZE, 40, 100, 67)
            self._slider(ctx, "Sticker Radius", _KEY_STICKER_RADIUS, 0, 50, 18)
            self._check(ctx, "show_default_sticker", strings.show_default_sticker)

        elif key == 'name':
            self._header(ctx, strings.card_section_name)
            self._slider(ctx, strings.card_name_size, _KEY_NAME_SIZE, 12, 28, 20)

        elif key == 'id':
            self._header(ctx, strings.card_section_id)
            self._check(ctx, _KEY_SHOW_ID, strings.card_show_id)
            self._slider(ctx, strings.card_id_size, _KEY_ID_SIZE, 9, 18, 13)

        elif key == 'desc':
            self._header(ctx, strings.card_section_desc)
            self._check(ctx, _KEY_SHOW_DESC, strings.card_show_desc)
            self._slider(ctx, strings.card_desc_size, _KEY_DESC_SIZE, 10, 20, 15)

        elif key == 'card':
            self._header(ctx, strings.card_section_shape)
            self._slider(ctx, strings.card_radius,  _KEY_CARD_RADIUS,  0, 28, 18)
            self._slider(ctx, strings.card_padding, _KEY_CARD_PADDING, 4, 24, 12)

        elif key == 'tags':
            self._header(ctx, strings.show_plugin_tags)
            self._check(ctx, "show_plugin_tags", strings.show_plugin_tags)

        elif key == 'chips':
            self._header(ctx, strings.card_section_extra)
            self._check(ctx, "show_plugin_min_version", strings.show_plugin_min_version)
            self._check(ctx, "show_plugin_size",        strings.show_plugin_size)
            self._check(ctx, "show_plugin_deps_count",  strings.show_plugin_deps_count)
            self._divider(ctx)
            self._chips_gravity(ctx)
            self._divider(ctx)
            for chip_key, label in [
                ("chip_ver",  strings.show_plugin_min_version),
                ("chip_size", strings.show_plugin_size),
                ("chip_deps", strings.show_plugin_deps_count),
            ]:
                self._chip_settings(ctx, chip_key, label)

        elif key == 'view_btn':
            self._header(ctx, strings["plugin_view_button"])
            self._check(ctx, "show_view_button", strings.show_view_button)

        elif key == 'details':
            self._header(ctx, strings.card_section_buttons)
            self._check_details_button(ctx, "show_details_button", strings.show_details_button)
            self._divider(ctx)
            for setting_key, label, icon in [
                ("relocate_copy_link", strings.copy_link, "msg_copy"),
                ("relocate_share", strings.share, "msg_share"),
                ("relocate_code", strings.code, "msg_view_file"),
                ("relocate_download", strings.download, "msg_download"),
                ("relocate_translate", strings.translate, "msg_replace"),
                ("relocate_report", strings.report, "msg_report"),
            ]:
                self._check_relocate_button(ctx, setting_key, label)

    def _chips_gravity(self, ctx):
        # horizontal gravity selector for chips column
        row = LinearLayout(ctx)
        row.setOrientation(LinearLayout.VERTICAL)
        row.setPadding(AndroidUtilities.dp(23), AndroidUtilities.dp(10), AndroidUtilities.dp(23), AndroidUtilities.dp(10))
        tv = TextView(ctx)
        tv.setText(str(strings["pce_chips_gravity"]))
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15.0)
        tv.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)).value)
        row.addView(tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))
        btn_row = LinearLayout(ctx)
        btn_row.setOrientation(LinearLayout.HORIZONTAL)
        gravities = [("Left", Gravity.LEFT), ("Center", Gravity.CENTER_HORIZONTAL), ("Right", Gravity.RIGHT)]
        btns = []
        preview = self.preview

        class GravClick(dynamic_proxy(View.OnClickListener)):
            def __init__(self, g): super().__init__(); self.g = g
            def onClick(self, v):
                _cs("chip_gravity", self.g)
                if preview:
                    run_on_ui_thread(lambda: self._update_chips_gravity(preview))
                for b, bg in btns:
                    is_act = (b.getTag() == self.g)
                    b.setTextColor(ctypes.c_int32(
                        Theme.getColor(Theme.key_featuredStickers_buttonText) if is_act
                        else Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader)
                    ).value)
                    b.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(8),
                        ctypes.c_int32(Theme.getColor(Theme.key_featuredStickers_addButton) if is_act
                                       else 0x00000000).value,
                        ctypes.c_int32(0x00000000).value
                    ))

        def _update_chips_gravity(preview):
            g = int(_gs("chip_gravity") or Gravity.RIGHT)
            col = preview.elements.get('chips_col')
            if col:
                col.setGravity(Gravity.TOP | g)

        GravClick._update_chips_gravity = staticmethod(_update_chips_gravity)

        cur_g = int(_gs("chip_gravity") or Gravity.RIGHT)
        for name, g in gravities:
            b = TextView(ctx)
            b.setText(name)
            b.setTag(g)
            b.setGravity(Gravity.CENTER)
            b.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
            is_act = (g == cur_g)
            b.setTextColor(ctypes.c_int32(
                Theme.getColor(Theme.key_featuredStickers_buttonText) if is_act
                else Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader)
            ).value)
            b.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(8),
                ctypes.c_int32(Theme.getColor(Theme.key_featuredStickers_addButton) if is_act
                               else 0x00000000).value,
                ctypes.c_int32(0x00000000).value
            ))
            b.setOnClickListener(GravClick(g))
            btns.append((b, g))
            btn_row.addView(b, LayoutHelper.createLinear(0, -2, 1.0, 2, 0, 2, 0))
        row.addView(btn_row, LayoutHelper.createLinear(-1, -2))
        self.settings_root.addView(row, LayoutHelper.createLinear(-1, -2))

    def _chip_settings(self, ctx, chip_key, label):
        # header
        self._header(ctx, str(label))
        # size slider
        self._slider(ctx, "Size (sp)", f"{chip_key}_size", 9, 18, 11)
        # color picker row
        color_row = LinearLayout(ctx)
        color_row.setOrientation(LinearLayout.HORIZONTAL)
        color_row.setGravity(Gravity.CENTER_VERTICAL)
        color_row.setMinimumHeight(AndroidUtilities.dp(50))
        color_row.setClickable(True)
        color_row.setFocusable(True)
        color_row.setBackground(Theme.createSelectorDrawable(
            ctypes.c_int32(Theme.getColor(Theme.key_listSelector)).value, 2
        ))
        lbl = TextView(ctx)
        lbl.setText(str(strings["pce_color_label"]))
        lbl.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16.0)
        lbl.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)).value)
        color_row.addView(lbl, LayoutHelper.createLinear(0, -2, 1.0, 23, 0, 12, 0))

        color_circle = View(ctx)
        preview = self.preview

        def _update_circle():
            c = preview._chip_color(chip_key) if preview else 0
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.OVAL)
            bg.setColor(ctypes.c_int32(c).value)
            color_circle.setBackground(bg)

        _update_circle()
        color_row.addView(color_circle, LayoutHelper.createLinear(24, 24, 0, 0, 23, 0))

        class ColorRowClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                try:
                    from org.telegram.ui.Components.Paint import ColorPickerBottomSheet
                    from java import jclass, dynamic_proxy as dyp
                    PipetteDelegate = jclass("org.telegram.ui.Components.Paint.ColorPickerBottomSheet$PipetteDelegate")
                    Consumer = jclass("androidx.core.util.Consumer")

                    class _DummyPipette(dyp(PipetteDelegate)):
                        def onStartColorPipette(self): pass
                        def onStopColorPipette(self): pass
                        def getContainerView(self): return None
                        def getSnapshotDrawingView(self): return None
                        def onDrawImageOverCanvas(self, b, c): pass
                        def isPipetteVisible(self): return False
                        def isPipetteAvailable(self): return False
                        def onColorSelected(self, c): pass

                    class _Consumer(dyp(Consumer)):
                        def accept(self, color):
                            c = int(color)
                            _cs(f"{chip_key}_color", c)
                            if preview:
                                run_on_ui_thread(lambda: (
                                    preview._refresh_chip(chip_key),
                                    _update_circle()
                                ))

                    from java import jint as _jint
                    cur = preview._chip_color(chip_key) if preview else 0
                    picker = ColorPickerBottomSheet(ctx, None)
                    picker.setPipetteDelegate(_DummyPipette())
                    picker.setColorListener(_Consumer())
                    picker.setColor(_jint(ctypes.c_int32(cur).value))
                    picker.show()
                except Exception as e:
                    log(f"chip color picker error: {e}")

        color_row.setOnClickListener(ColorRowClick())
        self.settings_root.addView(color_row, LayoutHelper.createLinear(-1, -2))

    def _hint_divider(self, ctx):
        # hint as bottom divider with text — like Divider(text=...) in native settings
        hint = "Tap an element above to edit it"
        try: hint = strings.card_tap_hint
        except Exception: pass
        tv = TextView(ctx)
        tv.setText(hint)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13.0)
        tv.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)).value)
        tv.setPadding(
            AndroidUtilities.dp(23), AndroidUtilities.dp(10),
            AndroidUtilities.dp(23), AndroidUtilities.dp(12)
        )
        self.settings_root.addView(tv, LayoutHelper.createLinear(-1, -2))

    def _header(self, ctx, text):
        tv = TextView(ctx)
        tv.setText(str(text))
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13.0)
        tv.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteBlueHeader)).value)
        try: tv.setTypeface(AndroidUtilities.bold())
        except Exception: pass
        tv.setAllCaps(True)
        self.settings_root.addView(tv, LayoutHelper.createLinear(-1, -2, 23, 16, 23, 6))

    def _divider(self, ctx):
        line = View(ctx)
        line.setBackgroundColor(ctypes.c_int32(Theme.getColor(Theme.key_divider)).value)
        self.settings_root.addView(line, LayoutHelper.createLinear(-1, 1, 0, 8, 0, 8))

    def _check_relocate_button(self, ctx, key, label):
        try:
            from org.telegram.ui.Cells import TextCheckCell
            cell = TextCheckCell(ctx)
            current_val = bool(_gs(key))
            cell.setTextAndCheck(str(label), current_val, False)
            preview = self.preview

            class CellClick(dynamic_proxy(View.OnClickListener)):
                def onClick(self, v):
                    relocate_keys = [
                        "relocate_copy_link", "relocate_share", "relocate_code",
                        "relocate_download", "relocate_translate", "relocate_report"
                    ]
                    enabled_count = sum(1 for k in relocate_keys if _gs(k))
                    details_enabled = _gs("show_details_button")
                    new_val = not _gs(key)
                    
                    if new_val and enabled_count + (1 if details_enabled else 0) >= 4:
                        try:
                            fragment = get_last_fragment()
                            if fragment and BulletinFactory:
                                container = fragment.getParentActivity().getWindow().getDecorView()
                                resource_provider = fragment.getResourceProvider()
                                BulletinFactory.of(container, resource_provider).createErrorBulletin(strings["max_buttons_allowed"]).show()
                        except Exception as e:
                            log(f"PCE: Failed to show button limit popup: {e}")
                        return
                        
                    if new_val and details_enabled and enabled_count >= 3:
                        try:
                            fragment = get_last_fragment()
                            if fragment and BulletinFactory:
                                container = fragment.getParentActivity().getWindow().getDecorView()
                                resource_provider = fragment.getResourceProvider()
                                BulletinFactory.of(container, resource_provider).createErrorBulletin(strings["max_buttons_allowed"]).show()
                        except Exception as e:
                            log(f"PCE: Failed to show button limit popup: {e}")
                        return
                    
                    _cs(key, new_val)
                    cell.setChecked(new_val)
                    if preview:
                        run_on_ui_thread(preview.refresh)

            cell.setOnClickListener(CellClick())
            self.settings_root.addView(cell, LayoutHelper.createLinear(-1, -2))
        except Exception as e:
            log(f"PCE: _check_relocate_button error: {e}")

    def _check_details_button(self, ctx, key, label):
        try:
            from org.telegram.ui.Cells import TextCheckCell
            cell = TextCheckCell(ctx)
            current_val = bool(_gs(key))
            cell.setTextAndCheck(str(label), current_val, False)
            preview = self.preview

            class CellClick(dynamic_proxy(View.OnClickListener)):
                def onClick(self, v):
                    relocate_keys = [
                        "relocate_copy_link", "relocate_share", "relocate_code",
                        "relocate_download", "relocate_translate", "relocate_report"
                    ]
                    enabled_count = sum(1 for k in relocate_keys if _gs(k))
                    new_val = not _gs(key)
                    
                    if new_val and enabled_count > 3:
                        try:
                            fragment = get_last_fragment()
                            if fragment and BulletinFactory:
                                container = fragment.getParentActivity().getWindow().getDecorView()
                                resource_provider = fragment.getResourceProvider()
                                BulletinFactory.of(container, resource_provider).createErrorBulletin(strings["max_buttons_allowed"]).show()
                        except Exception as e:
                            log(f"PCE: Failed to show button limit popup: {e}")
                        return
                    
                    _cs(key, new_val)
                    cell.setChecked(new_val)
                    if preview:
                        run_on_ui_thread(preview.refresh)

            cell.setOnClickListener(CellClick())
            self.settings_root.addView(cell, LayoutHelper.createLinear(-1, -2))
        except Exception as e:
            log(f"PCE: _check_details_button error: {e}")

    def _check(self, ctx, key, label):
        try:
            from org.telegram.ui.Cells import TextCheckCell
            cell = TextCheckCell(ctx)
            cell.setTextAndCheck(str(label), bool(_gs(key)), False)
            preview = self.preview

            class CellClick(dynamic_proxy(View.OnClickListener)):
                def onClick(self, v):
                    new_val = not _gs(key)
                    _cs(key, new_val)
                    cell.setChecked(new_val)
                    if preview:
                        run_on_ui_thread(preview.refresh)

            cell.setOnClickListener(CellClick())
            self.settings_root.addView(cell, LayoutHelper.createLinear(-1, -2))
        except Exception as e:
            log(f"PCE: _check error: {e}")

    def _slider(self, ctx, label, key, min_val, max_val, default):
        ll = LinearLayout(ctx)
        ll.setOrientation(LinearLayout.VERTICAL)
        ll.setPadding(
            AndroidUtilities.dp(23), AndroidUtilities.dp(10),
            AndroidUtilities.dp(23), AndroidUtilities.dp(10)
        )
        raw = _gs(key)
        val = int(raw) if raw is not None else default

        header_row = LinearLayout(ctx)
        header_row.setOrientation(LinearLayout.HORIZONTAL)
        header_row.setGravity(Gravity.CENTER_VERTICAL)

        tv = TextView(ctx)
        tv.setText(f"{label}: {val}")
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15.0)
        tv.setTextColor(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)).value)
        header_row.addView(tv, LayoutHelper.createLinear(0, -2, 1.0))

        reset_btn = ImageView(ctx)
        try:
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            reset_btn.setImageResource(getattr(R_tg.drawable, "msg_reset", 0))
        except Exception:
            pass
        reset_btn.setColorFilter(ctypes.c_int32(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)).value)
        reset_btn.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        reset_btn.setPadding(
            AndroidUtilities.dp(4), AndroidUtilities.dp(4),
            AndroidUtilities.dp(4), AndroidUtilities.dp(4)
        )
        header_row.addView(reset_btn, LayoutHelper.createLinear(28, 28))

        ll.addView(header_row, LayoutHelper.createLinear(-1, -2))

        sb = SeekBar(ctx)
        _style_seekbar(sb)
        sb.setOnTouchListener(_SeekTouchProxy())
        sb.setMax(max_val - min_val)
        sb.setProgress(val - min_val)
        preview = self.preview

        def on_change(prog):
            v = prog + min_val
            tv.setText(f"{label}: {v}")
            _cs(key, v)
            if preview:
                run_on_ui_thread(preview.refresh)

        sb.setOnSeekBarChangeListener(_SeekListener(on_change))

        class ResetClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                _cs(key, default)
                sb.setProgress(default - min_val)
                on_change(default - min_val)

        reset_btn.setClickable(True)
        reset_btn.setFocusable(True)
        reset_btn.setOnClickListener(ResetClick())
        reset_btn.setBackground(Theme.createSelectorDrawable(
            ctypes.c_int32(Theme.getColor(Theme.key_listSelector)).value, 1
        ))

        ll.addView(sb, LayoutHelper.createLinear(-1, -2, 0, 10, 0, 0))
        self.settings_root.addView(ll, LayoutHelper.createLinear(-1, -2))


def build_card_editor_page():
    return PluginCardEditorPage().build()

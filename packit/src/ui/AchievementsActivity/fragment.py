from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy, jclass
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"achievementsUi: import elyx strings failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme, BottomSheet
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities, R as R_tg
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"achievementsUi: import android/tg classes failed: {e}")

OnGlobalLayoutListener = jclass("android.view.ViewTreeObserver$OnGlobalLayoutListener")


def _add_actionbar_glow(fv):
    # fv must be the fragmentView already created; adds gradient overlay at top to soften actionBar edge
    try:
        from android.graphics import Color
        from android.graphics.drawable import GradientDrawable as GD
        from org.telegram.ui.Components import LayoutHelper
        bg = Theme.getColor(Theme.key_windowBackgroundGray)
        transparent = Color.argb(0, (bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF)
        glow = GD(GD.Orientation.TOP_BOTTOM, [bg, transparent])
        overlay = FrameLayout(fv.getContext())
        overlay.setBackground(glow)
        overlay.setClickable(False)
        fv.addView(overlay, LayoutHelper.createFrame(-1, 24, 0x30, 0, 0, 0, 0))
    except Exception as e:
        log(f"_add_actionbar_glow: {e}")


def _add_bottom_glow(fv):
    # fv must be the fragmentView already created; adds gradient overlay at bottom
    try:
        from android.graphics import Color
        from android.graphics.drawable import GradientDrawable as GD
        from org.telegram.ui.Components import LayoutHelper
        bg = Theme.getColor(Theme.key_windowBackgroundGray)
        transparent = Color.argb(0, (bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF)
        glow = GD(GD.Orientation.BOTTOM_TOP, [bg, transparent])
        overlay = FrameLayout(fv.getContext())
        overlay.setBackground(glow)
        overlay.setClickable(False)
        fv.addView(overlay, LayoutHelper.createFrame(-1, 24, 0x50, 0, 0, 0, 0))
    except Exception as e:
        log(f"_add_bottom_glow: {e}")


def _resolve_icon(name: str) -> int:
    try:
        return getattr(R_tg.drawable, name)
    except Exception:
        return 0


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


def _add_with_fade(container, view, lp, delay_ms: int):
    try:
        view.setAlpha(0.0)
        view.setScaleX(0.94)
        view.setScaleY(0.94)
        container.addView(view, lp)
        view.animate().alpha(1.0).scaleX(1.0).scaleY(1.0).setDuration(220).setStartDelay(delay_ms).start()
    except Exception:
        container.addView(view, lp)


# category card used in the first level fragment
def _make_category_card(act, category: str, achievements: list, on_click):
    total = len(achievements)
    completed = sum(1 for a in achievements if a.get("progress", 0) >= a.get("goal", 1))

    accent = Theme.getColor(Theme.key_featuredStickers_addButton)
    card_bg = Theme.getColor(Theme.key_windowBackgroundWhite)
    text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
    text_secondary = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

    card = LinearLayout(act)
    card.setOrientation(LinearLayout.VERTICAL)
    card.setClickable(True)
    card.setFocusable(True)
    card.setPadding(
        AndroidUtilities.dp(16), AndroidUtilities.dp(14),
        AndroidUtilities.dp(16), AndroidUtilities.dp(14)
    )
    try:
        pressed = Theme.getColor(Theme.key_listSelector)
        card.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(16), card_bg, pressed
        ))
    except Exception:
        card.setBackgroundColor(card_bg)

    # top row: icon + name + counter badge
    top_row = LinearLayout(act)
    top_row.setOrientation(LinearLayout.HORIZONTAL)
    top_row.setGravity(Gravity.CENTER_VERTICAL)

    # icon from first achievement in category
    icon_name = achievements[0].get("icon", "msg_fave") if achievements else "msg_fave"
    try:
        icon_view = ImageView(act)
        icon_id = _resolve_icon(icon_name)
        if icon_id:
            icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(accent)
        icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(22), AndroidUtilities.dp(22))
        icon_lp.rightMargin = AndroidUtilities.dp(12)
        top_row.addView(icon_view, icon_lp)
    except Exception:
        pass

    name_tv = TextView(act)
    try:
        name_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
    except Exception:
        pass
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    name_tv.setText(str(strings[category]))
    name_tv.setTextColor(text_primary)
    top_row.addView(name_tv, LinearLayout.LayoutParams(0, -2, 1.0))

    # badge: "X / Y"
    badge_bg = GradientDrawable()
    badge_bg.setShape(GradientDrawable.RECTANGLE)
    badge_bg.setCornerRadius(AndroidUtilities.dp(10))
    badge_bg.setColor(accent)
    badge_tv = TextView(act)
    badge_tv.setText(f"{completed}/{total}")
    badge_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    badge_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    badge_tv.setBackground(badge_bg)
    badge_tv.setPadding(
        AndroidUtilities.dp(8), AndroidUtilities.dp(3),
        AndroidUtilities.dp(8), AndroidUtilities.dp(3)
    )
    top_row.addView(badge_tv, LinearLayout.LayoutParams(-2, -2))
    card.addView(top_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

    # progress bar
    progress_ratio = completed / total if total > 0 else 0.0
    bar_bg = FrameLayout(act)
    bar_bg_drawable = GradientDrawable()
    bar_bg_drawable.setShape(GradientDrawable.RECTANGLE)
    bar_bg_drawable.setCornerRadius(AndroidUtilities.dp(3))
    try:
        bar_bg_drawable.setColor(Theme.multAlpha(accent, 0.18))
    except Exception:
        bar_bg_drawable.setColor(0x1A000000)
    bar_bg.setBackground(bar_bg_drawable)

    bar_fill = FrameLayout(act)
    bar_fill_drawable = GradientDrawable()
    bar_fill_drawable.setShape(GradientDrawable.RECTANGLE)
    bar_fill_drawable.setCornerRadius(AndroidUtilities.dp(3))
    bar_fill_drawable.setColor(accent)
    bar_fill.setBackground(bar_fill_drawable)

    bar_bg.addView(bar_fill, FrameLayout.LayoutParams(0, AndroidUtilities.dp(4)))
    card.addView(bar_bg, LayoutHelper.createLinear(-1, 4))

    # animate bar fill width after first layout pass
    _ratio = progress_ratio
    _fill_ref = bar_fill
    _bg_ref = bar_bg

    class _BarLayoutListener(dynamic_proxy(OnGlobalLayoutListener)):
        def onGlobalLayout(self):
            try:
                w = _bg_ref.getWidth()
                if w > 0:
                    lp = _fill_ref.getLayoutParams()
                    lp.width = int(w * _ratio)
                    _fill_ref.setLayoutParams(lp)
                _bg_ref.getViewTreeObserver().removeOnGlobalLayoutListener(self)
            except Exception:
                pass

    bar_bg.getViewTreeObserver().addOnGlobalLayoutListener(_BarLayoutListener())

    # hint line: "X of Y completed"
    hint_tv = TextView(act)
    hint_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    hint_tv.setTextColor(text_secondary)
    if completed == total:
        hint_tv.setText(strings["achiev_category_all_done"])
    else:
        hint_tv.setText(strings("achiev_category_progress", completed=completed, total=total))
    card.addView(hint_tv, LayoutHelper.createLinear(-2, -2, 0, 6, 0, 0))

    card.setOnClickListener(OnClickListener(lambda v: on_click()))
    _apply_press_scale(card)
    return card


# achievement card used in the second level fragment
def _make_achievement_card(act, achievement: dict, on_hint_click):
    is_secret_locked = achievement.get("secret") and not achievement.get("unlocked")
    progress = achievement.get("progress", 0)
    goal = achievement.get("goal", 1)
    completed = progress >= goal

    accent = Theme.getColor(Theme.key_featuredStickers_addButton)
    card_bg = Theme.getColor(Theme.key_windowBackgroundWhite)
    text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
    text_secondary = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

    card = LinearLayout(act)
    card.setOrientation(LinearLayout.HORIZONTAL)
    card.setClickable(True)
    card.setFocusable(True)
    card.setGravity(Gravity.CENTER_VERTICAL)
    card.setPadding(
        AndroidUtilities.dp(14), AndroidUtilities.dp(12),
        AndroidUtilities.dp(14), AndroidUtilities.dp(12)
    )
    try:
        pressed = Theme.getColor(Theme.key_listSelector)
        card.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(14), card_bg, pressed
        ))
    except Exception:
        card.setBackgroundColor(card_bg)

    # icon on the left
    icon_name = achievement.get("icon", "msg_fave") if not is_secret_locked else "msg_secret"
    try:
        icon_view = ImageView(act)
        icon_id = _resolve_icon(icon_name)
        if icon_id:
            icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(accent if completed else text_secondary)
        icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(26), AndroidUtilities.dp(26))
        icon_lp.rightMargin = AndroidUtilities.dp(14)
        card.addView(icon_view, icon_lp)
    except Exception:
        pass

    # center column: title / progress bar + counter
    col = LinearLayout(act)
    col.setOrientation(LinearLayout.VERTICAL)

    title_tv = TextView(act)
    try:
        title_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
    except Exception:
        pass
    title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    if is_secret_locked:
        title_tv.setText("???")
        title_tv.setTextColor(text_secondary)
    else:
        title_tv.setText(str(strings[achievement.get("title_key", "achiev_title_unknown")]))
        title_tv.setTextColor(text_primary)
    col.addView(title_tv, LayoutHelper.createLinear(-1, -2))

    if not is_secret_locked and not achievement.get("secret") and not completed:
        mini_bg = FrameLayout(act)
        mini_bg_drawable = GradientDrawable()
        mini_bg_drawable.setShape(GradientDrawable.RECTANGLE)
        mini_bg_drawable.setCornerRadius(AndroidUtilities.dp(2))
        try:
            mini_bg_drawable.setColor(Theme.multAlpha(accent, 0.18))
        except Exception:
            mini_bg_drawable.setColor(0x1A000000)
        mini_bg.setBackground(mini_bg_drawable)

        mini_fill = FrameLayout(act)
        mini_fill_drawable = GradientDrawable()
        mini_fill_drawable.setShape(GradientDrawable.RECTANGLE)
        mini_fill_drawable.setCornerRadius(AndroidUtilities.dp(2))
        mini_fill_drawable.setColor(accent)
        mini_fill.setBackground(mini_fill_drawable)
        mini_bg.addView(mini_fill, FrameLayout.LayoutParams(0, AndroidUtilities.dp(3)))

        _mini_ratio = min(1.0, progress / goal) if goal > 0 else 0.0
        _mini_fill = mini_fill
        _mini_bg = mini_bg

        class _MiniBarLayoutListener(dynamic_proxy(OnGlobalLayoutListener)):
            def onGlobalLayout(self):
                try:
                    w = _mini_bg.getWidth()
                    if w > 0:
                        lp = _mini_fill.getLayoutParams()
                        lp.width = int(w * _mini_ratio)
                        _mini_fill.setLayoutParams(lp)
                    _mini_bg.getViewTreeObserver().removeOnGlobalLayoutListener(self)
                except Exception:
                    pass

        mini_bg.getViewTreeObserver().addOnGlobalLayoutListener(_MiniBarLayoutListener())

        bar_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(3))
        bar_lp.topMargin = AndroidUtilities.dp(6)
        col.addView(mini_bg, bar_lp)

    card.addView(col, LinearLayout.LayoutParams(0, -2, 1.0))

    # right side: checkmark if completed, counter if not
    if completed:
        check_icon = ImageView(act)
        icon_id = _resolve_icon("msg_select")
        if icon_id:
            check_icon.setImageResource(icon_id)
        check_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
        lp = LinearLayout.LayoutParams(AndroidUtilities.dp(22), AndroidUtilities.dp(22))
        lp.leftMargin = AndroidUtilities.dp(10)
        card.addView(check_icon, lp)
    elif not is_secret_locked and not achievement.get("secret"):
        counter_tv = TextView(act)
        counter_tv.setText(f"{progress}/{goal}")
        counter_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        counter_tv.setTextColor(text_secondary)
        counter_tv.setGravity(Gravity.CENTER)
        lp = LinearLayout.LayoutParams(-2, -2)
        lp.leftMargin = AndroidUtilities.dp(10)
        card.addView(counter_tv, lp)

    def _on_card_click(v):
        nonlocal is_secret_locked
        if is_secret_locked and achievement.get("id") == "secret_curiosity":
            # clicking the card itself is the unlock trigger
            try:
                from .service.AchivementsEngine import unlock_secret
                unlock_secret("curiosity")
            except Exception as _e:
                log(f"_make_achievement_card: unlock_secret failed: {_e}")
            is_secret_locked = False
        if not is_secret_locked:
            on_hint_click()

    card.setOnClickListener(OnClickListener(_on_card_click))
    _apply_press_scale(card)
    return card


class _AchievementListFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    def __init__(self, category: str, achievements: list, show_hint_fn):
        super().__init__()
        self.category = category
        self.achievements = achievements
        self.show_hint_fn = show_hint_fn

    def onFragmentCreate(self, *_):
        log("achiev: _AchievementListFragment.onFragmentCreate called")

    def onFragmentDestroy(self, *_):
        log("achiev: _AchievementListFragment.onFragmentDestroy called")
        try:
            from .service.AchivementsEngine import unregister_bulletin_container
            if hasattr(self, '_root_view') and self._root_view is not None:
                unregister_bulletin_container(self._root_view)
            has_view = hasattr(self, '_root_view')
            log(f"achiev: has _root_view={has_view}")
            if has_view and self._root_view is not None:
                parent = self._root_view.getParent()
                log(f"achiev: parent={parent}")
                if parent is not None:
                    parent.removeView(self._root_view)
                    log("achiev: removeView done")
                else:
                    log("achiev: parent is None, skip removeView")
            else:
                log("achiev: _root_view is None or missing")
        except Exception as e:
            log(f"achiev: onFragmentDestroy error: {e}")

    def beforeCreateView(self):
        log("achiev: _AchievementListFragment.beforeCreateView called")
        try:
            if hasattr(self, '_root_view') and self._root_view is not None:
                parent = self._root_view.getParent()
                if parent is not None:
                    parent.removeView(self._root_view)
                    log("achiev: _AchievementListFragment removed old root_view")
                self._root_view = None
        except Exception as e:
            log(f"achiev: _AchievementListFragment cleanup error: {e}")
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            log("achiev: act is None, abort")
            return None
        try:
            bg = Theme.getColor(Theme.key_windowBackgroundGray)
            card_bg = Theme.getColor(Theme.key_windowBackgroundWhite)

            root = FrameLayout(act)
            root.setBackgroundColor(bg)

            scroll = ScrollView(act)
            scroll.setVerticalScrollBarEnabled(False)
            try:
                scroll.setFillViewport(True)
            except Exception:
                pass

            content = LinearLayout(act)
            content.setOrientation(LinearLayout.VERTICAL)
            content.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(12),
                AndroidUtilities.dp(16), AndroidUtilities.dp(16)
            )

            for i, a in enumerate(self.achievements):
                def make_hint_cb(achievement=a):
                    return lambda: self.show_hint_fn(achievement)

                card = _make_achievement_card(act, a, make_hint_cb())
                lp = LinearLayout.LayoutParams(-1, -2)
                if i > 0:
                    lp.topMargin = AndroidUtilities.dp(8)
                _add_with_fade(content, card, lp, i * 40)

            scroll.addView(content, ScrollView.LayoutParams(-1, -2))
            root.addView(scroll, FrameLayout.LayoutParams(-1, -1))
            self._root_view = root
            log(f"achiev: _AchievementListFragment._root_view set: {root}")
            from .service.AchivementsEngine import register_bulletin_container
            register_bulletin_container(root)
            _add_actionbar_glow(root)
            _add_bottom_glow(root)
            return root
        except Exception as e:
            log(f"achiev: _AchievementListFragment.beforeCreateView error: {e}")
            return None

    def afterCreateView(self, view):
        if view is not None:
            _add_actionbar_glow(view)
            _add_bottom_glow(view)
            try:
                from ..viewUtils import applyFontToTree
                applyFontToTree(view)
            except Exception:
                pass
        return view

    def getTitle(self):
        if self.achievements:
            category_key = self.achievements[0].get("category_key", self.category)
            return str(strings[category_key])
        return str(strings[self.category])

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, item_id):
        pass

    def onBackPressed(self):
        return None


class _CategoryFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    def __init__(self, categories: dict, cat_names: list, show_hint_fn):
        super().__init__()
        self.categories = categories
        self.cat_names = cat_names
        self.show_hint_fn = show_hint_fn

    def onFragmentCreate(self, *_):
        log("achiev: _CategoryFragment.onFragmentCreate called")

    def onFragmentDestroy(self, *_):
        log("achiev: _CategoryFragment.onFragmentDestroy called")
        try:
            from .service.AchivementsEngine import unregister_bulletin_container
            if hasattr(self, '_root_view') and self._root_view is not None:
                unregister_bulletin_container(self._root_view)
            has_view = hasattr(self, '_root_view')
            log(f"achiev: has _root_view={has_view}")
            if has_view and self._root_view is not None:
                parent = self._root_view.getParent()
                log(f"achiev: parent={parent}")
                if parent is not None:
                    parent.removeView(self._root_view)
                    log("achiev: removeView done")
                else:
                    log("achiev: parent is None, skip removeView")
            else:
                log("achiev: _root_view is None or missing")
        except Exception as e:
            log(f"achiev: _CategoryFragment.onFragmentDestroy error: {e}")

    def beforeCreateView(self):
        log("achiev: _CategoryFragment.beforeCreateView called")
        try:
            if hasattr(self, '_root_view') and self._root_view is not None:
                parent = self._root_view.getParent()
                if parent is not None:
                    parent.removeView(self._root_view)
                    log("achiev: _CategoryFragment removed old root_view")
                self._root_view = None
        except Exception as e:
            log(f"achiev: _CategoryFragment cleanup error: {e}")
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            log("achiev: act is None, abort")
            return None
        try:
            bg = Theme.getColor(Theme.key_windowBackgroundGray)

            root = FrameLayout(act)
            root.setBackgroundColor(bg)

            scroll = ScrollView(act)
            scroll.setVerticalScrollBarEnabled(False)
            try:
                scroll.setFillViewport(True)
            except Exception:
                pass

            content = LinearLayout(act)
            content.setOrientation(LinearLayout.VERTICAL)
            content.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(12),
                AndroidUtilities.dp(16), AndroidUtilities.dp(16)
            )

            for i, cat in enumerate(self.cat_names):
                achievements = self.categories[cat]

                def make_click_cb(c=cat, a=achievements):
                    def on_click():
                        try:
                            cur_frag = get_last_fragment()
                            if not cur_frag:
                                return
                            delegate = _AchievementListFragment(c, a, self.show_hint_fn)
                            new_frag = UniversalFragment(delegate)
                            cur_frag.presentFragment(new_frag)
                            try:
                                from hook_utils import find_class as _fc
                                if a:
                                    category_key = a[0].get("category_key", c)
                                    new_frag.setTitle(str(strings[category_key]) if category_key in strings else str(strings[c]), False, 0)
                                else:
                                    new_frag.setTitle(str(strings[c]) if c in strings else c, False, 0)
                                new_frag.getActionBar().setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                            except Exception as _e:
                                log(f"achievementsUi: category actionbar setup error: {_e}")
                        except Exception as e:
                            log(f"achievementsUi: open category fragment failed: {e}")
                    return on_click

                card = _make_category_card(act, cat, achievements, make_click_cb())
                lp = LinearLayout.LayoutParams(-1, -2)
                if i > 0:
                    lp.topMargin = AndroidUtilities.dp(8)
                _add_with_fade(content, card, lp, i * 50)

            scroll.addView(content, ScrollView.LayoutParams(-1, -2))
            root.addView(scroll, FrameLayout.LayoutParams(-1, -1))
            self._root_view = root
            log(f"achiev: _CategoryFragment._root_view set: {root}")
            from .service.AchivementsEngine import register_bulletin_container
            register_bulletin_container(root)
            _add_actionbar_glow(root)
            _add_bottom_glow(root)
            return root
        except Exception as e:
            log(f"achiev: _CategoryFragment.beforeCreateView error: {e}")
            return None

    def afterCreateView(self, view):
        if view is not None:
            _add_actionbar_glow(view)
            _add_bottom_glow(view)
            try:
                from ..viewUtils import applyFontToTree
                applyFontToTree(view)
            except Exception:
                pass
        return view

    def getTitle(self):
        return str(strings["profile_achievements"])

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, item_id):
        pass

    def onBackPressed(self):
        return None


def show_hint_sheet(achievement: dict):
    try:
        frag = get_last_fragment()
        if not frag:
            return
        act = frag.getParentActivity()
        if not act:
            return

        sheet = BottomSheet(act, False, frag.getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(20),
            AndroidUtilities.dp(20), AndroidUtilities.dp(8)
        )
        try:
            root.setBackground(_create_rounded_bg(act, Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))

        # icon + title row
        title_row = LinearLayout(act)
        title_row.setOrientation(LinearLayout.HORIZONTAL)
        title_row.setGravity(Gravity.CENTER_VERTICAL)

        icon_name = achievement.get("icon", "msg_fave")
        try:
            icon_view = ImageView(act)
            icon_id = _resolve_icon(icon_name)
            if icon_id:
                icon_view.setImageResource(icon_id)
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
            icon_view.setColorFilter(accent)
            icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(24), AndroidUtilities.dp(24))
            icon_lp.rightMargin = AndroidUtilities.dp(10)
            title_row.addView(icon_view, icon_lp)
        except Exception:
            pass

        title_tv = TextView(act)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            title_tv.setTypeface(AndroidUtilities.bold())
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        title_tv.setText(str(strings[achievement.get("title_key", "achiev_title_unknown")]))
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_row.addView(title_tv, LayoutHelper.createLinear(-1, -2))
        root.addView(title_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 14))

        # hint text
        hint_tv = TextView(act)
        hint_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        hint_tv.setText(str(strings[achievement.get("hint_key", "achiev_hint_unknown")]))
        hint_tv.setTextColor(Theme.getColor(Theme.key_dialogTextGray2))
        hint_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
        root.addView(hint_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        # close button
        close_btn = FrameLayout(act)
        try:
            base = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            base = Theme.getColor(Theme.key_dialogTextBlue)
            pressed = base
        close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base, pressed
        ))
        close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_tv = TextView(act)
        close_tv.setText(strings["close_button"])
        close_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_tv.setTypeface(AndroidUtilities.bold())
        close_tv.setGravity(Gravity.CENTER)
        close_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_tv, FrameLayout.LayoutParams(-1, -2))
        close_btn.setOnClickListener(OnClickListener(lambda v: sheet.dismiss()))
        _apply_press_scale(close_btn)
        root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

        sheet.setCustomView(root)
        try:
            from ..viewUtils import applyFontToTree
            applyFontToTree(root)
        except Exception:
            pass
        sheet.show()
    except Exception as e:
        log(f"achievementsUi.show_hint_sheet: {e}")


def _create_rounded_bg(act, color: int):
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadii([
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        0, 0, 0, 0
    ])
    bg.setColor(color)
    return bg


def show_achievements(categories: dict, cat_names: list):
    # categories: dict[str, list[dict]]  — from get_all_with_progress()
    # cat_names: list[str]               — ordered category keys
    try:
        from hook_utils import find_class
        frag = get_last_fragment()
        if not frag:
            return
        delegate = _CategoryFragment(categories, cat_names, show_hint_sheet)
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        try:
            new_frag.setTitle(strings["profile_achievements"], False, 0)
            new_frag.getActionBar().setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
        except Exception as _e:
            log(f"achievementsUi: show_achievements actionbar setup error: {_e}")
    except Exception as e:
        log(f"achievementsUi.show_achievements: {e}")

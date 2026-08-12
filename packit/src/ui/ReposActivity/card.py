# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# One repository card.
#
# Deliberately not the plugin card: that one is a filled surface with a 18dp
# radius, this is an outlined 16dp container so the two lists read as different
# places. Everything the card shows comes from the repomap already sitting in
# reposCache — the card never touches the network.

from packutil import logx
import ctypes

from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.view import View, Gravity
from android.text import TextUtils
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import OnClickListener

try:
    from org.telegram.messenger import AndroidUtilities
    from org.telegram.ui.ActionBar import Theme
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"repos card: import telegram classes failed: {e}")
    AndroidUtilities = None
    Theme = None
    LayoutHelper = None

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"repos card: import elyx strings failed: {e}")

from . import repoIcon
from ..PluginListActivity.helpers.uiHelpers import (
    make_info_chip, apply_press_scale_on_target, resolve_icon,
)


def _c(color: int) -> int:
    return ctypes.c_int32(color).value


def _alpha(color: int, a: int) -> int:
    return _c((a << 24) | (color & 0xFFFFFF))


def _theme(key: str, fallback: int = 0):
    try:
        return Theme.getColor(getattr(Theme, key))
    except Exception:
        return fallback


def _round_icon_button(ctx, icon_name: str, tint: int, on_click,
                       size_dp: int = 32, icon_dp: int = 16):
    btn = FrameLayout(ctx)
    btn.setClickable(True)
    btn.setFocusable(True)
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(size_dp) / 2))
    bg.setColor(_alpha(tint, 0x14))
    try:
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(size_dp) // 2, _alpha(tint, 0x14), _alpha(tint, 0x28)
        ))
    except Exception:
        btn.setBackground(bg)

    iv = ImageView(ctx)
    icon_id = resolve_icon(icon_name)
    if icon_id:
        iv.setImageResource(icon_id)
    iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    try:
        iv.setColorFilter(tint)
    except Exception:
        pass
    btn.addView(iv, FrameLayout.LayoutParams(
        AndroidUtilities.dp(icon_dp), AndroidUtilities.dp(icon_dp), Gravity.CENTER
    ))
    btn.setOnClickListener(OnClickListener(lambda v: on_click()))
    apply_press_scale_on_target(btn, btn)
    return btn


def _card_background(enabled: bool):
    # Filled, no outline. The border was there to set these cards apart from the
    # plugin ones, but a 1dp divider-coloured stroke reads as a stray line
    # rather than as a container — the fill against key_windowBackgroundGray is
    # what the client's own cards do and it is enough on its own.
    surface = _theme("key_windowBackgroundWhite")
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(16)))
    bg.setColor(surface if enabled else _alpha(surface, 0x80))
    return bg


def make_repo_card(ctx, repo: dict, info: dict, callbacks: dict, handle: dict = None):
    """
    repo      — the stored dict (id / name / url / enabled)
    info      — read off the ui thread from reposCache: maintainer, telegram,
                source, icon_url, plugins, icons, status ("loaded"/"missing")
    callbacks — on_toggle(bool, repo), on_menu(anchor, repo), on_open(url)
    handle    — filled with {"view", "update"}; call update(repo, info) to
                repaint this card in place instead of building another one
    """
    enabled = bool(repo.get("enabled", True))
    accent = repoIcon.accent_for(repo)

    card = LinearLayout(ctx)
    card.setOrientation(LinearLayout.VERTICAL)
    card.setPadding(*(AndroidUtilities.dp(16),) * 4)
    card.setClickable(True)
    card.setFocusable(True)
    # PluginCell does both of these on itself, and this is why: with exteraGram's
    # new switch style the toggle is an md3 pill wider than the 37dp box it is
    # laid out in, and Switch centres it, so it hangs over both edges by design.
    # Every cell in the client that hosts one stops clipping — copying the box
    # and the colours without this is what sheared the ends off ours. The 16dp
    # padding has room to spare for the overhang.
    card.setClipChildren(False)
    card.setClipToPadding(False)

    # ---- header: avatar | name + maintainer | switch
    header = LinearLayout(ctx)
    header.setOrientation(LinearLayout.HORIZONTAL)
    header.setGravity(Gravity.CENTER_VERTICAL)
    header.setClipChildren(False)
    header.setClipToPadding(False)

    def _icon_lp():
        lp = LinearLayout.LayoutParams(AndroidUtilities.dp(48), AndroidUtilities.dp(48))
        lp.gravity = Gravity.CENTER_VERTICAL
        lp.rightMargin = AndroidUtilities.dp(12)
        return lp

    icon_url = str(info.get("icon_url") or "")
    icon_view = repoIcon.build_icon_view(ctx, repo, 48, 14, icon_url)
    icon_holder = [icon_view]  # the avatar is swapped only when its url changes
    header.addView(icon_view, _icon_lp())

    col = LinearLayout(ctx)
    col.setOrientation(LinearLayout.VERTICAL)

    name_tv = TextView(ctx)
    name_tv.setText(str(repo.get("name") or strings.unnamed))
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
    name_tv.setSingleLine(True)
    # setSingleLine on its own only clips, and it clips mid-glyph: a name that
    # is within the stored limit but still too wide for a narrow screen has to
    # end in an ellipsis, not in half a letter
    name_tv.setEllipsize(TextUtils.TruncateAt.END)
    name_tv.setTextColor(_theme("key_windowBackgroundWhiteBlackText"))
    try:
        name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        try:
            name_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
    col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

    # always built, hidden when there is nothing to say: the card is repainted
    # in place, and a row that only exists sometimes cannot be
    sub_tv = TextView(ctx)
    sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
    sub_tv.setSingleLine(True)
    sub_tv.setEllipsize(TextUtils.TruncateAt.END)
    sub_tv.setTextColor(_theme("key_windowBackgroundWhiteGrayText"))
    col.addView(sub_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

    def _fill_sub(r, i):
        text = str(i.get("maintainer") or "").strip() or _host_of(r.get("url"))
        # rm_maintainer is free text from the repomap and reads like a message —
        # "@name", "ROBOT (список от @name)" — so it goes through the client's
        # own formatter, which resolves mentions, emoji and markdown.
        #
        # No LinkMovementMethod here on purpose: it makes a TextView clickable,
        # and this one sits inside a card whose tap opens the source's sheet. A
        # tappable mention belongs in that sheet, where nothing competes for it.
        try:
            from com.exteragram.messenger.utils.text import LocaleUtils
            sub_tv.setText(LocaleUtils.fullyFormatText(text))
        except Exception as e:
            logx(f"repos card: maintainer format unavailable: {e}", True)
            sub_tv.setText(text)
        sub_tv.setVisibility(0 if text else 8)  # VISIBLE / GONE

    _fill_sub(repo, info)

    header.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    # _toggle is defined further down; the lambda resolves it when tapped
    switch = _build_switch(ctx, enabled, lambda: _toggle())
    if switch is not None:
        # Explicit params, not LayoutHelper.createLinear(w, h, gravity, …): that
        # call has a (w, h, float weight, …) twin, and picking it gives the
        # switch a weight instead of a gravity. In a row that already has a
        # weighted column the switch then absorbs the overflow and is measured
        # narrower than the track Switch.onDraw centres in it, so the track is
        # clipped by the view bounds — which is what turned the pill into a
        # rectangle with square corners.
        #
        # 56x48 rather than the client's 37x40: the switch is the touch target
        # now that the card no longer toggles, and the box has to cover the
        # whole pill the new switch style draws, not just the middle of it.
        sw_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(56), AndroidUtilities.dp(48))
        sw_lp.gravity = Gravity.CENTER_VERTICAL
        sw_lp.leftMargin = AndroidUtilities.dp(6)
        header.addView(switch, sw_lp)

    card.addView(header, LayoutHelper.createLinear(-1, -2))

    # ---- chips: status and what the repository carries
    chips = LinearLayout(ctx)
    chips.setOrientation(LinearLayout.HORIZONTAL)
    chips.setGravity(Gravity.CENTER_VERTICAL)

    def _fill_chips(is_on, i):
        chips.removeAllViews()
        # No on/off chip. It said in words what the switch an inch away says by
        # being on or off, and two controls reporting one fact is one too many.
        # A source whose repomap never downloaded still gets a chip, because
        # nothing else on the card says that — it is switched on and gives
        # nothing, which the switch cannot show.
        if is_on and str(i.get("status") or "") == "missing":
            chips.addView(
                make_info_chip(ctx, str(getattr(strings, "repo_card_status_missing", "Not loaded")),
                               "key_text_RedBold"),
                LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))

        plugins = i.get("plugins")
        if isinstance(plugins, int):
            chips.addView(
                make_info_chip(ctx, str(strings.repo_card_plugins).replace("{0}", str(plugins)),
                               "key_windowBackgroundWhiteBlueText"),
                LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))
        icons_n = i.get("icons")
        if isinstance(icons_n, int):
            chips.addView(
                make_info_chip(ctx, str(strings.repo_card_icons).replace("{0}", str(icons_n)),
                               "key_avatar_backgroundViolet"),
                LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))
        # with the on/off chip gone most sources have nothing to put here; GONE
        # takes the row's top margin with it instead of leaving a gap
        chips.setVisibility(0 if chips.getChildCount() > 0 else 8)

    # filled by the first _apply_enabled below, together with the rest of the
    # state that depends on the switch
    card.addView(chips, LayoutHelper.createLinear(-1, -2, 0, 12, 0, 0))

    # ---- footer: telegram / source, overflow on the right
    footer = LinearLayout(ctx)
    footer.setOrientation(LinearLayout.HORIZONTAL)
    footer.setGravity(Gravity.CENTER_VERTICAL)

    on_open = callbacks.get("on_open") or (lambda _u: None)

    def _btn_lp(right_margin_dp=6):
        lp = LinearLayout.LayoutParams(AndroidUtilities.dp(32), AndroidUtilities.dp(32))
        lp.rightMargin = AndroidUtilities.dp(right_margin_dp)
        return lp

    # own container so a repaint can refill it without touching the overflow
    links = LinearLayout(ctx)
    links.setOrientation(LinearLayout.HORIZONTAL)
    links.setGravity(Gravity.CENTER_VERTICAL)

    def _fill_links(i):
        links.removeAllViews()
        tg_url = str(i.get("telegram") or "").strip()
        src_url = str(i.get("source") or "").strip()
        if tg_url:
            links.addView(
                _round_icon_button(ctx, "msg_channel", accent, lambda u=tg_url: on_open(u)),
                _btn_lp())
        if src_url:
            links.addView(
                _round_icon_button(ctx, "msg_link", accent, lambda u=src_url: on_open(u)),
                _btn_lp())

    _fill_links(info)
    footer.addView(links, LayoutHelper.createLinear(-2, -2))

    spacer = View(ctx)
    footer.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))

    on_menu = callbacks.get("on_menu")
    menu_btn = _round_icon_button(
        ctx, "ic_ab_other", _theme("key_windowBackgroundWhiteGrayText"),
        # state["repo"] and not the dict this card was built from: a repaint
        # hands over a freshly parsed one, and the menu prefills its dialogs
        lambda: on_menu(menu_holder[0], state["repo"]) if on_menu else None
    )
    menu_holder = [menu_btn]
    footer.addView(menu_btn, _btn_lp(0))

    card.addView(footer, LayoutHelper.createLinear(-1, -2, 0, 10, 0, 0))

    # the card opens the source's sheet; the switch beside it is what turns the
    # source on and off, so a tap meant for one is never the other
    on_toggle = callbacks.get("on_toggle")
    on_open_card = callbacks.get("on_open_card")
    state = {"enabled": enabled, "info": info, "repo": repo, "icon_url": icon_url}

    def _apply_enabled(is_on, animate):
        state["enabled"] = is_on
        try:
            card.setBackground(_card_background(is_on))
        except Exception as e:
            logx(f"repos card: background repaint error: {e}", False)
        try:
            if switch is not None:
                switch.setChecked(is_on, animate)
        except Exception:
            pass
        _fill_chips(is_on, state["info"])
        target = 1.0 if is_on else 0.55
        for view in (icon_holder[0], col, chips):
            try:
                if animate:
                    view.animate().alpha(target).setDuration(160).start()
                else:
                    view.setAlpha(target)
            except Exception:
                pass

    def _toggle(_v=None):
        _apply_enabled(not state["enabled"], True)
        if on_toggle:
            on_toggle(state["enabled"], state["repo"])

    def _update(new_repo, new_info):
        # Repaint, do not rebuild. The avatar in particular survives: rebuilding
        # the card meant a fresh ImageView with nothing in it, so flipping a
        # switch made every icon on screen blink.
        state["repo"] = new_repo
        state["info"] = new_info or {}
        try:
            name_tv.setText(str(new_repo.get("name") or strings.unnamed))
            _fill_sub(new_repo, state["info"])
            _fill_links(state["info"])
            new_url = str(state["info"].get("icon_url") or "")
            if new_url != state["icon_url"]:
                # only an updated repomap can do this, and then it really is a
                # different picture — swap the whole avatar
                state["icon_url"] = new_url
                try:
                    header.removeView(icon_holder[0])
                except Exception:
                    pass
                replacement = repoIcon.build_icon_view(ctx, new_repo, 48, 14, new_url)
                replacement.setAlpha(1.0 if state["enabled"] else 0.55)
                header.addView(replacement, 0, _icon_lp())
                icon_holder[0] = replacement
            now = bool(new_repo.get("enabled", True))
            if now != state["enabled"]:
                _apply_enabled(now, False)
            else:
                # the card is already showing this value — most repaints arrive
                # right after its own tap, and re-setting alpha mid-animation
                # would snap it
                _fill_chips(now, state["info"])
        except Exception as e:
            logx(f"repos card: update error: {e}", False)

    card.setOnClickListener(OnClickListener(
        lambda _v: on_open_card(state["repo"], state["info"]) if on_open_card else None
    ))
    apply_press_scale_on_target(card, card)
    _apply_enabled(enabled, False)
    if isinstance(handle, dict):
        handle["view"] = card
        handle["update"] = _update
    return card


def _build_switch(ctx, checked: bool, on_toggle):
    # Coloured the way the client colours the switch in its own plugin card
    # (PluginCell). Unlike that one it takes its own taps: the card opens a
    # sheet now, so turning a source on and off is the switch's job alone.
    try:
        from org.telegram.ui.Components import Switch as TgSwitch
        sw = TgSwitch(ctx)
        try:
            sw.setColors(
                Theme.key_switchTrack, Theme.key_switchTrackChecked,
                Theme.key_windowBackgroundWhite, Theme.key_windowBackgroundWhite,
            )
        except Exception as e:
            logx(f"repos card: switch colors unavailable: {e}", True)
        sw.setChecked(checked, False)
        sw.setClickable(True)
        sw.setFocusable(True)
        sw.setOnClickListener(OnClickListener(lambda v: on_toggle()))

        # Switch has no touch handling of its own — the cells that host it drive
        # its ripple from their own setPressed. Nothing overrides setPressed
        # here, so the press is forwarded by hand, and the listener returns
        # False so the click still goes through the normal path.
        try:
            from java import dynamic_proxy
            from android.view import View as _View

            class _Press(dynamic_proxy(_View.OnTouchListener)):
                def onTouch(self, v, event):
                    action = event.getActionMasked()
                    if action == 0:            # DOWN
                        sw.setDrawRipple(True)
                    elif action in (1, 3):     # UP, CANCEL
                        sw.setDrawRipple(False)
                    return False

            sw.setOnTouchListener(_Press())
        except Exception as e:
            logx(f"repos card: switch ripple unavailable: {e}", True)
        return sw
    except Exception as e:
        logx(f"repos card: switch unavailable: {e}", False)
        return None


def _host_of(url) -> str:
    try:
        text = str(url or "")
        if "://" in text:
            text = text.split("://", 1)[1]
        return text.split("/", 1)[0]
    except Exception:
        return ""

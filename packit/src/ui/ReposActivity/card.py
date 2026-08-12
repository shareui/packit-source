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
from java import dynamic_proxy

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
    apply_press_scale_on_target, resolve_icon,
)


def _chip(ctx, text: str, tint: int):
    # uiHelpers.make_info_chip fills at a third alpha and paints the label in a
    # palette colour. Both are wrong here: the fill has to be solid, and the
    # colour has to be the theme's, not a green borrowed from the avatar
    # palette that no other pixel on the screen is using.
    surface = _theme("key_windowBackgroundWhite")
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(8)))
    bg.setColor(repoIcon.tonal(tint, surface, 0.16))
    tv = TextView(ctx)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(_alpha(tint, 0xFF))
    tv.setBackground(bg)
    tv.setPadding(AndroidUtilities.dp(8), AndroidUtilities.dp(3),
                  AndroidUtilities.dp(8), AndroidUtilities.dp(3))
    return tv


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
                       size_dp: int = 32, icon_dp: int = 16, translucent: bool = False):
    # Opaque by default: a fill of accent-at-8-percent takes its colour from
    # whatever happens to be behind the button, which on an animating card is
    # not one thing. The overflow is the exception — it is a neutral grey on the
    # card and is meant to sit back.
    btn = FrameLayout(ctx)
    btn.setClickable(True)
    btn.setFocusable(True)
    if translucent:
        fill, pressed = _alpha(tint, 0x14), _alpha(tint, 0x28)
    else:
        surface = _theme("key_windowBackgroundWhite")
        fill = repoIcon.tonal(tint, surface, 0.16)
        pressed = repoIcon.tonal(tint, surface, 0.30)
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(size_dp) / 2))
    bg.setColor(fill)
    try:
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(size_dp) // 2, fill, pressed
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
        # Set up exactly the way the plugin catalogue sets up its author line
        # (PluginListActivity/card.py): fullyFormatText, grey body,
        # windowBackgroundWhiteBlueText for the mention, LinkMovementMethod.
        # Left to itself the formatter paints mentions in its own colour, which
        # is why these came out a teal that appears nowhere else on the screen.
        try:
            from com.exteragram.messenger.utils.text import LocaleUtils
            from android.text.method import LinkMovementMethod
            sub_tv.setText(LocaleUtils.fullyFormatText(text))
            sub_tv.setLinkTextColor(_theme("key_windowBackgroundWhiteBlueText"))
            sub_tv.setMovementMethod(LinkMovementMethod.getInstance())
        except Exception as e:
            logx(f"repos card: maintainer format unavailable: {e}", True)
            sub_tv.setText(text)
        sub_tv.setVisibility(0 if text else 8)  # VISIBLE / GONE

    _fill_sub(repo, info)

    header.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    switch = _build_switch(ctx, enabled)
    if switch is not None:
        # Switch draws itself to the size of its view, so the box is not a
        # matter of taste: at 56x48 the pill came out half again as big as the
        # one the client draws everywhere else. It gets the client's own 37x40
        # back, and the larger touch target moves to a wrapper around it —
        # 37x40 is under the 48dp a control should answer to, and this switch
        # takes its own taps now.
        #
        # Explicit params, not LayoutHelper.createLinear(w, h, gravity, …): that
        # call has a (w, h, float weight, …) twin, and picking it gives the
        # switch a weight instead of a gravity. In a row that already has a
        # weighted column the switch then absorbs the overflow and is measured
        # narrower than its own track, which shears the ends off the pill.
        sw_wrap = FrameLayout(ctx)
        sw_wrap.setClipChildren(False)
        sw_wrap.setClickable(True)
        sw_wrap.setFocusable(True)
        sw_wrap.setOnClickListener(OnClickListener(lambda v: _toggle()))
        # Switch has no touch handling of its own — the cells that host it drive
        # its ripple from their own setPressed, so the wrapper does the same.
        # The listener returns False, leaving the click to the normal path.
        try:
            from android.view import View as _View

            class _Press(dynamic_proxy(_View.OnTouchListener)):
                def onTouch(self, v, event):
                    action = event.getActionMasked()
                    if action == 0:            # DOWN
                        switch.setDrawRipple(True)
                    elif action in (1, 3):     # UP, CANCEL
                        switch.setDrawRipple(False)
                    return False

            sw_wrap.setOnTouchListener(_Press())
        except Exception as e:
            logx(f"repos card: switch ripple unavailable: {e}", True)

        sw_inner = FrameLayout.LayoutParams(AndroidUtilities.dp(37), AndroidUtilities.dp(40))
        sw_inner.gravity = Gravity.CENTER
        sw_wrap.addView(switch, sw_inner)

        sw_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(56), AndroidUtilities.dp(48))
        sw_lp.gravity = Gravity.CENTER_VERTICAL
        sw_lp.leftMargin = AndroidUtilities.dp(6)
        header.addView(sw_wrap, sw_lp)

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
        chip_lp = LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0)
        if is_on and str(i.get("status") or "") == "missing":
            # the one chip that is not the accent: this is a fault, and the
            # theme has a colour for those
            chips.addView(
                _chip(ctx, str(getattr(strings, "repo_card_status_missing", "Not loaded")),
                      _theme("key_text_RedBold")), chip_lp)

        plugins = i.get("plugins")
        if isinstance(plugins, int):
            chips.addView(
                _chip(ctx, str(strings.repo_card_plugins).replace("{0}", str(plugins)), accent),
                LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))
        icons_n = i.get("icons")
        if isinstance(icons_n, int):
            chips.addView(
                _chip(ctx, str(strings.repo_card_icons).replace("{0}", str(icons_n)), accent),
                LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))
        # how much of this source the user is actually running, off the
        # installer's own per-repository index
        installed = i.get("installed")
        if isinstance(installed, int) and installed > 0:
            chips.addView(
                _chip(ctx, str(getattr(strings, "repo_card_installed", "{0} installed"))
                      .replace("{0}", str(installed)), accent),
                LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))
        # a source nobody has opened yet has nothing to put here; GONE takes the
        # row's top margin with it instead of leaving a gap
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

    # When a source declares neither a channel nor a repository the footer used
    # to be one lone overflow button adrift on an empty row. The age of the
    # cached repomap belongs on a screen about sources anyway — it is what the
    # counts above it were read from.
    updated_tv = TextView(ctx)
    updated_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    updated_tv.setSingleLine(True)
    updated_tv.setEllipsize(TextUtils.TruncateAt.END)
    updated_tv.setTextColor(_theme("key_windowBackgroundWhiteGrayText"))

    def _fill_updated(i):
        text = _updated_label(i.get("updated_at"))
        updated_tv.setText(text)
        updated_tv.setVisibility(0 if text else 8)

    _fill_updated(info)
    footer.addView(updated_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

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

    on_menu = callbacks.get("on_menu")
    menu_btn = _round_icon_button(
        ctx, "ic_ab_other", _theme("key_windowBackgroundWhiteGrayText"),
        # state["repo"] and not the dict this card was built from: a repaint
        # hands over a freshly parsed one, and the menu prefills its dialogs
        lambda: on_menu(menu_holder[0], state["repo"]) if on_menu else None,
        translucent=True
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
            _fill_updated(state["info"])
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


def _build_switch(ctx, checked: bool):
    # Coloured the way the client colours the switch in its own plugin card
    # (PluginCell), and given that cell's box. The card opens a sheet now, so
    # the tap that turns a source on and off belongs to the switch — but it
    # arrives through the wrapper, which is big enough to aim at.
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
        # the wrapper around it takes the taps; the switch keeps the client's
        # box so it keeps the client's proportions
        sw.setClickable(False)
        sw.setFocusable(False)
        return sw
    except Exception as e:
        logx(f"repos card: switch unavailable: {e}", False)
        return None


def _updated_label(mtime) -> str:
    # LocaleController already words "just now / N minutes ago / today at …" for
    # the client's location updates, in every language it ships, and a repomap
    # cache is the same kind of fact — so the wording comes from there rather
    # than from four more locale keys of my own.
    try:
        seconds = int(float(mtime or 0))
        if seconds <= 0:
            return ""
        from org.telegram.messenger import LocaleController
        return str(LocaleController.formatLocationUpdateDate(seconds))
    except Exception as e:
        logx(f"repos card: updated label unavailable: {e}", True)
        return ""


def _host_of(url) -> str:
    try:
        text = str(url or "")
        if "://" in text:
            text = text.split("://", 1)[1]
        return text.split("/", 1)[0]
    except Exception:
        return ""

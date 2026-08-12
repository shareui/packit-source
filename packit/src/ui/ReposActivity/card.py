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


def _round_icon_button(ctx, icon_name: str, tint: int, on_click, size_dp: int = 36):
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
        AndroidUtilities.dp(18), AndroidUtilities.dp(18), Gravity.CENTER
    ))
    btn.setOnClickListener(OnClickListener(lambda v: on_click()))
    apply_press_scale_on_target(btn, btn)
    return btn


def make_repo_card(ctx, repo: dict, info: dict, callbacks: dict):
    """
    repo      — the stored dict (id / name / url / enabled)
    info      — read off the ui thread from reposCache: maintainer, telegram,
                source, plugins, icons, status ("ok"/"stale"/"missing")
    callbacks — on_toggle(bool), on_menu(anchor), on_open(url)
    """
    enabled = bool(repo.get("enabled", True))
    accent = repoIcon.accent_for(repo)

    card = LinearLayout(ctx)
    card.setOrientation(LinearLayout.VERTICAL)
    card.setPadding(*(AndroidUtilities.dp(16),) * 4)
    card.setClickable(True)
    card.setFocusable(True)
    try:
        surface = _theme("key_windowBackgroundWhite")
        outline = _theme("key_divider")
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(float(AndroidUtilities.dp(16)))
        bg.setColor(surface if enabled else _alpha(surface, 0x80))
        bg.setStroke(AndroidUtilities.dp(1), _alpha(outline, 0xFF if enabled else 0x66))
        card.setBackground(bg)
    except Exception as e:
        logx(f"repos card: background error: {e}", False)

    # ---- header: avatar | name + maintainer | switch
    header = LinearLayout(ctx)
    header.setOrientation(LinearLayout.HORIZONTAL)
    header.setGravity(Gravity.CENTER_VERTICAL)

    icon_view = repoIcon.build_icon_view(ctx, repo, 48, 14)
    header.addView(icon_view, LayoutHelper.createLinear(48, 48, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

    col = LinearLayout(ctx)
    col.setOrientation(LinearLayout.VERTICAL)

    name_tv = TextView(ctx)
    name_tv.setText(str(repo.get("name") or strings.unnamed))
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
    name_tv.setSingleLine(True)
    name_tv.setTextColor(_theme("key_windowBackgroundWhiteBlackText"))
    try:
        name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        try:
            name_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
    col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

    sub = str(info.get("maintainer") or "").strip() or _host_of(repo.get("url"))
    if sub:
        sub_tv = TextView(ctx)
        sub_tv.setText(sub)
        sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        sub_tv.setSingleLine(True)
        sub_tv.setTextColor(_theme("key_windowBackgroundWhiteGrayText"))
        col.addView(sub_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

    header.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    switch = _build_switch(ctx, enabled)
    if switch is not None:
        header.addView(switch, LayoutHelper.createLinear(37, 20, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    card.addView(header, LayoutHelper.createLinear(-1, -2))

    # ---- chips: status and what the repository carries
    chips = LinearLayout(ctx)
    chips.setOrientation(LinearLayout.HORIZONTAL)
    chips.setGravity(Gravity.CENTER_VERTICAL)

    status = "disabled" if not enabled else str(info.get("status") or "ok")
    status_text, status_key = {
        "ok": (getattr(strings, "repo_card_status_ok", "OK"), "key_avatar_backgroundGreen"),
        "stale": (getattr(strings, "repo_card_status_stale", "Stale"), "key_windowBackgroundWhiteGrayText"),
        "missing": (getattr(strings, "repo_card_status_missing", "Not loaded"), "key_text_RedBold"),
        "disabled": (getattr(strings, "repo_card_status_disabled", "Disabled"), "key_windowBackgroundWhiteGrayText"),
    }.get(status, (status, "key_windowBackgroundWhiteGrayText"))
    chips.addView(make_info_chip(ctx, str(status_text), status_key),
                  LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))

    plugins = info.get("plugins")
    if isinstance(plugins, int):
        chips.addView(
            make_info_chip(ctx, str(strings.repo_card_plugins).replace("{0}", str(plugins)),
                           "key_windowBackgroundWhiteBlueText"),
            LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))
    icons_n = info.get("icons")
    if isinstance(icons_n, int):
        chips.addView(
            make_info_chip(ctx, str(strings.repo_card_icons).replace("{0}", str(icons_n)),
                           "key_avatar_backgroundViolet"),
            LayoutHelper.createLinear(-2, -2, 0, 0, 6, 0))

    card.addView(chips, LayoutHelper.createLinear(-1, -2, 0, 12, 0, 0))

    # ---- footer: telegram / source, overflow on the right
    footer = LinearLayout(ctx)
    footer.setOrientation(LinearLayout.HORIZONTAL)
    footer.setGravity(Gravity.CENTER_VERTICAL)

    tg_url = str(info.get("telegram") or "").strip()
    src_url = str(info.get("source") or "").strip()
    on_open = callbacks.get("on_open") or (lambda _u: None)

    if tg_url:
        footer.addView(
            _round_icon_button(ctx, "msg_channel", accent, lambda u=tg_url: on_open(u)),
            LayoutHelper.createLinear(36, 36, 0, 0, 8, 0))
    if src_url:
        footer.addView(
            _round_icon_button(ctx, "msg_link", accent, lambda u=src_url: on_open(u)),
            LayoutHelper.createLinear(36, 36, 0, 0, 8, 0))

    spacer = View(ctx)
    footer.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))

    on_menu = callbacks.get("on_menu")
    menu_btn = _round_icon_button(
        ctx, "ic_ab_other", _theme("key_windowBackgroundWhiteGrayText"),
        lambda: on_menu(menu_holder[0]) if on_menu else None
    )
    menu_holder = [menu_btn]
    footer.addView(menu_btn, LayoutHelper.createLinear(36, 36))

    card.addView(footer, LayoutHelper.createLinear(-1, -2, 0, 10, 0, 0))

    # tapping the card flips the switch — it is the only stateful control here,
    # everything else lives behind explicit buttons
    on_toggle = callbacks.get("on_toggle")
    state = {"enabled": enabled}

    def _toggle(_v=None):
        state["enabled"] = not state["enabled"]
        try:
            if switch is not None:
                switch.setChecked(state["enabled"], True)
        except Exception:
            pass
        if on_toggle:
            on_toggle(state["enabled"])

    card.setOnClickListener(OnClickListener(_toggle))
    apply_press_scale_on_target(card, card)
    if not enabled:
        try:
            icon_view.setAlpha(0.55)
            col.setAlpha(0.55)
            chips.setAlpha(0.55)
        except Exception:
            pass
    return card


def _build_switch(ctx, checked: bool):
    # the host's own switch, the one it draws in its plugin cards
    try:
        from org.telegram.ui.Components import Switch as TgSwitch
        sw = TgSwitch(ctx)
        sw.setChecked(checked, False)
        try:
            sw.setColors(
                "key_switchTrack", "key_switchTrackChecked",
                "key_switchThumb", "key_switchThumbChecked",
            )
        except Exception:
            pass
        # taps are handled by the whole card, the switch only reflects state
        sw.setClickable(False)
        sw.setFocusable(False)
        return sw
    except Exception as e:
        logx(f"repos card: switch unavailable ({e}), falling back to a chip", True)
        return None


def _host_of(url) -> str:
    try:
        text = str(url or "")
        if "://" in text:
            text = text.split("://", 1)[1]
        return text.split("/", 1)[0]
    except Exception:
        return ""

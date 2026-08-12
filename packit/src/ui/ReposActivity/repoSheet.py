# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# The sheet behind a repository card.
#
# Tapping a card used to flip its switch; the switch does that itself now, and
# the card opens this instead. What goes in it is not decided yet, so for the
# moment it carries the source's identity and nothing else — the shell is real
# so that filling it is a matter of adding views under the header.

from packutil import logx
import ctypes

from android.widget import LinearLayout, TextView
from android.view import Gravity
from android.util import TypedValue
from android_utils import run_on_ui_thread
from client_utils import get_last_fragment

try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"repoSheet: import telegram classes failed: {e}")

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"repoSheet: import elyx strings failed: {e}")

from . import repoIcon
from ..viewUtils import applyFontToTree
from ..PluginListActivity.helpers.uiHelpers import setup_bottom_sheet, create_rounded_bg


def _c(color: int) -> int:
    return ctypes.c_int32(color).value


def _theme(key: str, fallback: int = 0):
    try:
        return Theme.getColor(getattr(Theme, key))
    except Exception:
        return fallback


def _handle(ctx):
    from android.graphics.drawable import GradientDrawable
    bar = TextView(ctx)
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(2)))
    bg.setColor(_c((0x3D << 24) | (_theme("key_sheet_scrollUp") & 0xFFFFFF)))
    bar.setBackground(bg)
    return bar


def show_repo_sheet(act, repo: dict, info: dict = None):
    info = info or {}

    def _show():
        try:
            frag = get_last_fragment()
            sheet = BottomSheet(act, False, frag.getResourceProvider() if frag else None)
            setup_bottom_sheet(sheet)

            root = LinearLayout(act)
            root.setOrientation(LinearLayout.VERTICAL)
            root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(10),
                            AndroidUtilities.dp(20), AndroidUtilities.dp(20))
            try:
                root.setBackground(create_rounded_bg(_theme("key_dialogBackground")))
            except Exception:
                root.setBackgroundColor(_theme("key_dialogBackground"))

            handle_lp = LayoutHelper.createLinear(36, 4, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 14)
            root.addView(_handle(act), handle_lp)

            header = LinearLayout(act)
            header.setOrientation(LinearLayout.HORIZONTAL)
            header.setGravity(Gravity.CENTER_VERTICAL)

            icon = repoIcon.build_icon_view(act, repo, 52, 15, str(info.get("icon_url") or ""))
            icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(52), AndroidUtilities.dp(52))
            icon_lp.rightMargin = AndroidUtilities.dp(14)
            header.addView(icon, icon_lp)

            col = LinearLayout(act)
            col.setOrientation(LinearLayout.VERTICAL)

            name = TextView(act)
            name.setText(str(repo.get("name") or strings.unnamed))
            name.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
            name.setTextColor(_theme("key_dialogTextBlack"))
            name.setSingleLine(True)
            try:
                name.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                pass
            col.addView(name, LayoutHelper.createLinear(-1, -2))

            sub_text = str(info.get("maintainer") or "").strip() or _host_of(repo.get("url"))
            if sub_text:
                sub = TextView(act)
                sub.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                sub.setTextColor(_theme("key_dialogTextGray2"))
                sub.setSingleLine(True)
                # here the mention can be tapped: unlike on the card, nothing
                # else in this row wants the touch
                try:
                    from com.exteragram.messenger.utils.text import LocaleUtils
                    from android.text.method import LinkMovementMethod
                    sub.setText(LocaleUtils.fullyFormatText(sub_text))
                    sub.setLinkTextColor(_theme("key_dialogTextBlue"))
                    sub.setMovementMethod(LinkMovementMethod.getInstance())
                except Exception as e:
                    logx(f"repoSheet: maintainer format unavailable: {e}", True)
                    sub.setText(sub_text)
                col.addView(sub, LayoutHelper.createLinear(-1, -2, 0, 3, 0, 0))

            header.addView(col, LayoutHelper.createLinear(-1, -2))
            root.addView(header, LayoutHelper.createLinear(-1, -2))

            sheet.setCustomView(root)
            applyFontToTree(root)
            sheet.show()
        except Exception as e:
            logx(f"repoSheet: show error: {e}", False)

    run_on_ui_thread(_show)


def _host_of(url) -> str:
    try:
        text = str(url or "")
        if "://" in text:
            text = text.split("://", 1)[1]
        return text.split("/", 1)[0]
    except Exception:
        return ""

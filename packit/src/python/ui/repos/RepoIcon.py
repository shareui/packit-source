# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Repository avatar — the view only. Where the picture comes from, and the
# memory and disk caches it comes through, are network/Storage's business.
#
# repomap declares the icon as a plain image url (repometa.rm_icon), so there is
# nothing to look up in R.drawable any more: the bitmap is drawn over a monogram
# that stands in until it arrives, and stays for repositories that declare none.
#
# The view is a FrameLayout of two layers, monogram below and bitmap above,
# because a Drawable subclass would have to be proxied into java just to paint
# one letter. Late answers are dropped by tag, the same guard utils/Stickers.py
# uses, so a card reused for another repository cannot inherit its avatar.

from packutil import logx
import ctypes

from android.widget import FrameLayout, TextView, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import run_on_ui_thread

try:
    from org.telegram.messenger import AndroidUtilities
    from org.telegram.ui.ActionBar import Theme
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"repoIcon: import telegram classes failed: {e}")
    AndroidUtilities = None
    Theme = None

from ...utils import ImagePool
from ...network import Storage
from ...utils import CachedRepos

def _c(color: int) -> int:
    # java setColor(int) rejects python ints >= 0x80000000
    return ctypes.c_int32(color).value


def _alpha(color: int, a: int) -> int:
    return _c((a << 24) | (color & 0xFFFFFF))


def tonal(accent: int, surface: int, fraction: float) -> int:
    """An opaque container colour: accent mixed into the surface behind it.

    Not accent-at-low-alpha. A translucent fill picks up whatever is under it —
    the card, then the window, then anything the card is animating over — so
    two identical chips on different backgrounds come out different colours,
    and overlapping ones stack. Mixing the two colours here gives the same look
    as one solid value that owes nothing to what is behind it.
    """
    fraction = max(0.0, min(1.0, float(fraction)))
    out = 0xFF000000
    for shift in (16, 8, 0):
        a = (accent >> shift) & 0xFF
        b = (surface >> shift) & 0xFF
        out |= int(round(b + (a - b) * fraction)) << shift
    return _c(out)


def _seed(repo: dict) -> int:
    key = str(repo.get("id") or repo.get("url") or repo.get("name") or "")
    total = 0
    for ch in key:
        total = (total * 31 + ord(ch)) & 0xFFFFFFFF
    return total


def accent_for(repo: dict) -> int:
    """The theme's accent. The repository does not get a say any more.

    This used to pick a colour per repository out of the avatar palette, so
    that a source kept its own look. On a theme built from one accent — which
    is every Monet theme, and the client's own — a violet or an orange dropped
    into it is simply the wrong colour on the screen, however stable it is.
    The argument stays so the call sites read the same.
    """
    for key in ("key_featuredStickers_addButton", "key_windowBackgroundWhiteBlueText"):
        try:
            return _c(int(Theme.getColor(getattr(Theme, key))))
        except Exception:
            continue
    return _c(0xFF2AABEE)


def _letter(repo: dict) -> str:
    for ch in str(repo.get("name") or ""):
        if ch.isalnum():
            return ch.upper()
    return "?"


def icon_url_for(repo: dict):
    return CachedRepos.icon_url(repo) or None


def build_icon_view(ctx, repo: dict, size_dp: int = 48, radius_dp: int = 14, url=None):
    # monogram now, real icon when it arrives — unless it has already arrived
    # once, in which case it is on screen before the card is
    size_px = AndroidUtilities.dp(size_dp)
    accent = accent_for(repo)

    holder = FrameLayout(ctx)

    try:
        surface = _c(int(Theme.getColor(Theme.key_windowBackgroundWhite)))
    except Exception:
        surface = _c(0xFF1C1C1E)

    mono = TextView(ctx)
    mono.setText(_letter(repo))
    mono.setGravity(Gravity.CENTER)
    mono.setTextSize(TypedValue.COMPLEX_UNIT_DIP, max(12, int(size_dp * 0.42)))
    mono.setTextColor(_alpha(accent, 0xFF))
    try:
        mono.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        try:
            mono.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(radius_dp)))
    bg.setColor(tonal(accent, surface, 0.16))
    mono.setBackground(bg)
    holder.addView(mono, FrameLayout.LayoutParams(size_px, size_px))

    image = ImageView(ctx)
    image.setScaleType(ImageView.ScaleType.CENTER_CROP)
    image.setVisibility(8)  # GONE
    try:
        image.setClipToOutline(True)
        image.setBackground(bg.getConstantState().newDrawable().mutate())
    except Exception:
        pass
    holder.addView(image, FrameLayout.LayoutParams(size_px, size_px))

    want = f"packit_repoicon_{_seed(repo)}"
    holder.setTag(want)

    if url is not None and not str(url).strip():
        # the caller read the cache and there is no icon in it — an empty string
        # is an answer, unlike None, so no worker goes and reads it again
        return holder

    cached = Storage.peek_icon(str(url or ""), size_px)
    if cached is not None:
        # straight onto the view, no fade: the icon was already on screen a
        # moment ago and fading it back in is exactly what reads as a blink
        try:
            image.setImageBitmap(cached)
            image.setVisibility(0)  # VISIBLE
            mono.setVisibility(8)
            return holder
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"repoIcon: cached bind error: {e}", False)

    def _task():
        target = url if url else icon_url_for(repo)
        if not target:
            return
        bmp = Storage.load_icon(target, size_px)
        if bmp is None:
            return

        def _apply():
            try:
                if str(holder.getTag() or "") != want:
                    return
                image.setImageBitmap(bmp)
                image.setVisibility(0)  # VISIBLE
                image.setAlpha(0.0)
                image.animate().alpha(1.0).setDuration(160).start()
                mono.setVisibility(8)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"repoIcon: bind error: {e}", False)

        run_on_ui_thread(_apply)

    ImagePool.submit(_task)
    return holder

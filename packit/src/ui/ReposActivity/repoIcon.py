# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Repository avatar.
#
# repomap declares the icon as a plain image url (repometa.rm_icon), so there is
# nothing to look up in R.drawable any more — the file is downloaded once, kept
# on disk and in memory, and drawn over a monogram that stands in until it
# arrives (and stays for repositories that declare no icon at all).
#
# The view is a FrameLayout of two layers, monogram below and bitmap above,
# because a Drawable subclass would have to be proxied into java just to paint
# one letter. Late answers are dropped by tag, the same guard utils/stickers.py
# uses, so a card reused for another repository cannot inherit its avatar.

from packutil import logx
import ctypes
from collections import OrderedDict

from android.widget import FrameLayout, TextView, ImageView
from android.view import Gravity
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import run_on_ui_thread

try:
    from org.telegram.messenger import AndroidUtilities
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"repoIcon: import telegram classes failed: {e}")
    AndroidUtilities = None
    Theme = None

from ...utils import imagePool
from ...utils.paths import getRepoIconCachePath, getRepoIconCacheDir, getRepoCachePath

_MEM_CAP = 64
_mem = OrderedDict()
_mem_lock = None

_PALETTE = (
    "key_avatar_backgroundBlue",
    "key_avatar_backgroundViolet",
    "key_avatar_backgroundGreen",
    "key_avatar_backgroundOrange",
    "key_avatar_backgroundPink",
    "key_avatar_backgroundCyan",
    "key_avatar_backgroundRed",
)


def _c(color: int) -> int:
    # java setColor(int) rejects python ints >= 0x80000000
    return ctypes.c_int32(color).value


def _alpha(color: int, a: int) -> int:
    return _c((a << 24) | (color & 0xFFFFFF))


def _lock():
    global _mem_lock
    if _mem_lock is None:
        import threading
        _mem_lock = threading.Lock()
    return _mem_lock


def _seed(repo: dict) -> int:
    key = str(repo.get("id") or repo.get("url") or repo.get("name") or "")
    total = 0
    for ch in key:
        total = (total * 31 + ord(ch)) & 0xFFFFFFFF
    return total


_harmonized = {}


def _harmonize(color: int) -> int:
    # The client ships MonetUtils for exactly this: on Android 12+ it pulls a
    # colour towards the system palette (MaterialColors.harmonize against
    # system_accent1_600), which is what keeps a fixed palette from clashing
    # with a Monet theme. Below 12, and on themes without it, it hands the
    # colour back unchanged.
    if color in _harmonized:
        return _harmonized[color]
    result = color
    try:
        from com.exteragram.messenger.utils.ui import MonetUtils
        result = _c(int(MonetUtils.harmonize(color)))
    except Exception:
        result = color
    _harmonized[color] = result
    return result


def accent_for(repo: dict) -> int:
    # deterministic colour so a repository keeps its look between launches
    try:
        name = _PALETTE[_seed(repo) % len(_PALETTE)]
        return _harmonize(Theme.getColor(getattr(Theme, name)))
    except Exception:
        try:
            return Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception:
            return _c(0xFF2AABEE)


def _letter(repo: dict) -> str:
    for ch in str(repo.get("name") or ""):
        if ch.isalnum():
            return ch.upper()
    return "?"


def icon_url_for(repo: dict):
    # rm_icon out of the cached repomap; anything that is not an http(s) link is
    # ignored — older repositories put an R.drawable name there
    try:
        repo_id = str(repo.get("id") or "")
        if not repo_id:
            return None
        import json
        import os
        path = getRepoCachePath(repo_id)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        url = str((cached.get("repometa") or {}).get("rm_icon") or "").strip()
        return url if url.lower().startswith(("http://", "https://")) else None
    except Exception as e:
        logx(f"repoIcon: icon_url_for error: {e}", True)
        return None


def peek_bitmap(url: str, px: int):
    # The already-decoded answer, or None. Card rebuilds go through here first:
    # routing a known bitmap through the worker pool costs a hop to the pool and
    # back to the ui thread, and in those two frames the card shows its
    # monogram — which is what made an avatar blink every time the list was
    # rebuilt after a toggle.
    if not url:
        return None
    key = _mem_key(url, px)
    with _lock():
        bmp = _mem.get(key)
        if bmp is not None:
            _mem.move_to_end(key)
        return bmp


def _mem_key(url: str, px: int) -> str:
    # px is part of the key: the same icon is decoded at different sizes for the
    # card and for the deeplink sheet, and the smaller decode looks soft blown up
    return f"{url}|{px}"


def _load_bitmap(url: str, px: int):
    # memory -> disk -> network, decoded to a px-sized bitmap
    bmp = peek_bitmap(url, px)
    if bmp is not None:
        return bmp

    import os
    path = getRepoIconCachePath(url)
    data = None
    try:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                data = f.read()
    except Exception:
        data = None

    if not data:
        data = imagePool.fetch(url)
        if not data:
            return None
        try:
            os.makedirs(getRepoIconCacheDir(), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            logx(f"repoIcon: cache write failed: {e}", True)

    bmp = imagePool.decode(data, px, imagePool.looks_like_svg(url, data))
    if bmp is None:
        # a corrupted cache entry would keep failing forever
        try:
            os.unlink(path)
        except Exception:
            pass
        return None
    with _lock():
        _mem[_mem_key(url, px)] = bmp
        while len(_mem) > _MEM_CAP:
            _mem.popitem(last=False)
    return bmp


def load_url_into(image_view, url: str, size_dp: int = 48):
    # for callers that already have their own ImageView (the repo=add deeplink
    # sheet), no monogram layer involved
    if not url:
        return
    size_px = AndroidUtilities.dp(size_dp)
    want = f"packit_repoicon_url_{abs(hash(url))}"
    try:
        image_view.setTag(want)
    except Exception:
        pass

    cached = peek_bitmap(url, size_px)
    if cached is not None:
        try:
            image_view.setImageBitmap(cached)
            try:
                image_view.setColorFilter(None)
            except Exception:
                pass
            return
        except Exception as e:
            logx(f"repoIcon: cached url bind error: {e}", False)

    def _task():
        bmp = _load_bitmap(url, size_px)
        if bmp is None:
            return

        def _apply():
            try:
                if str(image_view.getTag() or "") != want:
                    return
                image_view.setImageBitmap(bmp)
                try:
                    image_view.setColorFilter(None)
                except Exception:
                    pass
            except Exception as e:
                logx(f"repoIcon: url bind error: {e}", False)

        run_on_ui_thread(_apply)

    imagePool.submit(_task)


def build_icon_view(ctx, repo: dict, size_dp: int = 48, radius_dp: int = 14, url=None):
    # monogram now, real icon when it arrives — unless it has already arrived
    # once, in which case it is on screen before the card is
    size_px = AndroidUtilities.dp(size_dp)
    accent = accent_for(repo)

    holder = FrameLayout(ctx)

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
    bg.setColor(_alpha(accent, 0x1C))
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

    cached = peek_bitmap(str(url or ""), size_px)
    if cached is not None:
        # straight onto the view, no fade: the icon was already on screen a
        # moment ago and fading it back in is exactly what reads as a blink
        try:
            image.setImageBitmap(cached)
            image.setVisibility(0)  # VISIBLE
            mono.setVisibility(8)
            return holder
        except Exception as e:
            logx(f"repoIcon: cached bind error: {e}", False)

    def _task():
        target = url if url else icon_url_for(repo)
        if not target:
            return
        bmp = _load_bitmap(target, size_px)
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
            except Exception as e:
                logx(f"repoIcon: bind error: {e}", False)

        run_on_ui_thread(_apply)

    imagePool.submit(_task)
    return holder

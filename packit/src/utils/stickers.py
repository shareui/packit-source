# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Central sticker loader for the whole plugin.
#
# Resolving the set copies what the host itself does for a plugin icon —
# PluginCell -> MediaDataController.setPlaceholderImageByIndex ->
# getStickerSet(TL_inputStickerSetShortName, 0, false, callback):
#   * the callback belongs to one request and always answers, whether the set
#     comes from stickerSetsByName, from the sqlite copy or from a
#     messages.getStickerSet network fetch
#   * a resolved set lands in stickerSetsByName, so every later view for the
#     same pack binds synchronously
#   * the view carries a "packit_sticker_<pack>_<index>" tag and a callback
#     whose tag no longer matches is dropped, so a recycled row cannot end up
#     showing the previous row's icon
#
# The older route — loadStickersByEmojiOrName + NotificationCenter.
# diceStickersDidLoad — is kept only as a fallback. It dedups by pack name
# through loadingDiceStickerSets and posts the notification just for sets that
# resolve, so a screen that opens many icons at once (the export sheet lists
# every installed plugin) could sit unbound with nothing left to wake it.
#
# Binding copies org.telegram.ui.Components.StickerImageView:
# setImage(location, filter, "tgs", svgThumb, set) — the "tgs" ext makes
# animated stickers actually animate, the svg thumb stands in while the media
# downloads, and passing the set as parentObject lets the image receiver
# resolve the document. Until the set itself arrives there is no document and
# therefore no thumb, so a neutral block stands in underneath — the same idea
# as the placeholder a chat sticker shows while its media downloads.
#
# All sites call load_sticker(view, "pack/index", size_dp).

from packutil import logx

_CAP = 256

# Callbacks handed to getStickerSet, held until they answer. Strong refs on
# purpose: everything here that outlives the call has to be owned on the python
# side (a weakref would point at the chaquopy wrapper, which dies as soon as the
# caller's local goes out of scope even though the java object is alive).
_inflight = []

# Fallback route only: [view, pack, index, size_dp] waiting for
# diceStickersDidLoad, served by the single global observer below.
_pending = []
_global_obs = None


def _account() -> int:
    try:
        from org.telegram.messenger import UserConfig
        return int(UserConfig.selectedAccount)
    except Exception:
        return 0


def _parse(icon_str):
    try:
        if not icon_str or "/" not in icon_str:
            return None, 0
        pack, idx = icon_str.split("/", 1)
        return pack, int(idx)
    except Exception:
        return None, 0


def _tag(pack, idx) -> str:
    return f"packit_sticker_{pack}_{idx}"


def _tag_matches(view, want) -> bool:
    # the host guards setPlaceholderImageByIndex the same way, so a late answer
    # for a view that has since been rebound is ignored instead of overwriting it
    try:
        tag = view.getTag()
    except Exception:
        return True
    return tag is None or str(tag) == want


def _resolve_set(mdc, pack):
    ss = None
    try:
        ss = mdc.getStickerSetByName(pack)
    except Exception:
        pass
    if not ss:
        try:
            ss = mdc.getStickerSetByEmojiOrName(pack)
        except Exception:
            pass
    return ss


def _set_placeholder(view, size_dp):
    try:
        import ctypes
        from org.telegram.messenger import AndroidUtilities
        from org.telegram.ui.ActionBar import Theme
        from android.graphics.drawable import GradientDrawable
        color = Theme.getColor(Theme.key_emptyListPlaceholder)
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        block = GradientDrawable()
        block.setShape(GradientDrawable.RECTANGLE)
        block.setCornerRadius(float(AndroidUtilities.dp(max(4, int(size_dp) // 6))))
        block.setColor(ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value)
        view.setBackground(block)
    except Exception as e:
        logx(f"stickers: placeholder error: {e}", False)


def _clear_placeholder(view):
    try:
        view.setBackground(None)
    except Exception:
        pass


def _bind(view, ss, idx, size_dp) -> bool:
    # binds document #idx of an already resolved set
    if ss is None:
        return False
    try:
        docs = getattr(ss, "documents", None)
        if docs is None or idx < 0 or docs.size() <= idx:
            return False
        doc = docs.get(idx)
        if doc is None:
            return False
    except Exception:
        return False

    from org.telegram.messenger import ImageLocation, DocumentObject
    from org.telegram.ui.ActionBar import Theme
    from java import jfloat
    svg = None
    try:
        svg = DocumentObject.getSvgThumb(doc, Theme.key_emptyListPlaceholder, jfloat(0.2))
        if svg is not None:
            svg.overrideWidthAndHeight(512, 512)
    except Exception:
        svg = None
    view.setImage(
        ImageLocation.getForDocument(doc),
        f"{size_dp}_{size_dp}",
        "tgs", svg, ss,
    )
    # from here the image receiver owns the visuals (svg thumb first, sticker
    # once downloaded), so our stand-in has to go
    _clear_placeholder(view)
    return True


def _apply_now(view, pack, idx, size_dp) -> bool:
    # binds the sticker if its set is already in memory; returns True on success
    from org.telegram.messenger import MediaDataController
    mdc = MediaDataController.getInstance(_account())
    return _bind(view, _resolve_set(mdc, pack), idx, size_dp)


def _request_set(view, pack, idx, size_dp) -> bool:
    # the host's own plugin-icon route: one callback per view, answered from
    # memory, from the cache or from the network. Returns False if the route is
    # unavailable, so the caller can fall back to the notification one.
    try:
        from elyxcore import gen
        from android_utils import run_on_ui_thread
        from org.telegram.messenger import MediaDataController, Utilities
        from hook_utils import find_class

        ShortName = find_class("org.telegram.tgnet.TLRPC$TL_inputStickerSetShortName")
        if ShortName is None:
            return False

        want = _tag(pack, idx)
        holder = {}

        def _on_loaded(ss):
            try:
                _inflight.remove(holder.get("cb"))
            except Exception:
                pass

            def _apply():
                try:
                    if not _tag_matches(view, want):
                        return
                    if not _bind(view, ss, idx, size_dp):
                        logx(f"stickers: '{pack}/{idx}' unresolved (set missing or too short)", False)
                except Exception as e:
                    logx(f"stickers: bind error for '{pack}/{idx}': {e}", False)

            run_on_ui_thread(_apply)

        cb = gen(Utilities.Callback, "run")(_on_loaded)
        holder["cb"] = cb
        _inflight.append(cb)
        if len(_inflight) > _CAP:
            del _inflight[:len(_inflight) - _CAP]

        inp = ShortName()
        inp.short_name = pack
        mdc = MediaDataController.getInstance(_account())
        try:
            mdc.getStickerSet(inp, 0, False, cb)
        except TypeError:
            from java.lang import Integer as JInteger
            mdc.getStickerSet(inp, JInteger(0), False, cb)
        return True
    except Exception as e:
        logx(f"stickers: getStickerSet route unavailable ({e}), using notifications", False)
        return False


def _flush(name):
    # fallback route: bind every pending view whose set just loaded
    survivors = []
    for entry in _pending:
        view, pack, idx, size_dp = entry
        if name is not None and pack != name:
            survivors.append(entry)
            continue
        try:
            if not _bind(view, _resolve_set(_mdc(), pack), idx, size_dp):
                survivors.append(entry)
        except Exception as e:
            logx(f"stickers: flush apply error: {e}", False)
    bound = len(_pending) - len(survivors)
    _pending[:] = survivors
    if bound:
        logx(f"stickers: bound {bound} pending view(s) for '{name}'", True)


def _mdc():
    from org.telegram.messenger import MediaDataController
    return MediaDataController.getInstance(_account())


def _ensure_observer():
    global _global_obs
    if _global_obs is not None:
        return
    try:
        from hook_utils import find_class
        from org.telegram.messenger import NotificationCenter
        from java import dynamic_proxy
        from android_utils import run_on_ui_thread
        Delegate = find_class("org.telegram.messenger.NotificationCenter$NotificationCenterDelegate")

        class _Obs(dynamic_proxy(Delegate)):
            def didReceivedNotification(self, id, acc, *args):
                try:
                    if id != NotificationCenter.diceStickersDidLoad:
                        return
                    name = str(args[0]) if args else None
                    run_on_ui_thread(lambda: _flush(name))
                except Exception as e:
                    logx(f"stickers: observer error: {e}", False)

        obs = _Obs()
        NotificationCenter.getInstance(_account()).addObserver(obs, NotificationCenter.diceStickersDidLoad)
        _global_obs = obs
    except Exception as e:
        logx(f"stickers: addObserver failed: {e}", False)


def _load_via_notification(view, pack, idx, size_dp):
    try:
        _mdc().loadStickersByEmojiOrName(pack, False, True)
    except Exception as e:
        logx(f"stickers: loadStickersByEmojiOrName error: {e}", False)
    _pending.append([view, pack, idx, size_dp])
    if len(_pending) > _CAP:
        del _pending[:len(_pending) - _CAP]
    _ensure_observer()


def load_sticker(view, icon_str, size_dp=130):
    # binds "pack/index" into `view` (a BackupImageView), loading the set if it
    # is not in memory yet — no polling, no fixed delays.
    try:
        pack, idx = _parse(icon_str)
        if not pack:
            return
        try:
            view.setTag(_tag(pack, idx))
        except Exception:
            pass
        if _apply_now(view, pack, idx, size_dp):
            return
        # set isn't loaded: show a stand-in and ask for it
        _set_placeholder(view, size_dp)
        if _request_set(view, pack, idx, size_dp):
            return
        _load_via_notification(view, pack, idx, size_dp)
    except Exception as e:
        logx(f"stickers: load_sticker error: {e}", False)


def make_sticker_view(context, icon_str, size_dp=130, round_radius_dp=0):
    # convenience: build a BackupImageView already bound to the sticker
    from org.telegram.ui.Components import BackupImageView
    from org.telegram.messenger import AndroidUtilities
    view = BackupImageView(context)
    if round_radius_dp:
        try:
            view.setRoundRadius(AndroidUtilities.dp(round_radius_dp))
        except Exception:
            pass
    load_sticker(view, icon_str, size_dp)
    return view

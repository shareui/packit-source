# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Central sticker loader for the whole plugin.
#
# All sites call load_sticker(view, "pack/index", size_dp).
#
# Resolving the set copies what the host itself does for a plugin icon —
# PluginCell -> MediaDataController.setPlaceholderImageByIndex ->
# getStickerSet(TL_inputStickerSetShortName, 0, false, callback) — but that
# callback is not something to rely on alone: it belongs to one request, the
# host dedups concurrent requests for the same set internally, and a set can
# still land in memory through a route that never answers us (another screen
# asking for the same pack, the sqlite copy, the "did load" notification). That
# is why the icons only appeared after leaving and reopening the screen: the set
# was there, nothing woke the views up.
#
# So the flow here is: one request per pack (not per view), every view waiting
# for that pack fanned out from a single place, and three independent things
# able to complete it —
#   * the getStickerSet callback,
#   * NotificationCenter (diceStickersDidLoad / stickersDidLoad /
#     groupStickersDidLoad),
#   * a short backoff of main-thread re-checks (a map lookup, no network) that
#     stops the moment everything is bound and re-issues the request through the
#     other route a couple of times before giving up.
# Whichever fires first binds the views; the rest find nothing left to do.
#
# Binding copies org.telegram.ui.Components.StickerImageView:
# setImage(location, filter, "tgs", svgThumb, set) — the "tgs" ext makes
# animated stickers actually animate, the svg thumb stands in while the media
# downloads, and passing the set as parentObject lets the image receiver
# resolve the document. Until the set itself arrives there is no document and
# therefore no thumb, so a neutral block stands in underneath — the same idea
# as the placeholder a chat sticker shows while its media downloads.
#
# A view carries a "packit_sticker_<pack>_<index>" tag and an answer whose tag
# no longer matches is dropped, so a recycled row cannot end up showing the
# previous row's icon — the same guard the host uses.

from packutil import logx

# per pack: how many views may wait at once (the export sheet lists every
# installed plugin, so this is a real number, not a formality)
_CAP = 256

# delays, in ms after the request went out, at which the pending views for a
# pack are re-checked against what the host has in memory
_RECHECK_MS = (120, 300, 600, 1000, 1600, 2500, 4000, 6000, 9000, 13000, 20000, 30000)
# re-issue the request at these tick numbers (1-based), alternating routes
_RETRY_TICKS = {4: "byName", 8: "callback"}

# pack key (lowercased short name) -> _Pack
_packs = {}

# java objects handed to the host (callbacks, runnables) kept alive until they
# answer. Strong refs on purpose: a weakref would point at the chaquopy wrapper,
# which dies as soon as our local goes out of scope even though the java object
# is alive — that is what left the first-visit binds stranded.
_alive = []
_ALIVE_CAP = 512

_obs = None
_RunnableCls = None


class _Pack:
    __slots__ = ("key", "name", "waiters", "tick", "running")

    def __init__(self, key, name):
        self.key = key
        self.name = name
        # each waiter is [view, index, size_dp, tag, was_on_screen]
        self.waiters = []
        self.tick = 0
        self.running = False


def _account() -> int:
    try:
        from org.telegram.messenger import UserConfig
        return int(UserConfig.selectedAccount)
    except Exception:
        return 0


def _mdc():
    from org.telegram.messenger import MediaDataController
    return MediaDataController.getInstance(_account())


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
    try:
        tag = view.getTag()
    except Exception:
        return True
    return tag is None or str(tag) == want


def _same_view(a, b) -> bool:
    if a is b:
        return True
    try:
        return bool(a.equals(b))
    except Exception:
        return False


def _hold(obj):
    if obj is None:
        return
    _alive.append(obj)
    if len(_alive) > _ALIVE_CAP:
        del _alive[:len(_alive) - _ALIVE_CAP]


def _release(obj):
    if obj is None:
        return
    for i, held in enumerate(_alive):
        if held is obj:
            del _alive[i]
            return


def _post(fn, delay_ms=0):
    # runs fn on the UI thread after delay_ms. Everything that touches
    # MediaDataController or a view goes through here.
    global _RunnableCls
    try:
        from org.telegram.messenger import AndroidUtilities
        if _RunnableCls is None:
            from java import dynamic_proxy
            from hook_utils import find_class

            class _R(dynamic_proxy(find_class("java.lang.Runnable"))):
                def __init__(self, func):
                    super().__init__()
                    self._func = func

                def run(self):
                    try:
                        self._func()
                    except Exception as e:
                        logx(f"stickers: posted task error: {e}", False)
                    finally:
                        _release(self)

            _RunnableCls = _R
        r = _RunnableCls(fn)
        _hold(r)
        AndroidUtilities.runOnUIThread(r, int(delay_ms))
    except Exception as e:
        logx(f"stickers: post error: {e}", False)
        try:
            from android_utils import run_on_ui_thread
            run_on_ui_thread(fn)
        except Exception:
            pass


def _resolve_set(pack):
    # whatever the host already has for this short name, or None
    try:
        mdc = _mdc()
    except Exception as e:
        logx(f"stickers: MediaDataController unavailable: {e}", False)
        return None
    for name in (pack, pack.lower()):
        for getter in ("getStickerSetByName", "getStickerSetByEmojiOrName"):
            try:
                ss = getattr(mdc, getter)(name)
            except Exception:
                continue
            if ss:
                return ss
    return None


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
    try:
        view.invalidate()
    except Exception:
        pass
    return True


def _flush(st, ss=None) -> int:
    # binds every view waiting for this pack. Once the set is in hand each
    # waiter is decided — bound, stale (the view was rebound meanwhile) or
    # impossible (index past the end) — so none of them stays in the list.
    if not st.waiters:
        return 0
    if ss is None:
        ss = _resolve_set(st.name)
    if ss is None:
        return 0
    waiters, st.waiters = st.waiters, []
    bound = 0
    for view, idx, size_dp, want, _seen in waiters:
        try:
            if not _tag_matches(view, want):
                continue
            if _bind(view, ss, idx, size_dp):
                bound += 1
            else:
                logx(f"stickers: '{st.name}/{idx}' unresolved (set empty or too short)", False)
        except Exception as e:
            logx(f"stickers: bind error for '{st.name}/{idx}': {e}", False)
    if bound:
        logx(f"stickers: bound {bound} pending view(s) for '{st.name}'", True)
    return bound


def _flush_all():
    for key in list(_packs.keys()):
        st = _packs.get(key)
        if st is not None and st.waiters:
            try:
                _flush(st)
            except Exception as e:
                logx(f"stickers: flush error for '{st.name}': {e}", False)


def _request_via_callback(st) -> bool:
    # the host's own plugin-icon route. Returns False if it is unavailable, so
    # the caller can fall back to the name route.
    holder = {}
    try:
        from elyxcore import gen
        from org.telegram.messenger import MediaDataController, Utilities
        from hook_utils import find_class

        ShortName = find_class("org.telegram.tgnet.TLRPC$TL_inputStickerSetShortName")
        if ShortName is None:
            return False

        def _on_loaded(ss=None):
            _release(holder.get("cb"))
            # the answer can arrive on any thread, and "not found" answers with
            # null — re-resolving from memory then costs one map lookup
            _post(lambda: _flush(st, ss))

        cb = gen(Utilities.Callback, "run")(_on_loaded)
        holder["cb"] = cb
        _hold(cb)

        inp = ShortName()
        inp.short_name = st.name
        mdc = MediaDataController.getInstance(_account())
        try:
            mdc.getStickerSet(inp, 0, False, cb)
        except TypeError:
            from java.lang import Integer as JInteger
            mdc.getStickerSet(inp, JInteger(0), False, cb)
        return True
    except Exception as e:
        _release(holder.get("cb"))
        logx(f"stickers: getStickerSet route unavailable for '{st.name}' ({e})", False)
        return False


def _request_by_name(st) -> bool:
    try:
        _mdc().loadStickersByEmojiOrName(st.name, False, True)
        return True
    except Exception as e:
        logx(f"stickers: loadStickersByEmojiOrName error for '{st.name}': {e}", False)
        return False


def _request(st, route):
    if route == "callback":
        if _request_via_callback(st):
            return
        _request_by_name(st)
        return
    if not _request_by_name(st):
        _request_via_callback(st)


def _schedule(st):
    i = st.tick
    if i >= len(_RECHECK_MS):
        left = len(st.waiters)
        st.waiters = []
        st.running = False
        _packs.pop(st.key, None)
        if left:
            logx(f"stickers: '{st.name}' never resolved, {left} view(s) left unbound", False)
        return
    st.tick += 1
    _post(lambda: _tick(st), _RECHECK_MS[i])


def _prune(st):
    # a screen can be closed while its set is still on the way. Views are held
    # strongly, so let go of the ones that were on screen and are not any more
    # (a view built ahead of time and never attached yet is kept).
    survivors = []
    for w in st.waiters:
        try:
            if w[0].isAttachedToWindow():
                w[4] = True
                survivors.append(w)
                continue
            if not w[4]:
                survivors.append(w)
        except Exception:
            survivors.append(w)
    dropped = len(st.waiters) - len(survivors)
    if dropped:
        st.waiters = survivors
    return dropped


def _tick(st):
    try:
        _flush(st)
        _prune(st)
        if not st.waiters:
            st.running = False
            st.tick = 0
            _packs.pop(st.key, None)
            return
        route = _RETRY_TICKS.get(st.tick)
        if route:
            _request(st, route)
        _schedule(st)
    except Exception as e:
        logx(f"stickers: tick error for '{st.name}': {e}", False)
        st.running = False


def _enqueue(view, pack, idx, size_dp, want):
    key = pack.lower()
    st = _packs.get(key)
    if st is None:
        st = _Pack(key, pack)
        _packs[key] = st
    # a view can only wait for one sticker at a time (recycled rows rebind)
    st.waiters = [w for w in st.waiters if not _same_view(w[0], view)]
    st.waiters.append([view, idx, size_dp, want, False])
    if len(st.waiters) > _CAP:
        del st.waiters[:len(st.waiters) - _CAP]
    _ensure_observer()
    if not st.running:
        st.running = True
        st.tick = 0
        # one request per pack, however many views are waiting for it
        _request(st, "callback")
        _schedule(st)


def _ensure_observer():
    global _obs
    if _obs is not None:
        return
    try:
        from hook_utils import find_class
        from org.telegram.messenger import NotificationCenter
        from java import dynamic_proxy
        Delegate = find_class("org.telegram.messenger.NotificationCenter$NotificationCenterDelegate")

        class _Obs(dynamic_proxy(Delegate)):
            def didReceivedNotification(self, id, acc, *args):
                try:
                    _post(_flush_all)
                except Exception as e:
                    logx(f"stickers: observer error: {e}", False)

        obs = _Obs()
        nc = NotificationCenter.getInstance(_account())
        wired = 0
        for name in ("diceStickersDidLoad", "stickersDidLoad", "groupStickersDidLoad"):
            try:
                nc.addObserver(obs, getattr(NotificationCenter, name))
                wired += 1
            except Exception:
                pass
        if wired:
            _obs = obs
    except Exception as e:
        logx(f"stickers: addObserver failed: {e}", False)


def load_sticker(view, icon_str, size_dp=130):
    # binds "pack/index" into `view` (a BackupImageView), loading the set if it
    # is not in memory yet. Must be called on the UI thread.
    try:
        pack, idx = _parse(icon_str)
        if not pack:
            return
        want = _tag(pack, idx)
        try:
            view.setTag(want)
        except Exception:
            pass
        if _bind(view, _resolve_set(pack), idx, size_dp):
            return
        # set isn't loaded: show a stand-in and get in line for it
        _set_placeholder(view, size_dp)
        _enqueue(view, pack, idx, size_dp, want)
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

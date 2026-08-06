# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Central sticker loader for the whole plugin.
#
# Mirrors org.telegram.ui.Components.StickerImageView (the host's own widget for
# "show sticker N from pack <name>"):
#   * resolve the set: getStickerSetByName -> getStickerSetByEmojiOrName
#   * setImage(location, filter, "tgs", svgThumb, set) — the "tgs" ext makes
#     animated stickers actually animate, the SVG thumb is a placeholder while
#     the media downloads, and passing the set as parentObject lets the image
#     receiver resolve the document
#   * when the set is not cached yet: fire loadStickersByEmojiOrName and wait
#     for NotificationCenter.diceStickersDidLoad, then bind — instead of the old
#     per-site polling with time.sleep()/postDelayed, which showed the sticker
#     late (fixed delay) or never (a single retry that raced the download).
#
# A single global diceStickersDidLoad observer serves every pending view; views
# are held weakly, so nothing leaks and dead views drop themselves on the next
# event. All sites call load_sticker(view, "pack/index", size_dp).

from packutil import logx
import weakref

# pending binds waiting for their set to load: each is
# (weakref(view), pack, index, size_dp). Served by the single global observer.
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


def _apply_now(view, pack, idx, size_dp) -> bool:
    # binds the sticker if its set is cached; returns True on success
    from org.telegram.messenger import MediaDataController, ImageLocation, DocumentObject
    from org.telegram.ui.ActionBar import Theme
    from java import jfloat
    mdc = MediaDataController.getInstance(_account())
    ss = _resolve_set(mdc, pack)
    if ss is None or getattr(ss, "documents", None) is None or ss.documents.size() <= idx:
        return False
    doc = ss.documents.get(idx)
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
    return True


def _flush(name):
    # re-bind every pending view whose set just loaded; prune bound/dead ones
    survivors = []
    for ref, pack, idx, size_dp in _pending:
        view = ref()
        if view is None:
            continue  # view gone -> drop
        if name is not None and pack != name:
            survivors.append((ref, pack, idx, size_dp))
            continue
        try:
            if not _apply_now(view, pack, idx, size_dp):
                survivors.append((ref, pack, idx, size_dp))
        except Exception as e:
            logx(f"stickers: flush apply error: {e}", False)
    _pending[:] = survivors


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


def load_sticker(view, icon_str, size_dp=130):
    # binds "pack/index" into `view` (a BackupImageView). If the set is not
    # cached, triggers the load and binds on diceStickersDidLoad — no polling.
    try:
        pack, idx = _parse(icon_str)
        if not pack:
            return
        if _apply_now(view, pack, idx, size_dp):
            return
        try:
            from org.telegram.messenger import MediaDataController
            MediaDataController.getInstance(_account()).loadStickersByEmojiOrName(pack, False, True)
        except Exception as e:
            logx(f"stickers: loadStickersByEmojiOrName error: {e}", False)
        _pending.append((weakref.ref(view), pack, idx, size_dp))
        _ensure_observer()
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

# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Shared worker pool and decoder for remote images.
#
# One thread per image starves the CPU and the network the moment a screen
# opens a dozen of them at once — the icon catalog learned that the hard way and
# grew a small fixed pool. Repository icons need exactly the same thing, so the
# pool and the decode step live here instead of being copied a second time.

from packutil import logx
import threading

_WORKERS = 4
_queue = None
_queue_lock = threading.Lock()


def submit(task):
    # runs task() on one of the pool threads; tasks are served in order
    global _queue
    with _queue_lock:
        if _queue is None:
            import queue
            _queue = queue.Queue()

            def _worker():
                while True:
                    fn = _queue.get()
                    try:
                        fn()
                    except Exception as e:
                        logx(f"imagePool: worker error: {e}", True)
                    finally:
                        _queue.task_done()

            for _ in range(_WORKERS):
                threading.Thread(target=_worker, daemon=True).start()
    _queue.put(task)


def fetch(url: str, timeout: int = 15):
    # downloads the bytes of an image, or None
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"
        })
        if r.status_code != 200:
            logx(f"imagePool: HTTP {r.status_code} for {url}", True)
            return None
        return r.content
    except Exception as e:
        logx(f"imagePool: fetch error for {url}: {e}", False)
        return None


def decode(data, px: int, is_svg: bool = False):
    # bytes -> Bitmap scaled for a px-sized slot, or None
    if not data:
        return None
    from hook_utils import find_class
    try:
        if is_svg:
            SVG = find_class("com.caverock.androidsvg.SVG")
            ByteArrayInputStream = find_class("java.io.ByteArrayInputStream")
            Bitmap = find_class("android.graphics.Bitmap")
            Canvas = find_class("android.graphics.Canvas")
            svg = SVG.getFromInputStream(ByteArrayInputStream(data))
            # force the render size; the viewBox scales to it
            svg.setDocumentWidth(px)
            svg.setDocumentHeight(px)
            bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888)
            svg.renderToCanvas(Canvas(bmp))
            return bmp

        BitmapFactory = find_class("android.graphics.BitmapFactory")
        opts = BitmapFactory.Options()
        opts.inJustDecodeBounds = True
        BitmapFactory.decodeByteArray(data, 0, len(data), opts)
        if opts.outWidth > 0 and opts.outHeight > 0 and px > 0:
            opts.inSampleSize = max(1, min(opts.outWidth // px, opts.outHeight // px))
        opts.inJustDecodeBounds = False
        return BitmapFactory.decodeByteArray(data, 0, len(data), opts)
    except Exception as e:
        logx(f"imagePool: decode error: {e}", False)
        return None


def looks_like_svg(url: str, data=None) -> bool:
    try:
        if str(url).lower().split("?", 1)[0].endswith(".svg"):
            return True
        if data:
            head = bytes(data[:256]).lstrip()
            return head.startswith(b"<svg") or head.startswith(b"<?xml")
    except Exception:
        pass
    return False

# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# PackIt's own executors for network I/O. Historically these tasks went
# through client_utils.run_on_queue — the HOST's plugins DispatchQueue, the
# same one PluginsController uses to open any plugin settings screen. One
# slow fetch (github raw timing out at 10-20s) stalled that queue and froze
# every PackIt entry point until the timeout fired.
#
# run_io: small pool for independent fetches (catalogs, widgets, update
# checks) — parallel, unordered.
# run_serial_io: single lane for RepositoryManager tasks, preserving their
# previous relative ordering (they read/write the repo cache files).

import threading

from packutil import logx

_IO_WORKERS = 3

_io_queue = None
_serial_queue = None
_lock = threading.Lock()


def _start_workers(q, count, name):
    def _worker():
        while True:
            fn = q.get()
            try:
                fn()
            except Exception as e:
                logx(f"netQueue: {name} task error: {e}", False)
            finally:
                q.task_done()

    for _ in range(count):
        threading.Thread(target=_worker, daemon=True).start()


def run_io(task):
    global _io_queue
    with _lock:
        if _io_queue is None:
            import queue
            _io_queue = queue.Queue()
            _start_workers(_io_queue, _IO_WORKERS, "io")
    _io_queue.put(task)


def run_serial_io(task):
    global _serial_queue
    with _lock:
        if _serial_queue is None:
            import queue
            _serial_queue = queue.Queue()
            _start_workers(_serial_queue, 1, "serial")
    _serial_queue.put(task)

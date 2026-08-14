# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.bulletin import BulletinHelper  
from client_utils import get_last_fragment  

import threading
import time
import os
import signal
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()

def kill_process():
    time.sleep(1)
    pid = os.getpid()
    logx(f"Killing process {pid}", True)
    os.kill(pid, signal.SIGKILL)

def handle(url):  
    if url == "tg://packit?pkill":  
        try:  
            currentFragment = get_last_fragment()
            BulletinHelper.show_success(strings.pkill, currentFragment)
            
            thread = threading.Thread(target=kill_process)
            thread.daemon = True
            thread.start()
            
        except Exception as e:  
            logx(f"Pkill error: {e}", False)
            try:
                currentFragment = get_last_fragment()
                BulletinHelper.show_error(f"Pkill failed: {e}", currentFragment)
            except:
                pass
from ui.bulletin import BulletinHelper  
from client_utils import get_last_fragment  
from android_utils import log
import threading
import time
import os
import signal
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

def kill_process():
    time.sleep(1)
    pid = os.getpid()
    log(f"Killing process {pid}")
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
            log(f"Pkill error: {e}")
            try:
                currentFragment = get_last_fragment()
                BulletinHelper.show_error(f"Pkill failed: {e}", currentFragment)
            except:
                pass
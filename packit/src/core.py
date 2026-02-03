import requests
from android_utils import log, run_on_ui_thread
from client_utils import run_on_queue
from ui.bulletin import BulletinHelper
from java.io import File, FileOutputStream
from org.telegram.messenger import ApplicationLoader
from com.exteragram.messenger.plugins import PluginsController
from org.telegram.messenger import NotificationCenter
import time
import os
import signal


class PackItCore:
    def __init__(self, repoManager):
        self.repoManager = repoManager

    def _showErrorOnUi(self, text: str):
        def show():
            BulletinHelper.show_error(text)
        run_on_ui_thread(show)

    def _showSuccessOnUi(self, text: str):
        def show():
            BulletinHelper.show_success(text)
        run_on_ui_thread(show)

    def _killApp(self):
        try:
            pid = os.getpid()
            log(f"killing app with pid: {pid}")
            os.kill(pid, signal.SIGKILL)
        except Exception as e:
            log(f"failed to kill app: {e}")

    def getRepometaText(self):
        repos = self.repoManager.getRepositories()
        lines = []

        for repo in repos:
            if not repo.get("enabled"):
                continue
            
            repo_name = repo.get("name", "Unknown")
            repo_url = repo.get("url", "Unknown")
            
            lines.append(f"{repo_name}")
            lines.append(f"URL: {repo_url}")
            lines.append("")
        
        if lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines) if lines else "No repositories found"
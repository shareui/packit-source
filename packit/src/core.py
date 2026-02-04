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

from android_utils import log
from base_plugin import BasePlugin

class zalupa(BasePlugin):
    def on_plugin_load(self):
        log(f"{__name__} loaded")
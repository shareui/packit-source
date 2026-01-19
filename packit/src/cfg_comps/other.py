from ui.settings import Header, Selector
from elyx import strings, settings


class OtherSettings:
    def __init__(self):
        pass
    
    def build(self):
        return [
            Header(text=strings.other_settings),
            Selector(
                key="auto_update_interval",
                text="Auto-update",
                default=0,
                items=["Never", "30m", "1h", "4h", "8h", "12h", "24h"],
                icon="msg_retry"
            )
        ]
from ui.settings import Header, Switch
from elyx import strings, settings


class OtherSettings:
    def __init__(self):
        pass
    
    def build(self):
        return [
            Header(text=strings.other_settings),
            Switch(
                key="auto_update_on_start",
                text="Auto-update",
                subtext="Update repos when starting app",
                default=False,
                icon="msg_retry"
            )
        ]
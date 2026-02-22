from ui.settings import Header, Text, Divider
from elyx import strings


class DeepLinksSettings:
    def __init__(self):
        pass

    def notReady(self, view):
        # placeholder for feature not yet implemented
        pass

    def build(self):
        return [
            Header(text=strings.get("deeplinks_header", "Внутренние ссылки")),
            Text(
                text="Not ready",
                icon="msg_link",
                on_click=self.notReady
            ),
            Divider(),
        ]

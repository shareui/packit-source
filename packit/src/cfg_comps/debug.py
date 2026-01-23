from ui.settings import Header, Text
from elyx import strings, metainfo
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log


class DebugSettings:
    def __init__(self, core):
        self.core = core
    
    def _showRepometa(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return
            
            repometaText = self.core.getRepometaText()
            
            builder = AlertDialogBuilder(act)
            builder.set_title("Connected repositories")
            builder.set_message(repometaText)
            builder.set_positive_button("Close", lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"failed to show repometa: {e}")
    
    def build(self):
        version = metainfo.get("version", "unknown")
        
        return [
            Header(text=f"Packit {version} debug menu"),
            Text(
                text="Repometa",
                icon="msg_info",
                on_click=self._showRepometa
            )
        ]
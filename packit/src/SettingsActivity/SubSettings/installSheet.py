from ui.settings import Header, Switch, Divider
from elyx import strings


def build_install_sheet_page():
    return [
        Header(text=strings.install_sheet_header),
        Switch(
            key="install_sheet_links",
            text=strings.install_sheet_links,
            subtext=strings.install_sheet_links_desc,
            default=True,
            icon="msg_link",
            link_alias="install_sheet_links"
        ),
        Switch(
            key="install_sheet_hash",
            text=strings.install_sheet_hash,
            subtext=strings.install_sheet_hash_desc,
            default=True,
            icon="msg_sendfile",
            link_alias="install_sheet_hash"
        ),
        Switch(
            key="install_sheet_signatures",
            text=strings.install_sheet_signatures,
            subtext=strings.install_sheet_signatures_desc,
            default=True,
            icon="msg_policy",
            link_alias="install_sheet_signatures"
        ),
        Divider(),
    ]

# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.settings import Header, Switch
from elyx import strings


def build_file_settings_page(other_settings):
    return [
        Header(text=strings.file_system_settings_header),
        Switch(
            key="highlight_syntax",
            text=strings.highlight_syntax,
            subtext=strings.highlight_syntax_subtext,
            default=True
        ),
        Switch(
            key="hidden_files",
            text=strings.hidden_files,
            subtext=strings.hidden_files_subtext,
            default=False
        ),
    ]
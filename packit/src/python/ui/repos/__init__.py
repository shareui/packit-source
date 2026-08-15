# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Live screens listen here so a repository list changed anywhere else — a
# deeplink adding a source, the startup cache refresh dropping a dead one —
# repaints the open screen. RepositoryManager.setRepositories used to poke
# fragment.rebuildAllItems(), which only ever worked for the settings-list
# screen this one replaces.

_delegates = []


def register(delegate):
    if delegate not in _delegates:
        _delegates.append(delegate)


def unregister(delegate):
    try:
        _delegates.remove(delegate)
    except ValueError:
        pass


def notify_repos_changed():
    if not _delegates:
        return
    from android_utils import run_on_ui_thread
    for delegate in list(_delegates):
        try:
            run_on_ui_thread(delegate.reload)
        except Exception:
            pass


def show_repos_fragment(repoManager):
    # imported lazily: the fragment pulls in a good chunk of the ui package and
    # nothing needs it until the row is actually tapped
    from .Fragment import show_repos_fragment as _show
    return _show(repoManager)

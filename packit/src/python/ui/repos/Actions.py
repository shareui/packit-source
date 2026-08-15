# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Everything the Sources screen can do to a repository.
#
# The behaviour is the one the settings-list screen had — same confirmations,
# same bulletins, same easter eggs — only the entry points moved: per-card
# actions into the card's overflow menu, the bulk ones into the menu behind the
# summary row. The one cleanup: the screen no longer carries its own copy of
# RepositoryManager.updateAllCaches.

from packutil import logx

from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from hook_utils import find_class

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"repos actions: import elyx strings failed: {e}")
try:
    from ui.alert import AlertDialogBuilder
    from ui.bulletin import BulletinHelper
except Exception as e:
    import android_utils as _au; _au.log(f"repos actions: import ui helpers failed: {e}")
try:
    from org.telegram.messenger import R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"repos actions: import R failed: {e}")

from ...utils.Bulletins import factory as _pbf
from ..components.ContextMenu import show_plugin_context_menu
from . import notify_repos_changed


def _bulletin(raw_name: str, text):
    try:
        frag = get_last_fragment()
        container = frag.getParentActivity().getWindow().getDecorView()
        rp = frag.getResourceProvider()
        _pbf(container, rp).createSimpleBulletin(getattr(R_tg.raw, raw_name), str(text)).show()
    except Exception as e:
        logx(f"repos actions: bulletin error: {e}", True)


def open_url(act, url: str):
    if not url:
        return
    try:
        from android.net import Uri
        from org.telegram.messenger.browser import Browser
        Browser.openUrl(act, Uri.parse(url))
    except Exception as e:
        logx(f"repos actions: open_url error: {e}", False)
        try:
            from android.content import Intent
            from android.net import Uri
            act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        except Exception as e2:
            logx(f"repos actions: open_url fallback error: {e2}", False)


def copy_link(repo: dict):
    url = str(repo.get("url") or "").strip()
    try:
        from org.telegram.messenger import AndroidUtilities
        if url and AndroidUtilities.addToClipboard(url):
            _bulletin("voip_invite", strings.repo_link_copied)
            return
    except Exception as e:
        logx(f"repos actions: copy_link error: {e}", False)
    BulletinHelper.show_error(str(strings.failed_to_copy))


def _share_link(repo: dict) -> str:
    # The link goes into a telegram message, so it has to survive that client's
    # url detection: percent-encoding it whole made the message text look like
    # a link but stopped resolving. Only the name is escaped, and only for the
    # characters that would otherwise end or split the query.
    name = str(repo.get("name") or "").strip()
    for ch, esc in (("%", "%25"), ("&", "%26"), ("=", "%3D"), ("#", "%23"), (" ", "%20")):
        name = name.replace(ch, esc)
    url = str(repo.get("url") or "").strip()
    # no icon= any more: it carried an R.drawable name, and the other side now
    # takes the picture from the repomap. Links already sent with one still
    # work — the argument is accepted and ignored.
    return f"tg://packit?repo=add&name={name}&link={url}"


def share_repository(act, repo: dict):
    # the deeplink the other client will resolve back into a repository
    share_url = _share_link(repo)
    try:
        from java import jclass, dynamic_proxy
        frag = get_last_fragment()
        if not frag or not act:
            return
        ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
        ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")

        class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
            def __init__(self):
                super().__init__()

            def didShare(self):
                # the link went to a chat — saying it is in the clipboard, which
                # is what this reported before, describes the other button
                run_on_ui_thread(lambda: _bulletin("voip_invite", strings.repo_link_shared))

            def didCopy(self):
                # false: ShareAlert copies and reports it itself
                return False

        alert = ShareAlert(act, None, share_url, True, share_url, False)
        alert.setDelegate(ShareDelegate())
        frag.showDialog(alert)
    except Exception as e:
        logx(f"repos actions: share error: {e}", False)
        BulletinHelper.show_error(str(strings.failed_to_copy))


def delete_repository(act, delegate, repo: dict):
    try:
        builder = AlertDialogBuilder(act)
        builder.set_title(str(strings.delete_repository_title))
        builder.set_message(str(strings.delete_repository_message))

        def on_yes(b, w):
            idx, _ = delegate._index_of(repo)
            if idx < 0:
                delegate.reload()
                return
            delegate.repoManager.removeRepository(idx)
            delegate.reload()

        builder.set_positive_button(str(strings.delete_button), on_yes)
        builder.set_negative_button(str(strings.close_button), lambda b, w: b.dismiss())
        try:
            builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
        except Exception as e:
            logx(f"repos actions: red button error: {e}", True)
        builder.show()
    except Exception as e:
        logx(f"repos actions: delete error: {e}", False)


def refresh_all(delegate):
    _bulletin("shared_link_enter", strings.repos_updating)

    def _done():
        run_on_ui_thread(lambda: (_bulletin("shared_link_enter", strings.update_repos_success),
                                  delegate.reload()))

    try:
        delegate.repoManager.updateAllCaches(on_complete=_done)
    except Exception as e:
        logx(f"repos actions: refresh_all error: {e}", False)


def export_repositories(act, delegate):
    repos = delegate.repoManager.getRepositories()
    links = []
    for repo in repos:
        if not str(repo.get("url") or "").strip():
            continue
        links.append(_share_link(repo))
    if not links:
        BulletinHelper.show_error(str(strings.no_repositories_to_export))
        return
    text = "\n\n".join(links)
    try:
        from org.telegram.messenger import AndroidUtilities
        if AndroidUtilities.addToClipboard(text):
            _bulletin("voip_invite", strings.repositories_exported)
            return
    except Exception as e:
        logx(f"repos actions: export error: {e}", False)
    BulletinHelper.show_error(str(strings.failed_to_copy))


def toggle_all(delegate):
    repos = delegate.repoManager.getRepositories()
    if not repos:
        return
    target = not any(r.get("enabled", True) for r in repos)
    for repo in repos:
        repo["enabled"] = target
    delegate.repoManager.setRepositories(repos)
    delegate.reload()


def restore_default(delegate):
    repos = delegate.repoManager.getRepositories()
    if len(repos) >= 10:
        BulletinHelper.show_error(str(strings.max_repositories_allowed))
        return

    def _done(restored):
        def _ui():
            if restored:
                BulletinHelper.show_success(str(strings.default_repo_restored))
            else:
                BulletinHelper.show_info(str(strings.repo_default_already))
            delegate.reload()
        run_on_ui_thread(_ui)

    delegate.repoManager.restoreDefaultRepository(on_done=_done)


def _easter_egg(act, message):
    try:
        builder = AlertDialogBuilder(act)
        builder.set_title(str(strings.easter_egg_title))
        builder.set_message(str(message))
        builder.set_positive_button(str(strings.close_button), lambda b, w: b.dismiss())
        builder.show()
    except Exception as e:
        logx(f"repos actions: easter egg error: {e}", False)


def clear_all_except_first(act, delegate):
    repos = delegate.repoManager.getRepositories()
    if len(repos) <= 1:
        _easter_egg(act, strings.easter_egg_clear_message)
        return
    try:
        builder = AlertDialogBuilder(act)
        builder.set_title(str(strings.clear_all_title))
        builder.set_message(str(strings.clear_all_message))

        def on_yes(b, w):
            delegate.repoManager.clearAllExceptFirst()
            _bulletin("group_pip_delete_icon", strings.repositories_cleared)
            delegate.reload()

        builder.set_positive_button(str(strings.clear_button), on_yes)
        builder.set_negative_button(str(strings.close_button), lambda b, w: b.dismiss())
        try:
            builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
        except Exception:
            pass
        builder.show()
    except Exception as e:
        logx(f"repos actions: clear all error: {e}", False)


def reset_repositories(act, delegate):
    repos = delegate.repoManager.getRepositories()
    if len(repos) <= 1:
        _easter_egg(act, strings.easter_egg_reset_message)
        return
    try:
        builder = AlertDialogBuilder(act)
        builder.set_title(str(strings.reset_repositories_title))
        builder.set_message(str(strings.reset_repositories_message))

        def on_yes(b, w):
            delegate.repoManager.resetRepositories()
            _bulletin("group_pip_delete_icon", strings.repositories_reset)
            delegate.reload()

        builder.set_positive_button(str(strings.reset_button), on_yes)
        builder.set_negative_button(str(strings.close_button), lambda b, w: b.dismiss())
        try:
            builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
        except Exception:
            pass
        builder.show()
    except Exception as e:
        logx(f"repos actions: reset error: {e}", False)


def add_repository(act, delegate):
    repos = delegate.repoManager.getRepositories()
    if len(repos) >= 10:
        BulletinHelper.show_error(str(strings.max_repositories_allowed))
        return
    from .AddSheet import show_add_repo_dialog
    show_add_repo_dialog(act, delegate)


def edit_repository(act, delegate, repo: dict):
    from .AddSheet import show_edit_repo_dialog
    show_edit_repo_dialog(act, delegate, repo)


def show_card_menu(act, delegate, repo: dict, anchor):
    repos = delegate.repoManager.getRepositories()
    items = [
        {"icon": "msg_edit", "text": str(strings.repo_edit),
         "action": lambda: edit_repository(act, delegate, repo)},
        {"icon": "msg_copy", "text": str(strings.repo_copy_link),
         "action": lambda: copy_link(repo)},
        {"icon": "msg_share", "text": str(strings.share_repository),
         "action": lambda: share_repository(act, repo)},
        {"icon": "msg_delete", "text": str(strings.remove_repository), "red": True,
         "show": len(repos) > 1,
         "action": lambda: delete_repository(act, delegate, repo)},
    ]
    try:
        show_plugin_context_menu(anchor.getRootView(), anchor, items)
    except Exception as e:
        logx(f"repos actions: card menu error: {e}", False)


def show_bulk_menu(act, delegate, anchor):
    repos = delegate.repoManager.getRepositories()
    any_enabled = any(r.get("enabled", True) for r in repos)
    items = [
        {"icon": "msg_retry", "text": str(strings.update_repositories),
         "action": lambda: refresh_all(delegate)},
        {"icon": "msg_share", "text": str(strings.export_repositories),
         "action": lambda: export_repositories(act, delegate)},
        {"icon": "msg_customize",
         "text": str(strings.disable_all_repositories if any_enabled else strings.enable_all_repositories),
         "action": lambda: toggle_all(delegate)},
        {"icon": "msg_reset", "text": str(strings.restore_default_repository),
         "action": lambda: restore_default(delegate)},
        {"icon": "msg_clear", "text": str(strings.clear_all_except_first), "red": True,
         "action": lambda: clear_all_except_first(act, delegate)},
        {"icon": "msg_delete", "text": str(strings.reset_repositories), "red": True,
         "action": lambda: reset_repositories(act, delegate)},
    ]
    try:
        show_plugin_context_menu(anchor.getRootView(), anchor, items)
    except Exception as e:
        logx(f"repos actions: bulk menu error: {e}", False)

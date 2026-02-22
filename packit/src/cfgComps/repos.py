from ui.settings import Header, Input, Divider, Switch, Text
from elyx import strings, settings
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from .icons import IconSelector
from android_utils import log
from hook_utils import find_class
from org.telegram.messenger import R as R_tg

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


class RepositoriesSettings:
    def __init__(self, repoManager):
        self.repoManager = repoManager
    
    def build(self):
        repos = self.repoManager.getRepositories()

        if not repos:
            self.repoManager.addRepository(isFirst=True)
            repos = self.repoManager.getRepositories()
            try:
                fragment = get_last_fragment()
                if fragment and hasattr(fragment, "rebuildAllItems"):
                    fragment.rebuildAllItems()
            except Exception as e:
                log(f"{e}")
        
        def add_new_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    log("Repository add failed: max limit reached (10)")
                    BulletinHelper.show_error(strings.max_repositories_allowed)
                except Exception as e:
                    log(f"{e}")
                return
            
            for repo in repos:
                if repo.get('isFirst', False):
                    continue
                    
                if not repo.get('name', '').strip() or not repo.get('url', '').strip():
                    log("Repository add failed: previous repository not filled")
                    BulletinHelper.show_error(strings.fill_previous_repository)
                    return
        
            self.repoManager.addRepository(isFirst=False)
        
        def restore_default_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    log("Default repository restore failed: max limit reached (10)")
                    BulletinHelper.show_error(strings.max_repositories_allowed)
                except Exception as e:
                    log(f"{e}")
                return
            
            self.repoManager.restoreDefaultRepository()
            try:
                BulletinHelper.show_success(strings.default_repo_restored)
            except Exception as e:
                log(f"{e}")
        
        def reset_repositories(view):
            repos = self.repoManager.getRepositories()
            if len(repos) <= 1:
                try:
                    frag = get_last_fragment()
                    act = frag.getParentActivity() if frag else None
                    if not act:
                        return
                    
                    builder = AlertDialogBuilder(act)
                    builder.set_title(strings.easter_egg_title)
                    builder.set_message(strings.easter_egg_reset_message)
                    builder.set_positive_button(strings.close_button, lambda b, w: b.dismiss())
                    builder.show()
                except Exception as e:
                    log(f"{e}")
                return
            
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return
                
                builder = AlertDialogBuilder(act)
                builder.set_title(strings.reset_repositories_title)
                builder.set_message(strings.reset_repositories_message)
                
                def on_yes(b, w):
                    self.repoManager.resetRepositories()
                    try:
                        frag = get_last_fragment()
                        container = frag.getParentActivity().getWindow().getDecorView()
                        resourceProvider = frag.getResourceProvider()
                        BulletinFactory.of(container, resourceProvider).createSimpleBulletin(R_tg.raw.group_pip_delete_icon, strings.repositories_reset).show()
                    except Exception as e:
                        log(f"{e}")
                
                builder.set_positive_button(strings.reset_button, on_yes)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                try:
                    builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                except Exception as e:
                    log(f"{e}")
                builder.show()
            except Exception as e:
                log(f"{e}")
        
        def clear_all_except_first(view):
            repos = self.repoManager.getRepositories()
            if len(repos) <= 1:
                try:
                    frag = get_last_fragment()
                    act = frag.getParentActivity() if frag else None
                    if not act:
                        return
                    
                    builder = AlertDialogBuilder(act)
                    builder.set_title(strings.easter_egg_title)
                    builder.set_message(strings.easter_egg_clear_message)
                    builder.set_positive_button(strings.close_button, lambda b, w: b.dismiss())
                    builder.show()
                except Exception as e:
                    log(f"{e}")
                return
            
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return
                
                builder = AlertDialogBuilder(act)
                builder.set_title(strings.clear_all_title)
                builder.set_message(strings.clear_all_message)
                
                def on_yes(b, w):
                    self.repoManager.clearAllExceptFirst()
                    try:
                        frag = get_last_fragment()
                        container = frag.getParentActivity().getWindow().getDecorView()
                        resourceProvider = frag.getResourceProvider()
                        BulletinFactory.of(container, resourceProvider).createSimpleBulletin(R_tg.raw.utyan_cache, strings.repositories_cleared).show()
                    except Exception as e:
                        log(f"{e}")
                
                builder.set_positive_button(strings.clear_button, on_yes)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                try:
                    builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                except Exception as e:
                    log(f"{e}")
                builder.show()
            except Exception as e:
                log(f"{e}")
        
        def update_repositories(view):
            from client_utils import run_on_queue
            from android_utils import run_on_ui_thread
            import requests
            import json
            import os
            from org.telegram.messenger import ApplicationLoader

            def task():
                try:
                    repos = self.repoManager.getRepositories()
                    pkg = ApplicationLoader.applicationContext.getPackageName()
                    cache_dir = f"/data/data/{pkg}/files/packitCache"
                    os.makedirs(cache_dir, exist_ok=True)
                    changed = False
                    to_remove = []
                    seen_rids = set()

                    for i, repo in enumerate(repos):
                        url = (repo.get("url") or "").strip()
                        if not url:
                            continue
                        try:
                            r = requests.get(url, timeout=10)
                            if r.status_code != 200:
                                log(f"update_repositories: HTTP {r.status_code} for {url}")
                                continue
                            data = r.json()
                            repometa = data.get("repometa")
                            rm_rid = repometa.get("rm_rid") if repometa else None

                            if not repometa or not rm_rid:
                                log(f"update_repositories: no repometa for '{url}', removing repo")
                                to_remove.append(i)
                                changed = True
                                continue

                            if rm_rid in seen_rids:
                                log(f"update_repositories: duplicate rm_rid='{rm_rid}', removing repo")
                                to_remove.append(i)
                                changed = True
                                continue
                            seen_rids.add(rm_rid)

                            if repo.get("id") != rm_rid:
                                repos[i]["id"] = rm_rid
                                changed = True
                                log(f"update_repositories: set id='{rm_rid}' for repo '{repo.get('name')}'")

                            cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
                            with open(cache_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                            log(f"update_repositories: updated cache for '{rm_rid}'")
                        except Exception as e:
                            log(f"update_repositories: error for {url}: {e}")

                    for i in sorted(to_remove, reverse=True):
                        repos.pop(i)

                    if changed:
                        self.repoManager.setRepositories(repos)

                    run_on_ui_thread(lambda: BulletinHelper.show_success(strings.update_repos_success))
                except Exception as e:
                    log(f"update_repositories: task error: {e}")

            run_on_queue(task)

        isActionsCollapsed = settings.get("actions_collapsed", True)
        actionsCollapseIcon = "msg_go_up" if not isActionsCollapsed else "arrow_more_solar"

        def toggle_actions_collapsed(view):
            current = settings.get("actions_collapsed", True)
            settings.set("actions_collapsed", not current, reload_settings=True)

        def export_repositories(view):
            repos = self.repoManager.getRepositories()
            links = []
            for repo in repos:
                name = repo.get('name', '').strip()
                url = repo.get('url', '').strip()
                icon = repo.get('icon', '').strip()
                if not url:
                    continue
                links.append(f"tg://packit?repo=add&name={name}&link={url}&icon={icon}")

            if not links:
                BulletinHelper.show_error(strings.no_repositories_to_export)
                return

            try:
                from org.telegram.messenger import AndroidUtilities
                if AndroidUtilities.addToClipboard("\n\n".join(links)):
                    frag = get_last_fragment()
                    container = frag.getParentActivity().getWindow().getDecorView()
                    resourceProvider = frag.getResourceProvider()
                    BulletinFactory.of(container, resourceProvider).createSimpleBulletin(R_tg.raw.copy, strings.repositories_exported).show()
                else:
                    log("Failed to copy repository export links")
                    BulletinHelper.show_error(strings.failed_to_copy)
            except Exception as e:
                log(f"Export failed: {e}")
                BulletinHelper.show_error(strings.failed_to_copy)

        def toggle_all_repositories(view):
            repos = self.repoManager.getRepositories()
            anyEnabled = any(r.get('enabled', True) for r in repos)
            for repo in repos:
                repo['enabled'] = not anyEnabled
            self.repoManager.setRepositories(repos)

        anyEnabled = any(r.get('enabled', True) for r in repos)
        toggleAllText = strings.disable_all_repositories if anyEnabled else strings.enable_all_repositories

        actionItems = [
            Text(
                text=strings.update_repositories,
                icon="msg_retry",
                on_click=update_repositories,
                link_alias="update_repos"
            ),
            Text(
                text=strings.export_repositories,
                icon="msg_share",
                on_click=export_repositories,
                link_alias="export_repos"
            ),
            Text(
                text=toggleAllText,
                icon="msg_customize",
                on_click=toggle_all_repositories,
                link_alias="toggle_all_repos"
            ),
            Text(
                text=strings.restore_default_repository,
                icon="msg_reset",
                on_click=restore_default_repository,
                link_alias="restore_repo"
            ),
            Text(
                text=strings.clear_all_except_first,
                icon="msg_clear",
                red=True,
                on_click=clear_all_except_first,
                link_alias="clear_all"
            ),
            Text(
                text=strings.reset_repositories,
                icon="msg_delete",
                red=True,
                on_click=reset_repositories,
                link_alias="reset_repo"
            ),
        ]

        settingsList = [
            Header(text=strings.repositories),
            Text(
                text=strings.add_repository,
                icon="msg_add",
                accent=True,
                on_click=add_new_repository,
                link_alias="new_repo"
            ),
            Text(
                text=strings.additional_actions,
                icon=actionsCollapseIcon,
                accent=True,
                on_click=toggle_actions_collapsed
            ),
            *(actionItems if not isActionsCollapsed else []),
            Divider()
        ]
        
        def makeOnChange(field, i):
            return lambda value: self.repoManager.updateRepoField(i, field, value)
        
        def makeOnRemove(i):
            def show_confirm_dialog(view):
                try:
                    frag = get_last_fragment()
                    act = frag.getParentActivity() if frag else None
                    if not act:
                        return
                    
                    builder = AlertDialogBuilder(act)
                    builder.set_title(strings.delete_repository_title)
                    builder.set_message(strings.delete_repository_message)
                    
                    def on_yes(b, w):
                        self.repoManager.removeRepository(i)
                    
                    builder.set_positive_button(strings.delete_button, on_yes)
                    builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                    try:
                        builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                    except Exception as e:
                        log(f"{e}")
                    builder.show()
                except Exception as e:
                    log(f"{e}")
                    self.repoManager.removeRepository(i)
            
            return show_confirm_dialog
        
        def makeOnShare(i):
            def share_repository(view):
                current_repos = self.repoManager.getRepositories()
                if i >= len(current_repos):
                    BulletinHelper.show_error(strings.failed_to_copy)
                    return
                repo = current_repos[i]
                name = repo.get('name', '').strip()
                url = repo.get('url', '').strip()
                icon = repo.get('icon', '').strip()

                share_url = f"tg://packit?repo=add&name={name}&link={url}&icon={icon}"

                try:
                    from org.telegram.messenger import AndroidUtilities
                    if AndroidUtilities.addToClipboard(share_url):
                        BulletinHelper.show_success(strings.repo_link_copied)
                    else:
                        log(f"Failed to copy repository #{i+1} link")
                        BulletinHelper.show_error(strings.failed_to_copy)
                except Exception as e:
                    log(f"Copy failed: {e}")
                    BulletinHelper.show_error(strings.failed_to_copy)
            
            return share_repository
        
        def makeOnToggleCollapse(i):
            def toggle(view):
                repos = self.repoManager.getRepositories()
                if i < len(repos):
                    repos[i]['collapsed'] = not repos[i].get('collapsed', False)
                    self.repoManager.setRepositories(repos)
            return toggle
        
        def makeOnSelectIcon(i):
            def open_icon_selector():
                def on_icon_selected(icon_name):
                    self.repoManager.updateRepoField(i, 'icon', icon_name)
                
                icon_selector = IconSelector(self.repoManager, on_icon_selected)
                settings_list = icon_selector.build()
                return settings_list
            
            return open_icon_selector
        
        for idx, repo in enumerate(repos):
            isCollapsed = repo.get("collapsed", False)
            isEnabled = repo.get("enabled", True)
            collapseIcon = "msg_go_up" if not isCollapsed else "arrow_more_solar"
            headerText = strings.repository_form.format(idx + 1)
            settingsList.append(Text(
                text=headerText,
                icon=collapseIcon,
                accent=isEnabled,
                on_click=makeOnToggleCollapse(idx)
            ))
            
            if not isCollapsed:
                current_icon = repo.get('icon', '')
                icon_text = strings.repo_icon_text.format(current_icon) if current_icon else strings.repo_icon_not_selected
                key_suffix = repo['id'] if repo.get('id') else f"idx_{idx}"
                settingsList.extend([
                    Switch(
                        key=f"repo_enabled_{key_suffix}",
                        text=strings.repo_enabled,
                        default=repo.get("enabled", True),
                        icon="msg_customize",
                        on_change=makeOnChange("enabled", idx)
                    ),
                    Input(
                        key=f"repo_name_{key_suffix}",
                        text=strings.repo_name,
                        default=repo.get("name", ""),
                        icon="msg_edit",
                        on_change=makeOnChange("name", idx)
                    ),
                    Input(
                        key=f"repo_url_{key_suffix}",
                        text=strings.repo_url,
                        default=repo.get("url", ""),
                        icon="msg_link",
                        on_change=makeOnChange("url", idx)
                    ),
                    Text(
                        text=icon_text,
                        icon="msg_folders",
                        create_sub_fragment=makeOnSelectIcon(idx)
                    )
                ])
                
                settingsList.extend([
                    Text(
                        text=strings.share_repository,
                        icon="msg_share",
                        accent=True,
                        on_click=makeOnShare(idx)
                    )
                ])
                
                if len(repos) > 1:
                    settingsList.append(Text(
                        text=strings.remove_repository,
                        icon="msg_filled_blocked_solar",
                        red=True,
                        on_click=makeOnRemove(idx)
                    ))

            settingsList.append(Divider())
        
        return settingsList

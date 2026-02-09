from ui.settings import Header, Input, Divider, Switch, Text
from elyx import strings
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from .icons import IconSelector
from ..packlog import packlog


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
            except Exception:
                pass
        
        def add_new_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    packlog.text("Repository add failed: max limit reached (10)")
                    BulletinHelper.show_error(strings.max_repositories_allowed)
                except Exception:
                    pass
                return
            
            for repo in repos:
                if repo.get('isFirst', False):
                    continue
                    
                if not repo.get('name', '').strip() or not repo.get('url', '').strip():
                    packlog.text("Repository add failed: previous repository not filled")
                    BulletinHelper.show_error(strings.fill_previous_repository)
                    return
        
            self.repoManager.addRepository(isFirst=False)
            packlog.text("Repository added")
        
        def restore_default_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    packlog.text("Default repository restore failed: max limit reached (10)")
                    BulletinHelper.show_error(strings.max_repositories_allowed)
                except Exception:
                    pass
                return
            
            self.repoManager.restoreDefaultRepository()
            packlog.text("Default repository restored")
            try:
                BulletinHelper.show_success(strings.default_repo_restored)
            except Exception:
                pass
        
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
                except Exception:
                    pass
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
                    packlog.text("All repositories reset")
                    try:
                        BulletinHelper.show_success(strings.repositories_reset)
                    except Exception:
                        pass
                
                builder.set_positive_button(strings.reset_button, on_yes)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                try:
                    builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                except Exception:
                    pass
                builder.show()
            except Exception:
                pass
        
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
                except Exception:
                    pass
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
                    packlog.text("All repositories cleared except first")
                    try:
                        BulletinHelper.show_success(strings.repositories_cleared)
                    except Exception:
                        pass
                
                builder.set_positive_button(strings.clear_button, on_yes)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                try:
                    builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                except Exception:
                    pass
                builder.show()
            except Exception:
                pass
        
        settingsList = [
            Header(text=strings.repositories),
            Text(
                text=strings.add_repository,
                icon="msg_add",
                accent=True,
                on_click=add_new_repository,
                link_alias="new_repo"
            ),
            Divider(),
            Text(
                text=strings.restore_default_repository,
                icon="msg_reset",
                accent=True,
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
                        packlog.text(f"Repository #{i+1} removed")
                    
                    builder.set_positive_button(strings.delete_button, on_yes)
                    builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                    try:
                        builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                    except Exception:
                        pass
                    builder.show()
                except Exception:
                    self.repoManager.removeRepository(i)
            
            return show_confirm_dialog
        
        def makeOnShare(i):
            def share_repository(view):
                repo = repos[i]
                name = repo.get('name', '').strip()
                url = repo.get('url', '').strip()
                icon = repo.get('icon', '').strip()

                share_url = f"tg://packit?repo=add&name={name}&link={url}&icon={icon}"

                try:
                    from org.telegram.messenger import AndroidUtilities
                    if AndroidUtilities.addToClipboard(share_url):
                        packlog.text(f"Repository #{i+1} link copied to clipboard")
                        BulletinHelper.show_success(strings.repo_link_copied)
                    else:
                        packlog.text(f"Failed to copy repository #{i+1} link")
                        BulletinHelper.show_error(strings.failed_to_copy)
                except Exception:
                    packlog.text(f"Failed to copy repository #{i+1} link")
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
                    packlog.text(f"Repository #{i+1} icon changed to: {icon_name}")
                
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
                settingsList.extend([
                    Switch(
                        key=f"repo_enabled_{repo['id']}",
                        text=strings.repo_enabled,
                        default=repo.get("enabled", True),
                        icon="msg_customize",
                        on_change=makeOnChange("enabled", idx)
                    ),
                    Input(
                        key=f"repo_name_{repo['id']}",
                        text=strings.repo_name,
                        default=repo.get("name", ""),
                        icon="msg_edit",
                        on_change=makeOnChange("name", idx)
                    ),
                    Input(
                        key=f"repo_url_{repo['id']}",
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

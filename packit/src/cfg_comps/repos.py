from ui.settings import Header, Input, Divider, Switch, Text
from elyx import strings
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
from android_utils import log
from ui.alert import AlertDialogBuilder
from .icons import IconSelector


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
                    BulletinHelper.show_error("Maximum 10 repositories allowed")
                except Exception:
                    log("Maximum 10 repositories allowed")
                return
            
            for repo in repos:
                if repo.get('isFirst', False):
                    continue
                    
                if not repo.get('name', '').strip() or not repo.get('url', '').strip():
                    BulletinHelper.show_error("Fill in the previous repository first")
                    log("Please fill in the previous repository first")
                    return
        
            self.repoManager.addRepository(isFirst=False)
        
        settingsList = [
            Header(text=strings.repositories),
            Text(
                text=strings.add_repository,
                icon="msg_add",
                accent=True,
                on_click=add_new_repository
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
                    builder.set_title("Delete repository")
                    builder.set_message("Are you sure you want to delete repository?")
                    
                    def on_yes(b, w):
                        self.repoManager.removeRepository(i)
                    
                    builder.set_positive_button("Delete", on_yes)
                    builder.set_negative_button("Close", lambda b, w: b.dismiss())
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
                        BulletinHelper.show_success("Repository link copied to clipboard!")
                    else:
                        BulletinHelper.show_error("Failed to copy to clipboard")
                except Exception:
                    BulletinHelper.show_error("Failed to copy to clipboard")
            
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
            headerText = strings("repository_form", idx + 1)
            settingsList.append(Text(
                text=headerText,
                icon=collapseIcon,
                accent=isEnabled,
                on_click=makeOnToggleCollapse(idx)
            ))
            
            if not isCollapsed:
                current_icon = repo.get('icon', '')
                icon_text = f"Repository Icon: {current_icon}" if current_icon else "Repository Icon: not selected"
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
                        text="Share Repository",
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
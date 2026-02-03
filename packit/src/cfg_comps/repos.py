from ui.settings import Header, Input, Divider, Switch, Text
from elyx import strings


class RepositoriesSettings:
    def __init__(self, repoManager):
        self.repoManager = repoManager
    
    def build(self):
        repos = self.repoManager.getRepositories()

        if not repos:
            self.repoManager.addRepository(isFirst=True)
            repos = self.repoManager.getRepositories()
        
        def add_new_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    from ui.bulletin import BulletinHelper
                    BulletinHelper.show_error("Maximum 10 repositories allowed")
                except Exception:
                    try:
                        from android_utils import log
                        log("Maximum 10 repositories allowed")
                    except Exception:
                        pass
                return
            
            for repo in repos:
                if repo.get('isFirst', False):
                    continue
                    
                if not repo.get('name', '').strip() or not repo.get('url', '').strip():
                    try:
                        from ui.bulletin import BulletinHelper
                        BulletinHelper.show_error("Fill in the previous repository first")
                    except Exception:
                        try:
                            from android_utils import log
                            log("Please fill in the previous repository first")
                        except Exception:
                            pass
                    return
        
            self.repoManager.addRepository(isFirst=False)
        
        settingsList = [
            Header(text=strings.repositories),
            Text(
                text=strings.add_repository,
                icon="msg_add",
                on_click=add_new_repository
            ),
            Divider()
        ]
        
        def makeOnChange(field, i):
            return lambda value: self.repoManager.updateRepoField(i, field, value)
        
        def makeOnRemove(i):
            def show_confirm_dialog(view):
                try:
                    from ui.alert import AlertDialogBuilder
                    from client_utils import get_last_fragment
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
        
        def makeOnToggleCollapse(i):
            def toggle(view):
                repos = self.repoManager.getRepositories()
                if i < len(repos):
                    repos[i]['collapsed'] = not repos[i].get('collapsed', False)
                    self.repoManager.setRepositories(repos)
            return toggle
        
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
                if len(repos) > 1:
                    settingsList.append(Text(
                        text=strings.remove_repository,
                        icon="msg_filled_blocked_solar",
                        red=True,
                        on_click=makeOnRemove(idx)
                    ))
                
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
                    )
                ])

            settingsList.append(Divider())
        
        return settingsList
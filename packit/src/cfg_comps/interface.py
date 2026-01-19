from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment, run_on_queue
from android_utils import run_on_ui_thread, log
import requests
import json
from datetime import datetime


class InterfaceSettings:
    def __init__(self):
        self.plugin = None
    
    def setPlugin(self, plugin):
        self.plugin = plugin
    
    def _showNotReady(self, view):
        BulletinHelper.show_info("Not ready")
    
    def _handleUpdate(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        def task():
            repos = [r for r in self.plugin.repoManager.getRepositories() if r.get("enabled")]
            successCount = 0
            failedCount = 0
            
            for repo in repos:
                try:
                    from elyx import settings
                    response = requests.get(repo["url"], timeout=10)
                    config = response.json()
                    
                    cacheKey = f"{repo['id']}_cache"
                    cacheData = {
                        "last_update": datetime.now().isoformat(),
                        "url": repo["url"],
                        "name": repo["name"],
                        "plugins": config.get("plugins", {})
                    }
                    
                    settings.set(cacheKey, json.dumps(cacheData))
                    successCount += 1
                    log(f"updated repo cache: {repo['name']}")
                except Exception as e:
                    failedCount += 1
                    log(f"failed to update repo {repo['name']}: {e}")
            
            def showResult():
                BulletinHelper.show_info(f"Successful: {successCount} Failed: {failedCount}")
            
            run_on_ui_thread(showResult)
        
        run_on_queue(task)
    
    def _handlePluginList(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        allPlugins = self.plugin.core.getAllPluginsFromCache()
        
        if not allPlugins:
            BulletinHelper.show_info("No plugins found in cache. Try: Update")
            return
        
        countPlugins = len(allPlugins)
        
        pluginLines = []
        for plugin in allPlugins:
            displayName = plugin.get("displayName", plugin.get("packId", "Unknown"))
            packId = plugin.get("packId", "unknown")
            version = plugin.get("version", "unknown")
            repoName = plugin.get("repo_name", "unknown")
            
            pluginLines.append(f"{displayName} (v{version})\nPackID: {packId} | Repo: {repoName}")
        
        listText = "\n\n".join(pluginLines)
        fullMessage = f"Found {countPlugins} plugins\n\n{listText}"
        
        builder = AlertDialogBuilder(activity)
        builder.set_title("Plugin List")
        builder.set_message(fullMessage)
        builder.set_positive_button("OK", lambda b, w: b.dismiss())
        builder.show()
    
    def _handleRepoList(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        repos = [r for r in self.plugin.repoManager.getRepositories() if r.get("enabled")]
        
        if not repos:
            BulletinHelper.show_info("No repositories configured")
            return
        
        totalRepos = len(repos)
        
        repoLines = []
        for repo in repos:
            repoName = repo.get("name", "Unnamed")
            repoUrl = repo.get("url", "")
            
            if repoUrl:
                repoLines.append(f"{repoName}\n{repoUrl}")
            else:
                repoLines.append(f"{repoName}")
        
        listText = "\n\n".join(repoLines)
        fullMessage = f"Total {totalRepos} repositories\n\n{listText}"
        
        builder = AlertDialogBuilder(activity)
        builder.set_title("Repository List")
        builder.set_message(fullMessage)
        builder.set_positive_button("OK", lambda b, w: b.dismiss())
        builder.show()
    
    def build(self):
        return [
            Header(text="Actions"),
            Text(
                text="Install",
                icon="msg_download",
                on_click=self._showNotReady
            ),
            Text(
                text="Update",
                icon="msg_retry",
                on_click=self._handleUpdate
            ),
            Text(
                text="Upgrade",
                icon="gift_upgrade",
                on_click=self._showNotReady
            ),
            Text(
                text="Uninstall",
                icon="msg_delete",
                red=True,
                on_click=self._showNotReady
            ),
            Divider(),
            Text(
                text="Search",
                icon="msg_search",
                on_click=self._showNotReady
            ),
            Text(
                text="Plugin List",
                icon="msg_list",
                on_click=self._handlePluginList
            ),
            Text(
                text="Repository List",
                icon="msg_folders",
                on_click=self._handleRepoList
            )
        ]
from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment, run_on_queue
from android_utils import run_on_ui_thread, log
from hook_utils import find_class
import requests
import json
from datetime import datetime

Theme = find_class("org.telegram.ui.ActionBar.Theme")
PorterDuff = find_class("android.graphics.PorterDuff")


class InterfaceSettings:
    def __init__(self):
        self.plugin = None
    
    def setPlugin(self, plugin):
        self.plugin = plugin
    
    def _showNotReady(self, view):
        BulletinHelper.show_info("Not ready")
    
    def _handleInstall(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        builder = AlertDialogBuilder(activity)
        builder.set_title("Install Plugin")
        
        from android.widget import EditText, LinearLayout
        from android.view import ViewGroup
        from org.telegram.messenger import AndroidUtilities
        
        layout = LinearLayout(activity)
        layout.setOrientation(LinearLayout.VERTICAL)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        layout.setLayoutParams(layoutParams)
        
        paddingDp = AndroidUtilities.dp(16)
        layout.setPadding(paddingDp, paddingDp, paddingDp, paddingDp)
        
        pluginIdInput = EditText(activity)
        pluginIdInput.setHint("Pack ID")
        pluginIdInput.setSingleLine(True)
        pluginIdInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        pluginIdInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        pluginIdInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        layout.addView(pluginIdInput)
        
        repoNameInput = EditText(activity)
        repoNameInput.setHint("Repository name (optional)")
        repoNameInput.setSingleLine(True)
        repoNameInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        repoNameInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        repoNameInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        marginParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        marginParams.setMargins(0, AndroidUtilities.dp(8), 0, 0)
        repoNameInput.setLayoutParams(marginParams)
        layout.addView(repoNameInput)
        
        builder.set_view(layout)
        
        def onInstall(bld, which):
            pluginId = str(pluginIdInput.getText()).strip()
            repoName = str(repoNameInput.getText()).strip()
            
            if not pluginId:
                BulletinHelper.show_error("Pack ID cannot be empty")
                return
            
            repoNameToUse = repoName if repoName else None
            
            self.plugin.core.installPlugin(pluginId, repoNameToUse, autoRestart=False)
            bld.dismiss()
        
        builder.set_positive_button("Install", onInstall)
        builder.set_negative_button("Cancel", lambda b, w: b.dismiss())
        builder.show()
    
    def _handleSearch(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        builder = AlertDialogBuilder(activity)
        builder.set_title("Search Plugins")
        
        from android.widget import EditText, LinearLayout
        from android.view import ViewGroup
        from org.telegram.messenger import AndroidUtilities
        
        layout = LinearLayout(activity)
        layout.setOrientation(LinearLayout.VERTICAL)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        layout.setLayoutParams(layoutParams)
        
        paddingDp = AndroidUtilities.dp(16)
        layout.setPadding(paddingDp, paddingDp, paddingDp, paddingDp)
        
        queryInput = EditText(activity)
        queryInput.setHint("Search query")
        queryInput.setSingleLine(True)
        queryInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        queryInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        queryInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        layout.addView(queryInput)
        
        builder.set_view(layout)
        
        def onSearch(bld, which):
            query = str(queryInput.getText()).strip()
            
            if not query:
                BulletinHelper.show_error("Query cannot be empty")
                return
            
            results = self.plugin.core.searchInCache(query)
            
            if not results:
                BulletinHelper.show_info(f"No matches found for '{query}'")
                bld.dismiss()
                return
            
            countMatches = len(results)
            
            resultLines = []
            for result in results:
                displayName = result.get("displayName", result.get("id", "Unknown"))
                repoName = result.get("repo_name", "unknown")
                description = result.get("description", "No description")
                resultLines.append(f"{displayName} | repo: {repoName}\n{description}")
            
            listText = "\n\n".join(resultLines)
            fullMessage = f"{countMatches} matches found!\n\n{listText}"
            
            bld.dismiss()
            
            resultBuilder = AlertDialogBuilder(activity)
            resultBuilder.set_title("Search Results")
            resultBuilder.set_message(fullMessage)
            resultBuilder.set_positive_button("OK", lambda b, w: b.dismiss())
            resultBuilder.show()
        
        builder.set_positive_button("Search", onSearch)
        builder.set_negative_button("Cancel", lambda b, w: b.dismiss())
        builder.show()
    
    def _handleUninstall(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        builder = AlertDialogBuilder(activity)
        builder.set_title("Uninstall Plugin")
        
        from android.widget import EditText, LinearLayout
        from android.view import ViewGroup
        from org.telegram.messenger import AndroidUtilities
        
        layout = LinearLayout(activity)
        layout.setOrientation(LinearLayout.VERTICAL)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        layout.setLayoutParams(layoutParams)
        
        paddingDp = AndroidUtilities.dp(16)
        layout.setPadding(paddingDp, paddingDp, paddingDp, paddingDp)
        
        queryInput = EditText(activity)
        queryInput.setHint("Query")
        queryInput.setSingleLine(True)
        queryInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        queryInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        queryInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        layout.addView(queryInput)
        
        repoNameInput = EditText(activity)
        repoNameInput.setHint("Repository name (optional)")
        repoNameInput.setSingleLine(True)
        repoNameInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        repoNameInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        repoNameInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        marginParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        marginParams.setMargins(0, AndroidUtilities.dp(8), 0, 0)
        repoNameInput.setLayoutParams(marginParams)
        layout.addView(repoNameInput)
        
        builder.set_view(layout)
        
        def onUninstall(bld, which):
            query = str(queryInput.getText()).strip()
            repoName = str(repoNameInput.getText()).strip()
            
            if not query:
                BulletinHelper.show_error("Query cannot be empty")
                return
            
            repoNameToUse = repoName if repoName else None
            
            self.plugin.core.uninstallPlugin(query, repoNameToUse, autoRestart=False)
            bld.dismiss()
        
        builder.set_positive_button("Uninstall", onUninstall)
        builder.set_negative_button("Cancel", lambda b, w: b.dismiss())
        builder.show()
    
    def _handleUpgrade(self, view):
        if not self.plugin:
            BulletinHelper.show_error("Plugin not initialized")
            return
        
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        builder = AlertDialogBuilder(activity)
        builder.set_title("Upgrade Plugin")
        
        from android.widget import EditText, LinearLayout
        from android.view import ViewGroup
        from org.telegram.messenger import AndroidUtilities
        
        layout = LinearLayout(activity)
        layout.setOrientation(LinearLayout.VERTICAL)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        layout.setLayoutParams(layoutParams)
        
        paddingDp = AndroidUtilities.dp(16)
        layout.setPadding(paddingDp, paddingDp, paddingDp, paddingDp)
        
        queryInput = EditText(activity)
        queryInput.setHint("Query")
        queryInput.setSingleLine(True)
        queryInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        queryInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        queryInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        layout.addView(queryInput)
        
        repoNameInput = EditText(activity)
        repoNameInput.setHint("Repository name (optional)")
        repoNameInput.setSingleLine(True)
        repoNameInput.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        repoNameInput.setHintTextColor(Theme.getColor(Theme.key_dialogTextGray3))
        repoNameInput.getBackground().setColorFilter(
            Theme.getColor(Theme.key_dialogTextBlack),
            PorterDuff.Mode.SRC_ATOP
        )
        marginParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        marginParams.setMargins(0, AndroidUtilities.dp(8), 0, 0)
        repoNameInput.setLayoutParams(marginParams)
        layout.addView(repoNameInput)
        
        builder.set_view(layout)
        
        def onUpgrade(bld, which):
            query = str(queryInput.getText()).strip()
            repoName = str(repoNameInput.getText()).strip()
            
            if not query:
                BulletinHelper.show_error("Query cannot be empty")
                return
            
            repoNameToUse = repoName if repoName else None
            
            self.plugin.core.upgradePlugin(query, repoNameToUse, autoRestart=False)
            bld.dismiss()
        
        builder.set_positive_button("Upgrade", onUpgrade)
        builder.set_negative_button("Cancel", lambda b, w: b.dismiss())
        builder.show()
    
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
                on_click=self._handleInstall
            ),
            Text(
                text="Update",
                icon="msg_retry",
                on_click=self._handleUpdate
            ),
            Text(
                text="Upgrade",
                icon="gift_upgrade",
                on_click=self._handleUpgrade
            ),
            Text(
                text="Uninstall",
                icon="msg_delete",
                red=True,
                on_click=self._handleUninstall
            ),
            Divider(),
            Text(
                text="Search",
                icon="msg_search",
                on_click=self._handleSearch
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
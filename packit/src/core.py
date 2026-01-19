import json
import requests
from datetime import datetime
from android_utils import log, run_on_ui_thread
from client_utils import run_on_queue
from ui.bulletin import BulletinHelper
from elyx import settings
from java.io import File, FileOutputStream


class PackItCore:
    def __init__(self, repoManager):
        self.repoManager = repoManager
    
    def initializeRepositories(self):
        repos = self.repoManager.getRepositories()
        if not repos:
            self.repoManager.addRepository(isFirst=True)
            repos = self.repoManager.getRepositories()
        
        self.updateAllRepositories(silent=True)
    
    def updateAllRepositories(self, silent=False):
        def task():
            repos = [r for r in self.repoManager.getRepositories() if r.get("enabled")]
            successCount = 0
            failedCount = 0
            
            for repo in repos:
                try:
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
            
            if not silent:
                def showResult():
                    BulletinHelper.show_info(f"Successful: {successCount} Failed: {failedCount}")
                
                run_on_ui_thread(showResult)
        
        run_on_queue(task)
    
    def installPlugin(self, pluginId, repoName=None, autoRestart=False):
        def task():
            plugin = self.findPlugin(pluginId, repoName)
            
            if not plugin:
                def showError():
                    BulletinHelper.show_error("An error occurred. See logs.")
                
                run_on_ui_thread(showError)
                if repoName:
                    log(f"plugin '{pluginId}' not found in repository '{repoName}'")
                else:
                    log(f"plugin '{pluginId}' not found")
                return
            
            rawUrl = plugin.get("raw", "")
            pluginFileId = plugin.get("id", pluginId)
            
            if not rawUrl:
                def showError():
                    BulletinHelper.show_error("An error occurred. See logs.")
                
                run_on_ui_thread(showError)
                log(f"plugin '{pluginId}' has no raw url")
                return
            
            if not rawUrl.startswith("http"):
                rawUrl = f"https://{rawUrl}"
            
            try:
                response = requests.get(rawUrl, timeout=30)
                
                if response.status_code != 200:
                    def showError():
                        BulletinHelper.show_error("An error occurred. See logs.")
                    
                    run_on_ui_thread(showError)
                    log(f"failed to download plugin '{pluginId}': status {response.status_code}")
                    return
                
                from android.content import Context
                from org.telegram.messenger import ApplicationLoader
                
                context = ApplicationLoader.applicationContext
                packageName = context.getPackageName()
                
                pluginsDir = File(f"/data/data/{packageName}/files/plugins")
                
                if not pluginsDir.exists():
                    pluginsDir.mkdirs()
                
                pluginFile = File(pluginsDir, f"{pluginFileId}.py")
                
                fos = FileOutputStream(pluginFile)
                fos.write(response.content)
                fos.close()
                
                def showSuccess():
                    BulletinHelper.show_success("Installed successfully! A restart is required.")
                
                run_on_ui_thread(showSuccess)
                log(f"plugin '{pluginId}' installed as '{pluginFileId}.py'")
                
                if autoRestart:
                    import time
                    time.sleep(1)
                    self._killApp()
                
            except Exception as e:
                def showError():
                    BulletinHelper.show_error("An error occurred. See logs.")
                
                run_on_ui_thread(showError)
                log(f"failed to install plugin '{pluginId}': {e}")
                import traceback
                log(f"traceback: {traceback.format_exc()}")
        
        run_on_queue(task)
    
    def uninstallPlugin(self, query, repoName=None, autoRestart=False):
        def task():
            try:
                plugin = self.findPlugin(query, repoName)
                
                if not plugin:
                    def showError():
                        BulletinHelper.show_error("Plugin not found in repositories.")
                    
                    run_on_ui_thread(showError)
                    if repoName:
                        log(f"plugin '{query}' not found in repository '{repoName}'")
                    else:
                        log(f"plugin '{query}' not found")
                    return
                
                pluginFileId = plugin.get("id")
                
                if not pluginFileId:
                    def showError():
                        BulletinHelper.show_error("Plugin has no ID field.")
                    
                    run_on_ui_thread(showError)
                    log(f"plugin '{query}' has no id field")
                    return
                
                from android.content import Context
                from org.telegram.messenger import ApplicationLoader
                
                context = ApplicationLoader.applicationContext
                packageName = context.getPackageName()
                
                pluginFile = File(f"/data/data/{packageName}/files/plugins/{pluginFileId}.py")
                pycacheFile = File(f"/data/data/{packageName}/files/plugins/__pycache__/{pluginFileId}.cpython-311.pyc")
                
                if not pluginFile.exists():
                    def showError():
                        BulletinHelper.show_error("File not found.")
                    
                    run_on_ui_thread(showError)
                    log(f"plugin file '{pluginFileId}.py' not found")
                    return
                
                pluginDeleted = pluginFile.delete()
                pycacheDeleted = False
                
                if pycacheFile.exists():
                    pycacheDeleted = pycacheFile.delete()
                    if pycacheDeleted:
                        log(f"pycache file '{pluginFileId}.cpython-311.pyc' deleted")
                    else:
                        log(f"failed to delete pycache file '{pluginFileId}.cpython-311.pyc'")
                
                if pluginDeleted:
                    def showSuccess():
                        BulletinHelper.show_success("Plugin uninstall. Stopping the app required.")
                    
                    run_on_ui_thread(showSuccess)
                    log(f"plugin '{pluginFileId}.py' uninstalled successfully")
                    
                    if autoRestart:
                        import time
                        time.sleep(1)
                        self._killApp()
                else:
                    def showError():
                        BulletinHelper.show_error("File not found.")
                    
                    run_on_ui_thread(showError)
                    log(f"failed to delete plugin file '{pluginFileId}.py'")
                
            except Exception as e:
                def showError():
                    BulletinHelper.show_error("An error occurred. See logs.")
                
                run_on_ui_thread(showError)
                log(f"failed to uninstall plugin '{query}': {e}")
                import traceback
                log(f"traceback: {traceback.format_exc()}")
        
        run_on_queue(task)
    
    def upgradePlugin(self, query, repoName=None, autoRestart=False):
        def task():
            plugin = self.findPlugin(query, repoName)
            
            if not plugin:
                def showError():
                    BulletinHelper.show_error("Plugin not found in repositories.")
                
                run_on_ui_thread(showError)
                if repoName:
                    log(f"plugin '{query}' not found in repository '{repoName}'")
                else:
                    log(f"plugin '{query}' not found")
                return
            
            rawUrl = plugin.get("raw", "")
            pluginFileId = plugin.get("id")
            
            if not pluginFileId:
                def showError():
                    BulletinHelper.show_error("Plugin has no ID field.")
                
                run_on_ui_thread(showError)
                log(f"plugin '{query}' has no id field")
                return
            
            if not rawUrl:
                def showError():
                    BulletinHelper.show_error("Plugin has no raw URL.")
                
                run_on_ui_thread(showError)
                log(f"plugin '{query}' has no raw url")
                return
            
            if not rawUrl.startswith("http"):
                rawUrl = f"https://{rawUrl}"
            
            try:
                from android.content import Context
                from org.telegram.messenger import ApplicationLoader
                
                context = ApplicationLoader.applicationContext
                packageName = context.getPackageName()
                
                pluginFile = File(f"/data/data/{packageName}/files/plugins/{pluginFileId}.py")
                pycacheFile = File(f"/data/data/{packageName}/files/plugins/__pycache__/{pluginFileId}.cpython-311.pyc")
                
                if pluginFile.exists():
                    pluginDeleted = pluginFile.delete()
                    if not pluginDeleted:
                        def showError():
                            BulletinHelper.show_error("Failed to remove old version.")
                        
                        run_on_ui_thread(showError)
                        log(f"failed to delete old plugin file '{pluginFileId}.py'")
                        return
                    
                    log(f"old plugin file '{pluginFileId}.py' deleted")
                
                if pycacheFile.exists():
                    pycacheDeleted = pycacheFile.delete()
                    if pycacheDeleted:
                        log(f"pycache file '{pluginFileId}.cpython-311.pyc' deleted")
                
                response = requests.get(rawUrl, timeout=30)
                
                if response.status_code != 200:
                    def showError():
                        BulletinHelper.show_error("Failed to download plugin.")
                    
                    run_on_ui_thread(showError)
                    log(f"failed to download plugin '{query}': status {response.status_code}")
                    return
                
                pluginsDir = File(f"/data/data/{packageName}/files/plugins")
                
                if not pluginsDir.exists():
                    pluginsDir.mkdirs()
                
                newPluginFile = File(pluginsDir, f"{pluginFileId}.py")
                
                fos = FileOutputStream(newPluginFile)
                fos.write(response.content)
                fos.close()
                
                def showSuccess():
                    BulletinHelper.show_success("Successfully! App termination required.")
                
                run_on_ui_thread(showSuccess)
                log(f"plugin '{query}' upgraded to '{pluginFileId}.py'")
                
                if autoRestart:
                    import time
                    time.sleep(1)
                    self._killApp()
                
            except Exception as e:
                def showError():
                    BulletinHelper.show_error("An error occurred. See logs.")
                
                run_on_ui_thread(showError)
                log(f"failed to upgrade plugin '{query}': {e}")
                import traceback
                log(f"traceback: {traceback.format_exc()}")
        
        run_on_queue(task)
    
    def _killApp(self):
        try:
            import os
            import signal
            
            pid = os.getpid()
            log(f"killing app with pid: {pid}")
            os.kill(pid, signal.SIGKILL)
        except Exception as e:
            log(f"failed to kill app: {e}")
            import traceback
            log(f"traceback: {traceback.format_exc()}")
    
    def getPluginFromCache(self, pluginId):
        repos = self.repoManager.getRepositories()
        
        for repo in repos:
            if not repo.get("enabled"):
                continue
            
            cacheKey = f"{repo['id']}_cache"
            cacheJson = settings.get(cacheKey, "{}")
            
            try:
                cache = json.loads(cacheJson)
                plugins = cache.get("plugins", {})
                
                if pluginId in plugins:
                    return {
                        "repo_id": repo["id"],
                        "repo_name": repo["name"],
                        **plugins[pluginId]
                    }
            except Exception as e:
                log(f"failed to parse cache for {repo['name']}: {e}")
        
        return None
    
    def searchInCache(self, query):
        results = []
        repos = self.repoManager.getRepositories()
        
        for repo in repos:
            if not repo.get("enabled"):
                continue
            
            cacheKey = f"{repo['id']}_cache"
            cacheJson = settings.get(cacheKey, "{}")
            
            try:
                cache = json.loads(cacheJson)
                plugins = cache.get("plugins", {})
                
                for packId, info in plugins.items():
                    displayName = info.get("displayName", "")
                    description = info.get("description", "")
                    
                    if (query.lower() in packId.lower() or 
                        query.lower() in displayName.lower() or 
                        query.lower() in description.lower()):
                        
                        results.append({
                            "packId": packId,
                            "repo_id": repo["id"],
                            "repo_name": repo["name"],
                            **info
                        })
            except Exception as e:
                log(f"failed to search in {repo['name']}: {e}")
        
        return results
    
    def getAllPluginsFromCache(self):
        allPlugins = []
        repos = self.repoManager.getRepositories()
        
        for repo in repos:
            if not repo.get("enabled"):
                continue
            
            cacheKey = f"{repo['id']}_cache"
            cacheJson = settings.get(cacheKey, "{}")
            
            try:
                cache = json.loads(cacheJson)
                plugins = cache.get("plugins", {})
                
                for packId, info in plugins.items():
                    allPlugins.append({
                        "packId": packId,
                        "repo_id": repo["id"],
                        "repo_name": repo["name"],
                        **info
                    })
            except Exception as e:
                log(f"failed to get plugins from {repo['name']}: {e}")
        
        return allPlugins
    
    def findPlugin(self, pluginId, repoName=None):
        repos = self.repoManager.getRepositories()
        
        for repo in repos:
            if not repo.get("enabled"):
                continue
            
            if repoName and repo["name"].lower() != repoName.lower():
                continue
            
            cacheKey = f"{repo['id']}_cache"
            cacheJson = settings.get(cacheKey, "{}")
            
            try:
                cache = json.loads(cacheJson)
                plugins = cache.get("plugins", {})
                
                if pluginId in plugins:
                    return {
                        "packId": pluginId,
                        "repo_id": repo["id"],
                        "repo_name": repo["name"],
                        **plugins[pluginId]
                    }
            except Exception as e:
                log(f"failed to search in {repo['name']}: {e}")
        
        return None
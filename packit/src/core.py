import json
import requests
from datetime import datetime
from android_utils import log, run_on_ui_thread
from client_utils import run_on_queue
from ui.bulletin import BulletinHelper
from elyx import settings


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
                
                for pluginId, info in plugins.items():
                    displayName = info.get("displayName", "")
                    description = info.get("description", "")
                    
                    if (query.lower() in pluginId.lower() or 
                        query.lower() in displayName.lower() or 
                        query.lower() in description.lower()):
                        
                        results.append({
                            "id": pluginId,
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
                
                for pluginId, info in plugins.items():
                    allPlugins.append({
                        "id": pluginId,
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
                        "id": pluginId,
                        "repo_id": repo["id"],
                        "repo_name": repo["name"],
                        **plugins[pluginId]
                    }
            except Exception as e:
                log(f"failed to search in {repo['name']}: {e}")
        
        return None
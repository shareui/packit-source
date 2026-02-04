import json
from datetime import datetime
from client_utils import get_last_fragment
from elyx import settings


class RepositoryManager:
    def __init__(self):
        pass
    
    def getRepositories(self):
        reposJson = settings.get("repositories", "[]")
        try:
            repos = json.loads(reposJson)
            if not isinstance(repos, list):
                return []
            return repos
        except Exception:
            return []
    
    def setRepositories(self, repos):
        settings.set("repositories", json.dumps(repos), reload_settings=True)
        try:
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()
        except Exception:
            pass
    
    def addRepository(self, isFirst=False):
        repos = self.getRepositories()
        repoId = datetime.now().strftime("%Y.%m.%d %H:%M:%S.%f")
        
        if isFirst:
            newRepo = {
                "id": repoId,
                "name": "Official repository",
                "url": "https://raw.githubusercontent.com/shareui/packit/main/configs/config.json",
                "enabled": True,
                "collapsed": False,
                "icon": "chats_pin"
            }
        else:
            newRepo = {
                "id": repoId,
                "name": "",
                "url": "",
                "enabled": True,
                "collapsed": False
            }
        
        repos.append(newRepo)
        self.setRepositories(repos)
        
        fragment = get_last_fragment()
        if fragment and hasattr(fragment, "rebuildAllItems"):
            fragment.rebuildAllItems()
    
    def removeRepository(self, idx):
        repos = self.getRepositories()
        if idx < 0 or idx >= len(repos):
            return
        
        repos.pop(idx)
        self.setRepositories(repos)
        
        fragment = get_last_fragment()
        if fragment and hasattr(fragment, "rebuildAllItems"):
            fragment.rebuildAllItems()
    
    def updateRepoField(self, idx, field, value):
        repos = self.getRepositories()
        if idx < len(repos):
            repos[idx][field] = value
            self.setRepositories(repos)
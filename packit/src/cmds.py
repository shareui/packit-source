from typing import Any
from base_plugin import HookResult, HookStrategy
from elyx import strings, settings
from client_utils import send_message, get_last_fragment
from markdown_utils import parse_markdown
from org.telegram.tgnet import TLRPC
from android_utils import log
from ui.alert import AlertDialogBuilder


class CommandProcessor:
    def __init__(self, plugin):
        self.plugin = plugin
    
    def processMessage(self, params: Any) -> HookResult:
        if not isinstance(params.message, str):
            return HookResult()
        
        messageText = params.message.strip()
        
        cmdInfo = settings.get("cmd_info", "packit info")
        cmdSearch = settings.get("cmd_search", "packit search")
        cmdInstall = settings.get("cmd_install", "packit install")
        cmdUninstall = settings.get("cmd_uninstall", "packit uninstall")
        cmdPluginlist = settings.get("cmd_pluginlist", "packit pluginlist")
        cmdRepolist = settings.get("cmd_repolist", "packit repolist")
        cmdShare = settings.get("cmd_share", "packit share")
        cmdUpdate = settings.get("cmd_update", "packit update")
        cmdUpgrade = settings.get("cmd_upgrade", "packit upgrade")
        
        if messageText.startswith(cmdInfo):
            return self._handleInfo(messageText, params)
        
        if messageText.startswith(cmdSearch):
            return self._handleSearch(messageText, params)
        
        if messageText.startswith(cmdInstall):
            return self._handleInstall(messageText, params)
        
        if messageText.startswith(cmdUninstall):
            return self._handleUninstall(messageText, params)
        
        if messageText.startswith(cmdPluginlist):
            return self._handlePluginList(messageText, params)
        
        if messageText.startswith(cmdRepolist):
            return self._handleRepoList(messageText, params)
        
        if messageText.startswith(cmdShare):
            return self._handleShare(messageText, params)
        
        if messageText.startswith(cmdUpdate):
            return self._handleUpdate(messageText, params)
        
        if messageText.startswith(cmdUpgrade):
            return self._handleUpgrade(messageText, params)
        
        return HookResult()
    
    def _handleInfo(self, messageText: str, params: Any) -> HookResult:
        cmdInfo = settings.get("cmd_info", "packit info")
        args = messageText[len(cmdInfo):].strip().split(maxsplit=1)
        
        if not args or not args[0]:
            params.message = "Usage: packit info [plugin_id] [repository_name]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        pluginId = args[0]
        repoName = args[1] if len(args) > 1 else None
        
        plugin = self.plugin.core.findPlugin(pluginId, repoName)
        
        if not plugin:
            if repoName:
                params.message = f"Plugin '{pluginId}' not found in repository '{repoName}'"
            else:
                params.message = f"Plugin '{pluginId}' not found"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        displayName = plugin.get("displayName", pluginId)
        version = plugin.get("version", "unknown")
        description = plugin.get("description", "No description")
        rawUrl = plugin.get("raw", "")
        link = plugin.get("link", "")
        author = plugin.get("author", "")
        repoNameFound = plugin.get("repo_name", "unknown")
        
        if link and not link.startswith("http"):
            link = f"https://{link}"
        
        if rawUrl and not rawUrl.startswith("http"):
            rawUrl = f"https://{rawUrl}"
        
        headerText = f"*{displayName} v{version}*\n"
        
        if author:
            headerText += f"*Author:* {author}\n"
        
        if link:
            headerText += f"[.plugin file]({link})\n"
        
        headerText += f"[Open raw]({rawUrl})\n\n*Description*\n"
        fullText = headerText + description
        
        try:
            parsedMessage = parse_markdown(fullText)
            
            headerLength = len(parsedMessage.text) - len(description)
            blockquoteStart = headerLength
            blockquoteLength = len(description)
            
            messageParams = {
                "message": parsedMessage.text,
                "peer": params.peer,
                "entities": [],
                "searchLinks": False
            }
            
            for rawEntity in parsedMessage.entities:
                tlrpcEntity = rawEntity.to_tlrpc_object()
                messageParams["entities"].append(tlrpcEntity)
            
            blockquoteEntity = TLRPC.TL_messageEntityBlockquote()
            blockquoteEntity.offset = blockquoteStart
            blockquoteEntity.length = blockquoteLength
            blockquoteEntity.collapsed = True
            messageParams["entities"].append(blockquoteEntity)
            
            send_message(messageParams)
            
        except Exception as e:
            log(f"error sending plugin info: {e}")
            params.message = f"Error: {str(e)}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleSearch(self, messageText: str, params: Any) -> HookResult:
        cmdSearch = settings.get("cmd_search", "packit search")
        query = messageText[len(cmdSearch):].strip()
        
        if not query:
            params.message = "Usage: packit search [query]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        results = self.plugin.core.searchInCache(query)
        
        if not results:
            params.message = f"No matches found for '{query}'"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        countMatches = len(results)
        headerText = f"*{countMatches} matches found!*\n"
        
        resultLines = []
        for result in results:
            displayName = result.get("displayName", result.get("id", "Unknown"))
            repoName = result.get("repo_name", "unknown")
            resultLines.append(f"{displayName} | repo: {repoName}")
        
        listText = "\n".join(resultLines)
        fullText = headerText + listText
        
        try:
            parsedMessage = parse_markdown(fullText)
            
            headerLength = len(f"{countMatches} matches found!\n")
            blockquoteStart = headerLength
            blockquoteLength = len(parsedMessage.text) - headerLength
            
            messageParams = {
                "message": parsedMessage.text,
                "peer": params.peer,
                "entities": [],
                "searchLinks": False
            }
            
            for rawEntity in parsedMessage.entities:
                tlrpcEntity = rawEntity.to_tlrpc_object()
                messageParams["entities"].append(tlrpcEntity)
            
            blockquoteEntity = TLRPC.TL_messageEntityBlockquote()
            blockquoteEntity.offset = blockquoteStart
            blockquoteEntity.length = blockquoteLength
            blockquoteEntity.collapsed = True
            messageParams["entities"].append(blockquoteEntity)
            
            send_message(messageParams)
            
        except Exception as e:
            log(f"error sending search results: {e}")
            params.message = f"Error: {str(e)}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleInstall(self, messageText: str, params: Any) -> HookResult:
        cmdInstall = settings.get("cmd_install", "packit install")
        args = messageText[len(cmdInstall):].strip().split()
        
        if not args or not args[0]:
            params.message = "Usage: packit install [plugin_id] [repository_name] [-r]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        autoRestart = "-r" in args
        if autoRestart:
            args.remove("-r")
        
        if not args:
            params.message = "Usage: packit install [plugin_id] [repository_name] [-r]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        pluginId = args[0]
        repoName = args[1] if len(args) > 1 else None
        
        self.plugin.core.installPlugin(pluginId, repoName, autoRestart)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleUninstall(self, messageText: str, params: Any) -> HookResult:
        cmdUninstall = settings.get("cmd_uninstall", "packit uninstall")
        args = messageText[len(cmdUninstall):].strip().split()
        
        if not args or not args[0]:
            params.message = "Usage: packit uninstall [plugin_id] [-r]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        autoRestart = "-r" in args
        if autoRestart:
            args.remove("-r")
        
        if not args:
            params.message = "Usage: packit uninstall [plugin_id] [-r]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        pluginId = args[0]
        
        self.plugin.core.uninstallPlugin(pluginId, autoRestart)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handlePluginList(self, messageText: str, params: Any) -> HookResult:
        allPlugins = self.plugin.core.getAllPluginsFromCache()
        
        if not allPlugins:
            params.message = "No plugins found in cache. Try: packit update"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        countPlugins = len(allPlugins)
        headerText = f"*Found {countPlugins} plugins*\n"
        
        pluginLines = []
        for plugin in allPlugins:
            displayName = plugin.get("displayName", plugin.get("packId", "Unknown"))
            packId = plugin.get("packId", "unknown")
            version = plugin.get("version", "unknown")
            repoName = plugin.get("repo_name", "unknown")
            
            pluginLines.append(f"*{displayName}* (v{version})\nPackID: `{packId}` | Repo: {repoName}")
        
        listText = "\n\n".join(pluginLines)
        fullText = headerText + listText
        
        try:
            parsedMessage = parse_markdown(fullText)
            
            headerLength = len(f"Found {countPlugins} plugins\n")
            blockquoteStart = headerLength
            blockquoteLength = len(parsedMessage.text) - headerLength
            
            messageParams = {
                "message": parsedMessage.text,
                "peer": params.peer,
                "entities": [],
                "searchLinks": False
            }
            
            for rawEntity in parsedMessage.entities:
                tlrpcEntity = rawEntity.to_tlrpc_object()
                messageParams["entities"].append(tlrpcEntity)
            
            blockquoteEntity = TLRPC.TL_messageEntityBlockquote()
            blockquoteEntity.offset = blockquoteStart
            blockquoteEntity.length = blockquoteLength
            blockquoteEntity.collapsed = True
            messageParams["entities"].append(blockquoteEntity)
            
            send_message(messageParams)
            
        except Exception as e:
            log(f"error sending plugin list: {e}")
            params.message = f"Error: {str(e)}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleRepoList(self, messageText: str, params: Any) -> HookResult:
        repos = [r for r in self.plugin.repoManager.getRepositories() if r.get("enabled")]
        
        if not repos:
            params.message = "No repositories configured"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        totalRepos = len(repos)
        headerText = f"*Total {totalRepos} repositories*\n"
        
        repoLines = []
        for repo in repos:
            repoName = repo.get("name", "Unnamed")
            repoUrl = repo.get("url", "")
            
            if repoUrl:
                repoLines.append(f"[{repoName}]({repoUrl})")
            else:
                repoLines.append(f"*{repoName}*")
        
        listText = "\n".join(repoLines)
        fullText = headerText + listText
        
        try:
            parsedMessage = parse_markdown(fullText)
            
            headerLength = len(f"Total {totalRepos} repositories\n")
            blockquoteStart = headerLength
            blockquoteLength = len(parsedMessage.text) - headerLength
            
            messageParams = {
                "message": parsedMessage.text,
                "peer": params.peer,
                "entities": [],
                "searchLinks": False
            }
            
            for rawEntity in parsedMessage.entities:
                tlrpcEntity = rawEntity.to_tlrpc_object()
                messageParams["entities"].append(tlrpcEntity)
            
            blockquoteEntity = TLRPC.TL_messageEntityBlockquote()
            blockquoteEntity.offset = blockquoteStart
            blockquoteEntity.length = blockquoteLength
            blockquoteEntity.collapsed = True
            messageParams["entities"].append(blockquoteEntity)
            
            send_message(messageParams)
            
        except Exception as e:
            log(f"error sending repo list: {e}")
            params.message = f"Error: {str(e)}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleShare(self, messageText: str, params: Any) -> HookResult:
        cmdShare = settings.get("cmd_share", "packit share")
        args = messageText[len(cmdShare):].strip().split(maxsplit=1)
        
        if not args or not args[0]:
            params.message = "Usage: packit share [plugin_id] [repository_name]"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        pluginId = args[0]
        repoName = args[1] if len(args) > 1 else None
        
        plugin = self.plugin.core.findPlugin(pluginId, repoName)
        
        if not plugin:
            if repoName:
                params.message = f"Plugin '{pluginId}' not found in repository '{repoName}'"
            else:
                params.message = f"Plugin '{pluginId}' not found"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        displayName = plugin.get("displayName", pluginId)
        link = plugin.get("link", "")
        
        if not link:
            params.message = f"Plugin '{displayName}' has no download link"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        if not link.startswith("http"):
            link = f"https://{link}"
        
        shareText = f"*{displayName} shared!*\n\n{link}"
        
        try:
            parsedMessage = parse_markdown(shareText)
            
            messageParams = {
                "message": parsedMessage.text,
                "peer": params.peer,
                "entities": [],
                "searchLinks": False
            }
            
            for rawEntity in parsedMessage.entities:
                tlrpcEntity = rawEntity.to_tlrpc_object()
                messageParams["entities"].append(tlrpcEntity)
            
            send_message(messageParams)
            
        except Exception as e:
            log(f"error sending share: {e}")
            params.message = f"Error: {str(e)}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleUpdate(self, messageText: str, params: Any) -> HookResult:
        self.plugin.core.updateAllRepositories(silent=False)
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleUpgrade(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
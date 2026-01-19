from typing import Any
from base_plugin import HookResult, HookStrategy
from elyx import strings, settings
from client_utils import send_message
from markdown_utils import parse_markdown
from org.telegram.tgnet import TLRPC
from android_utils import log


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
        repoNameFound = plugin.get("repo_name", "unknown")
        
        headerText = f"*{displayName} v{version}*\n[Open raw]({rawUrl})\n\n*Description*\n"
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
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
    
    def _handleInstall(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
    
    def _handleUninstall(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
    
    def _handlePluginList(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
    
    def _handleRepoList(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
    
    def _handleShare(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
    
    def _handleUpdate(self, messageText: str, params: Any) -> HookResult:
        self.plugin.core.updateAllRepositories(silent=False)
        return HookResult(strategy=HookStrategy.CANCEL)
    
    def _handleUpgrade(self, messageText: str, params: Any) -> HookResult:
        params.message = strings.not_ready
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
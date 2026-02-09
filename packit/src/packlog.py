import time
import android_utils

PLUGIN_ID = "shareui_packit"

class packlog:
    
    @staticmethod
    def _getLogsDict():
        if not hasattr(android_utils, "_logs"):
            android_utils._logs = {}
        return android_utils._logs
    
    @staticmethod
    def _getLogsList():
        logsDict = packlog._getLogsDict()
        if PLUGIN_ID not in logsDict:
            logsDict[PLUGIN_ID] = {"logs": [], "cache": None}
        return logsDict[PLUGIN_ID]
    
    @staticmethod
    def _getMaxLogs():
        try:
            from elyx import settings
            maxLogs = settings.get("max_logs_count", 100)
            if isinstance(maxLogs, str):
                maxLogs = int(maxLogs) if maxLogs.strip() else 100
            if maxLogs < 1:
                maxLogs = 100
            return maxLogs
        except:
            return 100
    
    @staticmethod
    def _appendLog(message: str):
        logsData = packlog._getLogsList()
        logsData["logs"].append(message)
        maxLogs = packlog._getMaxLogs()
        if len(logsData["logs"]) > maxLogs:
            logsData["logs"].pop(0)
        logsData["cache"] = "\n".join(logsData["logs"])
    
    @staticmethod
    def info(message: str):
        timestamp = time.strftime("%H:%M:%S")
        packlog._appendLog(f"[{timestamp}] [INFO] {message}")
    
    @staticmethod
    def warn(message: str):
        timestamp = time.strftime("%H:%M:%S")
        packlog._appendLog(f"[{timestamp}] [WARN] {message}")
    
    @staticmethod
    def error(message: str):
        timestamp = time.strftime("%H:%M:%S")
        packlog._appendLog(f"[{timestamp}] [ERROR] {message}")
    
    @staticmethod
    def debug(message: str):
        timestamp = time.strftime("%H:%M:%S")
        packlog._appendLog(f"[{timestamp}] [DEBUG] {message}")
    
    @staticmethod
    def text(message: str):
        packlog._appendLog(message)
    
    @staticmethod
    def clear():
        logsDict = packlog._getLogsDict()
        if PLUGIN_ID in logsDict:
            logsDict[PLUGIN_ID] = {"logs": [], "cache": None}
    
    @staticmethod
    def get():
        logsData = packlog._getLogsList()
        return logsData["cache"]

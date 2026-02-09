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
    def _appendLog(message: str):
        logsDict = packlog._getLogsDict()
        currentLogs = logsDict.get(PLUGIN_ID, "")
        
        if currentLogs:
            logsDict[PLUGIN_ID] = f"{currentLogs}\n{message}"
        else:
            logsDict[PLUGIN_ID] = message
    
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
        logsDict.pop(PLUGIN_ID, None)
    
    @staticmethod
    def get():
        logsDict = packlog._getLogsDict()
        return logsDict.get(PLUGIN_ID, None)
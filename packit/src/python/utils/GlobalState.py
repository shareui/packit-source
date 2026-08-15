# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later



from packutil import logx
class GlobalState:
    _cache = {}

    @classmethod
    def get(cls, key: str, default=None):
        if key not in cls._cache:
            try:
                from elyx import settings
                cls._cache[key] = settings.get(key, default)
            except Exception as e:
                logx(f"GlobalState.get error for {key}: {e}", False)
                return default
        return cls._cache[key]

    @classmethod
    def set(cls, key: str, value):
        cls._cache[key] = value
        try:
            from elyx import settings
            settings.set(key, value)
        except Exception as e:
            logx(f"GlobalState.set error for {key}: {e}", False)

    @classmethod
    def clear(cls):
        cls._cache.clear()

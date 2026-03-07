import os
import json
from datetime import date
from android_utils import log
try:
    from elyx import assets
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import assets failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()


def _get_configs_dir() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache/packitConfigs"


def _get_config_path() -> str:
    return f"{_get_configs_dir()}/localConfig.json"


def _get_cache_dir() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache"


def _get_install_date_path() -> str:
    return f"{_get_configs_dir()}/installDate.json"


def _ensure_install_date():
    path = _get_install_date_path()
    if os.path.exists(path):
        return
    try:
        os.makedirs(_get_configs_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"date": date.today().isoformat()}, f)
        log(f"localConfig: install date recorded: {date.today().isoformat()}")
    except Exception as e:
        log(f"localConfig._ensure_install_date: error: {e}")


def days_since_install() -> int:
    try:
        path = _get_install_date_path()
        if not os.path.exists(path):
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        install = date.fromisoformat(data["date"])
        return (date.today() - install).days
    except Exception as e:
        log(f"localConfig.days_since_install: error: {e}")
        return 0


def _load_asset_defaults() -> dict:
    return json.loads(assets.localConfig.content_string())


class LocalConfig:
    @staticmethod
    def init():
        try:
            _ensure_install_date()
            config_path = _get_config_path()
            defaults = _load_asset_defaults()

            if not os.path.exists(config_path):
                os.makedirs(_get_configs_dir(), exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(assets.localConfig.content_string())
                log(f"localConfig.init: done, final keys={list(defaults.keys())}")
                return

            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            changed = False

            for key, default_value in defaults.items():
                if key not in data:
                    data[key] = default_value
                    changed = True
                elif type(data[key]) is not type(default_value):
                    data[key] = default_value
                    changed = True

            for key in list(data.keys()):
                if key not in defaults:
                    del data[key]
                    changed = True

            if changed:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            log(f"localConfig.init: done, final keys={list(data.keys())}")

        except Exception as e:
            log(f"localConfig.init: error: {e}")

    @staticmethod
    def get(key: str, default=None):
        try:
            with open(_get_config_path(), "r", encoding="utf-8") as f:
                return json.load(f).get(key, default)
        except Exception as e:
            log(f"localConfig.get: error reading '{key}': {e}")
            return default

    @staticmethod
    def set(key: str, value):
        try:
            config_path = _get_config_path()
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data[key] = value
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"localConfig.set: error setting '{key}': {e}")

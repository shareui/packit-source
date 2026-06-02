# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import json
from datetime import date
from android_utils import log
try:
    from elyx import assets
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import assets failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()


def _get_configs_dir() -> str:
    from .paths import getConfigsDir
    return getConfigsDir()


def _get_config_path() -> str:
    return f"{_get_configs_dir()}/localConfig.json"


def _get_cache_dir() -> str:
    from .paths import getCacheRoot
    return getCacheRoot()


def _get_install_date_path() -> str:
    return f"{_get_configs_dir()}/installDate.json"


def _ensure_install_date():
    import time
    path = _get_install_date_path()
    if os.path.exists(path):
        # migrate: add ts field if missing
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "ts" not in data:
                from datetime import datetime
                import base64
                try:
                    date_val = data["date"]
                    try:
                        date_val = base64.b64decode(date_val).decode("utf-8")
                    except Exception:
                        pass
                    data["ts"] = int(datetime.fromisoformat(date_val).timestamp())
                except Exception:
                    data["ts"] = int(time.time())
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                log(f"localConfig: migrated installDate ts={data['ts']}")
        except Exception as e:
            log(f"localConfig._ensure_install_date migrate: {e}")
        return
    try:
        os.makedirs(_get_configs_dir(), exist_ok=True)
        ts = int(time.time())
        import base64
        b64_date = base64.b64encode(date.today().isoformat().encode("utf-8")).decode("utf-8")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"date": b64_date, "ts": ts}, f)
        log(f"localConfig: install date recorded ts={ts}")
    except Exception as e:
        log(f"localConfig._ensure_install_date: error: {e}")


def days_since_install() -> int:
    try:
        path = _get_install_date_path()
        if not os.path.exists(path):
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        import base64
        try:
            date_str = base64.b64decode(data["date"]).decode("utf-8")
        except Exception:
            date_str = data["date"]
        install = date.fromisoformat(date_str)
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
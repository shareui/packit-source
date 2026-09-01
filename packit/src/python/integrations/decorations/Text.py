# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later



# triggers for secret achievements based on sent message text
from packutil import logx
_TRIGGER_TALKING = "ты про себя?"
_TRIGGER_UTILS = "кстати тебя врядли выложат в utilits. ты пофакту, повторил kpm. а как бы в utils правило второй вариант нельзя выкладыватьб"
_TRIGGER_CONNECT = "коннект хуйня"
_TRIGGER_OPSEC = "sudo packit install opsec"


def check_message(text: str):
    if not isinstance(text, str):
        return
    lower = text.lower().strip()
    try:
        from ...ui.achievements.service.AchivementsEngine import unlock_secret
        if lower == _TRIGGER_TALKING:
            unlock_secret("talking_about_you")
        elif lower == _TRIGGER_UTILS:
            unlock_secret("utils_rule")
        elif lower == _TRIGGER_CONNECT:
            unlock_secret("connect_is_bullshit")
        elif lower == _TRIGGER_OPSEC:
            unlock_secret("opsec")
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"[text] check_message error: {e}", False)

from android_utils import log

# triggers for secret achievements based on sent message text
_TRIGGER_TALKING = "ты про себя?"
_TRIGGER_UTILS = "кстати тебя врядли выложат в utilits. ты пофакту, повторил kpm. а как бы в utils правило второй вариант нельзя выкладыватьб"


def check_message(text: str):
    if not isinstance(text, str):
        return
    lower = text.lower().strip()
    try:
        from ..ui.AchievementsActivity.service.AchivementsEngine import unlock_secret
        if lower == _TRIGGER_TALKING:
            unlock_secret("talking_about_you")
        elif lower == _TRIGGER_UTILS:
            unlock_secret("utils_rule")
    except Exception as e:
        log(f"[text] check_message error: {e}")

import os
from android_utils import log
from android.media import MediaPlayer, AudioManager
from elyx import settings
from java import dynamic_proxy


def playSound(soundPath: str) -> None:
    if not settings.get("sfx_enabled", False):
        return

    if not soundPath or not os.path.exists(soundPath):
        log(f"media: sound file not found: {soundPath}")
        return

    player = MediaPlayer()
    try:
        player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        player.setDataSource(soundPath)
        player.prepare()
    except Exception as e:
        log(f"media: failed to prepare player: {e}")
        try:
            player.reset()
            player.release()
        except Exception:
            pass
        return

    try:
        player.start()
    except Exception as e:
        log(f"media: failed to start player: {e}")
        try:
            player.reset()
            player.release()
        except Exception:
            pass
        return

    # release player once playback completes
    class _Listener(dynamic_proxy(MediaPlayer.OnCompletionListener)):
        def onCompletion(self, mp):
            try:
                mp.reset()
                mp.release()
            except Exception:
                pass

    try:
        player.setOnCompletionListener(_Listener())
    except Exception as e:
        log(f"media: failed to set completion listener: {e}")

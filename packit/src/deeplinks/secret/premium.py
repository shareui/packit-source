import os
from android_utils import log
from android.media import MediaPlayer, AudioManager
from java import dynamic_proxy
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()


def handle(url):
    if url != "tg://packit?premium":
        return
    try:
        _playMaxVolume()
        from ...other.achievements import unlock_secret
        unlock_secret("premium")
    except Exception as e:
        log(f"deeplinks.premium: error: {e}")


def _playMaxVolume():
    ctx = ApplicationLoader.applicationContext
    audioManager = ctx.getSystemService("audio")
    maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)

    soundPath = os.path.join(os.path.dirname(__file__), "../../../res/sounds/pocxalko.mp3")

    player = MediaPlayer()
    try:
        player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        player.setDataSource(soundPath)
        player.prepare()
        player.setVolume(1.0, 1.0)
        # set system volume to max for the duration
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, maxVolume, 0)
        player.start()
    except Exception as e:
        log(f"deeplinks.premium: player error: {e}")
        try:
            player.reset()
            player.release()
        except Exception:
            pass
        return

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
        log(f"deeplinks.premium: completion listener error: {e}")

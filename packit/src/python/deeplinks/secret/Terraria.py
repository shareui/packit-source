# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx

from android.media import MediaPlayer, AudioManager
from java import dynamic_proxy
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


def handle(url):
    if url != "tg://packit?terraria":
        return
    try:
        _playMaxVolume()
        logx(f"deeplinks.terraria: calling unlock_secret", True)
        from ...ui.achievements.service.AchivementsEngine import unlock_secret
        unlock_secret("terraria")
        logx(f"deeplinks.terraria: unlock_secret returned", True)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        import traceback
        logx(f"deeplinks.terraria: error: {e}\n{traceback.format_exc()}", False)


def _playMaxVolume():
    ctx = ApplicationLoader.applicationContext
    audioManager = ctx.getSystemService("audio")
    maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)

    from elyx import assets
    soundPath = assets.sounds.terraria.path_str

    player = MediaPlayer()
    try:
        player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        player.setDataSource(soundPath)
        player.prepare()
        player.setVolume(1.0, 1.0)
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, maxVolume, 0)
        player.start()
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"deeplinks.terraria: player error: {e}", False)
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
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"deeplinks.terraria: completion listener error: {e}", False)
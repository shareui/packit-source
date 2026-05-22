# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from android_utils import log
from android.media import MediaPlayer, AudioManager
from java import dynamic_proxy
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()


def handle(url):
    log(f"deeplinks.terraria: handle called, url={url!r}")
    if url != "tg://packit?terraria":
        log(f"deeplinks.terraria: url mismatch, skipping")
        return
    try:
        _playMaxVolume()
        log(f"deeplinks.terraria: calling unlock_secret")
        from ...ui.AchievementsActivity.service.AchivementsEngine import unlock_secret
        unlock_secret("terraria")
        log(f"deeplinks.terraria: unlock_secret returned")
    except Exception as e:
        import traceback
        log(f"deeplinks.terraria: error: {e}\n{traceback.format_exc()}")


def _playMaxVolume():
    ctx = ApplicationLoader.applicationContext
    audioManager = ctx.getSystemService("audio")
    maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)

    soundPath = os.path.join(os.path.dirname(__file__), "../../../res/sounds/terraria.mp3")

    player = MediaPlayer()
    try:
        player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        player.setDataSource(soundPath)
        player.prepare()
        player.setVolume(1.0, 1.0)
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, maxVolume, 0)
        player.start()
    except Exception as e:
        log(f"deeplinks.terraria: player error: {e}")
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
        log(f"deeplinks.terraria: completion listener error: {e}")
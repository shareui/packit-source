# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os

from android.media import MediaPlayer, AudioManager
try:
    from elyx import settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
from java import dynamic_proxy


def playSound(soundPath: str, soundKey: str = None, check_pending: bool = True, default: bool = False) -> None:
    if not settings.get("sfx_enabled", True):
        return
    if soundKey and not settings.get(soundKey, default):
        return

    if check_pending:
        try:
            from ..ui.achievementsactivity.service.AchivementsEngine import is_achievement_pending
            if is_achievement_pending():
                return
        except Exception:
            pass

    if not soundPath or not os.path.exists(soundPath):
        logx(f"media: sound file not found: {soundPath}", True)
        return

    vol_pct = settings.get("sfx_volume", 100)
    try:
        vol = max(0.0, min(1.0, int(vol_pct) / 100.0))
    except Exception:
        vol = 1.0

    player = MediaPlayer()
    try:
        player.setAudioStreamType(AudioManager.STREAM_MUSIC)
        player.setDataSource(soundPath)
        player.prepare()
    except Exception as e:
        logx(f"media: failed to prepare player: {e}", False)
        try:
            player.reset()
            player.release()
        except Exception:
            pass
        return

    try:
        player.setVolume(vol, vol)
        player.start()
    except Exception as e:
        logx(f"media: failed to start player: {e}", False)
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
        logx(f"media: failed to set completion listener: {e}", False)
# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import random
from android_utils import run_on_ui_thread
from android.media import MediaPlayer, AudioManager
from android.widget import FrameLayout, VideoView
from android.view import ViewGroup
from java import dynamic_proxy

_MIN_COUNT = 25
_MAX_COUNT = 30
_MIN_SIZE_DP = 120
_MAX_SIZE_DP = 260

# ms between each video spawn
_SPAWN_DELAY_MS = 80


def handle(url):
    if url != "tg://packit?aytist":
        return
    try:
        from ...ui.AchievementsActivity.service.AchivementsEngine import unlock_secret
        unlock_secret("aytist")
        run_on_ui_thread(_startSpawnChain)
    except Exception as e:
        logx(f"deeplinks.aytist: handle error: {e}", False)


def _dpToPx(act, dp):
    density = act.getResources().getDisplayMetrics().density
    return int(dp * density + 0.5)


def _startSpawnChain():
    try:
        from client_utils import get_last_fragment
        fragment = get_last_fragment()
        if not fragment:
            logx("deeplinks.aytist: no fragment", True)
            return

        act = fragment.getParentActivity()
        if not act:
            logx("deeplinks.aytist: no activity", True)
            return

        decor = act.getWindow().getDecorView()
        metrics = act.getResources().getDisplayMetrics()
        screenW = metrics.widthPixels
        screenH = metrics.heightPixels

        count = random.randint(_MIN_COUNT, _MAX_COUNT)
        logx(f"deeplinks.aytist: spawning {count} videos", True)

        for i in range(count):
            run_on_ui_thread(
                lambda idx=i: _spawnOneVideo(act, decor, screenW, screenH, idx),
                _SPAWN_DELAY_MS * i,
            )
    except Exception as e:
        import traceback
        logx(f"deeplinks.aytist: startSpawnChain error: {e}\n{traceback.format_exc()}", False)


def _getVideoPath() -> str:
    from elyx import assets
    return assets.videos.amethyst.path_str


def _spawnOneVideo(act, decor, screenW, screenH, idx):
    try:
        sizePx = _dpToPx(act, random.randint(_MIN_SIZE_DP, _MAX_SIZE_DP))
        x = float(random.randint(0, max(0, screenW - sizePx)))
        y = float(random.randint(0, max(0, screenH - sizePx)))
        rotation = random.uniform(-180.0, 180.0)

        # container handles position + rotation; VideoView fills it
        container = FrameLayout(act)
        container.setX(x)
        container.setY(y)
        container.setRotation(rotation)

        videoView = VideoView(act)
        container.addView(
            videoView,
            FrameLayout.LayoutParams(sizePx, sizePx),
        )

        videoView.setVideoPath(_getVideoPath())

        class _PreparedListener(dynamic_proxy(MediaPlayer.OnPreparedListener)):
            def onPrepared(self, mp):
                try:
                    mp.setVolume(1.0, 1.0)
                    mp.start()
                except Exception as e:
                    logx(f"deeplinks.aytist: onPrepared error [{idx}]: {e}", False)

        class _CompletionListener(dynamic_proxy(MediaPlayer.OnCompletionListener)):
            def onCompletion(self, mp):
                try:
                    decor.removeView(container)
                except Exception:
                    pass
                try:
                    mp.reset()
                    mp.release()
                except Exception:
                    pass

        videoView.setOnPreparedListener(_PreparedListener())
        videoView.setOnCompletionListener(_CompletionListener())

        lp = ViewGroup.LayoutParams(sizePx, sizePx)
        decor.addView(container, lp)
        videoView.start()
    except Exception as e:
        import traceback
        logx(f"deeplinks.aytist: spawnOneVideo error [{idx}]: {e}\n{traceback.format_exc()}", False)
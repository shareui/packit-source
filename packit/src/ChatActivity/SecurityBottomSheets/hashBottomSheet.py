from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, OnClickListener
from android.widget import ImageView
from elyx import strings
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    log(f"hashBottomSheet: import error: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"hashBottomSheet: import Theme error: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    log(f"hashBottomSheet: import LayoutHelper error: {e}")


from ...utils.hashUtil import hashFile as _computeSha256


def _extractPluginVersion(filePath: str) -> str | None:
    import re
    try:
        with open(filePath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        m = re.search(r'__version__\s*=\s*["\'"]([^"\']+)["\']', source)
        if m:
            return m.group(1)
    except Exception:
        pass

    return None

def _parseVersion(raw: str) -> list:
    import re
    cleaned = re.sub(r"[^\d.]", "", raw)
    return [int(x) for x in cleaned.split(".") if x]


def _extractPluginId(filePath: str) -> str | None:
    import re
    try:
        with open(filePath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        m = re.search(r'__id__\s*=\s*["\'"]([^"\']+)["\']', source)
        if m:
            return m.group(1)
    except Exception:
        pass

    return None

def _loadCachedRepos() -> list:
    import os, json
    result = []
    try:
        from ...utils.paths import getReposCacheDir
        cacheDir = getReposCacheDir()
    except Exception as e:
        log(f"hashBottomSheet: _loadCachedRepos error: {e}")
        return result

    if not os.path.isdir(cacheDir):
        return result

    for fname in os.listdir(cacheDir):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(cacheDir, fname), "r", encoding="utf-8") as f:
                cached = json.load(f)
            pluginsUrl = cached.get("repomap", {}).get("plugins")
            if not pluginsUrl:
                continue
            name = cached.get("repometa", {}).get("rm_name") or fname.replace(".json", "")
            repoId = cached.get("repometa", {}).get("rm_rid") or fname.replace(".json", "")
            result.append((name, pluginsUrl, repoId))
        except Exception as e:
            log(f"hashBottomSheet: error reading cache {fname}: {e}")

    return result


def _getRepoPluginInfo(pluginId: str, pluginsUrl: str) -> dict | None:
    import requests
    r = requests.get(pluginsUrl, timeout=10)
    if r.status_code != 200:
        log(f"hashBottomSheet: HTTP {r.status_code} for {pluginsUrl}")
        return None
    for plugin in r.json().get("plugins", []):
        if plugin.get("id") == pluginId:
            return plugin
    return None


def _installFromRepo(pluginId: str, pluginsUrl: str, repoManager, act):
    from client_utils import run_on_queue
    from android_utils import run_on_ui_thread
    from ui.bulletin import BulletinHelper
    from ui.alert import AlertDialogBuilder
    import requests, os
    try:
        from org.telegram.messenger import ApplicationLoader
        from com.exteragram.messenger.plugins import PluginsController
    except Exception as e:
        log(f"hashBottomSheet: _installFromRepo import error: {e}")
        return

    builder = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
    builder.set_title(strings["sec_hash_downloading"])
    builder.set_cancelable(False)
    dlg = builder.create()
    run_on_ui_thread(lambda: dlg.show())

    def dismissDlg():
        def action():
            try:
                dlg.dismiss()
            except Exception:
                pass
        run_on_ui_thread(action)

    def task():
        try:
            r = requests.get(pluginsUrl, timeout=15)
            if r.status_code != 200:
                dismissDlg()
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings("sec_repo_load_failed", code=r.status_code)))
                return

            plugin = None
            for item in r.json().get("plugins", []):
                if isinstance(item, dict) and item.get("id") == pluginId:
                    plugin = item
                    break

            if not plugin:
                dismissDlg()
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings["sec_plugin_not_in_repo"]))
                return

            url = plugin.get("link") or plugin.get("raw")
            if not url:
                dismissDlg()
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings["sec_plugin_no_link"]))
                return

            from ...utils.paths import getPluginsDir
            pluginsDir = getPluginsDir()
            os.makedirs(pluginsDir, exist_ok=True)
            tempPath = os.path.join(pluginsDir, f".temp_{pluginId}.plugin")

            r2 = requests.get(url, stream=True, timeout=30)
            if r2.status_code != 200:
                dismissDlg()
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings("sec_download_failed", code=r2.status_code)))
                return

            r2.raw.decode_content = True
            with open(tempPath, "wb") as f:
                while True:
                    chunk = r2.raw.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

            dismissDlg()

            def openDialog():
                try:
                    from client_utils import get_last_fragment
                    fragment = get_last_fragment()
                    if not fragment:
                        return
                    PluginsController.getInstance().showInstallDialog(fragment, tempPath, True)
                except Exception as e:
                    log(f"hashBottomSheet: openDialog error: {e}")
                    BulletinHelper.show_error(strings["sec_install_dialog_failed"])

            run_on_ui_thread(openDialog)
        except Exception as e:
            log(f"hashBottomSheet: _installFromRepo error: {e}")
            dismissDlg()
            run_on_ui_thread(lambda: BulletinHelper.show_error(strings["sec_error_occurred"]))

    run_on_queue(task)


# ── UI helpers ────────────────────────────────────────────────────────────────

def _resolveColor(colorKey: str, fallback: int) -> int:
    try:
        return Theme.getColor(getattr(Theme, colorKey))
    except Exception:
        return fallback


def _applyPressScale(view):
    from android.view import MotionEvent, View
    from java import dynamic_proxy

    try:
        class _T(dynamic_proxy(View.OnTouchListener)):
            def __init__(self):
                super().__init__()

            def onTouch(self, v, event):
                try:
                    a = event.getActionMasked()
                    if a == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.95).scaleY(0.95).setDuration(100).start()
                    elif a in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(150).start()
                except Exception:
                    pass
                return False

        view.setOnTouchListener(_T())
    except Exception as e:
        log(f"hashBottomSheet: _applyPressScale error: {e}")


def _makeAccentBtn(act, text: str, onPress, colorKey: str = "key_featuredStickers_addButton",
                   pressedKey: str = "key_featuredStickers_addButtonPressed",
                   textColorKey: str = "key_featuredStickers_buttonText"):
    from android.widget import LinearLayout, FrameLayout, TextView
    from android.view import Gravity
    from android.util import TypedValue

    dp = AndroidUtilities.dp
    wrapper = LinearLayout(act)
    wrapper.setOrientation(LinearLayout.VERTICAL)
    wrapper.setPadding(dp(16), dp(4), dp(16), dp(4))

    btn = FrameLayout(act)
    try:
        base = Theme.getColor(getattr(Theme, colorKey))
        pressed = Theme.getColor(getattr(Theme, pressedKey))
    except Exception:
        base = _resolveColor("key_windowBackgroundWhiteBlueButton", 0xFF1E88E5)
        pressed = base
    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(28), base, pressed))
    btn.setPadding(0, dp(14), 0, dp(14))
    btn.setClickable(True)
    btn.setFocusable(True)

    label = TextView(act)
    label.setText(text)
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    label.setTypeface(AndroidUtilities.bold())
    label.setGravity(Gravity.CENTER)
    try:
        label.setTextColor(Theme.getColor(getattr(Theme, textColorKey)))
    except Exception:
        label.setTextColor(0xFFFFFFFF)
    btn.addView(label, FrameLayout.LayoutParams(-1, -2))

    btn.setOnClickListener(OnClickListener(onPress))
    _applyPressScale(btn)

    wrapper.addView(btn, LinearLayout.LayoutParams(-1, -2))
    return wrapper


def _showErrorSheet(act, msg: str):
    from android.widget import LinearLayout, TextView, FrameLayout
    from android.view import Gravity, View
    from android.util import TypedValue
    from org.telegram.ui.ActionBar import BottomSheet
    from org.telegram.ui.Components import RLottieImageView

    dp = AndroidUtilities.dp

    try:
        sheetRef = [None]

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            root.setBackground(_create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass

        title = TextView(act)
        title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
        try:
            title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title.setTypeface(AndroidUtilities.bold())
        title.setText(strings["sec_hash_comparison_title"])
        title.setGravity(Gravity.CENTER)
        root.addView(title, LinearLayout.LayoutParams(-1, -2))

        title_margin = View(act)
        root.addView(title_margin, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

        # lottie error icon
        try:
            lottie = RLottieImageView(act)
            lottie.setAnimation(R_tg.raw.error, dp(64), dp(64))
            lottie.setAutoRepeat(False)
            lottie.playAnimation()
            lp = LinearLayout.LayoutParams(dp(64), dp(64))
            lp.gravity = Gravity.CENTER_HORIZONTAL
            lp.bottomMargin = dp(12)
            root.addView(lottie, lp)
        except Exception as e:
            log(f"hashBottomSheet: error lottie: {e}")

        tv = TextView(act)
        tv.setText(msg)
        tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        tv.setTextColor(_resolveColor("key_windowBackgroundWhiteGrayText", 0xFF9E9E9E))
        tv.setGravity(Gravity.CENTER_HORIZONTAL)
        lp2 = LinearLayout.LayoutParams(-1, -2)
        lp2.bottomMargin = dp(16)
        root.addView(tv, lp2)

        closeBtn = _create_close_button(act, strings["close_button"])
        
        def on_close(v):
            try:
                sheetRef[0].dismiss()
            except Exception:
                pass
        
        closeBtn.setOnClickListener(OnClickListener(lambda v: on_close(v)))
        _applyPressScale(closeBtn)
        root.addView(closeBtn, LinearLayout.LayoutParams(-1, -2))

        builder = BottomSheet.Builder(act)
        builder.setCustomView(root)
        sheet = builder.create()
        sheetRef[0] = sheet
        sheet.show()
    except Exception as e:
        log(f"hashBottomSheet: _showErrorSheet error: {e}")


def _showResult(act, pluginId: str, localHash: str, localVersion: str | None,
                repoName: str, pluginsUrl: str, repoId: str, repoManager, sheet):
    from ui.alert import AlertDialogBuilder
    from android_utils import run_on_ui_thread
    import threading

    loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
    loading.set_title(strings["sec_hash_checking"])
    loading.set_cancelable(False)
    dlg = loading.create()
    run_on_ui_thread(lambda: dlg.show())

    def work():
        showInstall = False
        state = "match"  # match | mismatch | newer | not_found | error
        msg = ""
        try:
            repoInfo = _getRepoPluginInfo(pluginId, pluginsUrl)
            repoHash = repoInfo.get("hash") if repoInfo else None
            repoVersion = repoInfo.get("version") if repoInfo else None
            log(f"hashBottomSheet: repoHash={repoHash} repoVersion={repoVersion}")

            if repoHash is None:
                state = "not_found"
                msg = strings("sec_hash_not_found", repo=repoName)
            elif repoHash == localHash:
                state = "match"
                msg = strings["sec_hash_match"]
            else:
                showInstall = True
                isNewer = False
                if localVersion and repoVersion:
                    try:
                        isNewer = _parseVersion(localVersion) > _parseVersion(repoVersion)
                    except Exception:
                        pass
                if isNewer:
                    state = "newer"
                    msg = strings["sec_hash_mismatch_newer"]
                else:
                    state = "mismatch"
                    msg = strings["sec_hash_mismatch"]

        except Exception as e:
            log(f"hashBottomSheet: _showResult work error: {e}")
            state = "error"
            msg = f"Error: {e}"

        def show(_state=state, _msg=msg, _showInstall=showInstall):
            try:
                dlg.dismiss()
            except Exception:
                pass
            _showResultSheet(act, _state, _msg, localHash, _showInstall,
                             pluginId, pluginsUrl, repoManager, sheet)

        run_on_ui_thread(show)

    threading.Thread(target=work, daemon=True).start()


def _showResultSheet(act, state: str, msg: str, localHash: str, showInstall: bool,
                     pluginId: str, pluginsUrl: str, repoManager, sheet):
    from android.widget import LinearLayout, TextView, FrameLayout
    from android.view import Gravity, View
    from android.util import TypedValue
    from android.graphics.drawable import GradientDrawable
    from org.telegram.ui.ActionBar import BottomSheet
    from org.telegram.ui.Components import RLottieImageView

    dp = AndroidUtilities.dp

    # state -> (lottie_raw, color_key, fallback_color)
    STATE_STYLE = {
        "match":     ("done",  "key_avatar_nameInMessageGreen", 0xFF43A047),
        "mismatch":  ("error", "key_text_RedBold",                    0xFFE53935),
        "newer":     ("info",  "key_color_orange",                    0xFFFFA726),
        "not_found": ("info",  "key_windowBackgroundWhiteGrayText",   0xFF9E9E9E),
        "error":     ("error", "key_text_RedBold",                    0xFFE53935),
    }

    lottieRaw, colorKey, colorFallback = STATE_STYLE.get(state, STATE_STYLE["error"])
    stateColor = _resolveColor(colorKey, colorFallback)

    try:
        sheetRef = [None]

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            root.setBackground(_create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass

        title = TextView(act)
        title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
        try:
            title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title.setTypeface(AndroidUtilities.bold())
        title.setText(strings["sec_hash_comparison_title"])
        title.setGravity(Gravity.CENTER)
        root.addView(title, LinearLayout.LayoutParams(-1, -2))

        title_margin = View(act)
        root.addView(title_margin, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

        # lottie icon
        try:
            lottie = RLottieImageView(act)
            lottie.setAnimation(getattr(R_tg.raw, lottieRaw), dp(72), dp(72))
            lottie.setAutoRepeat(False)
            lottie.playAnimation()
            lp = LinearLayout.LayoutParams(dp(72), dp(72))
            lp.gravity = Gravity.CENTER_HORIZONTAL
            lp.bottomMargin = dp(10)
            root.addView(lottie, lp)
        except Exception as e:
            log(f"hashBottomSheet: lottie {lottieRaw} error: {e}")

        # status title (larger, black)
        statusTv = TextView(act)
        statusTv.setText(msg)
        statusTv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17 if state == "mismatch" else 15)
        statusTv.setTextColor(_resolveColor("key_windowBackgroundWhiteBlackText", 0xFF212121))
        if state == "mismatch":
            statusTv.setTypeface(AndroidUtilities.bold())
        statusTv.setGravity(Gravity.CENTER_HORIZONTAL)
        lpTitle = LinearLayout.LayoutParams(-1, -2)
        lpTitle.bottomMargin = dp(4) if state == "mismatch" else dp(14)
        root.addView(statusTv, lpTitle)

        # hint line for mismatch only
        if state == "mismatch":
            hintTv = TextView(act)
            hintTv.setText(strings["sec_hash_mismatch_hint"])
            hintTv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            hintTv.setTextColor(_resolveColor("key_dialogTextGray2", 0xFF707070))
            hintTv.setGravity(Gravity.CENTER_HORIZONTAL)
            lpHint = LinearLayout.LayoutParams(-1, -2)
            lpHint.bottomMargin = dp(14)
            root.addView(hintTv, lpHint)

        # hash card
        hashCard = LinearLayout(act)
        hashCard.setOrientation(LinearLayout.VERTICAL)
        hashCard.setPadding(dp(12), dp(10), dp(12), dp(10))
        try:
            r = (stateColor >> 16) & 0xFF
            g = (stateColor >> 8) & 0xFF
            b = stateColor & 0xFF
            gd = GradientDrawable()
            gd.setCornerRadius(dp(10))
            gd.setColor((0x18 << 24) | (r << 16) | (g << 8) | b)
            hashCard.setBackground(gd)
        except Exception:
            pass

        hashLabel = TextView(act)
        hashLabel.setText("SHA-256")
        hashLabel.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        hashLabel.setTypeface(AndroidUtilities.bold())
        hashLabel.setTextColor(stateColor)
        lp3 = LinearLayout.LayoutParams(-1, -2)
        lp3.bottomMargin = dp(4)
        hashCard.addView(hashLabel, lp3)

        hashTv = TextView(act)
        hashTv.setText(localHash)
        hashTv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        hashTv.setTextColor(_resolveColor("key_windowBackgroundWhiteGrayText", 0xFF9E9E9E))
        hashCard.addView(hashTv, LinearLayout.LayoutParams(-1, -2))

        lp4 = LinearLayout.LayoutParams(-1, -2)
        lp4.bottomMargin = dp(16)
        root.addView(hashCard, lp4)

        # buttons
        if showInstall:
            installBtn = _create_close_button(act, strings["sec_install_btn"])
            
            def on_install(v):
                try:
                    sheetRef[0].dismiss()
                except Exception:
                    pass
                _doInstall(sheet, pluginId, pluginsUrl, repoManager, act)
            
            installBtn.setOnClickListener(OnClickListener(lambda v: on_install(v)))
            _applyPressScale(installBtn)
            root.addView(installBtn, LinearLayout.LayoutParams(-1, -2))

        close_margin = View(act)
        root.addView(close_margin, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

        closeBtn = _create_close_button(act, strings["close_button"])
        
        def on_close(v):
            try:
                sheetRef[0].dismiss()
            except Exception:
                pass
        
        closeBtn.setOnClickListener(OnClickListener(lambda v: on_close(v)))
        _applyPressScale(closeBtn)
        root.addView(closeBtn, LinearLayout.LayoutParams(-1, -2))

        builder = BottomSheet.Builder(act)
        builder.setCustomView(root)
        s = builder.create()
        sheetRef[0] = s
        s.show()
    except Exception as e:
        log(f"hashBottomSheet: _showResultSheet error: {e}")


def _doInstall(sheet, pluginId: str, pluginsUrl: str, repoManager, act):
    try:
        sheet.dismiss()
    except Exception as e:
        log(f"hashBottomSheet: sheet dismiss error: {e}")
    _installFromRepo(pluginId, pluginsUrl, repoManager, act)


def _showRepoSelector(act, filePath: str, repoManager, sheet):
    from ui.alert import AlertDialogBuilder
    from android_utils import run_on_ui_thread
    import threading

    loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
    loading.set_title(strings["sec_hash_loading"])
    loading.set_cancelable(False)
    dlg = loading.create()
    run_on_ui_thread(lambda: dlg.show())

    def work():
        try:
            pluginId = _extractPluginId(filePath)
            log(f"hashBottomSheet: pluginId={pluginId}")
            localHash = _computeSha256(filePath)
            log(f"hashBottomSheet: localHash={localHash}")
            localVersion = _extractPluginVersion(filePath)
            log(f"hashBottomSheet: localVersion={localVersion}")
            repos = _loadCachedRepos()
            log(f"hashBottomSheet: repos={[r[0] for r in repos]}")
        except Exception as e:
            log(f"hashBottomSheet: work error: {e}")
            run_on_ui_thread(lambda: dlg.dismiss())
            return

        def show():
            try:
                dlg.dismiss()
            except Exception:
                pass

            if pluginId is None:
                _showErrorSheet(act, strings["sec_hash_no_plugin_id"])
                return

            if not repos:
                _showErrorSheet(act, strings["sec_hash_no_repos"])
                return

            _showRepoSelectorSheet(act, repos, pluginId, localHash, localVersion, repoManager, sheet)

        run_on_ui_thread(show)

    threading.Thread(target=work, daemon=True).start()


def _create_rounded_bg(color):
    from android.graphics.drawable import GradientDrawable
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadii([
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        0, 0, 0, 0
    ])
    bg.setColor(color)
    return bg


def _create_close_button(act, text=None):
    from android.widget import FrameLayout, TextView
    from android.view import Gravity
    from android.util import TypedValue
    
    close_btn = FrameLayout(act)
    try:
        from elyx import strings
        resolvedText = text if text is not None else strings["close_button"]
    except Exception:
        resolvedText = text if text is not None else "Close"
    
    try:
        base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
    except Exception:
        base_color = Theme.getColor(Theme.key_dialogTextBlue)
    try:
        pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
    except Exception:
        pressed_color = base_color
    close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
        AndroidUtilities.dp(28), base_color, pressed_color
    ))
    close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
    close_btn.setClickable(True)
    close_btn.setFocusable(True)
    close_text = TextView(act)
    close_text.setText(resolvedText)
    close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    close_text.setTypeface(AndroidUtilities.bold())
    close_text.setGravity(Gravity.CENTER)
    close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))
    return close_btn


def _showRepoSelectorSheet(act, repos: list, pluginId: str, localHash: str,
                           localVersion: str | None, repoManager, sheet):
    from android.widget import LinearLayout, TextView, FrameLayout
    from android.view import Gravity, View
    from android.util import TypedValue
    from org.telegram.ui.ActionBar import BottomSheet

    dp = AndroidUtilities.dp

    try:
        sheetRef = [None]

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            root.setBackground(_create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception:
            try:
                root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception:
                pass
        title = TextView(act)
        title.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 24)
        try:
            title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title.setTypeface(AndroidUtilities.bold())
        title.setText(strings["sec_select_repo_title"])
        title.setGravity(Gravity.CENTER)
        root.addView(title, LinearLayout.LayoutParams(-1, -2))

        title_margin = View(act)
        root.addView(title_margin, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

        accentColor = _resolveColor("key_featuredStickers_addButton", 0xFF1E88E5)

        for i, (name, pluginsUrl, repoId) in enumerate(repos):
            row = LinearLayout(act)
            row.setOrientation(LinearLayout.HORIZONTAL)
            row.setGravity(Gravity.CENTER_VERTICAL)
            row.setClickable(True)
            row.setFocusable(True)
            row.setPadding(dp(8), dp(10), dp(12), dp(10))

            try:
                row.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    dp(8),
                    Theme.getColor(Theme.key_dialogBackground),
                    Theme.getColor(Theme.key_dialogBackgroundGray)
                ))
            except Exception:
                try:
                    row.setBackground(Theme.createSelectorDrawable(
                        Theme.getColor(Theme.key_listSelector)
                    ))
                except Exception:
                    pass

            # icon
            iconView = ImageView(act)
            try:
                iconView.setImageResource(getattr(R_tg.drawable, "msg_folders"))
            except Exception:
                pass
            iconView.setColorFilter(accentColor)
            iconView.setScaleType(ImageView.ScaleType.CENTER)
            lpIcon = LinearLayout.LayoutParams(dp(24), dp(24))
            lpIcon.rightMargin = dp(14)
            row.addView(iconView, lpIcon)

            # text column: name + @id
            textCol = LinearLayout(act)
            textCol.setOrientation(LinearLayout.VERTICAL)

            nameTv = TextView(act)
            nameTv.setText(name)
            nameTv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            nameTv.setTypeface(AndroidUtilities.bold())
            nameTv.setTextColor(_resolveColor("key_dialogTextBlack", 0xFF212121))
            textCol.addView(nameTv, LinearLayout.LayoutParams(-1, -2))

            idTv = TextView(act)
            idTv.setText(f"@{repoId}")
            idTv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            idTv.setTextColor(_resolveColor("key_dialogTextGray2", 0xFF9E9E9E))
            lpId = LinearLayout.LayoutParams(-1, -2)
            lpId.topMargin = dp(1)
            textCol.addView(idTv, lpId)

            row.addView(textCol, LinearLayout.LayoutParams(0, -2, 1.0))

            # arrow
            arrowView = ImageView(act)
            try:
                arrowView.setImageResource(getattr(R_tg.drawable, "msg_arrowright"))
            except Exception:
                pass
            arrowView.setColorFilter(_resolveColor("key_dialogTextGray2", 0xFF9E9E9E))
            arrowView.setScaleType(ImageView.ScaleType.CENTER)
            row.addView(arrowView, LinearLayout.LayoutParams(dp(16), dp(16)))

            def makeOnClick(n, u, rid):
                def onClick(v):
                    if sheetRef[0]:
                        sheetRef[0].dismiss()
                    _showResult(act, pluginId, localHash, localVersion, n, u, rid, repoManager, sheet)
                return onClick

            row.setOnClickListener(OnClickListener(makeOnClick(name, pluginsUrl, repoId)))
            _applyPressScale(row)

            root.addView(row, LinearLayout.LayoutParams(-1, -2))


        cancel_margin = View(act)
        root.addView(cancel_margin, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(16)))

        cancelBtn = _create_close_button(act, strings["sec_cancel_btn"])

        def on_close(v):
            try:
                sheetRef[0].dismiss()
            except Exception:
                pass

        cancelBtn.setOnClickListener(OnClickListener(lambda v: on_close(v)))
        _applyPressScale(cancelBtn)
        root.addView(cancelBtn, LinearLayout.LayoutParams(-1, -2))

        builder = BottomSheet.Builder(act)
        builder.setCustomView(root)
        s = builder.create()
        sheetRef[0] = s
        s.show()
    except Exception as e:
        log(f"hashBottomSheet: _showRepoSelectorSheet error: {e}")


def _onHashClick(act, filePath: str, repoManager, sheet):
    log(f"hashBottomSheet: _onHashClick filePath={filePath}")
    _showRepoSelector(act, filePath, repoManager, sheet)


_pending: dict = {}
_repoManager = None


class ConstructorHook(MethodHook):

    def before_hooked_method(self, param):
        try:
            install_params = param.args[2]
            filePath = str(install_params.filePath)
            sheet = param.thisObject
            _pending[sheet.hashCode()] = (filePath, _repoManager, sheet)
            log(f"hashBottomSheet: stored filePath={filePath}")
        except Exception as e:
            log(f"hashBottomSheet: ConstructorHook error: {e}")


class SetCustomViewHook(MethodHook):

    def after_hooked_method(self, param):
        try:
            from elyx import settings
            if not settings.get("install_sheet_hash", True):
                return
            sheet = param.thisObject
            className = str(sheet.getClass().getName())
            if "InstallPluginBottomSheet" not in className:
                return

            view = param.args[0]
            if not view:
                log("hashBottomSheet: view is None")
                return

            frame = view.getChildAt(0)
            if not frame:
                log("hashBottomSheet: frame not found")
                return

            stored = _pending.pop(sheet.hashCode(), ("", None, None))
            filePath, _repoManager, _sheet = stored
            log(f"hashBottomSheet: SetCustomViewHook filePath={filePath}")
            act = sheet.getContext()

            hash_btn = ImageView(act)
            try:
                hash_btn.setImageResource(getattr(R_tg.drawable, "msg_sendfile"))
            except Exception as e:
                log(f"hashBottomSheet: msg_sendfile failed: {e}")
                try:
                    hash_btn.setImageResource(getattr(R_tg.drawable, "msg_secret"))
                except Exception as e2:
                    log(f"hashBottomSheet: fallback icon failed: {e2}")

            try:
                hash_btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
            except Exception as e:
                log(f"hashBottomSheet: setColorFilter error: {e}")

            hash_btn.setScaleType(ImageView.ScaleType.CENTER)
            hash_btn.setClickable(True)
            hash_btn.setFocusable(True)
            hash_btn.setOnClickListener(OnClickListener(lambda v: _onHashClick(act, filePath, _repoManager, _sheet)))

            try:
                from org.telegram.ui.Components import ScaleStateListAnimator
                ScaleStateListAnimator.apply(hash_btn, 0.15, 1.5)
            except Exception as e:
                log(f"hashBottomSheet: ScaleStateListAnimator error: {e}")

            try:
                selector_color = Theme.getColor(Theme.key_dialogButtonSelector)
                bg = Theme.createSelectorDrawable(selector_color, 1, AndroidUtilities.dp(20))
                hash_btn.setBackground(bg)
            except Exception as e:
                log(f"hashBottomSheet: setBackground error: {e}")

            lp = LayoutHelper.createFrame(40, 40.0, 53, 0.0, 104.0, 16.0, 0.0)
            frame.addView(hash_btn, lp)
            log("hashBottomSheet: hash_btn added to frame")

        except Exception as e:
            log(f"hashBottomSheet: SetCustomViewHook error: {e}")


def setup_hash_button_hook(plugin, repoManager):
    global _repoManager
    _repoManager = repoManager
    log("hashBottomSheet: setup_hash_button_hook called")
    hooks = []
    try:
        InstallSheet = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet"
        )
        if not InstallSheet:
            log("hashBottomSheet: InstallPluginBottomSheet not found")
            return None

        BaseFragment = find_class("org.telegram.ui.ActionBar.BaseFragment")
        ValidationResult = find_class(
            "com.exteragram.messenger.plugins.PluginsController$PluginValidationResult"
        )
        InstallParams = find_class(
            "com.exteragram.messenger.plugins.ui.components.InstallPluginBottomSheet$PluginInstallParams"
        )
        if ValidationResult and InstallParams:
            constructor = InstallSheet.getClass().getDeclaredConstructor(
                BaseFragment, ValidationResult, InstallParams
            )
            constructor.setAccessible(True)
            hooks.append(plugin.hook_method(constructor, ConstructorHook()))
            log("hashBottomSheet: ConstructorHook registered")
        else:
            log(f"hashBottomSheet: ValidationResult={ValidationResult} InstallParams={InstallParams}")

        BottomSheet = find_class("org.telegram.ui.ActionBar.BottomSheet")
        ViewClass = find_class("android.view.View")
        if BottomSheet and ViewClass:
            method = BottomSheet.getClass().getDeclaredMethod("setCustomView", ViewClass)
            method.setAccessible(True)
            hooks.append(plugin.hook_method(method, SetCustomViewHook()))
            log("hashBottomSheet: SetCustomViewHook registered")
        else:
            log(f"hashBottomSheet: BottomSheet={BottomSheet} ViewClass={ViewClass}")

        log(f"hashBottomSheet: setup done, hooks={len(hooks)}")
        return hooks
    except Exception as e:
        log(f"hashBottomSheet: setup error: {e}")
        return None

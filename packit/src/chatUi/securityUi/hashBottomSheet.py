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


def _computeSha256(filePath: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(filePath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extractPluginVersion(filePath: str) -> str | None:
    import re, zipfile
    try:
        with zipfile.ZipFile(filePath, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".py"):
                    continue
                try:
                    source = zf.read(name).decode("utf-8", errors="replace")
                    m = re.search(r'__version__\s*=\s*["\'"]([^"\']+)["\']', source)
                    if m:
                        return m.group(1)
                except Exception:
                    continue
    except Exception:
        pass

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
    import re, zipfile
    try:
        with zipfile.ZipFile(filePath, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".py"):
                    continue
                try:
                    source = zf.read(name).decode("utf-8", errors="replace")
                    m = re.search(r'__id__\s*=\s*["\']([^"\']+)["\']', source)
                    if m:
                        return m.group(1)
                except Exception:
                    continue
    except Exception:
        pass

    # fallback: plain text plugin
    try:
        with open(filePath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        m = re.search(r'__id__\s*=\s*["\']([^"\']+)["\']', source)
        if m:
            return m.group(1)
    except Exception:
        pass

    return None


def _loadCachedRepos() -> list:
    # returns list of (name, pluginsUrl) for all cached repos that have repomap.plugins
    import os, json
    result = []
    try:
        from org.telegram.messenger import ApplicationLoader
        pkg = ApplicationLoader.applicationContext.getPackageName()
        cacheDir = f"/data/data/{pkg}/files/packitCache"
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

            pkg = ApplicationLoader.applicationContext.getPackageName()
            pluginsDir = f"/data/data/{pkg}/files/plugins"
            os.makedirs(pluginsDir, exist_ok=True)
            tempPath = os.path.join(pluginsDir, f".temp_{pluginId}.plugin")

            r2 = requests.get(url, stream=True, timeout=30)
            if r2.status_code != 200:
                dismissDlg()
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings("sec_download_failed", code=r2.status_code)))
                return

            contentLength = r2.headers.get("content-length")
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


def _showResult(act, pluginId: str, localHash: str, localVersion: str | None, repoName: str, pluginsUrl: str, repoId: str, repoManager, sheet):
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
        msg = ""
        try:
            repoInfo = _getRepoPluginInfo(pluginId, pluginsUrl)
            repoHash = repoInfo.get("hash") if repoInfo else None
            repoVersion = repoInfo.get("version") if repoInfo else None
            log(f"hashBottomSheet: repoHash={repoHash} repoVersion={repoVersion}")

            if repoHash is None:
                msg = strings("sec_hash_not_found", repo=repoName)
            elif repoHash == localHash:
                msg = strings["sec_hash_match"]
            else:
                showInstall = True
                # check if local version is newer than repo version
                isNewer = False
                if localVersion and repoVersion:
                    try:
                        isNewer = _parseVersion(localVersion) > _parseVersion(repoVersion)
                    except Exception:
                        pass

                if isNewer:
                    msg = strings["sec_hash_mismatch_newer"]
                else:
                    msg = strings["sec_hash_mismatch"]

        except Exception as e:
            log(f"hashBottomSheet: _showResult work error: {e}")
            msg = f"Error: {e}"

        def show(_msg=msg, _showInstall=showInstall):
            try:
                dlg.dismiss()
            except Exception:
                pass
            builder = AlertDialogBuilder(act)
            builder.set_title(strings["sec_hash_comparison_title"])
            builder.set_message(_msg)
            builder.set_positive_button(strings["ok_button"], lambda b, w: b.dismiss())
            if _showInstall:
                def onInstall(b, w):
                    b.dismiss()
                    try:
                        sheet.dismiss()
                    except Exception as e:
                        log(f"hashBottomSheet: sheet dismiss error: {e}")
                    _installFromRepo(pluginId, pluginsUrl, repoManager, act)
                builder.set_negative_button(strings["sec_install_btn"], onInstall)
            builder.show()

        run_on_ui_thread(show)

    threading.Thread(target=work, daemon=True).start()


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
                builder = AlertDialogBuilder(act)
                builder.set_title(strings["sec_hash_comparison_title"])
                builder.set_message(strings["sec_hash_no_plugin_id"])
                builder.set_positive_button(strings["ok_button"], lambda b, w: b.dismiss())
                builder.show()
                return

            if not repos:
                builder = AlertDialogBuilder(act)
                builder.set_title(strings["sec_hash_comparison_title"])
                builder.set_message(strings["sec_hash_no_repos"])
                builder.set_positive_button(strings["ok_button"], lambda b, w: b.dismiss())
                builder.show()
                return

            names = [r[0] for r in repos]

            def onRepoSelected(bld, which: int):
                bld.dismiss()
                repoName, pluginsUrl, repoId = repos[which]
                _showResult(act, pluginId, localHash, localVersion, repoName, pluginsUrl, repoId, repoManager, sheet)

            builder = AlertDialogBuilder(act)
            builder.set_title(strings["sec_select_repo_title"])
            builder.set_items(names, onRepoSelected)
            builder.set_negative_button(strings["sec_cancel_btn"], lambda b, w: b.dismiss())
            builder.show()

        run_on_ui_thread(show)

    threading.Thread(target=work, daemon=True).start()


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

            # placed below the policy button (policy: top=60 right=16, this one: top=104 right=16)
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

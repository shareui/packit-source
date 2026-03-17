from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import log, run_on_ui_thread
from urllib.parse import urlparse, parse_qs
from ..core import install_plugin, install_icon_pack
from ..ui.PluginListActivity.fragment import InstallUI
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
import requests
import json
import os

try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

# install&repo=<rm_id>: required: repo — optional: plugin, icon, version
_INSTALL_REQUIRED = {"repo"}
_INSTALL_OPTIONAL = {"plugin", "icon", "version"}
_INSTALL_ALL = _INSTALL_REQUIRED | _INSTALL_OPTIONAL


def _getCachePath(repoId: str) -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache/reposCache/{repoId}.json"


def _findRepo(repoManager, repoId: str) -> dict | None:
    try:
        for r in (repoManager.getRepositories() or []):
            if r.get("id") == repoId:
                return r
    except Exception:
        pass
    return None


def _resolvePluginsUrl(repo: dict) -> str:
    repoId = (repo.get("id") or "").strip()
    fallback = (repo.get("url") or "").strip()
    if not repoId:
        return fallback
    try:
        cachePath = _getCachePath(repoId)
        if os.path.exists(cachePath):
            with open(cachePath, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached.get("repomap", {}).get("plugins") or fallback
    except Exception:
        pass
    return fallback


def handle(url, repoManager):
    try:
        if "install&repo=" not in url:
            if url == "tg://packit?install":
                _handleOpenInstall(repoManager)
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        # exclude the implicit 'install' flag key
        argKeys = {k for k in query.keys() if k != "install"}

        if not _INSTALL_REQUIRED.issubset(argKeys):
            BulletinHelper.show_error(strings.deeplink_too_few_args)
            return

        if not argKeys.issubset(_INSTALL_ALL):
            BulletinHelper.show_error(strings.deeplink_too_many_args)
            return

        repoId = query.get("repo", [""])[0].strip()
        pluginId = query.get("plugin", [""])[0].strip()
        iconId = query.get("icon", [""])[0].strip()
        versionId = query.get("version", [""])[0].strip()

        if not repoId:
            BulletinHelper.show_error(strings.deeplink_too_few_args)
            return

        repo = _findRepo(repoManager, repoId)
        if not repo:
            BulletinHelper.show_error(f"Repository '{repoId}' not found")
            return

        if iconId:
            _handleInstallIconPack(repo, iconId)
            return

        if not pluginId:
            installUI = InstallUI(type("_P", (), {"repoManager": repoManager})())
            installUI._open_repo_plugins(repo)
            return

        _handleInstallPlugin(repo, pluginId, versionId)
    except Exception as e:
        log(f"deeplinks.install: error: {e}")


def _handleOpenInstall(repoManager):
    try:
        class _FakePlugin:
            def __init__(self, rm):
                self.repoManager = rm
        installUI = InstallUI(_FakePlugin(repoManager))
        installUI.open()
    except Exception as e:
        log(f"deeplinks.install: open error: {e}")


def _is_version_ok(min_ver: str) -> bool:
    if not min_ver:
        return True
    try:
        from ..ui.PluginListActivity.fragment import _is_min_version_satisfied
        return _is_min_version_satisfied(min_ver)
    except Exception:
        return True


def _find_best_compatible(plugin: dict) -> dict | None:
    # returns a plugin dict with link/min_version set to best available compatible version
    # checks root version first (newest), then versions dict descending
    from ..ui.PluginActivity.versionPicker import _build_version_entries
    entries = _build_version_entries(plugin)
    for e in entries:
        if _is_version_ok(e["min_version"]):
            result = dict(plugin)
            result["link"] = e["link"]
            if e["min_version"]:
                result["min_version"] = e["min_version"]
            return result
    return None


def _show_incompatible_sheet(requested_version: str, compatible_plugin: dict, all_plugins: list):
    try:
        from client_utils import get_last_fragment
        from android_utils import OnClickListener
        from android.view import Gravity
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from org.telegram.ui.ActionBar import BottomSheet, Theme
        from org.telegram.ui.Components import LayoutHelper
        from org.telegram.messenger import AndroidUtilities
        from ..core import install_plugin

        fragment = get_last_fragment()
        if not fragment:
            return
        act = fragment.getParentActivity()
        if not act:
            return

        sheet = BottomSheet(act, False, fragment.getResourceProvider())

        bg_color = Theme.getColor(Theme.key_dialogBackground)
        text_color = Theme.getColor(Theme.key_dialogTextBlack)
        gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        accent_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(20),
            AndroidUtilities.dp(20), AndroidUtilities.dp(16)
        )
        try:
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setColor(bg_color)
            root.setBackground(bg)
        except Exception:
            root.setBackgroundColor(bg_color)

        title_tv = TextView(act)
        title_tv.setText(str(strings["dl_install_incompatible_sheet_title"]))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title_tv.setTypeface(AndroidUtilities.bold())
        title_tv.setTextColor(text_color)
        title_tv.setGravity(Gravity.CENTER)
        root.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))

        desc_tv = TextView(act)
        desc_tv.setText(str(strings["dl_install_incompatible_sheet_desc"]).format(requested_version))
        desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        desc_tv.setTextColor(gray_color)
        desc_tv.setGravity(Gravity.CENTER)
        root.addView(desc_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        install_btn = FrameLayout(act)
        install_btn.setClickable(True)
        install_btn.setFocusable(True)
        install_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), accent, accent_pressed
        ))
        install_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))

        install_tv = TextView(act)
        install_tv.setText(str(strings["dl_install_incompatible_sheet_btn"]))
        install_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        install_tv.setGravity(Gravity.CENTER)
        try:
            install_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        install_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        install_btn.addView(install_tv, FrameLayout.LayoutParams(-1, -2))

        def _on_install(v, _p=compatible_plugin, _all=all_plugins, _sheet=sheet):
            try:
                _sheet.dismiss()
            except Exception:
                pass
            install_plugin(_p, all_plugins=_all)

        install_btn.setOnClickListener(OnClickListener(_on_install))
        root.addView(install_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

        cancel_btn = FrameLayout(act)
        cancel_btn.setClickable(True)
        cancel_btn.setFocusable(True)
        try:
            import ctypes
            base = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            r2 = (base >> 16) & 0xFF
            g2 = (base >> 8) & 0xFF
            b2 = base & 0xFF
            bg_cancel = ctypes.c_int32((0x22 << 24) | (r2 << 16) | (g2 << 8) | b2).value
            bg_cancel_p = ctypes.c_int32((0x44 << 24) | (r2 << 16) | (g2 << 8) | b2).value
            cancel_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(28), bg_cancel, bg_cancel_p
            ))
        except Exception:
            pass
        cancel_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))

        cancel_tv = TextView(act)
        cancel_tv.setText(str(strings["dl_install_incompatible_sheet_cancel"]))
        cancel_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        cancel_tv.setGravity(Gravity.CENTER)
        cancel_tv.setTextColor(gray_color)
        cancel_btn.addView(cancel_tv, FrameLayout.LayoutParams(-1, -2))

        cancel_btn.setOnClickListener(OnClickListener(lambda v: sheet.dismiss()))
        root.addView(cancel_btn, LayoutHelper.createLinear(-1, -2))

        sheet.setCustomView(root)
        sheet.show()
    except Exception as e:
        log(f"deeplinks.install: incompatible sheet error: {e}")


def _handleInstallPlugin(repo: dict, pluginId: str, versionId: str = ""):
    def task():
        try:
            pluginsUrl = _resolvePluginsUrl(repo)
            if not pluginsUrl:
                run_on_ui_thread(lambda: BulletinHelper.show_error("Repository URL is empty"))
                return

            r = requests.get(pluginsUrl, timeout=15)
            if r.status_code != 200:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Failed to load repository: HTTP {r.status_code}"))
                return

            data = r.json()
            pluginsRaw = data.get("plugins", [])

            plugin = None
            if isinstance(pluginsRaw, dict):
                info = pluginsRaw.get(pluginId)
                if isinstance(info, dict):
                    plugin = {"id": pluginId, **info}
            elif isinstance(pluginsRaw, list):
                for item in pluginsRaw:
                    if isinstance(item, dict) and item.get("id") == pluginId:
                        plugin = item
                        break

            # normalize pluginsRaw to list for all_plugins
            all_plugins = []
            if isinstance(pluginsRaw, dict):
                for pid, info in pluginsRaw.items():
                    if isinstance(info, dict):
                        all_plugins.append({"id": pid, **info})
            elif isinstance(pluginsRaw, list):
                all_plugins = [p for p in pluginsRaw if isinstance(p, dict)]

            if not plugin:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Plugin '{pluginId}' not found"))
                return

            # resolve specific version if requested
            if versionId:
                original_plugin = plugin
                versions = plugin.get("versions") or {}
                if versionId == plugin.get("version"):
                    pass  # already the latest, use plugin as-is
                elif versionId in versions:
                    meta = versions[versionId]
                    link = meta.get("link") or meta.get("raw") or ""
                    if not link:
                        run_on_ui_thread(lambda: BulletinHelper.show_error(f"Version '{versionId}' has no link"))
                        return
                    original_plugin = plugin  # keep original for compatibility search
                    plugin = dict(plugin)
                    plugin["link"] = link
                    if meta.get("min_version"):
                        plugin["min_version"] = meta["min_version"]
                else:
                    run_on_ui_thread(lambda: BulletinHelper.show_error(f"Version '{versionId}' not found"))
                    return

                # check compatibility of resolved version
                min_ver = plugin.get("min_version") or ""
                if not _is_version_ok(min_ver):
                    compatible = _find_best_compatible(original_plugin)
                    if compatible:
                        _v = versionId
                        _c = compatible
                        _all = all_plugins
                        run_on_ui_thread(lambda: _show_incompatible_sheet(_v, _c, _all))
                    else:
                        run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_install_incompatible_all"])))
                    return

            run_on_ui_thread(lambda: install_plugin(plugin, all_plugins=all_plugins))
        except Exception as e:
            log(f"deeplinks.install: fetch error: {e}")
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while loading plugin"))

    run_on_queue(task)


def _resolveIconsUrl(repo: dict) -> str:
    repoId = (repo.get("id") or "").strip()
    fallback = (repo.get("url") or "").strip()
    if not repoId:
        return fallback
    try:
        cachePath = _getCachePath(repoId)
        if os.path.exists(cachePath):
            with open(cachePath, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached.get("repomap", {}).get("icons") or fallback
    except Exception:
        pass
    return fallback


def _handleInstallIconPack(repo: dict, iconId: str):
    def task():
        try:
            iconsUrl = _resolveIconsUrl(repo)
            if not iconsUrl:
                run_on_ui_thread(lambda: BulletinHelper.show_error("Repository URL is empty"))
                return

            r = requests.get(iconsUrl, timeout=15)
            if r.status_code != 200:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Failed to load repository: HTTP {r.status_code}"))
                return

            data = r.json()
            iconsRaw = data.get("icons", [])

            icon = None
            if isinstance(iconsRaw, dict):
                info = iconsRaw.get(iconId)
                if isinstance(info, dict):
                    icon = {"id": iconId, **info}
            elif isinstance(iconsRaw, list):
                for item in iconsRaw:
                    if isinstance(item, dict) and item.get("id") == iconId:
                        icon = item
                        break

            if not icon:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Icon pack '{iconId}' not found"))
                return

            run_on_ui_thread(lambda: install_icon_pack(icon))
        except Exception as e:
            log(f"deeplinks.install: icon fetch error: {e}")
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while loading icon pack"))

    run_on_queue(task)

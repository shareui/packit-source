# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ..utils import CachedRepos
from ..utils.Bulletins import factory as _pbf
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import run_on_ui_thread
from urllib.parse import urlparse, parse_qs
from ..core.Core import install_plugin, install_icon_pack
from ..ui.plugins.Fragment import InstallUI
try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
import requests
import json
import os

try:
    from org.telegram.messenger import ApplicationLoader
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()

# install&repo=<rm_id>: required: repo — optional: plugin, icon, version
_INSTALL_REQUIRED = {"repo"}
_INSTALL_OPTIONAL = {"plugin", "icon", "version"}
_INSTALL_ALL = _INSTALL_REQUIRED | _INSTALL_OPTIONAL


def _findRepo(repoManager, repoId: str) -> dict | None:
    try:
        for r in (repoManager.getRepositories() or []):
            if r.get("id") == repoId:
                return r
    except Exception:
        pass
    return None


def _resolvePluginsUrl(repo: dict) -> str:
    return CachedRepos.plugins_url(repo)


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
            BulletinHelper.show_error(str(strings("dl_repo_not_found", repo_id=repoId)))
            return

        if iconId:
            _handleInstallIconPack(repo, iconId)
            return

        if not pluginId:
            installUI = InstallUI(type("_P", (), {"repoManager": repoManager})())
            installUI._open_repo_plugins(repo)
            return

        _handleInstallPlugin(repo, pluginId, versionId)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"deeplinks.install: error: {e}", False)


def _handleOpenInstall(repoManager):
    try:
        class _FakePlugin:
            def __init__(self, rm):
                self.repoManager = rm
        installUI = InstallUI(_FakePlugin(repoManager))
        installUI.open()
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"deeplinks.install: open error: {e}", False)


def _is_version_ok(app_ver_expr: str) -> bool:
    if not app_ver_expr:
        return True
    try:
        from ..utils.AppVersion import check_app_version
        return check_app_version(app_ver_expr)
    except Exception:
        return True


def _find_best_compatible(plugin: dict) -> dict | None:
    # returns a plugin dict with link/app_version set to best available compatible version
    # checks root version first (newest), then versions dict descending
    from ..ui.plugin.VersionPicker import _build_version_entries
    entries = _build_version_entries(plugin)
    for e in entries:
        if _is_version_ok(e["app_version"]):
            result = dict(plugin)
            result["link"] = e["link"]
            if e["app_version"]:
                result["app_version"] = e["app_version"]
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
        from ..core.Core import install_plugin

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
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"deeplinks.install: incompatible sheet error: {e}", False)


def _handleInstallPlugin(repo: dict, pluginId: str, versionId: str = ""):
    def task():
        try:
            pluginsUrl = _resolvePluginsUrl(repo)
            if not pluginsUrl:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_repo_url_empty"])))
                return

            r = requests.get(pluginsUrl, timeout=15)
            if r.status_code != 200:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_repo_http_error", code=r.status_code))))
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
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_plugin_not_found", plugin_id=pluginId))))
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
                        run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_version_no_link", version_id=versionId))))
                        return
                    original_plugin = plugin  # keep original for compatibility search
                    plugin = dict(plugin)
                    plugin["link"] = link
                    plugin["version"] = versionId
                    if meta.get("app_version"):
                        plugin["app_version"] = meta["app_version"]
                    # old versions have no hash in repo — mark so update checker compares by version
                    plugin["hash"] = "Outdated"
                    plugin["bithash"] = "Outdated"
                else:
                    run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_version_not_found", version_id=versionId))))
                    return

                # check compatibility of resolved version
                app_ver = plugin.get("app_version") or ""
                if not _is_version_ok(app_ver):
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
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"deeplinks.install: fetch error: {e}", False)
            run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_install_error"])))

    if versionId:
        def _show_loading_bulletin():
            try:
                from hook_utils import find_class as _fc
                BulletinFactory = _fc("org.telegram.ui.Components.BulletinFactory")
                R_tg = _fc("org.telegram.messenger.R")
                frag = get_last_fragment()
                container = frag.getParentActivity().getWindow().getDecorView()
                resource_provider = None
                try:
                    resource_provider = frag.getResourceProvider()
                except Exception:
                    pass
                _pbf(container, resource_provider).createSimpleBulletin(
                    R_tg.raw.chats_infotip,
                    str(strings["dl_install_version_loading"]).format(versionId)
                ).show()
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"deeplinks.install: loading bulletin error: {e}", False)
        run_on_ui_thread(_show_loading_bulletin)

    run_on_queue(task)


def _resolveIconsUrl(repo: dict) -> str:
    return CachedRepos.icons_url(repo)


def _handleInstallIconPack(repo: dict, iconId: str):
    def task():
        try:
            iconsUrl = _resolveIconsUrl(repo)
            if not iconsUrl:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_repo_url_empty"])))
                return

            r = requests.get(iconsUrl, timeout=15)
            if r.status_code != 200:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_repo_http_error", code=r.status_code))))
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
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_iconpack_not_found", icon_id=iconId))))
                return

            run_on_ui_thread(lambda: install_icon_pack(icon))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"deeplinks.install: icon fetch error: {e}", False)
            run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_iconpack_load_error"])))

    run_on_queue(task)
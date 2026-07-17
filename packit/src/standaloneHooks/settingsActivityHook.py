# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import ctypes
from android_utils import run_on_ui_thread
from hook_utils import find_class
from base_plugin import MethodHook
from client_utils import get_last_fragment
try:
    from elyx import strings
except Exception as e:
    logx(f"settingsActivityHook: import strings failed: {e}", False)
try:
    from com.exteragram.messenger.plugins import PluginsController
    from com.exteragram.messenger.plugins.ui import PluginSettingsActivity
except Exception as e:
    logx(f"settingsActivityHook: import PluginsController/PSA failed: {e}", False)
try:
    from org.telegram.messenger import R as R_tg
    from org.telegram.ui.Components import UItem
except Exception as e:
    logx(f"settingsActivityHook: import tg classes failed: {e}", False)

# must not collide with existing ids (-1..19 used by SettingsActivity)
_PACKIT_SETTINGS_ID = 880099

# icon bg: #e6d9f5 = rgba(230, 217, 245)
_ICON_BG_COLOR = ctypes.c_int32((0xFF << 24) | (230 << 16) | (217 << 8) | 245).value
# icon fg: #615ea4 = rgba(97, 94, 164)
_ICON_FG_COLOR = ctypes.c_int32((0xFF << 24) | (97 << 16) | (94 << 8) | 164).value

# tag marking the PackIt settings icon so SettingCell.updateColors() (which
# resets the glyph to white on non-Monet themes) can re-apply our tint
_ICON_TAG = "packit_settings_icon"


def _tint_packit_icon(icon_view):
    # re-apply PackIt's glyph color; native updateColors() forces the glyph to
    # white on non-Monet themes, so this runs after both bindView and
    # updateColors. On Monet themes we leave the native themed color.
    try:
        from android.graphics import PorterDuff
        from org.telegram.ui.ActionBar import Theme
        if not Theme.isCurrentThemeMonet():
            icon_view.setColorFilter(_ICON_FG_COLOR, PorterDuff.Mode.SRC_IN)
    except Exception as e:
        logx(f"settingsActivityHook: _tint_packit_icon error: {e}", False)


def setup_settings_activity_hook(plugin):
    hooks = []
    try:
        SA = find_class("org.telegram.ui.SettingsActivity")
        if SA is None:
            logx("settingsActivityHook: SettingsActivity not found", True)
            return hooks

        ArrayList = find_class("java.util.ArrayList")
        UniversalAdapter = find_class("org.telegram.ui.Components.UniversalAdapter")

        if ArrayList is None or UniversalAdapter is None:
            logx("settingsActivityHook: ArrayList or UniversalAdapter not found", True)
            return hooks

        class FillItemsHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    from elyx import settings as elyx_settings
                    if not elyx_settings.get("show_settings_button", True):
                        return

                    items = param.args[0]
                    if items is None or items.size() == 0:
                        return

                    # guard: skip if already inserted
                    for i in range(items.size()):
                        item = items.get(i)
                        try:
                            if item is not None and int(item.id) == _PACKIT_SETTINGS_ID:
                                return
                        except Exception:
                            pass

                    # find exteraGram settings item (id == -1)
                    extera_idx = -1
                    for i in range(items.size()):
                        item = items.get(i)
                        try:
                            if item is not None and int(item.id) == -1:
                                extera_idx = i
                                break
                        except Exception:
                            pass

                    if extera_idx < 0:
                        logx("settingsActivityHook: extera item (id=-1) not found", True)
                        return

                    SettingCellFactory = find_class("org.telegram.ui.SettingsActivity$SettingCell$Factory")
                    if SettingCellFactory is None:
                        logx("settingsActivityHook: SettingCell$Factory not found", True)
                        return

                    icon_id = 0
                    try:
                        icon_id = int(R_tg.drawable.msg_download_remix)
                    except Exception as e:
                        logx(f"settingsActivityHook: icon resolve error: {e}", False)

                    label = str(strings.packit_settings) if hasattr(strings, "packit_settings") else "PackIt Settings"

                    # find of(int, int, int, int, CharSequence) — 5 args
                    of_method = None
                    for m in SettingCellFactory.getClass().getDeclaredMethods():
                        try:
                            if m.getName() == "of" and len(m.getParameterTypes()) == 5:
                                of_method = m
                                break
                        except Exception:
                            pass

                    if of_method is None:
                        logx("settingsActivityHook: SettingCell.Factory.of(5) not found", True)
                        return

                    of_method.setAccessible(True)
                    from java import jint
                    packit_item = of_method.invoke(
                        None,
                        [jint(_PACKIT_SETTINGS_ID), jint(_ICON_BG_COLOR), jint(_ICON_BG_COLOR), jint(icon_id), label]
                    )
                    if packit_item is None:
                        logx("settingsActivityHook: packit_item is None", True)
                        return

                    insert_offset = 1
                    try:
                        from org.telegram.messenger import ApplicationLoader
                        pkg = str(ApplicationLoader.applicationContext.getPackageName())
                        if pkg == "com.radolyn.ayugram":
                            insert_offset = 2
                    except Exception as e:
                        logx(f"settingsActivityHook: package check error: {e}", False)

                    items.add(extera_idx + insert_offset, packit_item)
                except Exception as e:
                    logx(f"settingsActivityHook: FillItemsHook error: {e}", False)

        class OnClickHook(MethodHook):
            def before_hooked_method(self, param):
                try:
                    uItem = param.args[0]
                    if uItem is None:
                        return
                    if int(uItem.id) != _PACKIT_SETTINGS_ID:
                        return

                    param.setResult(None)

                    def open():
                        try:
                            frag = get_last_fragment()
                            plugin_obj = PluginsController.getInstance().plugins.get(plugin.id)
                            if plugin_obj and frag:
                                frag.presentFragment(PluginSettingsActivity(plugin_obj))
                            else:
                                logx(f"settingsActivityHook: plugin_obj={plugin_obj} frag={frag}", True)
                        except Exception as e:
                            logx(f"settingsActivityHook: open settings error: {e}", False)

                    run_on_ui_thread(open)
                except Exception as e:
                    logx(f"settingsActivityHook: OnClickHook error: {e}", False)

        class BindViewHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    uItem = param.args[1]
                    view = param.args[0]
                    icon_view = view.getIconView()
                    if icon_view is None:
                        return
                    is_packit = False
                    try:
                        is_packit = uItem is not None and int(uItem.id) == _PACKIT_SETTINGS_ID
                    except Exception:
                        pass
                    # tag/untag so updateColors() recognises our (recycled) cell
                    try:
                        icon_view.setTag(_ICON_TAG if is_packit else None)
                    except Exception:
                        pass
                    if is_packit:
                        _tint_packit_icon(icon_view)
                except Exception as e:
                    logx(f"settingsActivityHook: BindViewHook error: {e}", False)

        class UpdateColorsHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    cell = param.thisObject
                    icon_view = cell.getIconView()
                    if icon_view is None:
                        return
                    tag = icon_view.getTag()
                    if tag is None or str(tag) != _ICON_TAG:
                        return
                    _tint_packit_icon(icon_view)
                except Exception as e:
                    logx(f"settingsActivityHook: UpdateColorsHook error: {e}", False)

        try:
            fill_method = SA.getClass().getDeclaredMethod("fillItems", ArrayList, UniversalAdapter)
            fill_method.setAccessible(True)
            hooks.append(plugin.hook_method(fill_method, FillItemsHook()))
        except Exception as e:
            logx(f"settingsActivityHook: fillItems hook error: {e}", False)

        try:
            SettingCellFactoryClass = find_class("org.telegram.ui.SettingsActivity$SettingCell$Factory")
            bind_method = None
            if SettingCellFactoryClass is not None:
                for m in SettingCellFactoryClass.getClass().getDeclaredMethods():
                    try:
                        if m.getName() == "bindView" and len(m.getParameterTypes()) == 5:
                            bind_method = m
                            break
                    except Exception:
                        pass
            if bind_method:
                bind_method.setAccessible(True)
                hooks.append(plugin.hook_method(bind_method, BindViewHook()))
        except Exception as e:
            logx(f"settingsActivityHook: bindView hook error: {e}", False)

        try:
            SettingCellClass = find_class("org.telegram.ui.SettingsActivity$SettingCell")
            update_colors_method = None
            if SettingCellClass is not None:
                for m in SettingCellClass.getClass().getDeclaredMethods():
                    try:
                        if m.getName() == "updateColors" and len(m.getParameterTypes()) == 0:
                            update_colors_method = m
                            break
                    except Exception:
                        pass
            if update_colors_method:
                update_colors_method.setAccessible(True)
                hooks.append(plugin.hook_method(update_colors_method, UpdateColorsHook()))
        except Exception as e:
            logx(f"settingsActivityHook: updateColors hook error: {e}", False)

        try:
            click_method = None
            for m in SA.getClass().getDeclaredMethods():
                try:
                    if m.getName() == "onClick" and len(m.getParameterTypes()) == 5:
                        click_method = m
                        break
                except Exception:
                    pass
            if click_method:
                click_method.setAccessible(True)
                hooks.append(plugin.hook_method(click_method, OnClickHook()))
        except Exception as e:
            logx(f"settingsActivityHook: onClick hook error: {e}", False)

    except Exception as e:
        logx(f"settingsActivityHook: setup error: {e}", False)

    return hooks
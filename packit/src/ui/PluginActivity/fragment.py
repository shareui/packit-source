# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
import threading
from android.view import Gravity, View
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView, ImageView, ProgressBar, HorizontalScrollView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class
from java import dynamic_proxy
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import elyx failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import AndroidUtilities failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import UniversalFragment failed: {e}")


def _get_saved_plugins_path() -> str:
    from ...utils.paths import getConfigsDir
    import os
    d = getConfigsDir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "saved_plugins.json")


def _read_saved_plugins() -> list:
    import json, os
    path = _get_saved_plugins_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        log(f"pluginProfile: _read_saved_plugins: {e}")
        return []


def _write_saved_plugins(ids: list):
    import json
    try:
        with open(_get_saved_plugins_path(), "w", encoding="utf-8") as f:
            json.dump(ids, f, ensure_ascii=False)
    except Exception as e:
        log(f"pluginProfile: _write_saved_plugins: {e}")


def _add_actionbar_glow(fv):
    try:
        from android.graphics import Color
        from android.graphics.drawable import GradientDrawable as GD
        bg = Theme.getColor(Theme.key_windowBackgroundGray)
        transparent = Color.argb(0, (bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF)
        glow = GD(GD.Orientation.TOP_BOTTOM, [bg, transparent])
        overlay = FrameLayout(fv.getContext())
        overlay.setBackground(glow)
        overlay.setClickable(False)
        fv.addView(overlay, LayoutHelper.createFrame(-1, 24, 0x30, 0, 0, 0, 0))
    except Exception as e:
        log(f"pluginProfile: _add_actionbar_glow: {e}")


def _add_bottom_glow(fv):
    try:
        from android.graphics import Color
        from android.graphics.drawable import GradientDrawable as GD
        bg = Theme.getColor(Theme.key_windowBackgroundGray)
        transparent = Color.argb(0, (bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF)
        glow = GD(GD.Orientation.BOTTOM_TOP, [bg, transparent])
        overlay = FrameLayout(fv.getContext())
        overlay.setBackground(glow)
        overlay.setClickable(False)
        fv.addView(overlay, LayoutHelper.createFrame(-1, 24, 0x50, 0, 0, 0, 0))
    except Exception as e:
        log(f"pluginProfile: _add_bottom_glow: {e}")

try:
    from org.telegram.messenger.browser import Browser
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import Browser failed: {e}")
    Browser = None
    Uri = None

try:
    from org.telegram.ui.ActionBar import ActionBarPopupWindow
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import ActionBarPopupWindow failed: {e}")
    ActionBarPopupWindow = None

try:
    from androidx.core.content import ContextCompat
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import ContextCompat failed: {e}")
    ContextCompat = None

try:
    from android.graphics.drawable import RippleDrawable
except Exception:
    RippleDrawable = None

try:
    from android.graphics import Color as AColor, PorterDuff
except Exception as e:
    import android_utils as _au; _au.log(f"pluginProfile: import AColor failed: {e}")
    AColor = None
    PorterDuff = None

try:
    from android.content.res import ColorStateList as AColorStateList
except Exception:
    AColorStateList = None




_STICKER_RETRY_DELAY = 1.5
_STICKER_MAX_RETRIES = 5


def _resolve_icon(name):
    try:
        R_tg = find_class("org.telegram.messenger.R")
        return getattr(R_tg.drawable, name)
    except Exception:
        return 0


def _try_load_sticker(iv, icon_str, size_dp):
    try:
        if not icon_str or "/" not in str(icon_str):
            return False
        pack_name, index_str = str(icon_str).split("/", 1)
        sticker_index = int(index_str)
        mdc = MediaDataController.getInstance(0)
        ss = None
        try:
            ss = mdc.getStickerSetByName(pack_name)
        except Exception:
            pass
        if not ss:
            try:
                ss = mdc.getStickerSetByEmojiOrName(pack_name)
            except Exception:
                pass
        if ss and getattr(ss, "documents", None) and ss.documents.size() > sticker_index:
            doc = ss.documents.get(sticker_index)
            iv.setImage(
                ImageLocation.getForDocument(doc),
                f"{size_dp}_{size_dp}",
                None, None, 0, 1
            )
            return True
        try:
            mdc.loadStickersByEmojiOrName(pack_name, False, False)
        except Exception:
            pass
        return False
    except Exception as e:
        log(f"pluginProfile: _try_load_sticker error: {e}")
        return False


def _schedule_sticker_retry(iv, icon_str, size_dp, alive_ref, attempt=0):
    if attempt >= _STICKER_MAX_RETRIES:
        return

    def _retry():
        if not alive_ref[0]:
            return
        loaded = _try_load_sticker(iv, icon_str, size_dp)
        if not loaded:
            _schedule_sticker_retry(iv, icon_str, size_dp, alive_ref, attempt + 1)

    threading.Timer(_STICKER_RETRY_DELAY, lambda: run_on_ui_thread(_retry)).start()


def _make_chip(act, text, color_key):
    try:
        color = Theme.getColor(getattr(Theme, color_key))
    except Exception:
        color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
    text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(AndroidUtilities.dp(6))
    bg.setColor(fill)
    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(text_color)
    tv.setBackground(bg)
    tv.setPadding(
        AndroidUtilities.dp(7), AndroidUtilities.dp(3),
        AndroidUtilities.dp(7), AndroidUtilities.dp(3)
    )
    return tv


def _make_section_header(act, text):
    tv = TextView(act)
    tv.setText(text.upper())
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    tv.setLetterSpacing(0.08)
    try:
        tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        tv.setTypeface(AndroidUtilities.bold())
    return tv


def _make_divider(act):
    v = View(act)
    v.setBackgroundColor(Theme.getColor(Theme.key_divider))
    lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
    lp.topMargin = AndroidUtilities.dp(16)
    lp.bottomMargin = AndroidUtilities.dp(14)
    return v, lp


def _make_card_bg(act, corner=14):
    try:
        base = Theme.getColor(Theme.key_windowBackgroundWhite)
        r = (base >> 16) & 0xFF
        g = (base >> 8) & 0xFF
        b = base & 0xFF
        fill = ctypes.c_int32((0xDD << 24) | (r << 16) | (g << 8) | b).value
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(corner))
        bg.setColor(fill)
        return bg
    except Exception:
        return None



def _pp_fetch_user(user_id, on_done):
    # fetch user by id; calls on_done(user|None) on ui thread
    def _do():
        try:
            from org.telegram.tgnet import TLRPC
            from org.telegram.messenger import UserConfig, MessagesController
            from client_utils import send_request
            account = getattr(UserConfig, 'selectedAccount', 0)
            mc = MessagesController.getInstance(account)
            cached = mc.getUser(user_id)
            if cached is not None and not getattr(cached, 'min', True):
                run_on_ui_thread(lambda: on_done(cached))
                return
            req = TLRPC.TL_users_getUsers()
            inp = TLRPC.TL_inputUser()
            inp.user_id = user_id
            inp.access_hash = 0
            req.id.add(inp)
            def _on_resp(resp, err):
                if err or resp is None:
                    run_on_ui_thread(lambda: on_done(None))
                    return
                user = None
                try:
                    objects = resp.objects
                    if objects.size() > 0:
                        user = objects.get(0)
                        mc.putUser(user, False)
                except Exception as _e:
                    log(f"pluginProfile: _pp_fetch_user putUser error: {_e}")
                run_on_ui_thread(lambda: on_done(user))
            send_request(req, _on_resp)
        except Exception as _e:
            log(f"pluginProfile: _pp_fetch_user outer error: {_e}")
            run_on_ui_thread(lambda: on_done(None))
    from client_utils import run_on_queue
    run_on_queue(_do)


def _pp_get_username(user):
    try:
        usernames = getattr(user, 'usernames', None)
        if usernames is not None:
            size = usernames.size()
            for i in range(size):
                entry = usernames.get(i)
                uname = getattr(entry, 'username', None)
                if uname:
                    return str(uname)
    except Exception:
        pass
    try:
        un = getattr(user, 'username', None)
        if un:
            return str(un)
    except Exception:
        pass
    return None


def _pp_open_profile(act, user_id, username):
    try:
        from android.net import Uri
        from org.telegram.messenger.browser import Browser
        frag = get_last_fragment()
        if not frag:
            return
        if username:
            uri = Uri.parse("https://t.me/" + username)
            Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        else:
            try:
                from android.os import Bundle
                ProfileActivity = find_class("org.telegram.ui.ProfileActivity")
                args = Bundle()
                args.putLong("user_id", int(user_id))
                frag.presentFragment(ProfileActivity(args))
            except Exception as _fe:
                log(f"pluginProfile: _pp_open_profile fallback error: {_fe}")
    except Exception as _e:
        log(f"pluginProfile: _pp_open_profile error: {_e}")


_ROLE_ORDER = {
    "founder":    0,
    "maintainer": 1,
    "developer":  2,
    "designer":   3,
}

_ROLE_COLOR_KEYS = {
    "founder":    "key_color_lightblue",
    "maintainer": "key_color_yellow",
    "developer":  "key_color_blue",
    "designer":   "key_color_green",
}

_ROLE_STRING_KEYS = {
    "founder":    "role_founder",
    "maintainer": "role_maintainer",
    "developer":  "role_developer",
    "designer":   "role_designer",
}


def _sort_team(team):
    def _key(idx_entry):
        idx, entry = idx_entry
        role = str(entry[1]).strip().lower() if len(entry) > 1 else ""
        return (_ROLE_ORDER.get(role, 3), idx)
    return [e for _, e in sorted(enumerate(team), key=_key)]


def _build_team_card(act, root, team):
    # team: list of [user_id_str, role_str]
    try:
        dp = AndroidUtilities.dp

        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        bg = _make_card_bg(act, 18)
        if bg:
            card.setBackground(bg)
        card.setPadding(dp(16), dp(14), dp(16), dp(14))

        card.addView(
            _make_section_header(act, str(strings["contributors"])),
            LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0, 10)
        )

        for entry in _sort_team(team):
            try:
                user_id = int(str(entry[0]))
            except Exception:
                continue

            role_raw = str(entry[1]).strip() if len(entry) > 1 else ""
            role_key = role_raw.lower()
            role_color_key = _ROLE_COLOR_KEYS.get(role_key, "key_windowBackgroundWhiteGrayText")
            role_str_key = _ROLE_STRING_KEYS.get(role_key)
            role_label = str(strings[role_str_key]) if role_str_key else role_raw

            row = LinearLayout(act)
            row.setOrientation(LinearLayout.HORIZONTAL)
            row.setGravity(Gravity.CENTER_VERTICAL)
            row.setPadding(0, dp(8), 0, dp(8))
            row.setMinimumHeight(dp(44))
            row.setClickable(True)
            row.setFocusable(True)
            row.setVisibility(View.GONE)
            try:
                selector = Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2)
                row.setBackground(selector)
            except Exception:
                pass

            img = None
            try:
                img = BackupImageView(act)
                img.setRoundRadius(dp(50))
                row.addView(img, LayoutHelper.createLinear(30, 30, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))
            except Exception:
                img = None

            name_tv = TextView(act)
            name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            try:
                name_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
            except Exception:
                name_tv.setTypeface(AndroidUtilities.bold())
            name_tv.setSingleLine(True)
            name_tv.setHorizontalFadingEdgeEnabled(True)
            name_tv.setFadingEdgeLength(dp(24))
            row.addView(name_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            if role_label:
                role_chip = _make_chip(act, role_label, role_color_key)
                role_chip_lp = LinearLayout.LayoutParams(-2, -2)
                role_chip_lp.leftMargin = dp(8)
                row.addView(role_chip, role_chip_lp)

            card.addView(row, LinearLayout.LayoutParams(-1, -2))

            _username_holder = [None]

            def _make_on_user(r, ntv, im, uh):
                def _on_user(user):
                    try:
                        if user is None:
                            return
                        username = _pp_get_username(user)
                        name = ""
                        try:
                            fn = getattr(user, 'first_name', None)
                            if fn:
                                name = str(fn)
                        except Exception:
                            pass
                        if not name and username:
                            name = "@" + username
                        if not name:
                            return
                        uh[0] = username
                        ntv.setText(name)
                        r.setVisibility(View.VISIBLE)
                    except Exception as _e:
                        log(f"pluginProfile: team _on_user error: {_e}")
                    try:
                        if im is not None and user is not None:
                            from org.telegram.ui.Components import AvatarDrawable
                            avatar_drawable = AvatarDrawable(user)
                            im.setForUserOrChat(user, avatar_drawable)
                    except Exception:
                        pass
                return _on_user

            def _make_click(uid, uh):
                def _on_click(v):
                    _pp_open_profile(act, uid, uh[0])
                return _on_click

            row.setOnClickListener(OnClickListener(_make_click(user_id, _username_holder)))
            _pp_fetch_user(user_id, _make_on_user(row, name_tv, img, _username_holder))

        root.addView(card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))
    except Exception as _e:
        log(f"pluginProfile: _build_team_card error: {_e}")


from .versionPicker import _show_version_picker


def _show_plugin_menu(act, p, anchor_view, repo_id: str = ""):
    try:
        from ..PluginListActivity.service.PluginActions import share_plugin_file, view_plugin_code, download_plugin_file
        from ..PluginListActivity.service.ReportService import report_plugin
        from org.telegram.ui.Components import ItemOptions
        from org.telegram.ui.ActionBar import ActionBarMenuSubItem
        from org.telegram.messenger import R as R_tg, AndroidUtilities
        from java import dynamic_proxy
        from java.lang import Runnable as JRunnable
        from android_utils import OnClickListener

        plugin_id = str(p.get("id") or "")
        version = str(p.get("version") or "")
        rid = repo_id or plugin_id

        def _icon(name):
            return int(getattr(R_tg.drawable, name, 0))

        def _runnable(fn):
            class _R(dynamic_proxy(JRunnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    try:
                        fn()
                    except Exception as _e:
                        log(f"pluginProfile: menu action error: {_e}")
            return _R()

        options = ItemOptions.makeOptions(anchor_view.getRootView(), None, anchor_view, True)

        # swipeback panel for copy link
        # install = no version, install latest = with current version pinned
        def _copy_and_dismiss(link):
            AndroidUtilities.addToClipboard(link)
            options.dismiss()
            try:
                from ...ui.AchievementsActivity.service.AchivementsEngine import increment_category
                increment_category("Copying links")
            except Exception as _ae:
                log(f"pluginProfile: achievement increment error: {_ae}")
            try:
                from hook_utils import find_class as _fc
                BulletinFactory = _fc("org.telegram.ui.Components.BulletinFactory")
                frag = get_last_fragment()
                container = anchor_view.getRootView()
                resource_provider = None
                try:
                    resource_provider = frag.getResourceProvider()
                except Exception:
                    pass
                icon_raw = getattr(R_tg.raw, "copy", getattr(R_tg.raw, "msg_copy", 0))
                BulletinFactory.of(container, resource_provider).createSimpleBulletin(
                    icon_raw,
                    str(strings["link_copied"])
                ).show()
            except Exception as _be:
                log(f"pluginProfile: copy bulletin error: {_be}")

        swipeback = options.makeSwipeback()
        swipeback.add(_icon("ic_ab_back"), str(strings["copy_link_back"]),
                      _runnable(lambda: options.closeSwipeback()))
        swipeback.addGap()
        swipeback.add(_icon("msg_download"), str(strings["copy_link_install"]),
                      _runnable(lambda: _copy_and_dismiss(f"tg://packit?install&repo={rid}&plugin={plugin_id}")))
        swipeback.add(_icon("msg_download"), str(strings["copy_link_install_latest"]),
                      _runnable(lambda: _copy_and_dismiss(f"tg://packit?install&repo={rid}&plugin={plugin_id}&version={version}")))
        swipeback.add(_icon("msg_contacts"), str(strings["copy_link_profile"]),
                      _runnable(lambda: _copy_and_dismiss(f"tg://packit?plugin={plugin_id}&repo={rid}")))

        # copy link row (opens swipeback)
        ctx = options.getContext()
        copy_sub = ActionBarMenuSubItem(ctx, False, False, None)
        copy_sub.setTextAndIcon(str(strings["copy_link"]), _icon("msg_copy"))
        copy_sub.setOnClickListener(OnClickListener(lambda v: options.openSwipeback(swipeback)))
        options.add(copy_sub)

        options.add(_icon("msg_share"),     str(strings["share"]),    _runnable(lambda: share_plugin_file(p, str(p.get("name") or plugin_id), act)))
        options.add(_icon("msg_view_file"), str(strings["code"]),     _runnable(lambda: view_plugin_code(p, act)))
        options.add(_icon("msg_download"),  str(strings["download"]), _runnable(lambda: download_plugin_file(p)))
        options.addGap()
        options.add(_icon("msg_report"),    str(strings["report"]),   Theme.key_text_RedRegular, Theme.key_text_RedRegular,
                    _runnable(lambda: report_plugin(p, act, repo_id=repo_id)))

        options.setSwipebackGravity(True, False)
        options.show()
        log("pluginProfile: _show_plugin_menu shown")
    except Exception as e:
        log(f"pluginProfile: _show_plugin_menu error: {e}")


class PluginProfileFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    _MENU_ID = 1001

    def __init__(self, plugin: dict, install_ui, all_plugins: list, repo_id: str = ""):
        super().__init__()
        self.plugin = plugin
        self.install_ui = install_ui
        self.all_plugins = all_plugins or []
        self.repo_id = repo_id
        self.content_view = None
        self._alive = [True]  # shared ref for sticker retry timers
        self._fragment_ref = [None]  # filled after presentFragment
        self._anchor_ref = [None]   # filled after menu button is created
        log(f"pluginProfile: init plugin={plugin.get('id')}")

    def onFragmentCreate(self, *_):
        log(f"pluginProfile: onFragmentCreate plugin={self.plugin.get('id')}")

    def onFragmentDestroy(self, *_):
        log(f"pluginProfile: onFragmentDestroy plugin={self.plugin.get('id')}")
        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import unregister_bulletin_container
            unregister_bulletin_container(self.content_view)
        except Exception as e:
            log(f"pluginProfile: unregister_bulletin_container error: {e}")
        self._alive[0] = False
        try:
            spinner = getattr(self, '_changelog_spinner', None)
            if spinner:
                try:
                    spinner.stop()
                except Exception:
                    pass
                self._changelog_spinner = None
        except Exception:
            pass
        try:
            if self.content_view is not None:
                parent = self.content_view.getParent()
                log(f"pluginProfile: removeView parent={parent}")
                if parent is not None:
                    parent.removeView(self.content_view)
                self.content_view = None
                log("pluginProfile: content_view removed and nulled")
        except Exception as e:
            log(f"pluginProfile: onFragmentDestroy removeView error: {e}")

    def getTitle(self):
        return str(self.plugin.get("name") or self.plugin.get("id") or strings.pp_unknown_plugin)

    def onBackPressed(self):
        return False

    def afterCreateView(self, v):
        log(f"pluginProfile: afterCreateView v={v}")
        if v is not None:
            _add_actionbar_glow(v)
            _add_bottom_glow(v)
        return None

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, mid):
        log(f"pluginProfile: onMenuItemClick mid={mid} MENU_ID={self._MENU_ID}")
        if mid == -1:
            try:
                frag = self._fragment_ref[0]
                if frag:
                    frag.finishFragment()
                else:
                    fragment = get_last_fragment()
                    if fragment:
                        fragment.finishFragment()
            except Exception as e:
                log(f"pluginProfile: failed to finish fragment: {e}")
            return
        if mid != self._MENU_ID:
            return
        try:
            frag = self._fragment_ref[0]
            anchor = self._anchor_ref[0]
            if not frag or not anchor:
                log("pluginProfile: onMenuItemClick missing frag or anchor")
                return
            act = frag.getParentActivity()
            _show_plugin_menu(act, self.plugin, anchor, repo_id=self.repo_id)
        except Exception as e:
            log(f"pluginProfile: onMenuItemClick error: {e}")

    def beforeCreateView(self):
        log(f"pluginProfile: beforeCreateView plugin={self.plugin.get('id')}")
        if self.content_view is not None:
            try:
                parent = self.content_view.getParent()
                if parent is not None:
                    parent.removeView(self.content_view)
                    log("pluginProfile: beforeCreateView removed stale content_view")
            except Exception as e:
                log(f"pluginProfile: beforeCreateView stale cleanup error: {e}")
            self.content_view = None
        frag = get_last_fragment()
        if not frag:
            log("pluginProfile: beforeCreateView no fragment, aborting")
            return None
        act = frag.getParentActivity()
        if not act:
            log("pluginProfile: beforeCreateView no activity, aborting")
            return None
        p = self.plugin

        bg_color = Theme.getColor(Theme.key_windowBackgroundGray)
        text_color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

        self.content_view = FrameLayout(act)
        self.content_view.setBackgroundColor(bg_color)

        try:
            from ...ui.AchievementsActivity.service.AchivementsEngine import register_bulletin_container
            register_bulletin_container(self.content_view)
        except Exception as e:
            log(f"pluginProfile: register_bulletin_container error: {e}")

        try:
            from extera_utils.classes import Base, java_subclass, joverride
            from android.widget import ScrollView as _SV

            @java_subclass(_SV)
            class _CappedScrollView(Base):
                @joverride()
                def overScrollBy(self, deltaX, deltaY, scrollX, scrollY,
                                 scrollRangeX, scrollRangeY,
                                 maxOverScrollX, maxOverScrollY, isTouchEvent):
                    # hard cap: no more than 8dp overscroll in either direction
                    cap = AndroidUtilities.dp(8)
                    return super().overScrollBy(
                        deltaX, deltaY, scrollX, scrollY,
                        scrollRangeX, scrollRangeY,
                        maxOverScrollX, cap, isTouchEvent
                    )

            _scroll_instance = _CappedScrollView.new_instance(act)
            scroll = _scroll_instance.java
        except Exception:
            scroll = ScrollView(act)
        scroll.setFillViewport(True)
        scroll.setVerticalScrollBarEnabled(False)
        scroll.setOverScrollMode(ScrollView.OVER_SCROLL_IF_CONTENT_SCROLLS)
        scroll.setClipToPadding(False)
        self.content_view.addView(scroll, FrameLayout.LayoutParams(-1, -1))

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), AndroidUtilities.dp(16)
        )
        scroll.addView(root)

        # hero card: [icon | name + meta] / [release_date | install_btn | menu_btn]
        hero = LinearLayout(act)
        hero.setOrientation(LinearLayout.VERTICAL)
        hero.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), AndroidUtilities.dp(16)
        )
        bg = _make_card_bg(act, 18)
        if bg:
            hero.setBackground(bg)

        # top row: icon + name/meta
        top_row = LinearLayout(act)
        top_row.setOrientation(LinearLayout.HORIZONTAL)
        top_row.setGravity(Gravity.CENTER_VERTICAL)

        icon_str = p.get("icon")
        sticker_size = 72
        if icon_str and "/" in str(icon_str):
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(16))
            try:
                iv.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            iv_lp = LinearLayout.LayoutParams(
                AndroidUtilities.dp(sticker_size), AndroidUtilities.dp(sticker_size)
            )
            iv_lp.rightMargin = AndroidUtilities.dp(14)
            top_row.addView(iv, iv_lp)
            if not _try_load_sticker(iv, icon_str, sticker_size):
                _schedule_sticker_retry(iv, icon_str, sticker_size, self._alive)

        info_col = LinearLayout(act)
        info_col.setOrientation(LinearLayout.VERTICAL)
        info_col.setGravity(Gravity.TOP)

        name_tv = TextView(act)
        name_tv.setText(str(p.get("name") or p.get("id") or strings.pp_unknown_name))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        name_tv.setTextColor(text_color)
        name_tv.setSingleLine(True)
        name_tv.setHorizontalFadingEdgeEnabled(True)
        name_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        info_col.addView(name_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 3))

        meta_parts = []
        if p.get("author"):
            meta_parts.append(str(p["author"]))
        if p.get("version"):
            meta_parts.append(f"v{p['version']}")
        if meta_parts:
            meta_tv = TextView(act)
            meta_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            meta_tv.setTextColor(gray_color)
            meta_tv.setSingleLine(True)
            meta_tv.setHorizontalFadingEdgeEnabled(True)
            meta_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                meta_tv.setText(LocaleUtils.fullyFormatText("  ·  ".join(meta_parts)))
                meta_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                meta_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                meta_tv.setText("  ·  ".join(meta_parts))
            info_col.addView(meta_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        # chips: state + size + min_version
        chips_row = LinearLayout(act)
        chips_row.setOrientation(LinearLayout.HORIZONTAL)
        chips_row.setGravity(Gravity.CENTER_VERTICAL)

        _STATE_COLOR_KEYS = {
            "release": "key_color_green",
            "beta":    "key_color_orange",
            "alpha":   "key_color_red",
        }
        state = str(p.get("state") or "").strip().lower()
        if state:
            color_key = _STATE_COLOR_KEYS.get(state, "key_windowBackgroundWhiteGrayText")
            chip = _make_chip(act, state, color_key)
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(4)
            chips_row.addView(chip, chip_lp)

        if p.get("size"):
            chip = _make_chip(act, str(p["size"]), "key_color_cyan")
            chip_lp = LinearLayout.LayoutParams(-2, -2)
            chip_lp.rightMargin = AndroidUtilities.dp(4)
            chips_row.addView(chip, chip_lp)

        if p.get("app_version"):
            chip = _make_chip(act, str(p["app_version"]), "key_avatar_background2Blue")
            chips_row.addView(chip, LinearLayout.LayoutParams(-2, -2))

        if chips_row.getChildCount() > 0:
            info_col.addView(chips_row, LayoutHelper.createLinear(-2, -2))

        top_row.addView(info_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))
        hero.addView(top_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 14))

        # bottom row: release_date chip | spacer | install circle btn | menu circle btn
        bottom_row = LinearLayout(act)
        bottom_row.setOrientation(LinearLayout.HORIZONTAL)
        bottom_row.setGravity(Gravity.TOP)

        # dates column (left) — release date + last updated
        release_date = str(p.get("release_date") or "").strip()
        update_date = str(p.get("update_date") or "").strip()

        def _format_date(raw, prefix):
            # parses DD.MM.YY or DD.MM.YYYY, returns "Prefix: N ago"
            try:
                parts = raw.split(".")
                if len(parts) != 3:
                    return f"{prefix}: {raw}"
                day, month, year_raw = int(parts[0]), int(parts[1]), int(parts[2])
                year = (2000 + year_raw) if year_raw < 100 else year_raw
                from java.util import Calendar
                rel = Calendar.getInstance()
                rel.set(year, month - 1, day, 0, 0, 0)
                rel.set(Calendar.MILLISECOND, 0)
                now = Calendar.getInstance()
                now.set(Calendar.HOUR_OF_DAY, 0)
                now.set(Calendar.MINUTE, 0)
                now.set(Calendar.SECOND, 0)
                now.set(Calendar.MILLISECOND, 0)
                diff_ms = now.getTimeInMillis() - rel.getTimeInMillis()
                diff_days = int(diff_ms // (1000 * 60 * 60 * 24))
                if diff_days < 0:
                    return f"{prefix}: {raw}"
                if diff_days == 0:
                    ago = str(strings["date_ago_today"])
                elif diff_days == 1:
                    ago = str(strings["date_ago_yesterday"])
                elif diff_days < 30:
                    ago = str(strings("date_ago_days", n=diff_days))
                elif diff_days < 365:
                    months = diff_days // 30
                    key = "date_ago_month" if months == 1 else "date_ago_months"
                    ago = str(strings(key, n=months))
                else:
                    years = diff_days // 365
                    key = "date_ago_year" if years == 1 else "date_ago_years"
                    ago = str(strings(key, n=years))
                return f"{prefix}: {ago}"
            except Exception:
                return f"{prefix}: {raw}"

        if release_date or update_date:
            dates_col = LinearLayout(act)
            dates_col.setOrientation(LinearLayout.VERTICAL)
            dates_col.setGravity(Gravity.TOP)

            if release_date:
                date_tv = TextView(act)
                date_tv.setText(_format_date(release_date, str(strings["pp_release_date"])))
                date_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                date_tv.setTextColor(text_color)
                date_tv.setSingleLine(True)
                date_tv.setHorizontalFadingEdgeEnabled(True)
                date_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
                try:
                    date_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    date_tv.setTypeface(AndroidUtilities.bold())
                dates_col.addView(date_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 2))

            effective_update = update_date if update_date else release_date
            if effective_update:
                update_tv = TextView(act)
                update_tv.setText(_format_date(effective_update, str(strings["pp_last_updated"])))
                update_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                update_tv.setTextColor(text_color)
                update_tv.setSingleLine(True)
                update_tv.setHorizontalFadingEdgeEnabled(True)
                update_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
                try:
                    update_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    update_tv.setTypeface(AndroidUtilities.bold())
                dates_col.addView(update_tv, LayoutHelper.createLinear(-1, -2))

            bottom_row.addView(dates_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP))
        else:
            spacer = View(act)
            bottom_row.addView(spacer, LayoutHelper.createLinear(0, 1, 1.0))

        # install circle button
        has_link = bool(p.get("link") or p.get("raw"))
        deps = p.get("deps") or []

        if has_link:
            from ...utils.app_version import check_app_version as _check_app_version
            plugin_app_ver = p.get("app_version")
            is_available = (not plugin_app_ver) or _check_app_version(plugin_app_ver)

            try:
                btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
                btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            except Exception:
                from android.graphics import Color
                btn_base = Color.parseColor("#2196F3")
                btn_pressed = Color.parseColor("#1976D2")

            circle_size = AndroidUtilities.dp(44)

            # read squareFab setting from ExteraConfig
            squareFab = True
            try:
                from hook_utils import find_class as _find_class
                _ExteraConfig = _find_class("com.exteragram.messenger.ExteraConfig")
                raw = _ExteraConfig.squareFab
                squareFab = bool(raw)
                log(f"pluginProfile: squareFab raw={raw} type={type(raw)} bool={squareFab}")
            except Exception as e:
                log(f"pluginProfile: squareFab read error: {e}")

            def _make_fab_bg(color, size_dp, isSquare):
                from android.graphics.drawable import GradientDrawable as _GD
                import math
                bg = _GD()
                if isSquare:
                    bg.setShape(_GD.RECTANGLE)
                    # matches TG formula: ceil(size * 16 / 56)
                    corner = AndroidUtilities.dp(float(math.ceil(size_dp * 16.0 / 56.0)))
                    bg.setCornerRadius(corner)
                else:
                    bg.setShape(_GD.OVAL)
                bg.setColor(color)
                return bg

            install_btn = FrameLayout(act)
            install_btn.setClickable(True)
            install_btn.setFocusable(True)

            if is_available:
                btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                try:
                    install_btn.setBackground(_make_fab_bg(btn_base, 56, squareFab))
                except Exception:
                    pass
            else:
                gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                r = (gray >> 16) & 0xFF
                g = (gray >> 8) & 0xFF
                b = gray & 0xFF
                bg_gray = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                try:
                    install_btn.setBackground(_make_fab_bg(bg_gray, 56, squareFab))
                except Exception:
                    pass
                btn_text_color = gray
                install_btn.setEnabled(False)

            install_label_container = LinearLayout(act)
            install_label_container.setOrientation(LinearLayout.HORIZONTAL)
            install_label_container.setGravity(Gravity.CENTER)
            install_icon = ImageView(act)
            install_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                install_icon.setImageResource(_resolve_icon("msg_download_remix"))
                install_icon.setColorFilter(btn_text_color)
            except Exception:
                pass
            install_label_container.addView(install_icon, LayoutHelper.createLinear(22, 22, Gravity.CENTER))
            install_btn.addView(install_label_container, FrameLayout.LayoutParams(circle_size, circle_size))

            if is_available:
                _install_ui_ref = self.install_ui
                _all_plugins_ref = self.all_plugins

                def _set_loading(_btn, _label, _btn_text_color, _act, isLoading):
                    try:
                        _btn.setEnabled(not isLoading)
                        _btn.removeAllViews()
                        if isLoading:
                            try:
                                from org.telegram.ui.Components import CircularProgressDrawable
                                d = CircularProgressDrawable(_btn_text_color)
                                try:
                                    d.size = float(AndroidUtilities.dp(20))
                                    d.thickness = float(AndroidUtilities.dp(2))
                                except Exception:
                                    pass
                                spinner = ImageView(_act)
                                spinner.setImageDrawable(d)
                                spinner.setScaleType(ImageView.ScaleType.CENTER)
                                spin_lp = FrameLayout.LayoutParams(circle_size, circle_size)
                                spin_lp.gravity = Gravity.CENTER
                                _btn.addView(spinner, spin_lp)
                            except Exception:
                                pb = ProgressBar(_act)
                                try:
                                    pb.setIndeterminate(True)
                                    from android.content.res import ColorStateList
                                    pb.setIndeterminateTintList(ColorStateList.valueOf(_btn_text_color))
                                except Exception:
                                    pass
                                pb_lp = FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                                pb_lp.gravity = Gravity.CENTER
                                _btn.addView(pb, pb_lp)
                        else:
                            _btn.addView(_label, FrameLayout.LayoutParams(circle_size, circle_size))
                    except Exception as e:
                        log(f"pluginProfile: _set_loading error: {e}")

                def _do_install(_p, _install_ui, _all, _btn, _label, _btn_text_color, _act,
                               on_finish_override=None, succ_download=None):
                    from ...core import install_plugin
                    if not on_finish_override:
                        _set_loading(_btn, _label, _btn_text_color, _act, True)

                    def _finish(ok):
                        if ok:
                            try:
                                import os as _os
                                from ...utils.media import playSound
                                _snd = _os.path.join(_os.path.dirname(__file__), "../../../res/sounds/install.opus")
                                playSound(_snd, "sfx_install")
                            except Exception:
                                pass
                        if on_finish_override:
                            run_on_ui_thread(lambda: on_finish_override(ok))

                    def _on_downloaded():
                        if succ_download:
                            succ_download()
                        elif not on_finish_override:
                            import threading as _t
                            log(f"pluginProfile: succ_download received, stopping spinner in 1s")
                            _t.Timer(1.0, lambda: run_on_ui_thread(
                                lambda: _set_loading(_btn, _label, _btn_text_color, _act, False)
                            )).start()

                    install_plugin(_p, on_finish=_finish, install_ui=_install_ui, all_plugins=_all, rm_rid=self.repo_id, succ_download=_on_downloaded)

                _unavail_hint_ref = [None]

                def _show_all_unavail_hint(_btn, _act):
                    try:
                        from org.telegram.ui.Stories.recorder import HintView2
                        from android.text import Layout
                        prev = _unavail_hint_ref[0]
                        if prev is not None:
                            try:
                                prev.hide()
                                prev.getParent().removeView(prev)
                            except Exception:
                                pass
                            _unavail_hint_ref[0] = None
                        dv = _act.getWindow().getDecorView()
                        hint = (
                            HintView2(_btn.getContext(), 3)
                            .setMultilineText(True)
                            .setBgColor(Theme.getColor(Theme.key_undo_background))
                            .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                            .setText(str(strings["plugin_version_below_min"]))
                            .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                            .allowBlur(True)
                            .setRounding(AndroidUtilities.dp(12))
                        )
                        try:
                            hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                        except Exception:
                            pass
                        dv.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                        _unavail_hint_ref[0] = hint
                        def _position():
                            try:
                                btn_loc = [0, 0]
                                _btn.getLocationInWindow(btn_loc)
                                dv_loc = [0, 0]
                                dv.getLocationInWindow(dv_loc)
                                cell_y = btn_loc[1] - dv_loc[1]
                                center_x = float(btn_loc[0] - dv_loc[0]) + float(_btn.getMeasuredWidth()) / 2.0
                                hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                                hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                                hint.setDuration(3500)
                                hint.show()
                            except Exception as e:
                                log(f"pluginProfile: unavail hint position error: {e}")
                        run_on_ui_thread(_position)
                    except Exception as e:
                        log(f"pluginProfile: unavail hint error: {e}")

            # attach install button as FAB in bottom-right of content_view
            fab_size = AndroidUtilities.dp(56)
            fab_margin = AndroidUtilities.dp(16)
            fab_lp = FrameLayout.LayoutParams(fab_size, fab_size)
            fab_lp.gravity = Gravity.BOTTOM | Gravity.END
            fab_lp.rightMargin = fab_margin
            fab_lp.bottomMargin = fab_margin
            # resize the button itself to FAB dimensions
            install_btn.removeAllViews()
            install_label_container2 = LinearLayout(act)
            install_label_container2.setOrientation(LinearLayout.HORIZONTAL)
            install_label_container2.setGravity(Gravity.CENTER)
            install_icon2 = ImageView(act)
            install_icon2.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                install_icon2.setImageResource(_resolve_icon("msg_download_remix"))
                install_icon2.setColorFilter(btn_text_color)
            except Exception:
                pass
            install_label_container2.addView(install_icon2, LayoutHelper.createLinear(26, 26, Gravity.CENTER))
            install_btn.addView(install_label_container2, FrameLayout.LayoutParams(fab_size, fab_size))
            # update _set_loading to use fab_size
            _fab_size_ref = [fab_size]

            def _set_loading_fab(_btn, _label, _btn_text_color, _act, isLoading,
                                 _fab_size_ref=_fab_size_ref):
                try:
                    sz = _fab_size_ref[0]
                    _btn.setEnabled(not isLoading)
                    _btn.removeAllViews()
                    if isLoading:
                        try:
                            from org.telegram.ui.Components import CircularProgressDrawable
                            d = CircularProgressDrawable(_btn_text_color)
                            try:
                                d.size = float(AndroidUtilities.dp(22))
                                d.thickness = float(AndroidUtilities.dp(2))
                            except Exception:
                                pass
                            spinner = ImageView(_act)
                            spinner.setImageDrawable(d)
                            spinner.setScaleType(ImageView.ScaleType.CENTER)
                            spin_lp = FrameLayout.LayoutParams(sz, sz)
                            spin_lp.gravity = Gravity.CENTER
                            _btn.addView(spinner, spin_lp)
                        except Exception:
                            pb = ProgressBar(_act)
                            try:
                                pb.setIndeterminate(True)
                                from android.content.res import ColorStateList
                                pb.setIndeterminateTintList(ColorStateList.valueOf(_btn_text_color))
                            except Exception:
                                pass
                            pb_lp = FrameLayout.LayoutParams(AndroidUtilities.dp(22), AndroidUtilities.dp(22))
                            pb_lp.gravity = Gravity.CENTER
                            _btn.addView(pb, pb_lp)
                    else:
                        _btn.addView(_label, FrameLayout.LayoutParams(sz, sz))
                except Exception as e:
                    log(f"pluginProfile: _set_loading_fab error: {e}")

            # rebind click handler to use fab-aware loader and label
            def onInstallClickFab(v, _p=p, _install_ui=_install_ui_ref, _all=_all_plugins_ref,
                                  _btn=install_btn, _label=install_label_container2,
                                  _btn_text_color=btn_text_color, _act=act):
                versions = _p.get("versions") or {}
                if not versions:
                    _do_install(_p, _install_ui, _all, _btn, _label, _btn_text_color, _act)
                    return
                from ...utils.app_version import check_app_version as _check_app_version2
                from .versionPicker import _build_version_entries
                all_entries = _build_version_entries(_p)
                hide_unavail = False
                try:
                    from elyx import settings as _s
                    hide_unavail = _s.get("hide_unavailable_plugins", False)
                except Exception:
                    pass
                avail = [e for e in all_entries if not e["app_version"] or _check_app_version2(e["app_version"])]
                if hide_unavail and not avail:
                    _show_all_unavail_hint(_btn, _act)
                    return
                if len(avail) == 1 and (hide_unavail or len(all_entries) == 1):
                    e = avail[0]
                    versioned = dict(_p)
                    versioned["link"] = e["link"]
                    if e["app_version"]:
                        versioned["app_version"] = e["app_version"]
                    _do_install(versioned, _install_ui, _all, _btn, _label, _btn_text_color, _act)
                    return
                _show_version_picker(_act, _p, _install_ui, _all, _btn, _label, _btn_text_color, _do_install,
                                     on_cancel=lambda: run_on_ui_thread(
                                         lambda: _set_loading_fab(_btn, _label, _btn_text_color, _act, False)
                                     ), repo_id=self.repo_id)

            install_btn.setOnClickListener(OnClickListener(onInstallClickFab))
            self.content_view.addView(install_btn, fab_lp)
            self._fab_ref = install_btn

            # rebind _do_install so its internal loader uses fab dimensions
            def _do_install(_p, _install_ui, _all, _btn, _label, _btn_text_color, _act,
                            on_finish_override=None, succ_download=None):
                from ...core import install_plugin
                if not on_finish_override:
                    _set_loading_fab(_btn, _label, _btn_text_color, _act, True)

                def _finish(ok):
                    if ok:
                        try:
                            import os as _os
                            from ...utils.media import playSound
                            _snd = _os.path.join(_os.path.dirname(__file__), "../../../res/sounds/install.opus")
                            playSound(_snd, "sfx_install")
                        except Exception:
                            pass
                    if on_finish_override:
                        run_on_ui_thread(lambda: on_finish_override(ok))

                def _on_downloaded():
                    if succ_download:
                        succ_download()
                    elif not on_finish_override:
                        import threading as _t
                        log(f"pluginProfile: succ_download (fab) received, stopping spinner in 1s")
                        _t.Timer(1.0, lambda: run_on_ui_thread(
                            lambda: _set_loading_fab(_btn, _label, _btn_text_color, _act, False)
                        )).start()

                install_plugin(_p, on_finish=_finish, install_ui=_install_ui, all_plugins=_all, rm_rid=self.repo_id, succ_download=_on_downloaded)

        # save circle button (msg_saved icon, yellow when active)
        _save_size = AndroidUtilities.dp(44)
        save_btn_hero = FrameLayout(act)
        save_btn_hero.setClickable(True)
        save_btn_hero.setFocusable(True)

        _plugin_id = str(p.get("id") or "")
        _repo_id_save = self.repo_id or ""

        def _is_saved():
            try:
                return _plugin_id in _read_saved_plugins()
            except Exception:
                return False

        def _make_circle_bg(color):
            try:
                from android.graphics.drawable import GradientDrawable as _GD3
                bg = _GD3()
                bg.setShape(_GD3.OVAL)
                bg.setColor(color)
                return bg
            except Exception:
                return None

        def _gray_fill():
            ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            r = (ic_color >> 16) & 0xFF
            g = (ic_color >> 8) & 0xFF
            b = ic_color & 0xFF
            return ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value

        def _yellow_fill():
            try:
                yc = Theme.getColor(Theme.key_avatar_nameInMessagePink)
                r = (yc >> 16) & 0xFF
                g = (yc >> 8) & 0xFF
                b = yc & 0xFF
                return ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
            except Exception:
                return ctypes.c_int32((0x33 << 24) | (0xFF << 16) | (0xCC << 8) | 0x00).value

        def _apply_save_state(active):
            try:
                fill = _yellow_fill() if active else _gray_fill()
                bg = _make_circle_bg(fill)
                if bg:
                    save_btn_hero.setBackground(bg)
            except Exception as e:
                log(f"pluginProfile: _apply_save_state error: {e}")

        # use RLottieImageView for msg_stories_saved animation
        save_iv_ref = [None]
        try:
            from org.telegram.ui.Components import RLottieImageView
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            anim_id = int(getattr(R_tg.raw, "msg_stories_saved", 0))
            if anim_id:
                lottie_iv = RLottieImageView(act)
                lottie_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                lottie_iv.setAnimation(anim_id, 28, 28)
                lottie_iv.setAutoRepeat(False)
                save_iv_ref[0] = lottie_iv
                save_btn_hero.addView(lottie_iv, FrameLayout.LayoutParams(_save_size, _save_size))
            else:
                raise Exception("anim not found")
        except Exception:
            # fallback to static icon
            save_iv = ImageView(act)
            save_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                save_iv.setImageResource(_resolve_icon("msg_saved"))
            except Exception:
                pass
            save_iv_ref[0] = save_iv
            save_btn_hero.addView(save_iv, FrameLayout.LayoutParams(_save_size, _save_size))

        def _apply_save_color(active):
            try:
                color = Theme.getColor(Theme.key_avatar_nameInMessagePink) if active else Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                iv = save_iv_ref[0]
                if iv is not None:
                    iv.setColorFilter(color)
            except Exception:
                pass

        _apply_save_state(_is_saved())
        _apply_save_color(_is_saved())

        def onSaveClick(v):
            try:
                saved = _read_saved_plugins()
                if _plugin_id in saved:
                    saved.remove(_plugin_id)
                    active = False
                else:
                    saved.append(_plugin_id)
                    active = True
                _write_saved_plugins(saved)
                _apply_save_state(active)
                _apply_save_color(active)
                if active:
                    try:
                        iv = save_iv_ref[0]
                        iv.setProgress(0)
                        iv.playAnimation()
                    except Exception:
                        pass
            except Exception as e:
                log(f"pluginProfile: onSaveClick error: {e}")
        save_btn_hero.setOnClickListener(OnClickListener(onSaveClick))

        save_lp = LinearLayout.LayoutParams(_save_size, _save_size)
        save_lp.rightMargin = AndroidUtilities.dp(8)
        bottom_row.addView(save_btn_hero, save_lp)

        # menu circle button (three dots)
        menu_size = AndroidUtilities.dp(44)
        menu_btn_hero = FrameLayout(act)
        menu_btn_hero.setClickable(True)
        menu_btn_hero.setFocusable(True)
        try:
            ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            r = (ic_color >> 16) & 0xFF
            g = (ic_color >> 8) & 0xFF
            b = ic_color & 0xFF
            ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
            ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
            try:
                from android.graphics.drawable import GradientDrawable as _GD2
                circle_menu_bg = _GD2()
                circle_menu_bg.setShape(_GD2.OVAL)
                circle_menu_bg.setColor(ic_fill)
                menu_btn_hero.setBackground(circle_menu_bg)
            except Exception:
                menu_btn_hero.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(22), ic_fill, ic_pressed
                ))
        except Exception:
            pass
        menu_iv = ImageView(act)
        menu_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        try:
            menu_iv.setImageResource(_resolve_icon("ic_ab_other"))
            menu_iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        menu_btn_hero.addView(menu_iv, FrameLayout.LayoutParams(menu_size, menu_size))

        def onHeroMenuClick(v):
            _show_plugin_menu(act, p, menu_btn_hero, repo_id=self.repo_id)
        menu_btn_hero.setOnClickListener(OnClickListener(onHeroMenuClick))
        bottom_row.addView(menu_btn_hero, LinearLayout.LayoutParams(menu_size, menu_size))

        hero.addView(bottom_row, LayoutHelper.createLinear(-1, -2))

        forked = p.get("forked")
        if isinstance(forked, list) and len(forked) >= 2:
            forked_name = str(forked[0])
            forked_url = str(forked[1])
            forked_raw = str(strings.pp_forked_from).format(name=forked_name, url=forked_url)
            forked_tv = TextView(act)
            forked_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            forked_tv.setTextColor(gray_color)
            forked_tv.setGravity(Gravity.START)
            try:
                forked_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                forked_tv.setTypeface(AndroidUtilities.bold())
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                forked_tv.setText(LocaleUtils.fullyFormatText(forked_raw))
                forked_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                forked_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                forked_tv.setText(forked_raw)
            hero.addView(forked_tv, LayoutHelper.createLinear(-2, -2, Gravity.START, 0, 8, 0, 0))

        # archived banner
        archived_raw = str(p.get("archived") or "").strip()
        if archived_raw:
            def _parse_archived_date(raw):
                try:
                    parts = raw.split(".")
                    if len(parts) != 3:
                        return raw
                    day, month, year_raw = int(parts[0]), int(parts[1]), int(parts[2])
                    year = (2000 + year_raw) if year_raw < 100 else year_raw
                    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    return f"{month_names[month - 1]} {day}, {year}"
                except Exception:
                    return raw

            try:
                archived_color = Theme.getColor(Theme.key_color_yellow)
            except Exception:
                archived_color = 0xFFFFAA00

            ar = (archived_color >> 16) & 0xFF
            ag = (archived_color >> 8) & 0xFF
            ab = archived_color & 0xFF
            archived_bg_color = ctypes.c_int32((0x22 << 24) | (ar << 16) | (ag << 8) | ab).value

            archived_banner = LinearLayout(act)
            archived_banner.setOrientation(LinearLayout.HORIZONTAL)
            archived_banner.setGravity(Gravity.CENTER_VERTICAL)
            archived_banner.setPadding(
                AndroidUtilities.dp(12), AndroidUtilities.dp(10),
                AndroidUtilities.dp(12), AndroidUtilities.dp(10)
            )
            try:
                from android.graphics.drawable import GradientDrawable as _GDA
                arc_bg = _GDA()
                arc_bg.setShape(_GDA.RECTANGLE)
                arc_bg.setCornerRadius(AndroidUtilities.dp(10))
                arc_bg.setColor(archived_bg_color)
                archived_banner.setBackground(arc_bg)
            except Exception:
                pass

            arc_icon = ImageView(act)
            arc_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                arc_icon.setImageResource(_resolve_icon("msg_archive"))
                arc_icon.setColorFilter(archived_color)
            except Exception:
                pass
            archived_banner.addView(arc_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 10, 0))

            arc_tv = TextView(act)
            arc_tv.setText(str(strings("pp_archived_text", date=_parse_archived_date(archived_raw))))
            arc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            arc_tv.setTextColor(archived_color)
            try:
                arc_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                arc_tv.setTypeface(AndroidUtilities.bold())
            arc_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
            archived_banner.addView(arc_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            _unavail_archived_hint_ref = [None]

            def onArchivedClick(v):
                try:
                    from org.telegram.ui.Stories.recorder import HintView2
                    from android.text import Layout
                    prev = _unavail_archived_hint_ref[0]
                    if prev is not None:
                        try:
                            prev.hide()
                            prev.getParent().removeView(prev)
                        except Exception:
                            pass
                        _unavail_archived_hint_ref[0] = None
                    dv = act.getWindow().getDecorView()
                    hint = (
                        HintView2(v.getContext(), 3)
                        .setMultilineText(True)
                        .setBgColor(Theme.getColor(Theme.key_undo_background))
                        .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                        .setText(str(strings["pp_archived_hint"]))
                        .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                        .allowBlur(True)
                        .setRounding(AndroidUtilities.dp(12))
                    )
                    try:
                        hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                    except Exception:
                        pass
                    dv.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                    _unavail_archived_hint_ref[0] = hint
                    def _position():
                        try:
                            loc = [0, 0]
                            v.getLocationInWindow(loc)
                            dv_loc = [0, 0]
                            dv.getLocationInWindow(dv_loc)
                            cell_y = loc[1] - dv_loc[1]
                            center_x = float(loc[0] - dv_loc[0]) + float(v.getMeasuredWidth()) / 2.0
                            hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                            hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                            hint.setDuration(3500)
                            hint.show()
                        except Exception as e:
                            log(f"pluginProfile: archived hint position error: {e}")
                    run_on_ui_thread(_position)
                except Exception as e:
                    log(f"pluginProfile: archived hint error: {e}")

            archived_banner.setClickable(True)
            archived_banner.setFocusable(True)
            archived_banner.setOnClickListener(OnClickListener(onArchivedClick))

            hero.addView(archived_banner, LayoutHelper.createLinear(-1, -2, 0, 12, 0, 0))

        # closed_source banner
        if p.get("closed_source") is True:
            try:
                cs_color = Theme.getColor(Theme.key_color_red)
            except Exception:
                cs_color = 0xFFE53935
            cs_r = (cs_color >> 16) & 0xFF
            cs_g = (cs_color >> 8) & 0xFF
            cs_b = cs_color & 0xFF
            cs_bg_color = ctypes.c_int32((0x22 << 24) | (cs_r << 16) | (cs_g << 8) | cs_b).value

            cs_banner = LinearLayout(act)
            cs_banner.setOrientation(LinearLayout.HORIZONTAL)
            cs_banner.setGravity(Gravity.CENTER_VERTICAL)
            cs_banner.setPadding(
                AndroidUtilities.dp(12), AndroidUtilities.dp(10),
                AndroidUtilities.dp(12), AndroidUtilities.dp(10)
            )
            try:
                from android.graphics.drawable import GradientDrawable as _GDC
                cs_bg = _GDC()
                cs_bg.setShape(_GDC.RECTANGLE)
                cs_bg.setCornerRadius(AndroidUtilities.dp(10))
                cs_bg.setColor(cs_bg_color)
                cs_banner.setBackground(cs_bg)
            except Exception:
                pass

            cs_icon = ImageView(act)
            cs_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                cs_icon.setImageResource(_resolve_icon("msg_secret"))
                cs_icon.setColorFilter(cs_color)
            except Exception:
                pass
            cs_banner.addView(cs_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 10, 0))

            cs_tv = TextView(act)
            cs_tv.setText(str(strings["pp_closed_source_text"]))
            cs_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            cs_tv.setTextColor(cs_color)
            try:
                cs_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                cs_tv.setTypeface(AndroidUtilities.bold())
            cs_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
            cs_banner.addView(cs_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            hero.addView(cs_banner, LayoutHelper.createLinear(-1, -2, 0, 12, 0, 0))

        # paid banner
        if p.get("paid") is True:
            try:
                pd_color = Theme.getColor(Theme.key_color_green)
            except Exception:
                pd_color = 0xFF43A047
            pd_r = (pd_color >> 16) & 0xFF
            pd_g = (pd_color >> 8) & 0xFF
            pd_b = pd_color & 0xFF
            pd_bg_color = ctypes.c_int32((0x22 << 24) | (pd_r << 16) | (pd_g << 8) | pd_b).value

            pd_banner = LinearLayout(act)
            pd_banner.setOrientation(LinearLayout.HORIZONTAL)
            pd_banner.setGravity(Gravity.CENTER_VERTICAL)
            pd_banner.setPadding(
                AndroidUtilities.dp(12), AndroidUtilities.dp(10),
                AndroidUtilities.dp(12), AndroidUtilities.dp(10)
            )
            try:
                from android.graphics.drawable import GradientDrawable as _GDP
                pd_bg = _GDP()
                pd_bg.setShape(_GDP.RECTANGLE)
                pd_bg.setCornerRadius(AndroidUtilities.dp(10))
                pd_bg.setColor(pd_bg_color)
                pd_banner.setBackground(pd_bg)
            except Exception:
                pass

            pd_icon = ImageView(act)
            pd_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                pd_icon.setImageResource(_resolve_icon("menu_feature_paid"))
                pd_icon.setColorFilter(pd_color)
            except Exception:
                pass
            pd_banner.addView(pd_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 10, 0))

            pd_tv = TextView(act)
            pd_tv.setText(str(strings["pp_paid_text"]))
            pd_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            pd_tv.setTextColor(pd_color)
            try:
                pd_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                pd_tv.setTypeface(AndroidUtilities.bold())
            pd_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
            pd_banner.addView(pd_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            hero.addView(pd_banner, LayoutHelper.createLinear(-1, -2, 0, 12, 0, 0))

        root.addView(hero, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # tab bar + tab content
        tab_names = [
            str(strings.pp_tab_description),
            str(strings.pp_tab_gallery),
            str(strings.pp_tab_changes),
        ]
        selected_tab = [0]

        # tab bar: FrameLayout with sliding indicator behind tab text
        tab_bar_frame = FrameLayout(act)
        tab_bar_bg = GradientDrawable()
        tab_bar_bg.setShape(GradientDrawable.RECTANGLE)
        tab_bar_bg.setCornerRadius(AndroidUtilities.dp(20))
        try:
            base = Theme.getColor(Theme.key_windowBackgroundWhite)
            r_c = (base >> 16) & 0xFF
            g_c = (base >> 8) & 0xFF
            b_c = base & 0xFF
            tab_bar_fill = ctypes.c_int32((0xDD << 24) | (r_c << 16) | (g_c << 8) | b_c).value
        except Exception:
            tab_bar_fill = 0xDD2A2A2A
        tab_bar_bg.setColor(tab_bar_fill)
        tab_bar_frame.setBackground(tab_bar_bg)
        tab_bar_frame.setPadding(
            AndroidUtilities.dp(4), AndroidUtilities.dp(4),
            AndroidUtilities.dp(4), AndroidUtilities.dp(4)
        )

        # sliding indicator
        accent_c = Theme.getColor(Theme.key_featuredStickers_addButton)
        r_a = (accent_c >> 16) & 0xFF
        g_a = (accent_c >> 8) & 0xFF
        b_a = accent_c & 0xFF
        ind_fill = ctypes.c_int32((0x33 << 24) | (r_a << 16) | (g_a << 8) | b_a).value
        ind_bg = GradientDrawable()
        ind_bg.setShape(GradientDrawable.RECTANGLE)
        ind_bg.setCornerRadius(AndroidUtilities.dp(16))
        ind_bg.setColor(ind_fill)
        indicator = View(act)
        indicator.setBackground(ind_bg)
        # height = tab text height: padding top+bottom + ~14sp text
        _ind_h = AndroidUtilities.dp(8 + 8) + AndroidUtilities.dp(14) + AndroidUtilities.dp(4)
        indicator_lp = FrameLayout.LayoutParams(0, _ind_h)
        indicator_lp.gravity = Gravity.CENTER_VERTICAL
        tab_bar_frame.addView(indicator, indicator_lp)

        tab_bar = LinearLayout(act)
        tab_bar.setOrientation(LinearLayout.HORIZONTAL)
        tab_bar_frame.addView(tab_bar, FrameLayout.LayoutParams(-1, -2))

        # tab content card (swapped on tab click)
        tab_content = LinearLayout(act)
        tab_content.setOrientation(LinearLayout.VERTICAL)
        tab_content_bg = _make_card_bg(act)
        if tab_content_bg:
            tab_content.setBackground(tab_content_bg)
        tab_content.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(14),
            AndroidUtilities.dp(16), AndroidUtilities.dp(14)
        )

        desc = self._get_localized_description(p)
        readme_url = str(p.get("readme") or "").strip()

        def _make_icon_btn(icon_name):
            btn = FrameLayout(act)
            btn.setClickable(True)
            btn.setFocusable(True)
            try:
                ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                r = (ic_color >> 16) & 0xFF
                g = (ic_color >> 8) & 0xFF
                b = ic_color & 0xFF
                ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(8), ic_fill, ic_pressed
                ))
            except Exception:
                pass
            btn.setPadding(
                AndroidUtilities.dp(6), AndroidUtilities.dp(4),
                AndroidUtilities.dp(6), AndroidUtilities.dp(4)
            )
            iv = ImageView(act)
            iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            try:
                iv.setImageResource(_resolve_icon(icon_name))
                iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass
            btn.addView(iv, FrameLayout.LayoutParams(
                AndroidUtilities.dp(16), AndroidUtilities.dp(16)
            ))
            return btn

        def _build_desc_content():
            wrap = LinearLayout(act)
            wrap.setOrientation(LinearLayout.VERTICAL)

            show_extended = False
            try:
                from elyx import settings as _s
                show_extended = _s.get("show_extended_desc", False)
            except Exception:
                pass

            use_extended = show_extended and bool(readme_url)

            desc_header_row = LinearLayout(act)
            desc_header_row.setOrientation(LinearLayout.HORIZONTAL)
            desc_header_row.setGravity(Gravity.CENTER_VERTICAL)
            header_label = str(strings.pp_section_extended_description) if use_extended else str(strings.pp_section_description)
            desc_header_row.addView(
                _make_section_header(act, header_label),
                LayoutHelper.createLinear(0, -2, 1.0)
            )

            wrap.addView(desc_header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))

            if use_extended:
                # show spinner + async loaded readme content
                spinner_frame = FrameLayout(act)
                try:
                    from org.telegram.ui.Components import CircularProgressDrawable
                    spin_color = Theme.getColor(Theme.key_featuredStickers_addButton)
                    d = CircularProgressDrawable(spin_color)
                    try:
                        d.size = float(AndroidUtilities.dp(24))
                        d.thickness = float(AndroidUtilities.dp(2))
                    except Exception:
                        pass
                    self._changelog_spinner = d
                    spin_iv = ImageView(act)
                    spin_iv.setImageDrawable(d)
                    spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                    spinner_frame.addView(spin_iv, LayoutHelper.createFrame(32, 32, Gravity.CENTER, 0, 8, 0, 8))
                except Exception:
                    pass
                wrap.addView(spinner_frame, LayoutHelper.createLinear(-1, -2))

                content_tv = TextView(act)
                content_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                content_tv.setVisibility(View.GONE)
                wrap.addView(content_tv, LayoutHelper.createLinear(-1, -2))

                # shared ref: filled after fetch completes, used by translate button
                fetched_readme = [""]

                def _show_readme_text(text, centered=False):
                    spinner_frame.setVisibility(View.GONE)
                    content_tv.setVisibility(View.VISIBLE)
                    if centered:
                        content_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                        content_tv.setTextColor(gray_color)
                        content_tv.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
                        content_tv.setText(text)
                    else:
                        fetched_readme[0] = text
                        content_tv.setGravity(Gravity.LEFT)
                        content_tv.setTextColor(text_color)
                        content_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
                        try:
                            from com.exteragram.messenger.utils.text import LocaleUtils
                            from android.text.method import LinkMovementMethod
                            content_tv.setText(LocaleUtils.fullyFormatText(text))
                            content_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                            content_tv.setMovementMethod(LinkMovementMethod.getInstance())
                        except Exception:
                            content_tv.setText(text)

                import threading as _threading
                import requests as _req

                def _fetch_readme():
                    try:
                        r = _req.get(readme_url, timeout=10)
                        if r.status_code != 200:
                            # readme not available — fall back to standard desc
                            def _fallback():
                                spinner_frame.setVisibility(View.GONE)
                                content_tv.setVisibility(View.VISIBLE)
                                content_tv.setGravity(Gravity.LEFT)
                                content_tv.setTextColor(text_color)
                                content_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
                                if desc:
                                    try:
                                        from com.exteragram.messenger.utils.text import LocaleUtils
                                        from android.text.method import LinkMovementMethod
                                        content_tv.setText(LocaleUtils.fullyFormatText(desc))
                                        content_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                                        content_tv.setMovementMethod(LinkMovementMethod.getInstance())
                                    except Exception:
                                        content_tv.setText(desc)
                                else:
                                    _show_readme_text(str(strings.pp_changelog_empty), centered=True)
                            run_on_ui_thread(_fallback)
                            return
                        md = r.text
                        run_on_ui_thread(lambda t=md: _show_readme_text(t))
                    except Exception as e:
                        log(f"pluginProfile: readme fetch error: {e}")
                        run_on_ui_thread(lambda: _show_readme_text(desc if desc else str(strings.pp_changelog_empty), centered=not bool(desc)))

                _threading.Thread(target=_fetch_readme, daemon=True).start()

                buttons_row_ext = LinearLayout(act)
                buttons_row_ext.setOrientation(LinearLayout.HORIZONTAL)
                buttons_row_ext.setGravity(Gravity.CENTER_VERTICAL | Gravity.FILL_HORIZONTAL)

                def _make_text_btn_ext(icon_name, text):
                    btn = LinearLayout(act)
                    btn.setOrientation(LinearLayout.HORIZONTAL)
                    btn.setGravity(Gravity.CENTER)
                    btn.setClickable(True)
                    btn.setFocusable(True)
                    try:
                        ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                        r = (ic_color >> 16) & 0xFF
                        g = (ic_color >> 8) & 0xFF
                        b = ic_color & 0xFF
                        ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                        ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                            AndroidUtilities.dp(16), ic_fill, ic_pressed
                        ))
                    except Exception:
                        pass
                    btn.setPadding(
                        AndroidUtilities.dp(10), AndroidUtilities.dp(8),
                        AndroidUtilities.dp(10), AndroidUtilities.dp(8)
                    )
                    iv = ImageView(act)
                    iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    try:
                        iv.setImageResource(_resolve_icon(icon_name))
                        iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                    except Exception:
                        pass
                    btn.addView(iv, LayoutHelper.createLinear(16, 16, Gravity.CENTER_VERTICAL, 0, 0, 4, 0))
                    tv = TextView(act)
                    tv.setText(text)
                    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                    try:
                        tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        tv.setTypeface(AndroidUtilities.bold())
                    btn.addView(tv, LayoutHelper.createLinear(-2, -2))
                    return btn

                translate_btn_ext = _make_text_btn_ext("msg_replace", str(strings["translate"]))

                def onTranslateClickExt(v, _p=p, _readme=fetched_readme):
                    from ..PluginListActivity.translation import translate_plugin
                    text = _readme[0] if _readme[0] else None
                    translate_plugin(_p, text_override=text)
                translate_btn_ext.setOnClickListener(OnClickListener(onTranslateClickExt))

                copy_btn_ext = _make_text_btn_ext("msg_copy", str(strings["copy"]))

                def onCopyClickExt(v, _desc=desc):
                    try:
                        from android.content import ClipData
                        clipboard_manager = act.getSystemService(act.CLIPBOARD_SERVICE)
                        clip = ClipData.newPlainText("Plugin description", _desc)
                        clipboard_manager.setPrimaryClip(clip)
                        from ui.bulletin import BulletinHelper
                        BulletinHelper.show_success(strings.get("copied_to_clipboard", "Скопировано в буфер обмена"))
                    except Exception as e:
                        log(f"pluginProfile: copy description error: {e}")
                copy_btn_ext.setOnClickListener(OnClickListener(onCopyClickExt))

                ext_btns = [translate_btn_ext, copy_btn_ext]
                gap_ext = AndroidUtilities.dp(6)
                for i, btn in enumerate(ext_btns):
                    lp = LinearLayout.LayoutParams(0, -2, 1.0)
                    if i < len(ext_btns) - 1:
                        lp.rightMargin = gap_ext
                    buttons_row_ext.addView(btn, lp)

                wrap.addView(buttons_row_ext, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))
                return wrap

            # standard description
            desc_tv = TextView(act)
            desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            desc_tv.setTextColor(text_color)
            desc_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
            if desc:
                try:
                    from com.exteragram.messenger.utils.text import LocaleUtils
                    from android.text.method import LinkMovementMethod
                    desc_tv.setText(LocaleUtils.fullyFormatText(desc))
                    desc_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                    desc_tv.setMovementMethod(LinkMovementMethod.getInstance())
                except Exception:
                    desc_tv.setText(desc)
            wrap.addView(desc_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 12))

            buttons_row = LinearLayout(act)
            buttons_row.setOrientation(LinearLayout.HORIZONTAL)
            buttons_row.setGravity(Gravity.CENTER_VERTICAL)

            def _make_icon_only_btn(icon_name):
                # square icon-only button
                btn = FrameLayout(act)
                btn.setClickable(True)
                btn.setFocusable(True)
                size = AndroidUtilities.dp(36)
                try:
                    ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                    r = (ic_color >> 16) & 0xFF
                    g = (ic_color >> 8) & 0xFF
                    b = ic_color & 0xFF
                    ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                    ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(12), ic_fill, ic_pressed
                    ))
                except Exception:
                    pass
                iv = ImageView(act)
                iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                try:
                    iv.setImageResource(_resolve_icon(icon_name))
                    iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    pass
                btn.addView(iv, FrameLayout.LayoutParams(size, size))
                return btn

            def _make_text_btn(icon_name, text):
                btn = LinearLayout(act)
                btn.setOrientation(LinearLayout.HORIZONTAL)
                btn.setGravity(Gravity.CENTER)
                btn.setClickable(True)
                btn.setFocusable(True)
                try:
                    ic_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                    r = (ic_color >> 16) & 0xFF
                    g = (ic_color >> 8) & 0xFF
                    b = ic_color & 0xFF
                    ic_fill    = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value
                    ic_pressed = ctypes.c_int32((0x44 << 24) | (r << 16) | (g << 8) | b).value
                    btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(16), ic_fill, ic_pressed
                    ))
                except Exception:
                    pass
                btn.setPadding(
                    AndroidUtilities.dp(10), AndroidUtilities.dp(8),
                    AndroidUtilities.dp(10), AndroidUtilities.dp(8)
                )
                iv = ImageView(act)
                iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                try:
                    iv.setImageResource(_resolve_icon(icon_name))
                    iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    pass
                btn.addView(iv, LayoutHelper.createLinear(16, 16, Gravity.CENTER_VERTICAL, 0, 0, 4, 0))
                tv = TextView(act)
                tv.setText(text)
                tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                try:
                    tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    tv.setTypeface(AndroidUtilities.bold())
                btn.addView(tv, LayoutHelper.createLinear(-2, -2))
                return btn

            gap = AndroidUtilities.dp(6)

            translate_btn = _make_icon_only_btn("msg_replace")

            def onTranslateClick(v, _p=p):
                from ..PluginListActivity.translation import translate_plugin
                translate_plugin(_p)
            translate_btn.setOnClickListener(OnClickListener(onTranslateClick))

            copy_btn = _make_icon_only_btn("msg_copy")
            _copy_hint_ref = [None]

            def onCopyClick(v, _desc=desc):
                try:
                    from android.content import ClipData
                    clipboard_manager = act.getSystemService(act.CLIPBOARD_SERVICE)
                    clip = ClipData.newPlainText("Plugin description", _desc)
                    clipboard_manager.setPrimaryClip(clip)
                except Exception as e:
                    log(f"pluginProfile: copy description error: {e}")
                try:
                    from org.telegram.ui.Stories.recorder import HintView2
                    from android.text import Layout
                    prev = _copy_hint_ref[0]
                    if prev is not None:
                        try:
                            prev.hide()
                            prev.getParent().removeView(prev)
                        except Exception:
                            pass
                        _copy_hint_ref[0] = None
                    dv = act.getWindow().getDecorView()
                    hint = (
                        HintView2(v.getContext(), 3)
                        .setMultilineText(True)
                        .setBgColor(Theme.getColor(Theme.key_undo_background))
                        .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                        .setText(str(strings["afp_copied"]))
                        .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                        .allowBlur(True)
                        .setRounding(AndroidUtilities.dp(12))
                    )
                    try:
                        hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                    except Exception:
                        pass
                    dv.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                    _copy_hint_ref[0] = hint
                    def _position():
                        try:
                            loc = [0, 0]
                            v.getLocationInWindow(loc)
                            dv_loc = [0, 0]
                            dv.getLocationInWindow(dv_loc)
                            cell_y = loc[1] - dv_loc[1]
                            center_x = float(loc[0] - dv_loc[0]) + float(v.getMeasuredWidth()) / 2.0
                            hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                            hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                            hint.setDuration(3500)
                            hint.show()
                        except Exception as e:
                            log(f"pluginProfile: copy hint position error: {e}")
                    run_on_ui_thread(_position)
                except Exception as e:
                    log(f"pluginProfile: copy hint error: {e}")
            copy_btn.setOnClickListener(OnClickListener(onCopyClick))

            tr_lp = LinearLayout.LayoutParams(-2, -2)
            tr_lp.rightMargin = gap
            buttons_row.addView(translate_btn, tr_lp)

            cp_lp = LinearLayout.LayoutParams(-2, -2)
            cp_lp.rightMargin = gap
            buttons_row.addView(copy_btn, cp_lp)

            if readme_url:
                more_btn = _make_icon_only_btn("msg_info")

                def _raw_to_github(url):
                    # https://raw.githubusercontent.com/user/repo/refs/heads/branch/path
                    # → https://github.com/user/repo/blob/branch/path
                    try:
                        prefix = "https://raw.githubusercontent.com/"
                        if not url.startswith(prefix):
                            return url
                        rest = url[len(prefix):]
                        parts = rest.split("/")
                        # parts: [user, repo, "refs", "heads", branch, ...path]
                        if len(parts) >= 6 and parts[2] == "refs" and parts[3] == "heads":
                            user, repo, _, _, branch = parts[:5]
                            path = "/".join(parts[5:])
                            return f"https://github.com/{user}/{repo}/blob/{branch}/{path}"
                        # fallback: user/repo/branch/path (no refs/heads)
                        if len(parts) >= 4:
                            user, repo, branch = parts[:3]
                            path = "/".join(parts[3:])
                            return f"https://github.com/{user}/{repo}/blob/{branch}/{path}"
                    except Exception:
                        pass
                    return url

                def onMoreClick(v, _url=readme_url, _act=act):
                    try:
                        if Browser and Uri:
                            Browser.openUrl(_act, Uri.parse(_raw_to_github(_url)), True, True, True, None, None, False, False, False)
                    except Exception as ex:
                        log(f"pluginProfile: more_btn openUrl error: {ex}")
                more_btn.setOnClickListener(OnClickListener(onMoreClick))

                more_lp = LinearLayout.LayoutParams(-2, -2)
                buttons_row.addView(more_btn, more_lp)

            wrap.addView(buttons_row, LayoutHelper.createLinear(-1, -2))
            return wrap

        def _build_stub_content():
            tv = TextView(act)
            tv.setText(str(strings["pp_not_ready"]))
            tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            tv.setTextColor(gray_color)
            tv.setGravity(Gravity.CENTER_HORIZONTAL)
            tv.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
            return tv

        fetched_changelog = [""]  # shared ref for translate button

        def _apply_cl_card_press(card):
            from android.view import MotionEvent
            from java import dynamic_proxy
            class _TL(dynamic_proxy(View.OnTouchListener)):
                def __init__(self):
                    super().__init__()
                def onTouch(self, v, event):
                    try:
                        action = event.getActionMasked()
                        if action == MotionEvent.ACTION_DOWN:
                            v.animate().scaleX(0.96).scaleY(0.96).setDuration(100).start()
                        elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                            v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                    except Exception:
                        pass
                    return False
            card.setOnTouchListener(_TL())

        def _build_changelog_content():
            wrap = LinearLayout(act)
            wrap.setOrientation(LinearLayout.VERTICAL)

            current_version = str(p.get("version") or "")
            # None means field absent; [] means field exists but no text
            current_cl = p.get("changelog")
            current_size = str(p.get("size") or "").strip()
            versions_map = p.get("versions") or {}

            # entries: (version_str, cl_or_none, is_latest, size_str)
            # cl_or_none is None if changelog field absent, list otherwise
            entries = []
            entries.append((current_version, current_cl, True, current_size))
            for v in reversed(list(versions_map.keys())):
                vdata = versions_map[v]
                cl_raw = vdata.get("changelog") if "changelog" in vdata else None
                v_size = str(vdata.get("size") or "").strip()
                entries.append((v, cl_raw, False, v_size))

            for version_str, cl, is_latest, entry_size in entries:
                card = LinearLayout(act)
                card.setOrientation(LinearLayout.VERTICAL)
                card.setPadding(
                    AndroidUtilities.dp(14), AndroidUtilities.dp(12),
                    AndroidUtilities.dp(14), AndroidUtilities.dp(12)
                )
                card_bg = _make_card_bg(act, 14)
                if card_bg:
                    card.setBackground(card_bg)

                label = f"v{version_str}"

                # index 0: link or "None"; index 1: +diff; index 2: -diff
                cl_raw_link = str(cl[0]).strip() if isinstance(cl, list) and len(cl) > 0 else None
                # "None" at index 0 means author explicitly omitted changelog
                cl_is_none = cl_raw_link == "None"
                cl_link = cl_raw_link if not cl_is_none else None

                cl_diff_add = str(cl[1]).strip() if isinstance(cl, list) and len(cl) > 1 else None
                cl_diff_rem = str(cl[2]).strip() if isinstance(cl, list) and len(cl) > 2 else None

                cl_absent = cl is None

                ver_tv = TextView(act)
                ver_tv.setText(label)
                ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                ver_tv.setTextColor(text_color)
                try:
                    ver_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    ver_tv.setTypeface(AndroidUtilities.bold())

                # header row: version label left, latest chip (if latest), size chip right
                header_row = LinearLayout(act)
                header_row.setOrientation(LinearLayout.HORIZONTAL)
                header_row.setGravity(Gravity.CENTER_VERTICAL)
                header_row.addView(ver_tv, LayoutHelper.createLinear(-2, -2))
                if is_latest:
                    latest_chip = _make_chip(act, str(strings.pp_changelog_latest), "key_color_green")
                    latest_chip_lp = LinearLayout.LayoutParams(-2, -2)
                    latest_chip_lp.leftMargin = AndroidUtilities.dp(6)
                    header_row.addView(latest_chip, latest_chip_lp)
                spacer = View(act)
                header_row.addView(spacer, LayoutHelper.createLinear(0, 0, 1.0))
                size_text = entry_size if entry_size else str(strings.pp_changelog_size_empty)
                size_chip = _make_chip(act, size_text, "key_color_cyan")
                header_row.addView(size_chip, LinearLayout.LayoutParams(-2, -2))
                card.addView(header_row, LayoutHelper.createLinear(-1, -2))

                if cl_absent:
                    # changelog field absent entirely
                    no_cl_tv = TextView(act)
                    no_cl_tv.setText(str(strings.pp_changelog_missing))
                    no_cl_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    no_cl_tv.setTextColor(gray_color)
                    card.addView(no_cl_tv, LayoutHelper.createLinear(-1, -2, 0, 6, 0, 0))
                elif cl_diff_add is not None and cl_diff_rem is not None:
                    # both diffs present — colored +N -N row
                    diff_row = LinearLayout(act)
                    diff_row.setOrientation(LinearLayout.HORIZONTAL)
                    diff_row.setGravity(Gravity.CENTER_VERTICAL)

                    add_tv = TextView(act)
                    add_tv.setText(cl_diff_add)
                    add_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    try:
                        add_tv.setTextColor(Theme.getColor(Theme.key_avatar_backgroundGreen))
                    except Exception:
                        add_tv.setTextColor(0xFF4CAF50)
                    diff_row.addView(add_tv, LayoutHelper.createLinear(-2, -2))

                    rem_tv = TextView(act)
                    rem_tv.setText(f"  {cl_diff_rem}")
                    rem_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    try:
                        rem_tv.setTextColor(Theme.getColor(Theme.key_avatar_backgroundRed))
                    except Exception:
                        rem_tv.setTextColor(0xFFF44336)
                    diff_row.addView(rem_tv, LayoutHelper.createLinear(-2, -2))

                    card.addView(diff_row, LayoutHelper.createLinear(-2, -2, 0, 6, 0, 0))
                elif cl_diff_add is not None or cl_diff_rem is not None:
                    # only one diff present — show both, missing one as ?
                    partial_tv = TextView(act)
                    add_part = cl_diff_add if cl_diff_add is not None else "+?"
                    rem_part = cl_diff_rem if cl_diff_rem is not None else "-?"
                    partial_tv.setText(f"{add_part}  {rem_part}")
                    partial_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    try:
                        partial_tv.setTextColor(Theme.getColor(Theme.key_dialogTextGray3))
                    except Exception:
                        partial_tv.setTextColor(gray_color)
                    card.addView(partial_tv, LayoutHelper.createLinear(-2, -2, 0, 6, 0, 0))
                elif not cl_is_none and not cl_absent:
                    # no diffs and not "None" — binary or empty
                    binary_tv = TextView(act)
                    binary_tv.setText(str(strings.pp_changelog_binary))
                    binary_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    binary_tv.setTextColor(gray_color)
                    card.addView(binary_tv, LayoutHelper.createLinear(-1, -2, 0, 6, 0, 0))

                if cl_is_none:
                    # author explicitly set "None" — tap shows bulletin
                    card.setClickable(True)
                    card.setFocusable(True)
                    _apply_cl_card_press(card)
                    def _on_none_click(v):
                        try:
                            from hook_utils import find_class as _fc
                            BulletinFactory = _fc("org.telegram.ui.Components.BulletinFactory")
                            frag = self._fragment_ref[0]
                            container = self.content_view
                            resource_provider = None
                            try:
                                resource_provider = frag.getResourceProvider()
                            except Exception:
                                pass
                            from hook_utils import find_class as _fc2
                            R_tg = _fc2("org.telegram.messenger.R")
                            icon_raw = getattr(R_tg.raw, "info", 0)
                            BulletinFactory.of(container, resource_provider).createSimpleBulletin(
                                icon_raw,
                                str(strings.pp_changelog_none_provided)
                            ).show()
                        except Exception as e:
                            log(f"pluginProfile: changelog none bulletin error: {e}")
                    card.setOnClickListener(OnClickListener(_on_none_click))
                elif cl_link:
                    card.setClickable(True)
                    card.setFocusable(True)
                    _apply_cl_card_press(card)
                    def _on_card_click(v, _url=cl_link):
                        try:
                            if Browser and Uri:
                                Browser.openUrl(act, Uri.parse(_url), True, True, True, None, None, False, False, False)
                        except Exception as e:
                            log(f"pluginProfile: changelog card openUrl error: {e}")
                    card.setOnClickListener(OnClickListener(_on_card_click))

                card_lp = LinearLayout.LayoutParams(-1, -2)
                card_lp.bottomMargin = AndroidUtilities.dp(8)
                wrap.addView(card, card_lp)

            hint_tv = TextView(act)
            hint_tv.setText(str(strings["pp_click_version_hint"]))
            hint_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            hint_tv.setTextColor(gray_color)
            hint_tv.setGravity(Gravity.CENTER_HORIZONTAL)
            wrap.addView(hint_tv, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))

            return wrap

        _tab_builders = [_build_desc_content, _build_stub_content, _build_changelog_content]

        def _move_indicator(tb, animate):
            try:
                w = tb.getWidth()
                x = float(tb.getLeft())
                pad = AndroidUtilities.dp(4)
                lp = indicator.getLayoutParams()
                lp.width = w
                indicator.setLayoutParams(lp)
                if animate:
                    indicator.animate().translationX(x).setDuration(200).start()
                else:
                    indicator.setTranslationX(x)
            except Exception as e:
                log(f"pluginProfile: _move_indicator error: {e}")

        def _switch_tab(idx, tab_btns):
            selected_tab[0] = idx
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
            for i, tb in enumerate(tab_btns):
                if i == idx:
                    tb.setTextColor(accent)
                    try:
                        tb.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    except Exception:
                        tb.setTypeface(AndroidUtilities.bold())
                else:
                    tb.setTextColor(gray_color)
                    try:
                        tb.setTypeface(AndroidUtilities.getTypeface("fonts/r.ttf"))
                    except Exception:
                        pass
            # move indicator to selected tab
            _move_indicator(tab_btns[idx], animate=True)
            # rebuild content
            tab_content.removeAllViews()
            # changelog tab has its own per-version cards — no shared container style
            if idx == 2:
                tab_content.setBackground(None)
                tab_content.setPadding(0, 0, 0, 0)
            else:
                tab_content_bg2 = _make_card_bg(act)
                if tab_content_bg2:
                    tab_content.setBackground(tab_content_bg2)
                tab_content.setPadding(
                    AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                    AndroidUtilities.dp(16), AndroidUtilities.dp(14)
                )
            try:
                tab_content.addView(_tab_builders[idx](), LayoutHelper.createLinear(-1, -2))
            except Exception as e:
                log(f"pluginProfile: tab content build error: {e}")

        tab_btns = []
        for i, name in enumerate(tab_names):
            tb = TextView(act)
            tb.setText(name)
            tb.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            tb.setGravity(Gravity.CENTER)
            tb.setClickable(True)
            tb.setFocusable(True)
            tb.setPadding(
                AndroidUtilities.dp(14), AndroidUtilities.dp(8),
                AndroidUtilities.dp(14), AndroidUtilities.dp(8)
            )
            tab_btns.append(tb)
            tab_bar.addView(tb, LayoutHelper.createLinear(0, -2, 1.0))

        _switch_tab(0, tab_btns)

        # reposition indicator after first layout pass (sizes are 0 before)
        def _init_indicator_on_layout():
            try:
                from android.view import ViewTreeObserver
                vto = tab_bar.getViewTreeObserver()

                class _LayoutListener(dynamic_proxy(ViewTreeObserver.OnGlobalLayoutListener)):
                    def onGlobalLayout(self):
                        try:
                            _move_indicator(tab_btns[selected_tab[0]], animate=False)
                            tab_bar.getViewTreeObserver().removeOnGlobalLayoutListener(self)
                        except Exception:
                            pass
                vto.addOnGlobalLayoutListener(_LayoutListener())
            except Exception as e:
                log(f"pluginProfile: layout listener error: {e}")
        _init_indicator_on_layout()

        desc_extra = LinearLayout(act)
        desc_extra.setOrientation(LinearLayout.VERTICAL)

        _orig_switch_tab = _switch_tab

        def _switch_tab(idx, tab_btns):
            _orig_switch_tab(idx, tab_btns)
            desc_extra.setVisibility(View.VISIBLE if idx == 0 else View.GONE)
            translate_bar.setVisibility(View.GONE)

        for i, tb in enumerate(tab_btns):
            def _on_tab_click(v, _i=i, _btns=tab_btns):
                _switch_tab(_i, _btns)
            tb.setOnClickListener(OnClickListener(_on_tab_click))

        root.addView(tab_bar_frame, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))
        root.addView(tab_content, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 8))

        # translate button shown only on changelog tab
        translate_bar = LinearLayout(act)
        translate_bar.setOrientation(LinearLayout.HORIZONTAL)
        translate_bar.setGravity(Gravity.CENTER)
        translate_bar.setVisibility(View.GONE)

        try:
            btn_base = Theme.getColor(Theme.key_featuredStickers_addButton)
            btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            from android.graphics import Color as _C
            btn_base = _C.parseColor("#2196F3")
            btn_pressed = _C.parseColor("#1976D2")

        translate_bar_btn = LinearLayout(act)
        translate_bar_btn.setOrientation(LinearLayout.HORIZONTAL)
        translate_bar_btn.setGravity(Gravity.CENTER)
        translate_bar_btn.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(12),
            AndroidUtilities.dp(20), AndroidUtilities.dp(12)
        )
        translate_bar_btn.setClickable(True)
        translate_bar_btn.setFocusable(True)
        translate_bar_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(14), btn_base, btn_pressed
        ))

        translate_bar_label = TextView(act)
        translate_bar_label.setText(str(strings["translate"]))
        translate_bar_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        try:
            translate_bar_label.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        except Exception:
            translate_bar_label.setTextColor(0xFFFFFFFF)
        try:
            translate_bar_label.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            translate_bar_label.setTypeface(AndroidUtilities.bold())
        translate_bar_btn.addView(translate_bar_label)

        def onTranslateBarClick(v, _p=p):
            text = fetched_changelog[0]
            if not text.strip():
                return
            import threading
            import requests as _req
            from ..PluginListActivity.translation import _show_translate_sheet
            from java.util import Locale

            def _set_loading(loading):
                try:
                    translate_bar_btn.setEnabled(not loading)
                    translate_bar_btn.removeAllViews()
                    if loading:
                        try:
                            from org.telegram.ui.Components import CircularProgressDrawable
                            spin_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                            d = CircularProgressDrawable(spin_color)
                            try:
                                d.size = float(AndroidUtilities.dp(20))
                                d.thickness = float(AndroidUtilities.dp(2))
                            except Exception:
                                pass
                            spin_iv = ImageView(act)
                            spin_iv.setImageDrawable(d)
                            spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                            translate_bar_btn.addView(spin_iv, LayoutHelper.createLinear(20, 20, Gravity.CENTER))
                        except Exception:
                            translate_bar_btn.addView(translate_bar_label)
                    else:
                        translate_bar_btn.addView(translate_bar_label)
                except Exception as e:
                    log(f"pluginProfile: translate _set_loading error: {e}")

            def _do_translate():
                try:
                    target_lang = Locale.getDefault().getLanguage() or "en"
                    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={_req.utils.quote(text)}"
                    response = _req.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        # collect all translation chunks
                        translated = "".join(
                            chunk[0] for chunk in data[0] if chunk and chunk[0]
                        ) if data and data[0] else text
                    else:
                        translated = text
                    def _done():
                        _show_translate_sheet(act, _p, target_lang, translated)
                        threading.Timer(1.0, lambda: run_on_ui_thread(lambda: _set_loading(False))).start()
                    run_on_ui_thread(_done)
                except Exception as e:
                    log(f"pluginProfile: changelog translate error: {e}")
                    run_on_ui_thread(lambda: _set_loading(False))

            run_on_ui_thread(lambda: _set_loading(True))
            threading.Thread(target=_do_translate, daemon=True).start()
        translate_bar_btn.setOnClickListener(OnClickListener(onTranslateBarClick))

        translate_bar.addView(translate_bar_btn, LayoutHelper.createLinear(-1, -2))
        root.addView(translate_bar, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # team card
        team = p.get("team")
        if isinstance(team, list) and team:
            _build_team_card(act, desc_extra, team)

        # social links card
        social = p.get("social") or []
        if social:
            social_card = LinearLayout(act)
            social_card.setOrientation(LinearLayout.VERTICAL)
            social_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg_social = _make_card_bg(act)
            if bg_social:
                social_card.setBackground(bg_social)

            social_card.addView(
                _make_section_header(act, str(strings.pp_section_social)),
                LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0, 10)
            )

            for i, entry in enumerate(social):
                if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                    continue
                icon_name = str(entry[0])
                link_label = str(entry[1])
                link_url = str(entry[2])

                row = LinearLayout(act)
                row.setOrientation(LinearLayout.HORIZONTAL)
                row.setGravity(Gravity.CENTER_VERTICAL)
                row.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
                row.setClickable(True)
                row.setFocusable(True)
                row.setBackground(Theme.createSelectorDrawable(
                    Theme.getColor(Theme.key_listSelector), 2
                ))

                icon_iv = ImageView(act)
                icon_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                try:
                    icon_iv.setImageResource(_resolve_icon(icon_name))
                    icon_iv.setColorFilter(gray_color)
                except Exception:
                    pass
                row.addView(icon_iv, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

                label_tv = TextView(act)
                label_tv.setText(link_label)
                label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                label_tv.setTextColor(text_color)
                row.addView(label_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                if link_url:
                    def _on_social_click(v, _url=link_url):
                        try:
                            if Browser and Uri:
                                Browser.openUrl(act, Uri.parse(_url), True, True, True, None, None, False, False, False)
                        except Exception as e:
                            log(f"pluginProfile: social link error: {e}")
                    row.setOnClickListener(OnClickListener(_on_social_click))

                social_card.addView(row, LayoutHelper.createLinear(-1, -2))

                if i < len(social) - 1:
                    dv = View(act)
                    dv.setBackgroundColor(Theme.getColor(Theme.key_divider))
                    dv_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
                    dv_lp.leftMargin = AndroidUtilities.dp(32)
                    social_card.addView(dv, dv_lp)

            desc_extra.addView(social_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # tags card
        tags = p.get("tags") or []
        if tags:
            tags_card = LinearLayout(act)
            tags_card.setOrientation(LinearLayout.VERTICAL)
            tags_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg_tags = _make_card_bg(act)
            if bg_tags:
                tags_card.setBackground(bg_tags)

            tags_card.addView(
                _make_section_header(act, str(strings.pp_section_tags)),
                LayoutHelper.createLinear(-2, -2, 0, 0, 0, 0, 8)
            )

            chips_row_tags = LinearLayout(act)
            chips_row_tags.setOrientation(LinearLayout.HORIZONTAL)

            for tag in tags:
                if not isinstance(tag, (list, tuple)) or len(tag) < 2:
                    continue
                chip = _make_chip(act, str(tag[0]), str(tag[1]))
                chip_lp = LinearLayout.LayoutParams(-2, -2)
                chip_lp.rightMargin = AndroidUtilities.dp(5)
                chips_row_tags.addView(chip, chip_lp)

            if chips_row_tags.getChildCount() > 0:
                tags_card.addView(chips_row_tags, LayoutHelper.createLinear(-2, -2))
                desc_extra.addView(tags_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # dependencies
        if deps:
            deps_card = LinearLayout(act)
            deps_card.setOrientation(LinearLayout.VERTICAL)
            deps_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg3 = _make_card_bg(act)
            if bg3:
                deps_card.setBackground(bg3)

            # header row: "DEPENDENCIES" label + count pill on the right
            deps_header_row = LinearLayout(act)
            deps_header_row.setOrientation(LinearLayout.HORIZONTAL)
            deps_header_row.setGravity(Gravity.CENTER_VERTICAL)
            deps_header_row.addView(
                _make_section_header(act, str(strings.pp_section_dependencies)),
                LayoutHelper.createLinear(0, -2, 1.0)
            )
            dep_count_str = str(strings.pp_dep_library_one) if len(deps) == 1 else str(strings.pp_dep_library_other).format(len(deps))
            count_chip = _make_chip(act, dep_count_str, "key_color_purple")
            deps_header_row.addView(count_chip, LinearLayout.LayoutParams(-2, -2))
            deps_card.addView(deps_header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

            deps_meta = {
                dp["id"]: dp for dp in self.all_plugins
                if isinstance(dp, dict) and dp.get("id")
            }

            try:
                from com.exteragram.messenger.plugins import PluginsController
                controller = PluginsController.getInstance()
            except Exception:
                controller = None

            try:
                red_color = Theme.getColor(Theme.key_avatar_backgroundRed)
            except Exception:
                from android.graphics import Color
                red_color = Color.parseColor("#FF5252")
            try:
                green_color = Theme.getColor(Theme.key_avatar_backgroundGreen)
            except Exception:
                from android.graphics import Color
                green_color = Color.parseColor("#4CAF50")

            for i, dep_id in enumerate(deps):
                if not isinstance(dep_id, str):
                    continue
                dep_plugin = deps_meta.get(dep_id)

                dep_row = LinearLayout(act)
                dep_row.setOrientation(LinearLayout.HORIZONTAL)
                dep_row.setGravity(Gravity.CENTER_VERTICAL)
                dep_row.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))

                # sticker icon (same size as depsSheet: 36dp)
                dep_icon_str = (dep_plugin.get("icon") if dep_plugin else None) or ""
                icon_size_dp = 36
                if dep_icon_str and "/" in dep_icon_str:
                    dep_iv = BackupImageView(act)
                    dep_iv.setRoundRadius(AndroidUtilities.dp(8))
                    try:
                        dep_iv.getImageReceiver().setCrossfadeWithOldImage(True)
                    except Exception:
                        pass
                    iv_lp = LinearLayout.LayoutParams(
                        AndroidUtilities.dp(icon_size_dp), AndroidUtilities.dp(icon_size_dp)
                    )
                    iv_lp.rightMargin = AndroidUtilities.dp(10)
                    dep_row.addView(dep_iv, iv_lp)
                    if not _try_load_sticker(dep_iv, dep_icon_str, icon_size_dp):
                        _schedule_sticker_retry(dep_iv, dep_icon_str, icon_size_dp, self._alive)

                # status icon: msg_select green / msg_cancel red
                installed = False
                if controller:
                    try:
                        installed = controller.getPluginEngine(dep_id) is not None
                    except Exception:
                        pass
                status_iv = ImageView(act)
                status_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                if installed:
                    status_iv.setImageResource(_resolve_icon("msg_select"))
                    status_iv.setColorFilter(green_color)
                else:
                    status_iv.setImageResource(_resolve_icon("msg_cancel"))
                    status_iv.setColorFilter(red_color)
                dep_row.addView(status_iv, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

                # name + version inline
                name_row = LinearLayout(act)
                name_row.setOrientation(LinearLayout.HORIZONTAL)
                name_row.setGravity(Gravity.CENTER_VERTICAL)

                dep_name = (dep_plugin.get("name") if dep_plugin else None) or dep_id
                dep_name_tv = TextView(act)
                dep_name_tv.setText(str(dep_name))
                dep_name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                dep_name_tv.setTextColor(text_color)
                try:
                    dep_name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    dep_name_tv.setTypeface(AndroidUtilities.bold())
                name_row.addView(dep_name_tv, LayoutHelper.createLinear(-2, -2))

                dep_ver = (dep_plugin.get("version") if dep_plugin else None) or ""
                if dep_ver:
                    ver_tv = TextView(act)
                    ver_tv.setText(f"  v{dep_ver}")
                    ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                    ver_tv.setTextColor(gray_color)
                    name_row.addView(ver_tv, LayoutHelper.createLinear(-2, -2))

                dep_row.addView(name_row, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                if dep_plugin:
                    dep_row.setClickable(True)
                    dep_row.setFocusable(True)
                    dep_row.setBackground(Theme.createSelectorDrawable(
                        Theme.getColor(Theme.key_listSelector), 2
                    ))

                    def onDepClick(v, target=dep_plugin):
                        show_plugin_profile(target, self.install_ui, self.all_plugins)
                    dep_row.setOnClickListener(OnClickListener(onDepClick))

                deps_card.addView(dep_row, LayoutHelper.createLinear(-1, -2))

                if i < len(deps) - 1:
                    dv = View(act)
                    dv.setBackgroundColor(Theme.getColor(Theme.key_divider))
                    dv_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1))
                    dv_lp.leftMargin = AndroidUtilities.dp(46)
                    deps_card.addView(dv, dv_lp)

            desc_extra.addView(deps_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        # other plugins by author
        author = str(p.get("author") or "").strip()
        plugin_id = p.get("id")
        others = [
            op for op in self.all_plugins
            if isinstance(op, dict)
            and str(op.get("author") or "").strip() == author
            and op.get("id") != plugin_id
        ] if author else []

        if others:
            others_card = LinearLayout(act)
            others_card.setOrientation(LinearLayout.VERTICAL)
            others_card.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(14),
                AndroidUtilities.dp(16), AndroidUtilities.dp(14)
            )
            bg4 = _make_card_bg(act)
            if bg4:
                others_card.setBackground(bg4)

            others_header_row = LinearLayout(act)
            others_header_row.setOrientation(LinearLayout.HORIZONTAL)
            others_header_row.setGravity(Gravity.CENTER_VERTICAL)

            more_from_raw = str(strings.pp_section_more_from).format(author)
            more_from_tv = TextView(act)
            more_from_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            more_from_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            more_from_tv.setLetterSpacing(0.08)
            try:
                more_from_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                more_from_tv.setTypeface(AndroidUtilities.bold())
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                more_from_tv.setText(LocaleUtils.fullyFormatText(more_from_raw.upper()))
                more_from_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                more_from_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                more_from_tv.setText(more_from_raw.upper())
            others_header_row.addView(more_from_tv, LayoutHelper.createLinear(0, -2, 1.0))

            others_count_str = str(strings.pp_other_plugin_one) if len(others) == 1 else str(strings.pp_other_plugin_other).format(len(others))
            others_chip = _make_chip(act, others_count_str, "key_color_green")
            others_header_row.addView(others_chip, LinearLayout.LayoutParams(-2, -2))
            others_card.addView(others_header_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

            # horizontal scroll with edge fades
            scroll_frame = FrameLayout(act)

            hsv = HorizontalScrollView(act)
            hsv.setHorizontalScrollBarEnabled(False)
            hsv.setOverScrollMode(HorizontalScrollView.OVER_SCROLL_NEVER)
            hsv.setClipToPadding(False)
            hsv.setPadding(0, 0, 0, 0)

            items_row = LinearLayout(act)
            items_row.setOrientation(LinearLayout.HORIZONTAL)
            items_row.setGravity(Gravity.TOP)

            item_w = AndroidUtilities.dp(72)
            for i, other in enumerate(others):
                item = self._make_scroll_item(act, other, item_w, text_color)
                item_lp = LinearLayout.LayoutParams(item_w, -2)
                if i < len(others) - 1:
                    item_lp.rightMargin = AndroidUtilities.dp(8)
                items_row.addView(item, item_lp)

            hsv.addView(items_row, FrameLayout.LayoutParams(-2, -2))

            # block swipe-back when user touches this scroll
            try:
                from android.view import MotionEvent as _ME

                class _HsvTouch(dynamic_proxy(View.OnTouchListener)):
                    def __init__(self):
                        super().__init__()
                        self._down_x = 0.0
                        self._down_y = 0.0

                    def onTouch(self, v, event):
                        action = event.getAction()
                        if action == _ME.ACTION_DOWN:
                            self._down_x = event.getX()
                            self._down_y = event.getY()
                            # disallow immediately on touch down so swipe-back never starts
                            v.getParent().requestDisallowInterceptTouchEvent(True)
                        elif action == _ME.ACTION_MOVE:
                            dx = abs(event.getX() - self._down_x)
                            dy = abs(event.getY() - self._down_y)
                            if dx > dy:
                                v.getParent().requestDisallowInterceptTouchEvent(True)
                        elif action in (_ME.ACTION_UP, _ME.ACTION_CANCEL):
                            v.getParent().requestDisallowInterceptTouchEvent(False)
                        return False

                hsv.setOnTouchListener(_HsvTouch())
            except Exception as _te:
                log(f"pluginProfile: hsv touch listener error: {_te}")

            scroll_frame.addView(hsv, FrameLayout.LayoutParams(-1, -2))

            # left fade overlay
            try:
                from android.graphics import Color as _C
                from android.graphics.drawable import GradientDrawable as _GD
                bg_base = Theme.getColor(Theme.key_windowBackgroundWhite)
                _r = (bg_base >> 16) & 0xFF
                _g = (bg_base >> 8) & 0xFF
                _b = bg_base & 0xFF
                solid = ctypes.c_int32((0xDD << 24) | (_r << 16) | (_g << 8) | _b).value
                transp = _C.argb(0, _r, _g, _b)

                fade_l = _GD(_GD.Orientation.LEFT_RIGHT, [solid, transp])
                left_overlay = View(act)
                left_overlay.setBackground(fade_l)
                left_overlay.setClickable(False)
                lp_l = FrameLayout.LayoutParams(AndroidUtilities.dp(16), -1)
                lp_l.gravity = Gravity.START | Gravity.FILL_VERTICAL
                scroll_frame.addView(left_overlay, lp_l)

                fade_r = _GD(_GD.Orientation.RIGHT_LEFT, [solid, transp])
                right_overlay = View(act)
                right_overlay.setBackground(fade_r)
                right_overlay.setClickable(False)
                lp_r = FrameLayout.LayoutParams(AndroidUtilities.dp(16), -1)
                lp_r.gravity = Gravity.END | Gravity.FILL_VERTICAL
                scroll_frame.addView(right_overlay, lp_r)
            except Exception as _fe:
                log(f"pluginProfile: others fade overlay error: {_fe}")

            others_card.addView(scroll_frame, LayoutHelper.createLinear(-1, -2))

            desc_extra.addView(others_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0, 10))

        root.addView(desc_extra, LayoutHelper.createLinear(-1, -2))

        log(f"pluginProfile: beforeCreateView done, content_view={self.content_view}")
        try:
            from ..viewUtils import applyFontToTree
            applyFontToTree(self.content_view)
        except Exception:
            pass
        
        if self.content_view is not None:
            _add_actionbar_glow(self.content_view)
            _add_bottom_glow(self.content_view)
            fab = getattr(self, '_fab_ref', None)
            if fab is not None:
                fab.bringToFront()
        
        return self.content_view

    def _get_localized_description(self, plugin):
        about = plugin.get("about", [])
        if isinstance(about, list) and len(about) >= 1:
            try:
                from java.util import Locale
                lang = Locale.getDefault().getLanguage()
                if lang == "ru" and len(about) > 1:
                    return str(about[1])
                return str(about[0])
            except Exception:
                return str(about[0])
        return str(plugin.get("description") or "")

    def _make_scroll_item(self, act, plugin, item_w, text_color):
        # vertical item: icon on top, name below (max 2 lines with fading edge)
        col = LinearLayout(act)
        col.setOrientation(LinearLayout.VERTICAL)
        col.setGravity(Gravity.TOP | Gravity.CENTER_HORIZONTAL)
        col.setClickable(True)
        col.setFocusable(True)
        try:
            col.setBackground(Theme.createSelectorDrawable(
                Theme.getColor(Theme.key_listSelector), 2
            ))
        except Exception:
            pass
        col.setPadding(
            AndroidUtilities.dp(4), AndroidUtilities.dp(4),
            AndroidUtilities.dp(4), AndroidUtilities.dp(8)
        )

        icon_str = plugin.get("icon")
        size_dp = 54
        show_icon = bool(icon_str and icon_str != "Unknown" and "/" in str(icon_str))

        icon_container_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp))
        icon_container_lp.bottomMargin = AndroidUtilities.dp(6)

        if show_icon:
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(12))
            try:
                iv.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            col.addView(iv, icon_container_lp)
            if not _try_load_sticker(iv, icon_str, size_dp):
                _schedule_sticker_retry(iv, icon_str, size_dp, self._alive)
        else:
            # same placeholder as ImportBottomSheet: circle with plugins_filled icon
            try:
                from android.widget import ImageView as _IV
                from android.graphics import PorterDuffColorFilter as _PDCF, PorterDuff as _PD
                stub = _IV(act)
                stub.setScaleType(_IV.ScaleType.FIT_CENTER)
                stub.setImageResource(_resolve_icon("plugins_filled"))
                stub.setColorFilter(_PDCF(
                    Theme.getColor(Theme.key_featuredStickers_buttonText),
                    _PD.Mode.SRC_IN
                ))
                p = AndroidUtilities.dp(12)
                stub.setPadding(p, p, p, p)
                stub.setBackground(Theme.createCircleDrawable(
                    AndroidUtilities.dp(size_dp),
                    Theme.getColor(Theme.key_featuredStickers_addButton)
                ))
                col.addView(stub, icon_container_lp)
            except Exception as _pe:
                log(f"pluginProfile: scroll item placeholder error: {_pe}")

        name_tv = TextView(act)
        name_tv.setText(str(plugin.get("name") or plugin.get("id") or "?"))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        name_tv.setTextColor(text_color)
        name_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        name_tv.setMaxLines(2)
        name_tv.setHorizontalFadingEdgeEnabled(True)
        name_tv.setFadingEdgeLength(AndroidUtilities.dp(12))
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

        def onItemClick(v, target=plugin):
            show_plugin_profile(target, self.install_ui, self.all_plugins)
        col.setOnClickListener(OnClickListener(onItemClick))
        return col

    def _make_mini_card(self, act, plugin, text_color, gray_color):
        row = LinearLayout(act)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(8))
        row.setClickable(True)
        row.setFocusable(True)
        row.setBackground(Theme.createSelectorDrawable(
            Theme.getColor(Theme.key_listSelector), 2
        ))

        icon_str = plugin.get("icon")
        size_dp = 42
        show_default_sticker = settings.get("show_default_sticker", False)
        show_icon = icon_str and icon_str != "Unknown"
        if not show_icon and show_default_sticker:
            icon_str = "Plugins_Stickers/0"
            show_icon = True
        if show_icon:
            iv = BackupImageView(act)
            iv.setRoundRadius(AndroidUtilities.dp(10))
            iv_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp))
            iv_lp.rightMargin = AndroidUtilities.dp(12)
            row.addView(iv, iv_lp)
            if not _try_load_sticker(iv, icon_str, size_dp):
                _schedule_sticker_retry(iv, icon_str, size_dp, self._alive)

        info = LinearLayout(act)
        info.setOrientation(LinearLayout.VERTICAL)
        info.setGravity(Gravity.CENTER_VERTICAL)

        name_tv = TextView(act)
        name_tv.setText(str(plugin.get("name") or plugin.get("id") or "?"))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        name_tv.setTextColor(text_color)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        info.addView(name_tv, LayoutHelper.createLinear(-2, -2))

        sub_parts = []
        if plugin.get("version"):
            sub_parts.append(f"v{plugin['version']}")
        desc = str(plugin.get("description") or "")
        if desc:
            sub_parts.append(desc[:40] + ("…" if len(desc) > 40 else ""))
        if sub_parts:
            sub_tv = TextView(act)
            sub_text = "  ·  ".join(sub_parts)
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                sub_tv.setText(LocaleUtils.fullyFormatText(sub_text))
                sub_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                sub_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                sub_tv.setText(sub_text)
            sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            sub_tv.setTextColor(gray_color)
            sub_tv.setSingleLine(True)
            sub_tv.setHorizontalFadingEdgeEnabled(True)
            sub_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
            info.addView(sub_tv, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        row.addView(info, LayoutHelper.createLinear(0, -2, 1.0))

        def onRowClick(v, target=plugin):
            show_plugin_profile(target, self.install_ui, self.all_plugins)
        row.setOnClickListener(OnClickListener(onRowClick))
        return row


def show_plugin_profile(plugin: dict, install_ui, all_plugins: list = None, repo_id: str = ""):
    try:
        fragment = get_last_fragment()
        if not fragment:
            log("pluginProfile: no fragment")
            return
        log(f"pluginProfile: show_plugin_profile plugin={plugin.get('id')}")
        delegate = PluginProfileFragment(plugin, install_ui, all_plugins or [], repo_id=repo_id)
        new_fragment = UniversalFragment(delegate)
        fragment.presentFragment(new_fragment)
        log(f"pluginProfile: presentFragment done")
        try:
            new_fragment.setTitle(str(plugin.get("name") or plugin.get("id") or strings.pp_unknown_plugin), False, 0)
            action_bar = new_fragment.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                try:
                    from org.telegram.messenger import R as R_tg
                    back_icon = getattr(R_tg.drawable, 'ic_ab_back', 0)
                    if back_icon:
                        action_bar.setBackButtonImage(back_icon)
                        action_bar.setBackButtonContentDescription("Back")
                        try:
                            back_button = action_bar.getBackButton()
                            if back_button:
                                def _on_back_click(v):
                                    f = get_last_fragment()
                                    if f: f.finishFragment()
                                back_button.setOnClickListener(OnClickListener(_on_back_click))
                        except Exception:
                            pass
                except Exception as e:
                    log(f"Failed to add back button: {e}")
                delegate._fragment_ref[0] = new_fragment
        except Exception as e:
            log(f"pluginProfile: actionBar setup error: {e}")
    except Exception as e:
        log(f"pluginProfile: show_plugin_profile error: {e}")

C = True


def _show_not_tester_sheet():
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from android.view import Gravity
        from org.telegram.ui.ActionBar import Theme, BottomSheet
        from org.telegram.ui.Components import LayoutHelper
        from org.telegram.messenger import AndroidUtilities
        from android_utils import OnClickListener
        from client_utils import get_last_fragment
        from java import dynamic_proxy

        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        sheet = BottomSheet(act, False, frag.getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)
        sheet.setCanDismissWithSwipe(False)
        sheet.setCanDismissWithTouchOutside(False)
        sheet.makeAttached(frag)

        class _Delegate(dynamic_proxy(BottomSheet.BottomSheetDelegateInterface)):
            def __init__(self):
                super().__init__()
            def canDismiss(self):
                return False
            def onOpenAnimationEnd(self):
                pass
            def onOpenAnimationStart(self):
                pass

        sheet.setDelegate(_Delegate())

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(
            AndroidUtilities.dp(20), AndroidUtilities.dp(20),
            AndroidUtilities.dp(20), AndroidUtilities.dp(8)
        )
        try:
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadii([
                AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                0, 0, 0, 0
            ])
            bg.setColor(Theme.getColor(Theme.key_dialogBackground))
            root.setBackground(bg)
        except Exception:
            root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))

        title_tv = TextView(act)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        title_tv.setText("Beta build")
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER)
        try:
            title_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        root.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 10))

        msg_tv = TextView(act)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        msg_tv.setText("You are not a tester, you shouldn't have installed the PackIt.")
        msg_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        msg_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
        msg_tv.setGravity(Gravity.CENTER)
        root.addView(msg_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        try:
            base_active = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed_active = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            base_active = Theme.getColor(Theme.key_dialogTextBlue)
            pressed_active = base_active

        btn = FrameLayout(act)
        btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        btn.setClickable(True)
        btn.setFocusable(True)
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base_active, pressed_active
        ))

        btn_tv = TextView(act)
        btn_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        try:
            btn_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        btn_tv.setGravity(Gravity.CENTER)
        btn_tv.setText("Delete PackIt")
        btn_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        btn.addView(btn_tv, FrameLayout.LayoutParams(-1, -2))

        def on_delete(v):
            try:
                import shutil
                import os
                import signal
                from ...utils.paths import getPackItPluginDir
                try:
                    shutil.rmtree(getPackItPluginDir(), ignore_errors=True)
                except Exception as e:
                    log(f"process_start: rmtree failed: {e}")
                os.kill(os.getpid(), signal.SIGKILL)
            except Exception as e:
                log(f"process_start: on_delete error: {e}")

        btn.setOnClickListener(OnClickListener(on_delete))
        root.addView(btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

        sheet.setCustomView(root)
        sheet.show()
    except Exception as e:
        log(f"process_start: _show_not_tester_sheet error: {e}")


def process_start():
    if not C:
        return
    try:
        import threading
        from android_utils import run_on_ui_thread as _rut

        def _run():
            try:
                import json
                import requests
                r = requests.get(
                    "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json",
                    timeout=10
                )
                cfg = r.json()
                beta_ids = set(cfg.get("permissions", {}).get("beta_builds", []))
            except Exception as e:
                log(f"process_start: cfg load failed: {e}")
                return
            try:
                from org.telegram.messenger import UserConfig as _UC
                account_ids = set()
                for i in range(_UC.MAX_ACCOUNT_COUNT):
                    inst = _UC.getInstance(i)
                    if inst.isClientActivated():
                        account_ids.add(inst.getClientUserId())
            except Exception as e:
                log(f"process_start: accounts load failed: {e}")
                return
            if account_ids & beta_ids:
                return
            _rut(_show_not_tester_sheet)

        threading.Thread(target=_run, daemon=True).start()
    except Exception as e:
        log(f"process_start: error: {e}")

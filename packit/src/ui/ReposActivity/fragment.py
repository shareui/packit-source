# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# The "Sources" screen.
#
# Replaces the settings-list version, where every repository took seven rows and
# its icon was picked out of the host's R.drawable catalogue. Here a repository
# is one card that already knows what it carries, and the icon comes from the
# repomap itself (repometa.rm_icon).
#
# Everything the cards show is read from reposCache off the ui thread; the
# screen makes no network call of its own.

from packutil import logx
import ctypes
import json
import os

from java import dynamic_proxy
from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment, run_on_queue

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"repos fragment: import elyx strings failed: {e}")
try:
    from android.widget import FrameLayout, LinearLayout, TextView, ImageView, ScrollView
    from android.view import View, Gravity
    from android.util import TypedValue
    from android.graphics.drawable import GradientDrawable
except Exception as e:
    import android_utils as _au; _au.log(f"repos fragment: import android widgets failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"repos fragment: import telegram classes failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"repos fragment: import UniversalFragment failed: {e}")

from . import register, unregister
from .card import make_repo_card
from ..viewUtils import applyFontToTree
from ...utils.paths import getRepoCachePath


def _c(color: int) -> int:
    return ctypes.c_int32(color).value


def _alpha(color: int, a: int) -> int:
    return _c((a << 24) | (color & 0xFFFFFF))


def _theme(key: str, fallback: int = 0):
    try:
        return Theme.getColor(getattr(Theme, key))
    except Exception:
        return fallback


def read_repo_info(repo: dict) -> dict:
    """Everything the card needs, straight out of the cached repomap."""
    info = {"maintainer": "", "telegram": "", "source": "", "icon_url": "",
            "plugins": None, "icons": None, "status": "missing"}
    repo_id = str(repo.get("id") or "")
    if not repo_id:
        return info
    path = getRepoCachePath(repo_id)
    try:
        if not os.path.isfile(path):
            return info
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
    except Exception as e:
        logx(f"repos: cache unreadable for '{repo_id}': {e}", True)
        return info

    meta = cached.get("repometa") or {}
    info["maintainer"] = str(meta.get("rm_maintainer") or "")
    info["telegram"] = str(meta.get("rm_telegram") or "")
    info["source"] = str(meta.get("rm_source") or "")
    icon_url = str(meta.get("rm_icon") or "").strip()
    # older repositories put an R.drawable name in rm_icon; only a link is an icon
    info["icon_url"] = icon_url if icon_url.lower().startswith(("http://", "https://")) else ""
    # the chip reports whether the source is in use, not how old its cache is:
    # every start refreshes the caches anyway, so an age reading only ever told
    # the reader that they had been offline for a day
    info["status"] = "loaded"

    # a repomap that is itself the plugin list carries the count; the usual
    # shape only points at it by url, and the screen does not go online to count
    plugins = cached.get("plugins")
    if isinstance(plugins, list):
        info["plugins"] = len(plugins)
    icons = cached.get("icons")
    if isinstance(icons, list):
        info["icons"] = len(icons)
    return info


class ReposFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    def __init__(self, repoManager):
        super().__init__()
        self.repoManager = repoManager
        self._root = None
        self._list = None
        self._summary = None
        self._alive = [True]
        self._fragment = [None]
        self._first_build = True
        self._handles = []
        self._signature_shown = None

    # ---------------------------------------------------------------- delegate
    def onFragmentCreate(self, *_):
        register(self)

    def onFragmentDestroy(self, *_):
        self._alive[0] = False
        unregister(self)
        self._handles = []
        self._signature_shown = None
        try:
            if self._root is not None:
                parent = self._root.getParent()
                if parent is not None:
                    parent.removeView(self._root)
                self._root = None
        except Exception as e:
            logx(f"repos fragment: onFragmentDestroy error: {e}", False)

    def beforeCreateView(self):
        try:
            if self._root is not None:
                parent = self._root.getParent()
                if parent is not None:
                    parent.removeView(self._root)
                self._root = None
        except Exception as e:
            logx(f"repos fragment: view cleanup error: {e}", False)

        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return None

        try:
            root = FrameLayout(act)
            root.setBackgroundColor(_theme("key_windowBackgroundGray"))

            scroll = ScrollView(act)
            scroll.setVerticalScrollBarEnabled(False)
            try:
                scroll.setFillViewport(True)
            except Exception:
                pass

            content = LinearLayout(act)
            content.setOrientation(LinearLayout.VERTICAL)
            content.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(8),
                               AndroidUtilities.dp(12), AndroidUtilities.dp(96))

            content.addView(self._build_summary_row(act), LayoutHelper.createLinear(-1, -2))

            self._list = LinearLayout(act)
            self._list.setOrientation(LinearLayout.VERTICAL)
            # the container is new, so nothing is on screen to repaint
            self._handles = []
            self._signature_shown = None
            content.addView(self._list, LayoutHelper.createLinear(-1, -2))

            scroll.addView(content, ScrollView.LayoutParams(-1, -2))
            root.addView(scroll, FrameLayout.LayoutParams(-1, -1))
            root.addView(self._build_add_button(act), LayoutHelper.createFrame(
                -2, -2, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL, 0, 0, 0, 20))

            self._root = root
            run_on_ui_thread(lambda: self.reload(), 30)
            return root
        except Exception as e:
            logx(f"repos fragment: beforeCreateView error: {e}", False)
            return None

    def afterCreateView(self, v):
        return None

    def getTitle(self):
        try:
            return str(strings.repositories)
        except Exception:
            return "Repositories"

    def onBackPressed(self):
        # UniversalFragment negates this before deciding: it does
        # `return !delegate.onBackPressed()` and only calls finishFragment when
        # that is true. Returning True here therefore swallowed both the button
        # and the gesture. False means "nothing to handle, go ahead and close",
        # which is what every other fragment in the plugin returns.
        return False

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, mid):
        if mid == -1:
            try:
                frag = self._fragment[0] or get_last_fragment()
                if frag:
                    frag.finishFragment()
            except Exception:
                pass

    # ------------------------------------------------------------------- build
    def reload(self):
        # cards are rebuilt wholesale: the list is capped at ten entries, so
        # diffing would cost more than it saves
        if not self._alive[0] or self._list is None:
            return
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return
        repos = self.repoManager.getRepositories()

        def _work():
            infos = [read_repo_info(r) for r in repos]

            def _paint():
                if not self._alive[0] or self._list is None:
                    return
                try:
                    self._render(act, repos, infos)
                except Exception as e:
                    logx(f"repos fragment: render error: {e}", False)

            run_on_ui_thread(_paint)

        run_on_queue(_work)

    def _signature(self, repos):
        return [(str(r.get("id") or ""), str(r.get("url") or "")) for r in repos]

    def _render(self, act, repos, infos):
        self._summary.setText(self._summary_text(len(repos)))

        # A repaint is not a rebuild. Flipping a switch writes the list back
        # through RepositoryManager, which notifies this screen, which used to
        # throw every card away and build it again — and a fresh card starts
        # with an empty avatar, so every icon on screen blinked. When the same
        # sources are still there in the same order, hand each card its new
        # values and let it repaint itself.
        signature = self._signature(repos)
        if signature and signature == self._signature_shown and len(self._handles) == len(repos):
            for idx, repo in enumerate(repos):
                update = self._handles[idx].get("update")
                if update:
                    update(repo, infos[idx] if idx < len(infos) else {})
            # a repaint makes fresh chip labels, and those have no font yet
            applyFontToTree(self._list)
            return

        self._list.removeAllViews()
        self._handles = []
        self._signature_shown = signature

        if not repos:
            self._list.addView(self._build_empty_state(act), LayoutHelper.createLinear(-1, -2))
            self._first_build = False
            applyFontToTree(self._root)
            return

        for idx, repo in enumerate(repos):
            info = infos[idx] if idx < len(infos) else {}
            handle = {}
            card = make_repo_card(act, repo, info, self._callbacks_for(act, repo), handle)
            self._handles.append(handle)
            lp = LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8)
            self._list.addView(card, lp)
            if self._first_build:
                self._reveal(card, idx)

        self._first_build = False
        applyFontToTree(self._root)

    def _summary_text(self, count: int) -> str:
        try:
            from ..PluginListActivity.helpers.utils import _format_plural
            return str(_format_plural(count, strings.repo_one, strings.repo_few,
                                      strings.repo_many, strings["plural_type"]))
        except Exception:
            return f"{count}"

    def _reveal(self, card, idx: int):
        # md3 enter: fade plus a short rise, staggered down the list
        try:
            card.setAlpha(0.0)
            card.setTranslationY(float(AndroidUtilities.dp(12)))
            card.animate().alpha(1.0).translationY(0.0).setStartDelay(idx * 45).setDuration(220).start()
        except Exception:
            pass

    # --------------------------------------------------------------- callbacks
    def _index_of(self, repo: dict):
        # never trust a captured index: updateAllCaches drops repositories by
        # index while the screen is open
        repos = self.repoManager.getRepositories()
        repo_id = repo.get("id")
        if repo_id:
            for i, r in enumerate(repos):
                if r.get("id") == repo_id:
                    return i, repos
        url = repo.get("url")
        if url:
            for i, r in enumerate(repos):
                if r.get("url") == url:
                    return i, repos
        return -1, repos

    def _callbacks_for(self, act, repo):
        from . import actions

        # the card passes its own repo dict back: a repaint replaces the one
        # captured here with the freshly parsed entry
        def _on_toggle(value, current):
            idx, _ = self._index_of(current)
            if idx < 0:
                self.reload()
                return
            current["enabled"] = value
            self.repoManager.updateRepoField(idx, "enabled", value)

        def _on_menu(anchor, current):
            actions.show_card_menu(act, self, current, anchor)

        def _on_open_card(current, info):
            from .repoSheet import show_repo_sheet
            show_repo_sheet(act, current, info)

        def _on_open(url):
            actions.open_url(act, url)

        return {"on_toggle": _on_toggle, "on_menu": _on_menu, "on_open": _on_open,
                "on_open_card": _on_open_card}

    # ------------------------------------------------------------------ pieces
    def _build_summary_row(self, act):
        # the bulk actions the old screen kept under "Дополнительно" live behind
        # the button on the right of this row
        row = LinearLayout(act)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(AndroidUtilities.dp(6), 0, 0, AndroidUtilities.dp(8))

        self._summary = TextView(act)
        self._summary.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        self._summary.setTextColor(_theme("key_windowBackgroundWhiteGrayText"))
        row.addView(self._summary, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        from .card import _round_icon_button

        def _menu():
            from . import actions
            actions.show_bulk_menu(act, self, menu_btn)

        menu_btn = _round_icon_button(
            act, "msg_customize", _theme("key_windowBackgroundWhiteGrayText"), _menu, 34)
        menu_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(34), AndroidUtilities.dp(34))
        menu_lp.gravity = Gravity.CENTER_VERTICAL
        row.addView(menu_btn, menu_lp)
        return row

    def _build_add_button(self, act):
        accent = _theme("key_featuredStickers_addButton")
        btn = LinearLayout(act)
        btn.setOrientation(LinearLayout.HORIZONTAL)
        btn.setGravity(Gravity.CENTER_VERTICAL)
        btn.setPadding(AndroidUtilities.dp(18), AndroidUtilities.dp(14),
                       AndroidUtilities.dp(20), AndroidUtilities.dp(14))
        btn.setClickable(True)
        btn.setFocusable(True)
        try:
            btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(28), accent,
                _theme("key_featuredStickers_addButtonPressed", accent)))
            btn.setElevation(float(AndroidUtilities.dp(10)))
        except Exception:
            pass

        icon = ImageView(act)
        try:
            icon.setImageResource(getattr(R_tg.drawable, "msg_add"))
            icon.setColorFilter(_theme("key_featuredStickers_buttonText"))
        except Exception:
            pass
        icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
        icon_lp.gravity = Gravity.CENTER_VERTICAL
        icon_lp.rightMargin = AndroidUtilities.dp(8)
        btn.addView(icon, icon_lp)

        label = TextView(act)
        try:
            label.setText(str(strings.add_repository))
        except Exception:
            label.setText("Add")
        label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        label.setTextColor(_theme("key_featuredStickers_buttonText"))
        try:
            label.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        btn.addView(label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

        def _add(v):
            from . import actions
            actions.add_repository(act, self)

        btn.setOnClickListener(OnClickListener(_add))
        try:
            from ..PluginListActivity.helpers.uiHelpers import apply_press_scale
            apply_press_scale(btn)
        except Exception:
            pass
        return btn

    def _build_empty_state(self, act):
        box = LinearLayout(act)
        box.setOrientation(LinearLayout.VERTICAL)
        box.setGravity(Gravity.CENTER)
        box.setPadding(0, AndroidUtilities.dp(64), 0, AndroidUtilities.dp(24))

        icon = ImageView(act)
        try:
            icon.setImageResource(getattr(R_tg.drawable, "msg_folders"))
            icon.setColorFilter(_alpha(_theme("key_windowBackgroundWhiteGrayText"), 0x66))
        except Exception:
            pass
        stub_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(56), AndroidUtilities.dp(56))
        stub_lp.gravity = Gravity.CENTER_HORIZONTAL
        stub_lp.bottomMargin = AndroidUtilities.dp(14)
        box.addView(icon, stub_lp)

        title = TextView(act)
        try:
            title.setText(str(strings.repos_empty_title))
        except Exception:
            title.setText("No repositories")
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        title.setGravity(Gravity.CENTER)
        title.setTextColor(_theme("key_windowBackgroundWhiteBlackText"))
        try:
            title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        box.addView(title, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL))

        sub = TextView(act)
        try:
            sub.setText(str(strings.repos_empty_text))
        except Exception:
            sub.setText("")
        sub.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        sub.setGravity(Gravity.CENTER)
        sub.setTextColor(_theme("key_windowBackgroundWhiteGrayText"))
        box.addView(sub, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 24, 6, 24, 0))
        return box


def show_repos_fragment(repoManager):
    try:
        frag = get_last_fragment()
        if not frag:
            return
        delegate = ReposFragment(repoManager)
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        delegate._fragment[0] = new_frag

        def _setup(attempt=0):
            # the action bar is null for a few frames after presentFragment
            try:
                action_bar = new_frag.getActionBar()
                if not action_bar:
                    if attempt < 10:
                        run_on_ui_thread(lambda: _setup(attempt + 1), 120)
                    return
                new_frag.setTitle(str(strings.repositories), False, 0)
                action_bar.setBackgroundColor(_theme("key_windowBackgroundGray"))
                back_icon = getattr(R_tg.drawable, "ic_ab_back", 0)
                if back_icon:
                    action_bar.setBackButtonImage(back_icon)
                    action_bar.setBackButtonContentDescription("Back")
                    back_button = action_bar.getBackButton()
                    if back_button:
                        def _on_back(v):
                            f = get_last_fragment()
                            if f:
                                f.finishFragment()
                        back_button.setOnClickListener(OnClickListener(_on_back))
            except Exception as e:
                logx(f"repos fragment: actionbar setup error: {e}", False)

        _setup()
    except Exception as e:
        logx(f"repos fragment: show_repos_fragment error: {e}", False)

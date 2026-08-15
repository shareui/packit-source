# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ..utils.Bulletins import factory as _pbf
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import run_on_ui_thread, OnClickListener
from android.widget import LinearLayout, TextView, FrameLayout, ScrollView
from android.util import TypedValue
from android.view import Gravity
from android.graphics.drawable import GradientDrawable
from android.text.method import LinkMovementMethod
from java import dynamic_proxy
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
from hook_utils import find_class
try:
    from org.telegram.messenger import R as R_tg, ApplicationLoader
    from org.telegram.ui.ActionBar import Theme, BottomSheet
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
    from org.telegram.ui.Stories.recorder import ButtonWithCounterView
except Exception as e:
    import android_utils as _au; _au.log(f"repo deeplink: import tg classes failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.utils.text import LocaleUtils
except Exception as e:
    import android_utils as _au; _au.log(f"repo deeplink: import LocaleUtils failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
from urllib.parse import urlparse, parse_qs
import requests
import json
from ..network import Storage
from ..utils import CachedRepos

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")

# repo=add: required: link — optional: name
#
# "icon" stays in the accepted set and is read nowhere. It used to name an
# R.drawable, which is not how a repository is pictured any more — the icon
# comes out of the repomap the link points at. Links minted before that are
# still in people's chats, so the argument has to be tolerated rather than
# rejected; it is simply ignored.
_REPO_ADD_REQUIRED = {"link"}
_REPO_ADD_OPTIONAL = {"name", "icon"}
_REPO_ADD_ALL = _REPO_ADD_REQUIRED | _REPO_ADD_OPTIONAL


def _sheet_chip(act, text: str):
    # the same pill the source cards use, so the sheet that adds a source and
    # the card it becomes are recognisably the same thing
    from ..ui.repos.Card import _chip
    from ..ui.repos.RepoIcon import accent_for
    return _chip(act, text, accent_for({}))


def _sheet_chip_lp(margin_dp=3):
    from ..ui.repos.Card import _ROW_H
    lp = LinearLayout.LayoutParams(-2, AndroidUtilities.dp(_ROW_H))
    lp.leftMargin = AndroidUtilities.dp(margin_dp)
    lp.rightMargin = AndroidUtilities.dp(margin_dp)
    return lp


def _balance_lines(tv):
    # Android breaks a paragraph greedily by default: it fills the first line to
    # the margin and drops whatever is left onto the second, which for a
    # centred two-line sentence leaves one word stranded under a full line.
    # BALANCED asks the line breaker to even the lines out instead.
    try:
        from android.text import Layout
        tv.setBreakStrategy(Layout.BREAK_STRATEGY_BALANCED)
    except Exception as e:
        logx(f"repo deeplink: balanced break unavailable: {e}", True)


def handle(url, repoManager):
    try:
        if "repo=add" not in url:
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        argKeys = {k for k in query.keys() if k != "repo"}

        if not _REPO_ADD_REQUIRED.issubset(argKeys):
            BulletinHelper.show_error(strings.deeplink_too_few_args)
            return

        if not argKeys.issubset(_REPO_ADD_ALL):
            BulletinHelper.show_error(strings.deeplink_too_many_args)
            return

        name = query.get("name", [""])[0].strip()
        link = query.get("link", [""])[0].strip()

        if not link:
            BulletinHelper.show_error(strings.repo_add_invalid)
            return

        repos = repoManager.getRepositories()
        if len(repos) >= 10:
            BulletinHelper.show_error(strings.repo_add_limit)
            return

        try:
            frag = get_last_fragment()
            container = frag.getParentActivity().getWindow().getDecorView()
            resourceProvider = frag.getResourceProvider()
            _pbf(container, resourceProvider).createSimpleBulletin(
                R_tg.raw.camera_flip,
                strings.repo_add_fetching
            ).show()
        except Exception as e:
            logx(f"repo deeplink: bulletin error: {e}", False)

        def fetch_task():
            repometa = None
            pluginCount = 0
            try:
                data, error = Storage.fetch_repomap(link)
                if error:
                    logx(f"repo deeplink: {error} for '{link}'", True)
                else:
                    repometa = data.get("repometa")
                    # cached now, so the sheet's avatar and everything the
                    # source screen shows are there the moment it is added
                    CachedRepos.write(repometa.get("rm_rid"), data)

                    plugins_url = CachedRepos.plugins_url(repometa.get("rm_rid"), link)
                    entries, list_error = Storage.fetch_plugins(plugins_url)
                    if list_error:
                        logx(f"repo deeplink: plugin count unavailable: {list_error}", True)
                    else:
                        pluginCount = len(entries)
            except Exception as e:
                logx(f"repo deeplink: fetch error: {e}", False)

            run_on_ui_thread(lambda: _show_confirm_sheet(repometa, pluginCount, name, link, repoManager))

        run_on_queue(fetch_task)
    except Exception as e:
        logx(f"repo deeplink: handle error: {e}", False)


def _show_confirm_sheet(repometa, pluginCount, name, link, repoManager):
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        if not repometa or not repometa.get("rm_rid"):
            BulletinHelper.show_error(str(strings["dl_repo_no_metadata"]))
            return

        rm_rid = str(repometa.get("rm_rid") or "")
        rm_name = str(repometa.get("rm_name") or name or "")
        rm_url = str(repometa.get("rm_url") or link)
        rm_url_display = rm_url.removeprefix("https://").removeprefix("http://").rstrip("/")
        rm_maintainer = str(repometa.get("rm_maintainer") or name)
        # only ever the repomap's own picture — the link's icon argument named an
        # R.drawable, and a repository is not a glyph out of the client's sheet
        rm_icon = str(repometa.get("rm_icon") or "").strip()
        if not rm_icon.lower().startswith(("http://", "https://")):
            rm_icon = ""

        sheet = BottomSheet(act, False, frag.getResourceProvider())
        sheet.fixNavigationBar()

        frame = FrameLayout(act)
        linear = LinearLayout(act)
        linear.setOrientation(LinearLayout.VERTICAL)
        frame.addView(linear)

        # The source itself, drawn the way the sources screen draws it: the
        # repomap's picture, falling back to a monogram on a tonal square. What
        # used to be here was a folder glyph tinted with the accent — the same
        # picture for every repository in existence, which told the reader
        # nothing about the one they were about to add.
        try:
            from ..ui.repos.RepoIcon import build_icon_view
            icon_view = build_icon_view(
                act, {"id": rm_rid, "name": rm_name, "url": link}, 76, 22, rm_icon)
            linear.addView(icon_view, LayoutHelper.createLinear(
                76, 76, Gravity.CENTER_HORIZONTAL, 0, 22, 0, 0))
        except Exception as e:
            logx(f"repo deeplink: icon error: {e}", False)

        # the repository's name, not "Add repository?" — the question is what
        # the buttons are for, and the name is the thing being decided about
        title_tv = TextView(act)
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        # SP, not DIP: everything written on this sheet is prose, and prose is
        # what the system font scale is for. The pills keep DIP — their height
        # is fixed, so a label that grew would sit in a box that did not.
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 23)
        title_tv.setSingleLine(True)
        try:
            from android.text import TextUtils as _TextUtils
            title_tv.setEllipsize(_TextUtils.TruncateAt.END)
        except Exception:
            pass
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title_tv.setTypeface(AndroidUtilities.bold())
        title_tv.setText(rm_name or str(strings.repo_add_title))
        title_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
        linear.addView(title_tv, LayoutHelper.createFrame(-1, -2, 0, 21.0, 14.0, 21.0, 0.0))

        # Maintainer, with the mention live. Medium weight and a size up on the
        # disclaimer: both are centred grey paragraphs a few dp apart, and at
        # the same weight the eye read them as one block of small print instead
        # of as a subtitle belonging to the name above it.
        if rm_maintainer:
            sub_tv = TextView(act)
            sub_tv.setGravity(Gravity.CENTER_HORIZONTAL)
            sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15)
            sub_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteGrayText))
            _balance_lines(sub_tv)
            try:
                sub_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                pass
            try:
                sub_tv.setText(LocaleUtils.fullyFormatText(rm_maintainer))
                sub_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                sub_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                sub_tv.setText(rm_maintainer)
            linear.addView(sub_tv, LayoutHelper.createFrame(-1, -2, 0, 21.0, 5.0, 21.0, 0.0))

        # the facts as pills rather than as a sentence: how much is in there and
        # where it comes from
        try:
            chips_row = LinearLayout(act)
            chips_row.setOrientation(LinearLayout.HORIZONTAL)
            chips_row.setGravity(Gravity.CENTER)
            if pluginCount:
                chips_row.addView(
                    _sheet_chip(act, str(strings.repo_card_plugins).replace("{0}", str(pluginCount))),
                    _sheet_chip_lp(3))
            if rm_url_display:
                chips_row.addView(_sheet_chip(act, rm_url_display), _sheet_chip_lp(3))
            if chips_row.getChildCount():
                linear.addView(chips_row, LayoutHelper.createFrame(-1, -2, 0, 16.0, 14.0, 16.0, 0.0))
        except Exception as e:
            logx(f"repo deeplink: chips error: {e}", False)

        # What is left of the disclaimer once the concrete facts are drawn
        # above. It keeps the plain weight and stays the smallest thing here —
        # that is what tells it apart from the subtitle — but it gains a dp and
        # a wider gap above, because it was small enough to skip over.
        msg_tv = TextView(act)
        msg_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14)
        msg_tv.setText(str(strings["repo_add_disclaimer_short"]))
        msg_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteGrayText))
        msg_tv.setLineSpacing(AndroidUtilities.dp(3), 1.0)
        _balance_lines(msg_tv)
        linear.addView(msg_tv, LayoutHelper.createFrame(-1, -2, 0, 24.0, 18.0, 24.0, 0.0))

        # add button
        add_btn = ButtonWithCounterView(act, True, frag.getResourceProvider())
        add_btn.setRound()
        add_btn.setText(strings.repo_add_button, False)

        from android.view import View as _View
        class _AddClickSimple(dynamic_proxy(_View.OnClickListener)):
            def onClick(self, v):
                try:
                    rm_rid = repometa.get("rm_rid")
                    repo_name = repometa.get("rm_name") or name

                    currentRepos = repoManager.getRepositories()
                    for existing in currentRepos:
                        if existing.get("id") == rm_rid or existing.get("url") == link:
                            BulletinHelper.show_error(str(strings["dl_repo_already_added"]))
                            sheet.dismiss()
                            return

                    # no "icon": it held an R.drawable name and nothing reads
                    # one any more — the picture comes from the repomap
                    newRepo = {
                        "id": rm_rid,
                        "name": repo_name,
                        "url": link,
                        "enabled": True,
                        "collapsed": False,
                    }
                    currentRepos.append(newRepo)
                    repoManager.setRepositories(currentRepos)
                    BulletinHelper.show_success(strings.repo_add_success)
                    try:
                        from ..ui.achievements.service.AchivementsEngine import increment_category
                        increment_category("Repositories")
                    except Exception as e:
                        logx(f"repo deeplink: achievements increment error: {e}", False)
                except Exception as e:
                    logx(f"repo deeplink: on_add error: {e}", False)
                sheet.dismiss()

        add_btn.setOnClickListener(_AddClickSimple())
        linear.addView(add_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 20.0, 16.0, 8.0))

        # close button
        close_btn = ButtonWithCounterView(act, False, frag.getResourceProvider())
        close_btn.setRound()
        close_btn.setNeutral()
        close_btn.setText(strings.close_button, False)

        class _CloseClick(dynamic_proxy(_View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()

        close_btn.setOnClickListener(_CloseClick())
        linear.addView(close_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 0.0, 16.0, 0.0))

        scroll = ScrollView(act)
        scroll.addView(frame)
        sheet.setCustomView(scroll)
        sheet.show()
    except Exception as e:
        logx(f"repo deeplink: _show_confirm_sheet error: {e}", False)
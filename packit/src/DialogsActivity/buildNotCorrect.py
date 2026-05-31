# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from android_utils import log, run_on_ui_thread
from android.graphics.drawable import GradientDrawable
from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, TextView
from java import dynamic_proxy
from org.telegram.messenger import AndroidUtilities
from org.telegram.ui.ActionBar import BottomSheet, Theme
from org.telegram.ui.Components import LayoutHelper
from org.telegram.ui.Stories.recorder import ButtonWithCounterView
try:
    from elyx import strings
except Exception as e:
    log(f"buildNotCorrect: import strings failed: {e}")

_HASH_CONFIG_KEY = "build_not_correct_dismissed_hash"


def _getDismissedHash() -> str:
    try:
        from ..utils.localConfig import LocalConfig
        return LocalConfig.get(_HASH_CONFIG_KEY, "")
    except Exception as e:
        log(f"buildNotCorrect: _getDismissedHash error: {e}")
        return ""


def _saveDismissedHash(hashVal: str):
    try:
        from ..utils.localConfig import LocalConfig
        LocalConfig.set(_HASH_CONFIG_KEY, hashVal)
    except Exception as e:
        log(f"buildNotCorrect: _saveDismissedHash error: {e}")


def _makeBlockBg(radius: int, resource_provider=None) -> GradientDrawable:
    gd = GradientDrawable()
    gd.setShape(GradientDrawable.RECTANGLE)
    gd.setCornerRadius(float(radius))
    gd.setColor(Theme.getColor(Theme.key_dialogScrollGlow, resource_provider) | 0xFF000000)
    return gd


def _makeMessageBlock(activity, message: str, resource_provider=None) -> LinearLayout:
    dp = AndroidUtilities.dp
    block = LinearLayout(activity)
    block.setOrientation(LinearLayout.VERTICAL)
    block.setPadding(dp(14), dp(12), dp(14), dp(12))
    block.setBackground(_makeBlockBg(dp(12), resource_provider))

    tv = TextView(activity)
    tv.setText(message)
    tv.setTextSize(1, 14.0)
    tv.setGravity(Gravity.CENTER_HORIZONTAL)
    tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText, resource_provider))
    block.addView(tv, LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT,
    ))
    return block


def _makeInfoCard(activity, rows: list, resource_provider=None) -> LinearLayout:
    dp = AndroidUtilities.dp
    card = LinearLayout(activity)
    card.setOrientation(LinearLayout.VERTICAL)
    card.setBackground(_makeBlockBg(dp(12), resource_provider))

    for i, (label, value) in enumerate(rows):
        row = LinearLayout(activity)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(dp(14), dp(12), dp(14), dp(12))

        label_tv = TextView(activity)
        label_tv.setText(label)
        label_tv.setTextSize(1, 13.0)
        label_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText, resource_provider))
        row.addView(label_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        value_tv = TextView(activity)
        value_tv.setText(value)
        value_tv.setTextSize(1, 13.0)
        value_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        value_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText, resource_provider))
        value_tv.setGravity(Gravity.END)
        row.addView(value_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL | Gravity.END))

        card.addView(row, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ))

        if i < len(rows) - 1:
            divider = View(activity)
            divider.setBackgroundColor(Theme.getColor(Theme.key_divider, resource_provider))
            divider_lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(1)
            )
            divider_lp.leftMargin = dp(14)
            card.addView(divider, divider_lp)

    return card


def _buildSheet(title: str, message: str, rows: list, buildHash: str):
    try:
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        if not frag:
            log("buildNotCorrect: no fragment")
            return
        activity = frag.getParentActivity()
        if not activity:
            log("buildNotCorrect: no activity")
            return
        resource_provider = frag.getResourceProvider()

        sheet = BottomSheet(activity, False, resource_provider)
        sheet.fixNavigationBar()

        root = LinearLayout(activity)
        root.setOrientation(LinearLayout.VERTICAL)

        pad_h = AndroidUtilities.dp(16)

        title_tv = TextView(activity)
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        title_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title_tv.setTextSize(1, 20.0)
        title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        title_tv.setText(title)
        title_lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        )
        title_lp.topMargin = AndroidUtilities.dp(20)
        title_lp.leftMargin = pad_h
        title_lp.rightMargin = pad_h
        root.addView(title_tv, title_lp)

        msg_block = _makeMessageBlock(activity, message, resource_provider)
        msg_lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        )
        msg_lp.topMargin = AndroidUtilities.dp(12)
        msg_lp.leftMargin = pad_h
        msg_lp.rightMargin = pad_h
        root.addView(msg_block, msg_lp)

        card = _makeInfoCard(activity, rows, resource_provider)
        card_lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        )
        card_lp.topMargin = AndroidUtilities.dp(8)
        card_lp.leftMargin = pad_h
        card_lp.rightMargin = pad_h
        root.addView(card, card_lp)

        versions_btn = ButtonWithCounterView(activity, True, resource_provider)
        versions_btn.setRound()
        versions_btn.setText(strings["build_not_correct_list_of_versions"], False)

        class _VersionsClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                if buildHash:
                    _saveDismissedHash(buildHash)
                try:
                    from android.net import Uri
                    from org.telegram.messenger.browser import Browser
                    Browser.openUrl(activity, Uri.parse("https://t.me/packitGround/8/11481"), True, True, True, None, None, False, False, False)
                except Exception as _e:
                    log(f"buildNotCorrect: openUrl error: {_e}")

        versions_btn.setOnClickListener(_VersionsClick())
        versions_lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            AndroidUtilities.dp(48),
        )
        versions_lp.topMargin = AndroidUtilities.dp(16)
        versions_lp.leftMargin = pad_h
        versions_lp.rightMargin = pad_h
        root.addView(versions_btn, versions_lp)

        close_btn = ButtonWithCounterView(activity, False, resource_provider)
        close_btn.setRound()
        close_btn.setNeutral()
        close_btn.setText(strings["close_button"], False)

        class _CloseClick(dynamic_proxy(View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()
                if buildHash:
                    _saveDismissedHash(buildHash)

        close_btn.setOnClickListener(_CloseClick())
        close_lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            AndroidUtilities.dp(48),
        )
        close_lp.topMargin = AndroidUtilities.dp(8)
        close_lp.leftMargin = pad_h
        close_lp.rightMargin = pad_h
        close_lp.bottomMargin = AndroidUtilities.dp(8)
        root.addView(close_btn, close_lp)

        sheet.setCustomView(root)
        sheet.show()
        log("buildNotCorrect: sheet shown")
    except Exception as e:
        log(f"buildNotCorrect: _buildSheet error: {e}")


def _checkAndShow():
    try:
        from ..utils.buildInfo import (
            getBuildClientPkg, getBuildClientName,
            getBuildStaticVersion,
            getCurrClientPkg, getCurrClientName,
            getClientVersion,
            getBuildHash,
        )

        buildPkg = getBuildClientPkg()
        buildVer = getBuildStaticVersion()

        # no build info — skip
        if buildPkg is None and buildVer is None:
            log("buildNotCorrect: no build info, skipping")
            return

        buildHash = getBuildHash()

        # already dismissed for this exact build
        if buildHash and _getDismissedHash() == buildHash:
            log("buildNotCorrect: hash matches dismissed, skipping")
            return

        currPkg = getCurrClientPkg()
        currVer = getClientVersion()

        buildClient = getBuildClientName()
        currClient = getCurrClientName()
        pkgMismatch = False
        if buildClient != "Universal" and buildClient != currClient:
            pkgMismatch = True
        verMismatch = buildVer is not None and currVer != buildVer

        if not pkgMismatch and not verMismatch:
            log("buildNotCorrect: build matches client, skipping")
            return

        title = str(strings.build_not_correct_title)
        rows = []

        if pkgMismatch and verMismatch:
            message = str(strings.build_not_correct_both_short)
            buildName = getBuildClientName()
            currName = getCurrClientName()
            rows = [
                (str(strings.build_not_correct_label_build), f"{buildName} {buildVer}"),
                (str(strings.build_not_correct_label_yours), f"{currName} {currVer}"),
            ]
        elif pkgMismatch:
            message = str(strings.build_not_correct_client_short)
            buildName = getBuildClientName()
            currName = getCurrClientName()
            rows = [
                (str(strings.build_not_correct_label_build), buildName),
                (str(strings.build_not_correct_label_yours), currName),
            ]
        else:
            message = str(strings.build_not_correct_version_short)
            rows = [
                (str(strings.build_not_correct_label_build), str(buildVer)),
                (str(strings.build_not_correct_label_yours), str(currVer)),
            ]

        run_on_ui_thread(lambda: _buildSheet(title, message, rows, buildHash or ""))
    except Exception as e:
        log(f"buildNotCorrect: _checkAndShow error: {e}")


def setup_build_not_correct_check():
    threading.Thread(target=_checkAndShow, daemon=True).start()
from ui.settings import Header, Switch, Divider, Text, Input, Custom
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log, run_on_ui_thread, OnClickListener
try:
    from org.telegram.messenger import ApplicationLoader, AndroidUtilities, R
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader, AndroidUtilities failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.ActionBar import Theme, BottomSheet
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.ActionBar import Theme failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.ui.Components import LayoutHelper failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.widget import LinearLayout, TextView, FrameLayout
from android.view import Gravity
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser as _Browser
except Exception:
    _Browser = None
from android.util import TypedValue
import shutil
import threading
import time
import os
import signal

from typing import List, Any, Callable
from dataclasses import dataclass, field
from ..ui.FontPickerBottomSheet import showFontPicker
from ..ui.FontManager import getSelectedFilename

def _getCacheInfo(cacheDir):
    # returns (human readb size str, file count)
    try:
        total = 0
        count = 0
        for dirpath, _, filenames in os.walk(cacheDir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                    count += 1
                except Exception:
                    pass
        if total < 1024:
            size = f"{total} B"
        elif total < 1024 * 1024:
            size = f"{total // 1024} KB"
        else:
            size = f"{total / (1024 * 1024):.1f} MB"
        return size, count
    except Exception:
        return "—", 0


def _getCacheSize(cacheDir):
    return _getCacheInfo(cacheDir)[0]


def _getFreeSpace(path):
    # returns free space for the given path
    try:
        stat = os.statvfs(path)
        free = stat.f_bavail * stat.f_frsize
        if free < 1024 * 1024:
            return f"{free // 1024} KB"
        elif free < 1024 * 1024 * 1024:
            return f"{free / (1024 * 1024):.1f} MB"
        else:
            return f"{free / (1024 * 1024 * 1024):.1f} GB"
    except Exception:
        return "—"


def _buildTextSubtextCell(context, text, subtext, icon, on_click):
    # native-looking cell: icon on left, title + subtitle stacked, full-row ripple tap
    try:
        from android.widget import ImageView
        from hook_utils import find_class
        dp = AndroidUtilities.dp
        log("other: _buildTextSubtextCell start")

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setMinimumHeight(dp(64))
        row.setClickable(True)
        row.setFocusable(True)
        row.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))
        row.setOnClickListener(OnClickListener(on_click))
        log("other: _buildTextSubtextCell row created")

        icon_id = None
        try:
            R = find_class("org.telegram.messenger.R")
            icon_id = getattr(R.drawable, icon)
            log(f"other: _buildTextSubtextCell icon_id={icon_id}")
        except Exception as e:
            log(f"other: _buildTextSubtextCell icon resolve error: {e}")

        if icon_id is not None:
            iconView = ImageView(context)
            iconView.setImageResource(icon_id)
            iconView.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
            # left=23 matches native TextCheckCell icon indent
            row.addView(iconView, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 23, 0, 0, 0))
            log("other: _buildTextSubtextCell icon added")

        textBlock = LinearLayout(context)
        textBlock.setOrientation(LinearLayout.VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(text))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        textBlock.addView(titleView, LayoutHelper.createLinear(-2, -2))

        subtitleView = TextView(context)
        subtitleView.setText(str(subtext))
        subtitleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        subtitleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        textBlock.addView(subtitleView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        # 23+24+25=72dp total left offset
        row.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL, 25, 10, 17, 10))

        log("other: _buildTextSubtextCell done")
        return row
    except Exception as e:
        log(f"other: _buildTextSubtextCell error: {e}")
        return None


def _buildTextSubtextCellIconRight(context, text, subtext, icon, on_click):
    # cell: title + subtitle on left, icon on right
    try:
        from android.widget import ImageView
        from hook_utils import find_class
        dp = AndroidUtilities.dp
        log("other: _buildTextSubtextCellIconRight start")

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setMinimumHeight(dp(64))
        row.setClickable(True)
        row.setFocusable(True)
        row.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))
        row.setOnClickListener(OnClickListener(on_click))
        log("other: _buildTextSubtextCellIconRight row created")

        textBlock = LinearLayout(context)
        textBlock.setOrientation(LinearLayout.VERTICAL)
        textBlock.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(text))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        titleView.setGravity(Gravity.LEFT)
        textBlock.addView(titleView, LayoutHelper.createLinear(-1, -2))

        if subtext:
            subtitleView = TextView(context)
            subtitleView.setText(str(subtext))
            subtitleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
            subtitleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            subtitleView.setGravity(Gravity.LEFT)
            textBlock.addView(subtitleView, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

        row.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL, 23, 10, 0, 10))
        log("other: _buildTextSubtextCellIconRight textBlock added")

        icon_id = None
        try:
            R = find_class("org.telegram.messenger.R")
            icon_id = getattr(R.drawable, icon)
            log(f"other: _buildTextSubtextCellIconRight icon_id={icon_id}")
        except Exception as e:
            log(f"other: _buildTextSubtextCellIconRight icon resolve error: {e}")

        if icon_id is not None:
            iconView = ImageView(context)
            iconView.setImageResource(icon_id)
            iconView.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
            icon_lp = LayoutHelper.createLinear(24, 24, Gravity.RIGHT | Gravity.CENTER_VERTICAL, 0, 0, 23, 0)
            row.addView(iconView, icon_lp)
            log("other: _buildTextSubtextCellIconRight icon added")

        log("other: _buildTextSubtextCellIconRight done")
        return row
    except Exception as e:
        log(f"other: _buildTextSubtextCellIconRight error: {e}")
        return None



def _buildCacheCard(context, cacheDir, on_clear, title=None):
    # card showing cache size with clear button
    try:
        dp = AndroidUtilities.dp

        card = LinearLayout(context)
        card.setOrientation(LinearLayout.HORIZONTAL)
        card.setGravity(Gravity.CENTER_VERTICAL)
        card.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        card.setPadding(dp(16), dp(14), dp(8), dp(14))

        left = LinearLayout(context)
        left.setOrientation(LinearLayout.VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(title) if title is not None else str(strings.clear_cache))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        left.addView(titleView, LayoutHelper.createLinear(-2, -2))

        sizeView = TextView(context)
        size, fileCount = _getCacheInfo(cacheDir)
        sizeView.setText(f"{size} • {fileCount} files")
        sizeView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        sizeView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        left.addView(sizeView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        card.addView(left, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        from android.widget import ImageView
        from android.graphics import Color

        clearBtn = ImageView(context)
        clearBtn.setImageResource(R.drawable.msg_clearcache)
        clearBtn.setColorFilter(Theme.getColor(Theme.key_avatar_backgroundRed))
        clearBtn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
        clearBtn.setPadding(dp(8), dp(8), dp(8), dp(8))
        clearBtn.setOnClickListener(OnClickListener(on_clear))
        card.addView(clearBtn, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

        return card
    except Exception as e:
        log(f"other: _buildCacheCard error: {e}")
        return None


def _showEditPathDialog(context, pathView, freeView):
    try:
        from android.text import InputType
        from android.content import DialogInterface
        from android.view import View
        from android.widget import ScrollView
        from java import dynamic_proxy
        from org.telegram.ui.ActionBar import AlertDialog
        from org.telegram.ui.Components import EditTextBoldCursor, OutlineTextContainerView, RLottieImageView

        dp = AndroidUtilities.dp

        builder = AlertDialog.Builder(context)

        frameLayout = FrameLayout(context)
        builder.setView(frameLayout)

        scrollView = ScrollView(context)
        scrollView.setFillViewport(True)
        frameLayout.addView(scrollView, LayoutHelper.createFrame(-1, -1))

        linear = LinearLayout(context)
        linear.setOrientation(LinearLayout.VERTICAL)
        linear.setGravity(Gravity.CENTER_HORIZONTAL)
        scrollView.addView(linear, LayoutHelper.createFrame(-1, -2, Gravity.TOP))

        try:
            anim = RLottieImageView(context)
            anim.setAnimation(R.raw.folder_in, 100, 100)
            anim.playAnimation()
            linear.addView(anim, LayoutHelper.createLinear(100, 100, Gravity.CENTER_HORIZONTAL, 0, 16, 0, 0))
        except Exception as e:
            log(f"other: folder_in anim error: {e}")

        title = TextView(context)
        title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        title.setGravity(Gravity.CENTER_HORIZONTAL)
        title.setTypeface(AndroidUtilities.bold())
        title.setText(str(strings.download_path))
        linear.addView(title, LayoutHelper.createFrame(-2, -2, Gravity.CENTER_HORIZONTAL, 24, 8, 24, 0))

        outlineView = OutlineTextContainerView(context)
        outlineView.setText(str(strings.download_path))
        outlineView.animateSelection(1, False)
        linear.addView(outlineView, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_HORIZONTAL, 24, 24, 24, 16))

        input = EditTextBoldCursor(context)
        input.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        input.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        input.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText))
        input.setBackground(None)
        input.setSingleLine(True)
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI)
        input.setCursorColor(Theme.getColor(Theme.key_windowBackgroundWhiteInputFieldActivated))
        input.setCursorWidth(1.5)
        padding = dp(16)
        input.setPadding(padding, padding, padding, padding)
        input.setText(pathView.getText())
        input.setSelection(input.getText().length())
        outlineView.addView(input, LayoutHelper.createFrame(-1, -2))
        outlineView.attachEditText(input)

        class _FocusListener(dynamic_proxy(View.OnFocusChangeListener)):
            def onFocusChange(self, v, hasFocus):
                outlineView.animateSelection(1 if hasFocus else 0)

        input.setOnFocusChangeListener(_FocusListener())

        dialog = builder.create()

        def onOk():
            newPath = str(input.getText()).strip()
            if not newPath:
                return
            try:
                settings.set("download_path", newPath)
            except Exception as e:
                log(f"other: save download_path error: {e}")
            pathView.setText(newPath)
            freeView.setText(f"Free: {_getFreeSpace(newPath)}")
            AndroidUtilities.hideKeyboard(input)
            dialog.dismiss()

        doneBtn = TextView(context)
        doneBtn.setText(str(strings.ok_button) if hasattr(strings, "ok_button") else "OK")
        doneBtn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        doneBtn.setGravity(Gravity.CENTER)
        doneBtn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(6),
            Theme.getColor(Theme.key_featuredStickers_addButton),
            Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        ))
        doneBtn.setClickable(True)
        doneBtn.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        doneBtn.setOnClickListener(OnClickListener(lambda v: onOk()))
        linear.addView(doneBtn, LayoutHelper.createFrame(-1, 44, Gravity.TOP, 30, 0, 30, 16))

        class _DismissListener(dynamic_proxy(DialogInterface.OnDismissListener)):
            def onDismiss(self, d):
                AndroidUtilities.hideKeyboard(input)

        class _ShowListener(dynamic_proxy(DialogInterface.OnShowListener)):
            def onShow(self, d):
                input.requestFocus()
                input.setSelection(input.getText().length())
                AndroidUtilities.showKeyboard(input)

        dialog.setOnDismissListener(_DismissListener())
        dialog.setOnShowListener(_ShowListener())
        dialog.show()
    except Exception as e:
        log(f"other: _showEditPathDialog error: {e}")

def _buildDownloadPathCard(context, currentPath):
    # card: text block on the left, edit icon on the right
    try:
        from android.widget import ImageView
        dp = AndroidUtilities.dp

        card = LinearLayout(context)
        card.setOrientation(LinearLayout.HORIZONTAL)
        card.setGravity(Gravity.CENTER_VERTICAL)
        card.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        card.setPadding(dp(16), dp(14), dp(8), dp(14))

        textBlock = LinearLayout(context)
        textBlock.setOrientation(LinearLayout.VERTICAL)

        titleView = TextView(context)
        titleView.setText(str(strings.download_path))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        textBlock.addView(titleView, LayoutHelper.createLinear(-2, -2))

        pathView = TextView(context)
        pathView.setText(currentPath)
        pathView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        pathView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        try:
            pathView.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        textBlock.addView(pathView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 4))

        freeSpace = _getFreeSpace(currentPath)
        freeView = TextView(context)
        freeView.setText(f"Free: {freeSpace}")
        freeView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        freeView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        textBlock.addView(freeView, LayoutHelper.createLinear(-2, -2))

        card.addView(textBlock, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        editIcon = ImageView(context)
        editIcon.setImageResource(R.drawable.msg_edit)
        editIcon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        editIcon.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
        editIcon.setPadding(dp(8), dp(8), dp(8), dp(8))
        editIcon.setOnClickListener(OnClickListener(lambda v: _showEditPathDialog(context, pathView, freeView)))
        card.addView(editIcon, LayoutHelper.createLinear(40, 40, Gravity.CENTER_VERTICAL))

        return card
    except Exception as e:
        log(f"other: _buildDownloadPathCard error: {e}")
        return None


def _buildSearchEngineCards(context, key, default, on_change=None):
    try:
        from elyx import settings as _settings
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from java import dynamic_proxy
        dp = AndroidUtilities.dp

        wrapper = LinearLayout(context)
        wrapper.setOrientation(LinearLayout.VERTICAL)
        wrapper.setPadding(dp(16), dp(8), dp(16), dp(8))

        headerView = TextView(context)
        headerView.setText(str(strings.search_engine))
        headerView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        headerView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        headerView.setGravity(Gravity.CENTER_HORIZONTAL)
        wrapper.addView(headerView, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        wrapper.addView(row, LayoutHelper.createLinear(-1, -2))

        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        surfaceColor = Theme.getColor(Theme.key_windowBackgroundWhite)
        grayColor = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        blackText = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)

        accentR = (accentColor >> 16) & 0xFF
        accentG = (accentColor >> 8) & 0xFF
        accentB = accentColor & 0xFF
        activeFill = Color.argb(30, accentR, accentG, accentB)
        inactiveFill = surfaceColor
        activeStroke = accentColor
        inactiveStroke = Color.argb(40, 128, 128, 128)

        labels = [str(strings.search_engine_native_short), str(strings.search_engine_python_short)]
        subtexts = [str(strings.search_engine_native), str(strings.search_engine_python)]

        current_ref = [_settings.get(key, default)]
        card_refs = [None, None]
        bg_refs = [None, None]

        def lerpColor(c1, c2, t):
            # linear interpolation between two ARGB ints, avoids ArgbEvaluator Long cast issue
            a = int(((c1 >> 24) & 0xFF) + t * (((c2 >> 24) & 0xFF) - ((c1 >> 24) & 0xFF)))
            r = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
            g = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
            b = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
            return Color.argb(a, r, g, b)

        def animateCard(card, bg, toActive):
            fromFill = inactiveFill if toActive else activeFill
            toFill = activeFill if toActive else inactiveFill
            fromStroke = inactiveStroke if toActive else activeStroke
            toStroke = activeStroke if toActive else inactiveStroke
            strokeFrom = dp(1) if toActive else dp(2)
            strokeTo = dp(2) if toActive else dp(1)

            class _Listener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self, anim):
                    t = float(anim.getAnimatedFraction())
                    bg.setColor(lerpColor(fromFill, toFill, t))
                    bg.setStroke(int(strokeFrom + t * (strokeTo - strokeFrom)), lerpColor(fromStroke, toStroke, t))
                    card.setBackground(bg)

            anim = ValueAnimator.ofFloat(0.0, 1.0)
            anim.setDuration(350)
            anim.setInterpolator(DecelerateInterpolator(2.0))
            anim.addUpdateListener(_Listener())
            anim.start()

        def makeCardBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(12))
            bg.setColor(activeFill if active else inactiveFill)
            bg.setStroke(dp(2) if active else dp(1), activeStroke if active else inactiveStroke)
            return bg

        def refreshCards(prev):
            cur = current_ref[0]
            for i, card in enumerate(card_refs):
                if card is not None and bg_refs[i] is not None:
                    if i == cur and i != prev:
                        animateCard(card, bg_refs[i], True)
                    elif i == prev and i != cur:
                        animateCard(card, bg_refs[i], False)

        def makeCardClick(idx):
            def onClick(v):
                prev = current_ref[0]
                if prev == idx:
                    return
                _settings.set(key, idx)
                current_ref[0] = idx
                refreshCards(prev)
                if on_change:
                    on_change(idx)
            return onClick

        for i in range(2):
            card = LinearLayout(context)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setGravity(Gravity.CENTER)
            card.setClickable(True)
            card.setFocusable(True)
            card.setPadding(dp(12), dp(14), dp(12), dp(14))
            cardBg = makeCardBg(current_ref[0] == i)
            card.setBackground(cardBg)
            bg_refs[i] = cardBg
            card.setOnClickListener(OnClickListener(makeCardClick(i)))
            card_refs[i] = card

            nameView = TextView(context)
            nameView.setText(labels[i])
            nameView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            nameView.setTextColor(blackText)
            nameView.setGravity(Gravity.CENTER)
            try:
                nameView.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
            except Exception:
                pass
            card.addView(nameView, LayoutHelper.createLinear(-1, -2))

            subView = TextView(context)
            subView.setText(subtexts[i])
            subView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            subView.setTextColor(grayColor)
            subView.setGravity(Gravity.CENTER)
            card.addView(subView, LayoutHelper.createLinear(-1, -2, 0, 3, 0, 0))

            lp = LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP)
            if i == 0:
                row.addView(card, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 6, 0))
            else:
                row.addView(card, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 0, 0))

        hintView = TextView(context)
        hintView.setText(str(strings.search_engine_desc))
        hintView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        hintView.setTextColor(grayColor)
        wrapper.addView(hintView, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

        return wrapper
    except Exception as e:
        log(f"_buildSearchEngineCards error: {e}")
        return None


def _buildSearchEngineToggle(context, key, default, on_change=None):
    try:
        from elyx import settings as _settings
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        dp = AndroidUtilities.dp

        wrapper = LinearLayout(context)
        wrapper.setOrientation(LinearLayout.VERTICAL)
        wrapper.setPadding(dp(16), dp(8), dp(16), dp(8))

        headerRow = LinearLayout(context)
        headerRow.setOrientation(LinearLayout.HORIZONTAL)
        headerRow.setGravity(Gravity.CENTER_VERTICAL)
        wrapper.addView(headerRow, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

        labelView = TextView(context)
        labelView.setText(str(strings.search_engine))
        labelView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        labelView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        headerRow.addView(labelView, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        grayColor = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        surfaceColor = Theme.getColor(Theme.key_windowBackgroundWhite)
        blackText = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)

        labels = [str(strings.search_engine_native_short), str(strings.search_engine_python_short)]
        current_ref = [_settings.get(key, default)]

        trackBg = GradientDrawable()
        trackBg.setCornerRadius(dp(10))
        trackBg.setColor(Theme.getColor(Theme.key_switchTrack))

        track = LinearLayout(context)
        track.setOrientation(LinearLayout.HORIZONTAL)
        track.setBackground(trackBg)
        track.setPadding(dp(2), dp(2), dp(2), dp(2))
        headerRow.addView(track, LayoutHelper.createLinear(-2, 36, Gravity.CENTER_VERTICAL))

        btn_views = [None, None]

        def makeThumbBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(8))
            bg.setColor(accentColor if active else 0x00000000)
            return bg

        def refreshToggle():
            cur = current_ref[0]
            for i, btn in enumerate(btn_views):
                if btn is not None:
                    btn.setBackground(makeThumbBg(cur == i))
                    btn.setTextColor(blackText if cur == i else grayColor)

        def makeToggleClick(idx):
            def onClick(v):
                _settings.set(key, idx)
                current_ref[0] = idx
                refreshToggle()
                if on_change:
                    on_change(idx)
            return onClick

        for i, label in enumerate(labels):
            btn = TextView(context)
            btn.setText(label)
            btn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            btn.setGravity(Gravity.CENTER)
            btn.setClickable(True)
            btn.setFocusable(True)
            btn.setPadding(dp(14), dp(4), dp(14), dp(4))
            btn.setBackground(makeThumbBg(current_ref[0] == i))
            btn.setTextColor(blackText if current_ref[0] == i else grayColor)
            btn.setOnClickListener(OnClickListener(makeToggleClick(i)))
            btn_views[i] = btn
            track.addView(btn, LayoutHelper.createLinear(-2, -1))

        hintView = TextView(context)
        hintView.setText(str(strings.search_engine_desc))
        hintView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        hintView.setTextColor(grayColor)
        wrapper.addView(hintView, LayoutHelper.createLinear(-1, -2))

        return wrapper
    except Exception as e:
        log(f"_buildSearchEngineToggle error: {e}")
        return None


def _buildHashFunctionCards(context, key, default, on_change=None):
    try:
        from elyx import settings as _settings
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from java import dynamic_proxy
        dp = AndroidUtilities.dp

        wrapper = LinearLayout(context)
        wrapper.setOrientation(LinearLayout.VERTICAL)
        wrapper.setPadding(dp(16), dp(8), dp(16), dp(8))

        headerView = TextView(context)
        headerView.setText(str(strings.hash_function))
        headerView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        headerView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        headerView.setGravity(Gravity.CENTER_HORIZONTAL)
        wrapper.addView(headerView, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        wrapper.addView(row, LayoutHelper.createLinear(-1, -2))

        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        surfaceColor = Theme.getColor(Theme.key_windowBackgroundWhite)
        grayColor = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        blackText = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)

        accentR = (accentColor >> 16) & 0xFF
        accentG = (accentColor >> 8) & 0xFF
        accentB = accentColor & 0xFF
        activeFill = Color.argb(30, accentR, accentG, accentB)
        inactiveFill = surfaceColor
        activeStroke = accentColor
        inactiveStroke = Color.argb(40, 128, 128, 128)

        # 0 = sha256 (default), 1 = bithash
        labels = [str(strings.hash_function_sha256_short), str(strings.hash_function_bithash_short)]
        subtexts = [str(strings.hash_function_sha256_sub), str(strings.hash_function_bithash_sub)]

        current_ref = [_settings.get(key, default)]
        card_refs = [None, None]
        bg_refs = [None, None]

        def lerpColor(c1, c2, t):
            a = int(((c1 >> 24) & 0xFF) + t * (((c2 >> 24) & 0xFF) - ((c1 >> 24) & 0xFF)))
            r = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
            g = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
            b = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
            return Color.argb(a, r, g, b)

        def animateCard(card, bg, toActive):
            fromFill = inactiveFill if toActive else activeFill
            toFill = activeFill if toActive else inactiveFill
            fromStroke = inactiveStroke if toActive else activeStroke
            toStroke = activeStroke if toActive else inactiveStroke
            strokeFrom = dp(1) if toActive else dp(2)
            strokeTo = dp(2) if toActive else dp(1)

            class _Listener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self, anim):
                    t = float(anim.getAnimatedFraction())
                    bg.setColor(lerpColor(fromFill, toFill, t))
                    bg.setStroke(int(strokeFrom + t * (strokeTo - strokeFrom)), lerpColor(fromStroke, toStroke, t))
                    card.setBackground(bg)

            anim = ValueAnimator.ofFloat(0.0, 1.0)
            anim.setDuration(350)
            anim.setInterpolator(DecelerateInterpolator(2.0))
            anim.addUpdateListener(_Listener())
            anim.start()

        def makeCardBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(12))
            bg.setColor(activeFill if active else inactiveFill)
            bg.setStroke(dp(2) if active else dp(1), activeStroke if active else inactiveStroke)
            return bg

        def refreshCards(prev):
            cur = current_ref[0]
            for i, card in enumerate(card_refs):
                if card is not None and bg_refs[i] is not None:
                    if i == cur and i != prev:
                        animateCard(card, bg_refs[i], True)
                    elif i == prev and i != cur:
                        animateCard(card, bg_refs[i], False)

        def makeCardClick(idx):
            def onClick(v):
                prev = current_ref[0]
                if prev == idx:
                    return
                _settings.set(key, idx)
                current_ref[0] = idx
                refreshCards(prev)
                if on_change:
                    on_change(idx)
            return onClick

        for i in range(2):
            card = LinearLayout(context)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setGravity(Gravity.CENTER)
            card.setClickable(True)
            card.setFocusable(True)
            card.setPadding(dp(12), dp(14), dp(12), dp(14))
            cardBg = makeCardBg(current_ref[0] == i)
            card.setBackground(cardBg)
            bg_refs[i] = cardBg
            card.setOnClickListener(OnClickListener(makeCardClick(i)))
            card_refs[i] = card

            nameView = TextView(context)
            nameView.setText(labels[i])
            nameView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            nameView.setTextColor(blackText)
            nameView.setGravity(Gravity.CENTER)
            try:
                nameView.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
            except Exception:
                pass
            card.addView(nameView, LayoutHelper.createLinear(-1, -2))

            subView = TextView(context)
            subView.setText(subtexts[i])
            subView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            subView.setTextColor(grayColor)
            subView.setGravity(Gravity.CENTER)
            card.addView(subView, LayoutHelper.createLinear(-1, -2, 0, 3, 0, 0))

            if i == 0:
                row.addView(card, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 6, 0))
            else:
                row.addView(card, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 0, 0))

        hintView = TextView(context)
        hintView.setText(str(strings.hash_function_desc))
        hintView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        hintView.setTextColor(grayColor)
        wrapper.addView(hintView, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))

        return wrapper
    except Exception as e:
        log(f"_buildHashFunctionCards error: {e}")
        return None


def _buildSortMenuDesignToggle(context, key, default, on_change=None):
    try:
        from elyx import settings as _settings
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from android.view import View
        from android.widget import ImageView
        from java import dynamic_proxy
        from hook_utils import find_class
        dp = AndroidUtilities.dp

        wrapper = LinearLayout(context)
        wrapper.setOrientation(LinearLayout.VERTICAL)
        wrapper.setPadding(dp(16), dp(8), dp(16), dp(8))

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        wrapper.addView(row, LayoutHelper.createLinear(-1, -2))

        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        surfaceColor = Theme.getColor(Theme.key_windowBackgroundWhite)
        grayColor = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        blackText = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        dialogBg = Theme.getColor(Theme.key_dialogBackground)
        dialogBgGray = Theme.getColor(Theme.key_dialogBackgroundGray)
        dialogTextBlack = Theme.getColor(Theme.key_dialogTextBlack)
        dialogTextGray = Theme.getColor(Theme.key_dialogTextGray2)
        buttonText = Theme.getColor(Theme.key_featuredStickers_buttonText)

        accentR = (accentColor >> 16) & 0xFF
        accentG = (accentColor >> 8) & 0xFF
        accentB = accentColor & 0xFF
        activeStroke = accentColor
        inactiveStroke = Color.argb(40, 128, 128, 128)

        # 0 = modern (default), 1 = classic
        current_ref = [_settings.get(key, default)]
        card_refs = [None, None]
        bg_refs = [None, None]

        def lerpColor(c1, c2, t):
            a = int(((c1 >> 24) & 0xFF) + t * (((c2 >> 24) & 0xFF) - ((c1 >> 24) & 0xFF)))
            r = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
            g = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
            b = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
            return Color.argb(a, r, g, b)

        def animateCard(card, bg, toActive):
            fromStroke = inactiveStroke if toActive else activeStroke
            toStroke = activeStroke if toActive else inactiveStroke
            strokeFrom = dp(1) if toActive else dp(2)
            strokeTo = dp(2) if toActive else dp(1)

            class _Listener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self, anim):
                    t = float(anim.getAnimatedFraction())
                    bg.setStroke(int(strokeFrom + t * (strokeTo - strokeFrom)), lerpColor(fromStroke, toStroke, t))
                    card.setBackground(bg)

            anim = ValueAnimator.ofFloat(0.0, 1.0)
            anim.setDuration(350)
            anim.setInterpolator(DecelerateInterpolator(2.0))
            anim.addUpdateListener(_Listener())
            anim.start()

        def makeCardBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(12))
            bg.setColor(0x00000000)
            bg.setStroke(dp(2) if active else dp(1), activeStroke if active else inactiveStroke)
            return bg

        def refreshCards(prev):
            cur = current_ref[0]
            for i, card in enumerate(card_refs):
                if card is not None and bg_refs[i] is not None:
                    if i == cur and i != prev:
                        animateCard(card, bg_refs[i], True)
                    elif i == prev and i != cur:
                        animateCard(card, bg_refs[i], False)

        def makeCardClick(idx):
            def onClick(v):
                prev = current_ref[0]
                if prev == idx:
                    return
                _settings.set(key, idx)
                current_ref[0] = idx
                refreshCards(prev)
                if on_change:
                    on_change(idx)
            return onClick

        def resolveIcon(name):
            try:
                R = find_class("org.telegram.messenger.R")
                return getattr(R.drawable, name)
            except Exception:
                return 0

        def buildPreviewRow(act, isClassic):
            container = LinearLayout(act)
            container.setOrientation(LinearLayout.VERTICAL)
            container.setPadding(dp(6), dp(6), dp(6), dp(4))

            previewBg = GradientDrawable()
            previewBg.setCornerRadius(dp(8))
            previewBg.setColor(dialogBg)
            container.setBackground(previewBg)

            def makeRow(label, isSelected):
                optRow = LinearLayout(act)
                optRow.setOrientation(LinearLayout.HORIZONTAL)
                optRow.setGravity(Gravity.CENTER_VERTICAL)
                optRow.setPadding(dp(6), dp(5), dp(6), dp(5))

                rowBg = GradientDrawable()
                rowBg.setCornerRadius(dp(5))
                rowBg.setColor(accentColor if (isSelected and isClassic) else 0x00000000)
                optRow.setBackground(rowBg)

                if not isClassic:
                    dot = FrameLayout(act)
                    dotSize = dp(8)
                    dotBg = GradientDrawable()
                    dotBg.setShape(GradientDrawable.OVAL)
                    if isSelected:
                        dotBg.setColor(accentColor)
                        dotBg.setStroke(dp(1), Color.WHITE)
                    else:
                        dotBg.setColor(0x00000000)
                    dot.setBackground(dotBg)
                    dotLp = LinearLayout.LayoutParams(dotSize, dotSize)
                    dotLp.rightMargin = dp(5)
                    optRow.addView(dot, dotLp)

                iconView = ImageView(act)
                iconId = resolveIcon("msg_archive")
                if iconId:
                    iconView.setImageResource(iconId)
                    if isSelected and isClassic:
                        iconView.setColorFilter(Color.WHITE)
                    elif isSelected:
                        iconView.setColorFilter(accentColor)
                    else:
                        iconView.setColorFilter(dialogTextGray)
                iconLp = LinearLayout.LayoutParams(dp(12), dp(12))
                iconLp.rightMargin = dp(5)
                optRow.addView(iconView, iconLp)

                labelView = TextView(act)
                labelView.setText(label)
                labelView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 9)
                if isSelected and isClassic:
                    labelView.setTextColor(buttonText)
                elif isSelected:
                    labelView.setTextColor(accentColor)
                else:
                    labelView.setTextColor(dialogTextBlack)
                optRow.addView(labelView, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))

                return optRow

            container.addView(makeRow("A \u2192 Z", True), LayoutHelper.createLinear(-1, -2))

            div = View(act)
            div.setBackgroundColor(Theme.getColor(Theme.key_divider))
            container.addView(div, LayoutHelper.createLinear(-1, 1, 0, dp(4), 0, dp(4)))

            container.addView(makeRow("Z \u2192 A", False), LayoutHelper.createLinear(-1, -2))

            return container

        for i in range(2):
            # outer column: card + label underneath
            col = LinearLayout(context)
            col.setOrientation(LinearLayout.VERTICAL)
            col.setGravity(Gravity.CENTER_HORIZONTAL)

            card = LinearLayout(context)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setGravity(Gravity.CENTER_HORIZONTAL)
            card.setClickable(True)
            card.setFocusable(True)
            card.setPadding(dp(10), dp(10), dp(10), dp(10))
            cardBg = makeCardBg(current_ref[0] == i)
            card.setBackground(cardBg)
            bg_refs[i] = cardBg
            card.setOnClickListener(OnClickListener(makeCardClick(i)))
            card_refs[i] = card

            preview = buildPreviewRow(context, isClassic=(i == 1))
            card.addView(preview, LayoutHelper.createLinear(-1, -2))
            col.addView(card, LayoutHelper.createLinear(-1, -2))

            if i == 0:
                row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 6, 0))
            else:
                row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 0, 0))

        return wrapper
    except Exception as e:
        log(f"_buildSortMenuDesignToggle error: {e}")
        return None


class OtherSettings:
    def __init__(self, chat_button=None, plugin=None):
        self.chat_button = chat_button
        self.plugin = plugin

    def _build_dialogs_btn_item(self, ctx):
        try:
            if ctx:
                view = _buildTextSubtextCell(
                    ctx,
                    text=strings.button_in_dialogs_menu,
                    subtext=strings.button_in_dialogs_menu_desc,
                    icon="msg_addbot",
                    on_click=self._open_main_menu_settings
                )
                if view is not None:
                    return Custom(view=view)
            log("other: _build_dialogs_btn_item falling back to Text")
        except Exception as e:
            log(f"other: _build_dialogs_btn_item error: {e}")
        return Text(
            text=strings.button_in_dialogs_menu,
            icon="msg_addbot",
            on_click=self._open_main_menu_settings
        )

    def _build_sort_menu_design_item(self, ctx):
        try:
            if ctx:
                view = _buildSortMenuDesignToggle(ctx, key="old_sort_menu_design", default=False)
                if view is not None:
                    return Custom(view=view)
            log("other: _build_sort_menu_design_item falling back to Switch")
        except Exception as e:
            log(f"other: _build_sort_menu_design_item error: {e}")
        return Switch(
            key="old_sort_menu_design",
            text=strings.classic_sort_menu,
            subtext=strings.classic_sort_menu_desc,
            default=False,
            icon="msg_list",
            link_alias="old_sort_menu_design"
        )

    def _build_search_engine_item(self, ctx):
        try:
            if ctx:
                view = _buildSearchEngineCards(ctx, key="search_engine", default=0)
                if view is not None:
                    return Custom(view=view)
            log("other: _build_search_engine_item falling back to Text")
        except Exception as e:
            log(f"other: _build_search_engine_item error: {e}")
        return Text(
            text=strings.search_engine,
            icon="msg_speed",
        )

    def _build_hash_function_item(self, ctx):
        try:
            if ctx:
                # 0 = sha256 (default), 1 = bithash
                view = _buildHashFunctionCards(ctx, key="hash_function", default=0)
                if view is not None:
                    return Custom(view=view)
            log("other: _build_hash_function_item falling back to Text")
        except Exception as e:
            log(f"other: _build_hash_function_item error: {e}")
        return Text(
            text=strings.hash_function,
            icon="msg_sendfile",
        )

    def _build_search_engine_item_v3(self, ctx):
        try:
            if ctx:
                view = _buildSearchEngineToggle(ctx, key="search_engine", default=0)
                if view is not None:
                    return Custom(view=view)
            log("other: _build_search_engine_item_v3 falling back to Text")
        except Exception as e:
            log(f"other: _build_search_engine_item_v3 error: {e}")
        return Text(
            text=strings.search_engine,
            icon="msg_speed",
        )

    def _open_main_menu_settings(self, view):
        try:
            from hook_utils import find_class
            frag = get_last_fragment()
            if frag:
                MainMenuPreferencesActivity = find_class("com.exteragram.messenger.preferences.appearance.AppNavigationPreferencesActivity")
                frag.presentFragment(MainMenuPreferencesActivity())
        except Exception as e:
            log(f"OtherSettings: _open_main_menu_settings error: {e}")

    def _build_pill_stack_item(self, ctx):
        try:
            if ctx:
                view = _buildTextSubtextCell(
                    ctx,
                    text=strings.pill_stack_settings,
                    subtext=strings.pill_stack_settings_desc,
                    icon="msg_view_file",
                    on_click=self._open_pill_stack_settings
                )
                if view is not None:
                    return Custom(view=view)
            log("other: _build_pill_stack_item falling back to Text")
        except Exception as e:
            log(f"other: _build_pill_stack_item error: {e}")
        return Text(
            text=strings.pill_stack_settings,
            icon="msg_view_file",
            on_click=self._open_pill_stack_settings
        )

    def _build_font_picker_item(self, ctx):
        try:
            if ctx:
                selected = getSelectedFilename()
                subtext = str(strings.font_picker_desc)
                if selected:
                    display = selected
                    if display.lower().endswith(".ttf"):
                        display = display[:-4]
                    display = display.replace("-", " ").replace("_", " ")
                    subtext = display
                view = _buildTextSubtextCell(
                    ctx,
                    text=strings.font_picker,
                    subtext=subtext,
                    icon="msg_theme",
                    on_click=self._open_font_picker
                )
                if view is not None:
                    return Custom(view=view)
            log("other: _build_font_picker_item falling back to Text")
        except Exception as e:
            log(f"other: _build_font_picker_item error: {e}")
        return Text(
            text=strings.font_picker,
            icon="msg_theme",
            on_click=self._open_font_picker
        )

    def _open_font_picker(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return
            showFontPicker(act)
        except Exception as e:
            log(f"OtherSettings: _open_font_picker error: {e}")

    def _open_pill_stack_settings(self, view):
        try:
            from hook_utils import find_class
            PillStackPreferencesActivity = find_class("com.exteragram.messenger.pillstack.ui.PillStackPreferencesActivity")
            if PillStackPreferencesActivity is None:
                return
            frag = get_last_fragment()
            if frag:
                frag.presentFragment(PillStackPreferencesActivity())
        except Exception as e:
            log(f"OtherSettings: _open_pill_stack_settings error: {e}")

    def _open_files_browser(self):
        try:
            from ..ui.FilesActivity.fragment import show_files_browser
            show_files_browser(plugin=self.plugin)
        except Exception as e:
            log(f"OtherSettings: _open_files_browser error: {e}")

    def _getCacheDir(self) -> str:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        return f"/data/data/{pkg}/files/packitCache"

    def _killProcess(self):
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGKILL)

    def _onClearCacheClick(self, view):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return

            builder = AlertDialogBuilder(act)
            builder.set_title(strings.clear_cache_confirm_title)
            builder.set_message(strings.clear_cache_confirm_message)

            def onConfirm(b, w):
                b.dismiss()
                try:
                    cacheDir = self._getCacheDir()
                    if os.path.exists(cacheDir):
                        shutil.rmtree(cacheDir)
                except Exception as e:
                    log(f"clear cache error: {e}")

                try:
                    frag2 = get_last_fragment()
                    act2 = frag2.getParentActivity() if frag2 else None
                    if not act2:
                        return

                    restartBuilder = AlertDialogBuilder(act2)
                    restartBuilder.set_title(strings.clear_cache_done_title)
                    restartBuilder.set_message(strings.clear_cache_done_message)

                    def onRestart(rb, rw):
                        rb.dismiss()
                        thread = threading.Thread(target=self._killProcess)
                        thread.daemon = True
                        thread.start()

                    restartBuilder.set_positive_button(strings.restart_now, onRestart)
                    restartBuilder.set_negative_button(strings.restart_later, lambda rb, rw: rb.dismiss())
                    restartBuilder.show()
                except Exception as e:
                    log(f"clear cache restart dialog error: {e}")

            builder.set_positive_button(strings.clear_cache_button, onConfirm)
            builder.set_negative_button(strings.cancel_button, lambda b, w: b.dismiss())
            try:
                builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
            except Exception as e:
                log(f"make_button_red error: {e}")
            builder.show()
        except Exception as e:
            log(f"clear cache dialog error: {e}")

    def _onClearPluginCacheClick(self, view):
        try:
            pkg = ApplicationLoader.applicationContext.getPackageName()
            plugin_cache_dir = f"/data/data/{pkg}/files/packitCache/pluginCache"
            if os.path.exists(plugin_cache_dir):
                shutil.rmtree(plugin_cache_dir)
                log("other: plugin cache cleared")
        except Exception as e:
            log(f"other: clear plugin cache error: {e}")

    def _getContext(self):
        frag = get_last_fragment()
        return frag.getParentActivity() if frag else None

    def _onRestartRequiredSwitch(self, val):
        def show():
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return
                builder = AlertDialogBuilder(act)
                builder.set_title(strings.restart_required_title)
                builder.set_message(strings.restart_required_message)

                def onRestart(b, w):
                    b.dismiss()
                    thread = threading.Thread(target=self._killProcess)
                    thread.daemon = True
                    thread.start()

                builder.set_positive_button(strings.restart_now, onRestart)
                builder.set_negative_button(strings.restart_later, lambda b, w: b.dismiss())
                builder.show()
            except Exception as e:
                log(f"other: _onRestartRequiredSwitch error: {e}")

        from android_utils import run_on_ui_thread
        run_on_ui_thread(show)

    def _open_card_editor(self):
        try:
            from .PluginCardEditor import build_card_editor_page
            return build_card_editor_page()
        except Exception as e:
            log(f"OtherSettings: _open_card_editor error: {e}")
            return []

    def _onClearIgnoreListClick(self, view):
        try:
            from ..ui.pluginsUpdates.clearIgnoreListDialog import show_clear_ignore_list_dialog
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return
            show_clear_ignore_list_dialog(act)
        except Exception as e:
            log(f"OtherSettings: _onClearIgnoreListClick error: {e}")

    def build(self):
        ctx = self._getContext()

        items = [
            Header(text=strings.buttons_header),
            self._build_dialogs_btn_item(ctx),
            self._build_pill_stack_item(ctx),
            Switch(
                key="show_chat_menu",
                text=strings.button_in_chat_menu,
                subtext=strings.button_in_chat_menu_desc,
                default=False,
                icon="msg_settings",
                link_alias="show_chat_menu",
                on_change=self.chat_button.on_chat_switch if self.chat_button else None
            ),
            Switch(
                key="show_chat_plugins_menu",
                text=strings.button_in_chat_plugins,
                subtext=strings.button_in_chat_plugins_desc,
                default=False,
                icon="msg_plugins",
                link_alias="show_chat_plugins_menu",
                on_change=self.chat_button.on_chat_plugins_switch if self.chat_button else None
            ),

            Switch(
                key="show_settings_button",
                text=strings.show_settings_button,
                subtext=strings.show_settings_button_desc,
                default=True,
                icon="msg_settings",
                link_alias="show_settings_button",
                on_change=self._onRestartRequiredSwitch
            ),
        ]

        items += [
            Divider(text=strings.buttons_header_desc),
            Header(text=strings.interface_header),
            self._build_sort_menu_design_item(ctx),
            self._build_font_picker_item(ctx),
            Text(
                text=strings.edit_plugin_card,
                subtext=strings.edit_plugin_card_desc,
                icon="msg_edit",
                create_sub_fragment=self._open_card_editor
            ),
            Switch(
                key="hide_unavailable_plugins",
                text=strings.hide_unavailable_plugins,
                subtext=strings.hide_unavailable_plugins_desc,
                default=False,
                icon="msg_block",
                link_alias="hide_unavailable_plugins"
            ),
            Divider(),
            Header(text=strings.plugin_profile_header),
            Switch(
                key="show_extended_desc",
                text=strings.show_extended_desc,
                subtext=strings.show_extended_desc_desc,
                default=False,
                icon="msg_info",
            ),
            Divider(text=strings.show_extended_desc_hint),
            Header(text=strings.install_sheet_header),
            Switch(
                key="install_sheet_links",
                text=strings.install_sheet_links,
                subtext=strings.install_sheet_links_desc,
                default=True,
                icon="msg_link",
                link_alias="install_sheet_links"
            ),
            Switch(
                key="install_sheet_hash",
                text=strings.install_sheet_hash,
                subtext=strings.install_sheet_hash_desc,
                default=True,
                icon="msg_sendfile",
                link_alias="install_sheet_hash"
            ),
            Switch(
                key="install_sheet_signatures",
                text=strings.install_sheet_signatures,
                subtext=strings.install_sheet_signatures_desc,
                default=True,
                icon="msg_policy",
                link_alias="install_sheet_signatures"
            ),
            Divider(),
            Header(text=strings.navigation_header),
            Switch(
                key="skip_repository_selection",
                text=strings.skip_repository_selection,
                subtext=strings.skip_repository_selection_desc,
                default=False,
                icon="msg_leave",
                link_alias="skip_repository_selection"
            ),
            Switch(
                key="version_picker_auto_expand",
                text=strings.version_picker_auto_expand,
                subtext=strings.version_picker_auto_expand_desc,
                default=False,
                icon="msg_list",
                link_alias="version_picker_auto_expand"
            ),
            Divider(text=strings.navigation_header_desc),
            Header(text=strings.sfx_header),
            Switch(key="sfx_install", text=strings.sfx_install, default=False, icon="msg_download", link_alias="sfx_install"),
            Switch(key="sfx_copy_link", text=strings.sfx_copy_link, default=False, icon="msg_link", link_alias="sfx_copy_link"),
            Switch(key="sfx_search", text=strings.sfx_search, default=False, icon="msg_search", link_alias="sfx_search"),
            Switch(key="sfx_clear_search", text=strings.sfx_clear_search, default=False, icon="msg_close", link_alias="sfx_clear_search"),
            Switch(key="sfx_achievement", text=strings.sfx_achievement, default=True, icon="msg_gift_premium", link_alias="sfx_achievement"),
            Divider(text=strings.sfx_header_desc),
            Header(text=strings.components_header),
            self._build_search_engine_item(ctx),    
            self._build_hash_function_item(ctx),
            Divider(),
            Header(text=strings.misc_header),
            Switch(
                key="show_startup_status",
                text=strings.show_startup_status,
                subtext=strings.show_startup_status_desc,
                default=False,
                icon="msg_info",
                link_alias="show_startup_status"
            ),
            Switch(
                key="fuzzy_search",
                text=strings.fuzzy_search,
                subtext=strings.fuzzy_search_desc,
                default=True,
                icon="msg_search",
                link_alias="fuzzy_search"
            ),
            Switch(
                key="static_online_status",
                text=strings.static_online_status,
                subtext=strings.static_online_status_desc,
                default=False,
                icon="msg_online",
                link_alias="static_online_status"
            ),
            Switch(
                key="show_from_repo",
                text=strings.show_from_repo,
                subtext=strings.show_from_repo_desc,
                default=False,
                icon="msg_channel",
                link_alias="show_from_repo"
            ),
        ]

        items.append(Switch(
            key="disable_achievements_notify",
            text=strings.disable_achievements_notify,
            subtext=strings.disable_achievements_notify_desc,
            default=False,
            icon="msg_gift_premium",
            link_alias="disable_achievements_notify"
        ))

        items.append(Divider())
        items.append(Header(text=strings.updating_plugins_header))
        items.append(Switch(
            key="show_updates_on_startup",
            text=strings.show_updates_on_startup,
            subtext=strings.show_updates_on_startup_desc,
            default=False,
            icon="msg_download",
            link_alias="show_updates_on_startup"
        ))
        items.append(Text(
            text=strings.clear_ignore_list,
            subtext=strings.clear_ignore_list_desc,
            icon="msg_delete",
            on_click=self._onClearIgnoreListClick
        ))

        items.append(Divider())

        # filesystem section should always be at the bottom of the page
        items.append(Header(text=strings.filesystem_header))
        if ctx:
            openDirView = _buildTextSubtextCellIconRight(
                ctx,
                text="Open Directory",
                subtext="Browse packitCache files and folders",
                icon="files_folder",
                on_click=lambda v: self._open_files_browser()
            )
            if openDirView is not None:
                items.append(Custom(view=openDirView))
            else:
                items.append(Text(
                    text="Open Directory",
                    icon="files_folder",
                    on_click=lambda v: self._open_files_browser()
                ))
        else:
            items.append(Text(
                text="Open Directory",
                icon="files_folder",
                on_click=lambda v: self._open_files_browser()
            ))

        pathCardBuilt = False
        if ctx:
            currentPath = settings.get("download_path", "/storage/emulated/0/Download")
            pathCard = _buildDownloadPathCard(ctx, currentPath)
            if pathCard is not None:
                items.append(Custom(view=pathCard))
                pathCardBuilt = True
            else:
                log("OtherSettings.build: _buildDownloadPathCard returned None")

        if not pathCardBuilt:
            items.append(
                Input(
                    key="download_path",
                    text=strings.download_path,
                    default="/storage/emulated/0/Download",
                    icon="msg_download"
                )
            )

        if ctx:
            cacheDir = self._getCacheDir()
            cacheCard = _buildCacheCard(ctx, cacheDir, self._onClearCacheClick)
            if cacheCard is not None:
                items.append(Custom(view=cacheCard))
            else:
                items.append(Text(
                    text=strings.clear_cache,
                    icon="msg_delete",
                    on_click=self._onClearCacheClick,
                    red=True
                ))

            pkg = ApplicationLoader.applicationContext.getPackageName()
            pluginCacheDir = f"/data/data/{pkg}/files/packitCache/pluginCache"
            pluginCacheCard = _buildCacheCard(ctx, pluginCacheDir, self._onClearPluginCacheClick, title=strings.clear_plugin_cache)
            if pluginCacheCard is not None:
                items.append(Custom(view=pluginCacheCard))
            else:
                items.append(Text(
                    text=strings.clear_plugin_cache,
                    icon="msg_delete",
                    on_click=self._onClearPluginCacheClick,
                    red=True
                ))
        else:
            items.append(Text(
                text=strings.clear_cache,
                icon="msg_delete",
                on_click=self._onClearCacheClick,
                red=True
            ))
            items.append(Text(
                text=strings.clear_plugin_cache,
                icon="msg_delete",
                on_click=self._onClearPluginCacheClick,
                red=True
            ))

        items.append(Divider(text=strings.cache_header_desc))

        return items

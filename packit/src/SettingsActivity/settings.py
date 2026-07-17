# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Switch, Divider, Text, Input, Custom
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import run_on_ui_thread, OnClickListener
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
from extera_utils.classes import Base, java_subclass, jMVELoverride, joverride

def _reload_plugin_settings():
    try:
        from com.exteragram.messenger.plugins import PluginsController
        PluginsController.getInstance().loadPluginSettings("shareui_packit")
    except Exception as e:
        logx(f"settings: reload failed: {e}", False)


def _open_url(url):
    try:
        from android_utils import run_on_ui_thread
        from client_utils import get_last_fragment
        def _do():
            try:
                act = get_last_fragment().getParentActivity()
                if _Browser:
                    _Browser.openUrl(act, Uri.parse(url), True, True, True, None, None, False, False, False)
                else:
                    from android.content import Intent
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(url))
                    act.startActivity(intent)
            except Exception as e:
                logx(f"settings: _open_url ui error: {e}", False)
        run_on_ui_thread(_do)
    except Exception as e:
        logx(f"settings: _open_url error: {e}", False)

def _fmt_inline_str(template):
    # replaces {cmd} in template with the current inline command setting
    try:
        from elyx import settings as _s
        cmd = _s.get("inline_search_command", ".packit").strip() or ".packit"
    except Exception:
        cmd = ".packit"
    return template.replace("{cmd}", cmd)

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


@java_subclass(FrameLayout)
class TextSubtextCell(Base):
    @joverride()
    def onMeasure(self, widthMeasureSpec: int, heightMeasureSpec: int):
        from android.view import View
        MS = View.MeasureSpec
        # measure with unconstrained height to get natural content height
        super().onMeasure(
            MS.makeMeasureSpec(MS.getSize(widthMeasureSpec), MS.EXACTLY),
            MS.makeMeasureSpec(0, MS.UNSPECIFIED),
        )
        h = max(self.getMeasuredHeight(), AndroidUtilities.dp(64))
        super().onMeasure(
            MS.makeMeasureSpec(MS.getSize(widthMeasureSpec), MS.EXACTLY),
            MS.makeMeasureSpec(h, MS.EXACTLY),
        )

    def on_post_init(self, context):
        from android.widget import ImageView
        dp = AndroidUtilities.dp

        self.setWillNotDraw(False)
        self._need_divider = False

        # icon left (visible when icon_right=False)
        self._iconLeft = ImageView(context)
        self._iconLeft.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
        self.addView(self._iconLeft, LayoutHelper.createFrame(24, 24, Gravity.LEFT | Gravity.CENTER_VERTICAL, 23, 0, 0, 0))

        # text block
        textBlock = LinearLayout(context)
        textBlock.setOrientation(LinearLayout.VERTICAL)
        self._textBlock = textBlock

        self._titleView = TextView(context)
        self._titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        self._titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))

        self._subtitleView = TextView(context)
        self._subtitleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        self._subtitleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))

        textBlock.addView(self._titleView, LayoutHelper.createLinear(-1, -2))
        textBlock.addView(self._subtitleView, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))
        self.addView(textBlock)

        # icon right (visible when icon_right=True)
        self._iconRight = ImageView(context)
        self._iconRight.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        self._iconRight.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
        self._iconRight.setPadding(dp(8), dp(8), dp(8), dp(8))
        self.addView(self._iconRight, LayoutHelper.createFrame(-2, -2, Gravity.RIGHT | Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

        # full-row ripple background (used for icon_left mode)
        self._rippleBg = Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2)

    def set_data(self, text, subtext, icon_name, on_click, icon_right=False, need_divider=False):
        from hook_utils import find_class
        dp = AndroidUtilities.dp

        self._need_divider = need_divider

        # resolve icon id
        icon_id = 0
        try:
            icon_id = int(getattr(find_class("org.telegram.messenger.R").drawable, icon_name))
        except Exception as e:
            logx(f"TextSubtextCell icon resolve error: {e}", False)

        self._titleView.setText(str(text))

        if subtext:
            self._subtitleView.setText(str(subtext))
            self._subtitleView.setVisibility(0)  # VISIBLE
        else:
            self._subtitleView.setVisibility(8)  # GONE

        if icon_right:
            self.setClickable(False)
            self.setFocusable(False)
            self.setBackground(None)

            self._iconLeft.setVisibility(8)  # GONE
            self._iconRight.setVisibility(0)  # VISIBLE
            if icon_id:
                self._iconRight.setImageResource(icon_id)
            self._iconRight.setOnClickListener(OnClickListener(on_click))

            self._titleView.setGravity(Gravity.LEFT)
            # right margin 56dp leaves room for the icon button (40dp) + 8dp padding + 8dp gap
            self._textBlock.setLayoutParams(LayoutHelper.createFrame(-1, -2, Gravity.LEFT | Gravity.CENTER_VERTICAL, 16, 10, 56, 10))
        else:
            self.setClickable(True)
            self.setFocusable(True)
            self.setBackground(self._rippleBg)
            self.setOnClickListener(OnClickListener(on_click))

            self._iconRight.setVisibility(8)  # GONE
            self._iconLeft.setVisibility(0 if icon_id else 8)
            if icon_id:
                self._iconLeft.setImageResource(icon_id)

            # 23+24+25=72dp total left offset
            self._textBlock.setLayoutParams(LayoutHelper.createFrame(-1, -2, Gravity.LEFT | Gravity.CENTER_VERTICAL, 72, 10, 17, 10))

        self.invalidate()

    @joverride()
    def onDraw(self, canvas):
        if self._need_divider:
            # matches native TG pattern: drawLine at bottom with dp(20) offset
            canvas.drawLine(
                AndroidUtilities.dp(20), self.getMeasuredHeight() - 1,
                self.getMeasuredWidth(), self.getMeasuredHeight() - 1,
                Theme.dividerPaint,
            )
        super().onDraw(canvas)


def _buildTextSubtextCell(context, text, subtext, icon, on_click, icon_right=False):
    # icon_right=False: icon left, full-row ripple; icon_right=True: text left, icon right
    try:
        cell = TextSubtextCell.new_instance(context)
        cell.set_data(text, subtext, icon, on_click, icon_right=icon_right)
        return cell.java
    except Exception as e:
        logx(f"other: _buildTextSubtextCell error: {e}", False)
        return None


def _buildTextSubtextCellIconRight(context, text, subtext, icon, on_click):
    return _buildTextSubtextCell(context, text, subtext, icon, on_click, icon_right=True)


@java_subclass(LinearLayout)
class CacheCard(Base):
    def on_post_init(self, context):
        from android.widget import ImageView
        dp = AndroidUtilities.dp

        self._cache_dir = None
        self._on_clear = None

        self.setOrientation(LinearLayout.HORIZONTAL)
        self.setGravity(Gravity.CENTER_VERTICAL)
        self.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        self.setPadding(dp(16), dp(14), dp(8), dp(14))

        left = LinearLayout(context)
        left.setOrientation(LinearLayout.VERTICAL)

        self._titleView = TextView(context)
        self._titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        self._titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        left.addView(self._titleView, LayoutHelper.createLinear(-2, -2))

        self._sizeView = TextView(context)
        self._sizeView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        self._sizeView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        left.addView(self._sizeView, LayoutHelper.createLinear(-2, -2, 0, 2, 0, 0))

        self.addView(left, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        clearBtn = ImageView(context)
        clearBtn.setImageResource(R.drawable.msg_clearcache)
        clearBtn.setColorFilter(Theme.getColor(Theme.key_avatar_backgroundRed))
        clearBtn.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 1))
        clearBtn.setPadding(dp(8), dp(8), dp(8), dp(8))
        clearBtn.setOnClickListener(OnClickListener(lambda v: self._on_clear(v) if self._on_clear else None))
        self.addView(clearBtn, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

    def set_data(self, cache_dir, title, on_clear):
        self._cache_dir = cache_dir
        self._on_clear = on_clear
        self._titleView.setText(str(title))
        self.refresh()

    def refresh(self):
        try:
            size, count = _getCacheInfo(self._cache_dir)
            self._sizeView.setText(str(strings.cache_size_label).format(size=size, count=count))
        except Exception as e:
            logx(f"CacheCard refresh error: {e}", False)


def _buildCacheCard(context, cacheDir, on_clear, title=None):
    # card showing cache size with clear button
    try:
        cardTitle = str(title) if title is not None else str(strings.clear_cache)
        card = CacheCard.new_instance(context)
        card.set_data(cacheDir, cardTitle, on_clear)
        return card.java, card.refresh
    except Exception as e:
        logx(f"other: _buildCacheCard error: {e}", False)
        return None, None


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
            logx(f"other: folder_in anim error: {e}", False)

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
                logx(f"other: save download_path error: {e}", False)
            pathView.setText(newPath)
            freeView.setText(str(strings("settings_free_space", space=_getFreeSpace(newPath))))
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
        logx(f"other: _showEditPathDialog error: {e}", False)

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
        freeView.setText(str(strings("settings_free_space", space=freeSpace)))
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
        logx(f"other: _buildDownloadPathCard error: {e}", False)
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
        logx(f"_buildSearchEngineCards error: {e}", False)
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
        logx(f"_buildSearchEngineToggle error: {e}", False)
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
        logx(f"_buildHashFunctionCards error: {e}", False)
        return None


def _getDialogsMenuItems():
    return [
        ("msg_plugins", str(strings["dialogs_menu_packit_settings"])),
        ("msg_addbot", str(strings["install_plugin_btn"])),
        ("input_smile", str(strings["dialogs_menu_install_icon"])),
    ]


_DIALOGS_MENU_ICON_IDS = None


def _getDialogsMenuIconIds():
    global _DIALOGS_MENU_ICON_IDS
    if _DIALOGS_MENU_ICON_IDS is None:
        from hook_utils import find_class
        items = _getDialogsMenuItems()
        ids = []
        for icon_name, _ in items:
            try:
                R = find_class("org.telegram.messenger.R")
                ids.append(int(getattr(R.drawable, icon_name)))
            except Exception:
                ids.append(0)
        _DIALOGS_MENU_ICON_IDS = ids
    return _DIALOGS_MENU_ICON_IDS


def _buildDialogsMenuToggle(context, key, default, on_change=None):
    # vertical toggle: each option is a preview row mimicking a dialogs menu button
    try:
        from elyx import settings as _settings
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from android.widget import ImageView
        from java import dynamic_proxy
        dp = AndroidUtilities.dp

        wrapper = LinearLayout(context)
        wrapper.setOrientation(LinearLayout.VERTICAL)
        wrapper.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        wrapper.setPadding(dp(16), dp(8), dp(16), dp(8))

        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        grayColor = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        blackText = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        dialogBg = Theme.getColor(Theme.key_dialogBackground)
        activeStroke = accentColor
        inactiveStroke = Color.argb(40, 128, 128, 128)

        accentR = (accentColor >> 16) & 0xFF
        accentG = (accentColor >> 8) & 0xFF
        accentB = accentColor & 0xFF
        activeFill = Color.argb(30, accentR, accentG, accentB)

        menuItems = _getDialogsMenuItems()
        itemCount = len(menuItems)

        current_ref = [_settings.get(key, default)]
        card_refs = [None] * itemCount
        bg_refs = [None] * itemCount
        icon_refs = [None] * itemCount
        label_refs = [None] * itemCount

        def lerpColor(c1, c2, t):
            a = int(((c1 >> 24) & 0xFF) + t * (((c2 >> 24) & 0xFF) - ((c1 >> 24) & 0xFF)))
            r = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
            g = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
            b = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
            return Color.argb(a, r, g, b)

        grayIcon = Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon)

        def animateCard(idx, bg, card, iconView, labelView, toActive):
            fromFill = Color.argb(0, 0, 0, 0) if toActive else activeFill
            toFill = activeFill if toActive else Color.argb(0, 0, 0, 0)
            fromStroke = inactiveStroke if toActive else activeStroke
            toStroke = activeStroke if toActive else inactiveStroke
            strokeFrom = dp(1) if toActive else dp(2)
            strokeTo = dp(2) if toActive else dp(1)
            fromTextColor = blackText if toActive else accentColor
            toTextColor = accentColor if toActive else blackText
            fromIconColor = grayIcon if toActive else accentColor
            toIconColor = accentColor if toActive else grayIcon

            class _Listener(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self, anim):
                    t = float(anim.getAnimatedFraction())
                    bg.setColor(lerpColor(fromFill, toFill, t))
                    bg.setStroke(int(strokeFrom + t * (strokeTo - strokeFrom)), lerpColor(fromStroke, toStroke, t))
                    card.setBackground(bg)
                    textColor = lerpColor(fromTextColor, toTextColor, t)
                    iconColor = lerpColor(fromIconColor, toIconColor, t)
                    labelView.setTextColor(textColor)
                    if iconView is not None:
                        iconView.setColorFilter(iconColor)

            anim = ValueAnimator.ofFloat(0.0, 1.0)
            anim.setDuration(300)
            anim.setInterpolator(DecelerateInterpolator(2.0))
            anim.addUpdateListener(_Listener())
            anim.start()

        def makeCardBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(10))
            bg.setColor(activeFill if active else Color.argb(0, 0, 0, 0))
            bg.setStroke(dp(2) if active else dp(1), activeStroke if active else inactiveStroke)
            return bg

        def refreshCards(prev):
            cur = current_ref[0]
            for i, card in enumerate(card_refs):
                if card is not None and bg_refs[i] is not None:
                    if i == cur and i != prev:
                        animateCard(i, bg_refs[i], card, icon_refs[i], label_refs[i], True)
                    elif i == prev and i != cur:
                        animateCard(i, bg_refs[i], card, icon_refs[i], label_refs[i], False)

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

        cachedIconIds = _getDialogsMenuIconIds()

        for i, (icon_name, label) in enumerate(menuItems):
            card = LinearLayout(context)
            card.setOrientation(LinearLayout.HORIZONTAL)
            card.setGravity(Gravity.CENTER_VERTICAL)
            card.setClickable(True)
            card.setFocusable(True)
            card.setPadding(dp(10), dp(10), dp(10), dp(10))
            cardBg = makeCardBg(current_ref[0] == i)
            card.setBackground(cardBg)
            bg_refs[i] = cardBg
            card.setOnClickListener(OnClickListener(makeCardClick(i)))
            card_refs[i] = card

            isActive = current_ref[0] == i
            icon_id = cachedIconIds[i]
            iconView = None
            if icon_id:
                iconView = ImageView(context)
                iconView.setImageResource(icon_id)
                iconView.setColorFilter(accentColor if isActive else grayIcon)
                card.addView(iconView, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 10, 0))
            icon_refs[i] = iconView

            labelView = TextView(context)
            labelView.setText(label)
            labelView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            labelView.setTextColor(accentColor if isActive else blackText)
            card.addView(labelView, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))
            label_refs[i] = labelView

            margin_top = 0 if i == 0 else 6
            wrapper.addView(card, LayoutHelper.createLinear(-1, -2, 0, margin_top, 0, 0))

        return wrapper
    except Exception as e:
        logx(f"_buildDialogsMenuToggle error: {e}", False)
        return None


@java_subclass(LinearLayout)
class SortDesignCard(Base):
    def on_post_init(self, context):
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from android.view import View
        from android.widget import ImageView, FrameLayout
        from java import dynamic_proxy
        from hook_utils import find_class
        from elyx import settings as _settings
        dp = AndroidUtilities.dp

        self.setOrientation(LinearLayout.VERTICAL)
        self.setPadding(dp(16), dp(8), dp(16), dp(8))

        self._dp = dp
        self._settings = _settings
        self._key = None
        self._default = None
        self._on_change = None

        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        dialogBg = Theme.getColor(Theme.key_dialogBackground)
        dialogTextGray = Theme.getColor(Theme.key_dialogTextGray2)
        dialogTextBlack = Theme.getColor(Theme.key_dialogTextBlack)
        buttonText = Theme.getColor(Theme.key_featuredStickers_buttonText)
        activeStroke = accentColor
        inactiveStroke = Color.argb(40, 128, 128, 128)

        accentR = (accentColor >> 16) & 0xFF
        accentG = (accentColor >> 8) & 0xFF
        accentB = accentColor & 0xFF

        self._accentColor = accentColor
        self._activeStroke = activeStroke
        self._inactiveStroke = inactiveStroke

        # resolve icon once
        iconId = 0
        try:
            R = find_class("org.telegram.messenger.R")
            iconId = int(getattr(R.drawable, "msg_archive"))
        except Exception:
            pass

        def lerpColor(c1, c2, t):
            a = int(((c1 >> 24) & 0xFF) + t * (((c2 >> 24) & 0xFF) - ((c1 >> 24) & 0xFF)))
            r = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
            g = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
            b = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
            return Color.argb(a, r, g, b)

        self._lerpColor = lerpColor

        def makeCardBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(12))
            bg.setColor(0x00000000)
            bg.setStroke(dp(2) if active else dp(1), activeStroke if active else inactiveStroke)
            return bg

        def buildPreview(isClassic):
            container = LinearLayout(context)
            container.setOrientation(LinearLayout.VERTICAL)
            container.setPadding(dp(6), dp(6), dp(6), dp(4))

            previewBg = GradientDrawable()
            previewBg.setCornerRadius(dp(8))
            previewBg.setColor(dialogBg)
            container.setBackground(previewBg)

            def makeRow(label, isSelected):
                optRow = LinearLayout(context)
                optRow.setOrientation(LinearLayout.HORIZONTAL)
                optRow.setGravity(Gravity.CENTER_VERTICAL)
                optRow.setPadding(dp(6), dp(5), dp(6), dp(5))

                rowBg = GradientDrawable()
                rowBg.setCornerRadius(dp(5))
                rowBg.setColor(accentColor if (isSelected and isClassic) else 0x00000000)
                optRow.setBackground(rowBg)

                if not isClassic:
                    dot = FrameLayout(context)
                    dotSize = dp(12)
                    if isSelected:
                        outerBg = GradientDrawable()
                        outerBg.setShape(GradientDrawable.OVAL)
                        outerBg.setColor(accentColor)
                        dot.setBackground(outerBg)

                        middleView = View(context)
                        middleBg = GradientDrawable()
                        middleBg.setShape(GradientDrawable.OVAL)
                        middleBg.setColor(dialogBg)
                        middleView.setBackground(middleBg)
                        dot.addView(middleView, FrameLayout.LayoutParams(dp(9), dp(9), Gravity.CENTER))

                        innerView = View(context)
                        innerBg = GradientDrawable()
                        innerBg.setShape(GradientDrawable.OVAL)
                        innerBg.setColor(accentColor)
                        innerView.setBackground(innerBg)
                        dot.addView(innerView, FrameLayout.LayoutParams(dp(5), dp(5), Gravity.CENTER))
                    else:
                        emptyBg = GradientDrawable()
                        emptyBg.setShape(GradientDrawable.OVAL)
                        emptyBg.setColor(0x00000000)
                        emptyBg.setStroke(dp(1), dialogTextGray)
                        dot.setBackground(emptyBg)
                    dotLp = LinearLayout.LayoutParams(dotSize, dotSize)
                    dotLp.rightMargin = dp(5)
                    optRow.addView(dot, dotLp)

                iconView = ImageView(context)
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

                labelView = TextView(context)
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

            div = View(context)
            div.setBackgroundColor(Theme.getColor(Theme.key_divider))
            container.addView(div, LayoutHelper.createLinear(-1, 1, 0, dp(4), 0, dp(4)))

            container.addView(makeRow("Z \u2192 A", False), LayoutHelper.createLinear(-1, -2))

            return container

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        self.addView(row, LayoutHelper.createLinear(-1, -2))

        self._card_refs = [None, None]
        self._bg_refs = [None, None]
        self._current_ref = [0]

        def makeCardClick(idx):
            def onClick(v):
                prev = self._current_ref[0]
                if prev == idx:
                    return
                self._settings.set(self._key, idx)
                self._current_ref[0] = idx
                self._refreshCards(prev)
                if self._on_change:
                    self._on_change(idx)
            return onClick

        for i in range(2):
            col = LinearLayout(context)
            col.setOrientation(LinearLayout.VERTICAL)
            col.setGravity(Gravity.CENTER_HORIZONTAL)

            card = LinearLayout(context)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setGravity(Gravity.CENTER_HORIZONTAL)
            card.setClickable(True)
            card.setFocusable(True)
            card.setPadding(dp(10), dp(10), dp(10), dp(10))
            cardBg = makeCardBg(False)
            card.setBackground(cardBg)
            self._bg_refs[i] = cardBg
            card.setOnClickListener(OnClickListener(makeCardClick(i)))
            self._card_refs[i] = card

            preview = buildPreview(isClassic=(i == 1))
            card.addView(preview, LayoutHelper.createLinear(-1, -2))
            col.addView(card, LayoutHelper.createLinear(-1, -2))

            if i == 0:
                row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 6, 0))
            else:
                row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 0, 0))

    def _animateCard(self, card, bg, toActive):
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from android.graphics import Color
        from java import dynamic_proxy
        dp = self._dp
        fromStroke = self._inactiveStroke if toActive else self._activeStroke
        toStroke = self._activeStroke if toActive else self._inactiveStroke
        strokeFrom = dp(1) if toActive else dp(2)
        strokeTo = dp(2) if toActive else dp(1)
        lerpColor = self._lerpColor

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

    def _refreshCards(self, prev):
        cur = self._current_ref[0]
        for i, card in enumerate(self._card_refs):
            if card is not None and self._bg_refs[i] is not None:
                if i == cur and i != prev:
                    self._animateCard(card, self._bg_refs[i], True)
                elif i == prev and i != cur:
                    self._animateCard(card, self._bg_refs[i], False)

    def set_selection(self, cur):
        # restore stroke state without animation (called on bind)
        dp = self._dp
        for i, bg in enumerate(self._bg_refs):
            if bg is not None:
                active = (i == cur)
                bg.setStroke(dp(2) if active else dp(1), self._activeStroke if active else self._inactiveStroke)
                if self._card_refs[i] is not None:
                    self._card_refs[i].setBackground(bg)
        self._current_ref[0] = cur

    def setup(self, key, default, on_change=None):
        self._key = key
        self._default = default
        self._on_change = on_change
        cur = self._settings.get(key, default)
        self.set_selection(cur)


def _buildSortMenuDesignToggle(context, key, default, on_change=None):
    try:
        card = SortDesignCard.new_instance(context)
        card.setup(key, default, on_change)
        return card.java
    except Exception as e:
        logx(f"_buildSortMenuDesignToggle error: {e}", False)
        return None


@java_subclass(LinearLayout)
class SfxVolumeSlider(Base):
    onMeasure = jMVELoverride(
        arguments=[("widthMeasureSpec", "int"), ("heightMeasureSpec", "int")],
        code="""
            SUPER_onMeasure(
                android.view.View$MeasureSpec.makeMeasureSpec(
                    android.view.View$MeasureSpec.getSize(widthMeasureSpec),
                    android.view.View$MeasureSpec.EXACTLY
                ),
                android.view.View$MeasureSpec.makeMeasureSpec(
                    org.telegram.messenger.AndroidUtilities.dp(72),
                    android.view.View$MeasureSpec.EXACTLY
                )
            );
            return null;
        """,
    )

    def on_post_init(self, context):
        from android.widget import SeekBar
        from android.view import Gravity
        from java import dynamic_proxy
        from elyx import settings as _s
        dp = AndroidUtilities.dp

        self._s = _s
        self.setOrientation(LinearLayout.VERTICAL)
        self.setPadding(dp(21), dp(8), dp(21), dp(8))
        self.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))

        labelRow = LinearLayout(context)
        labelRow.setOrientation(LinearLayout.HORIZONTAL)
        labelRow.setGravity(Gravity.CENTER_VERTICAL)
        self.addView(labelRow, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        self._labelView = TextView(context)
        self._labelView.setText(str(strings.sfx_volume))
        self._labelView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        self._labelView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        labelRow.addView(self._labelView, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        self._valueView = TextView(context)
        self._valueView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        self._valueView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        labelRow.addView(self._valueView, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

        self._seekBar = SeekBar(context)
        self._seekBar.setMax(100)

        try:
            from android.graphics import PorterDuff, PorterDuffColorFilter
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
            self._seekBar.getProgressDrawable().setColorFilter(PorterDuffColorFilter(accent, PorterDuff.Mode.SRC_IN))
            self._seekBar.getThumb().setColorFilter(PorterDuffColorFilter(accent, PorterDuff.Mode.SRC_IN))
        except Exception:
            pass

        valueView = self._valueView

        class _ChangeListener(dynamic_proxy(SeekBar.OnSeekBarChangeListener)):
            def onProgressChanged(self_l, sb, progress, fromUser):
                try:
                    _s.set("sfx_volume", progress, reload_settings=False)
                    valueView.setText(SfxVolumeSlider._volLabel(progress))
                except Exception:
                    pass

            def onStartTrackingTouch(self_l, sb):
                pass

            def onStopTrackingTouch(self_l, sb):
                pass

        self._seekBar.setOnSeekBarChangeListener(_ChangeListener())
        self.addView(self._seekBar, LayoutHelper.createLinear(-1, -2))

    def bind(self):
        try:
            vol = int(self._s.get("sfx_volume", 100))
        except Exception:
            vol = 100
        self._seekBar.setProgress(vol)
        self._valueView.setText(SfxVolumeSlider._volLabel(vol))

    @staticmethod
    def _volLabel(v):
        if v == 0:
            return str(strings["sfx_volume_off"])
        if v == 100:
            return str(strings["sfx_volume_maximum"])
        return f"{v}%"


class OtherSettings:
    def __init__(self, chat_button=None, plugin=None):
        self.chat_button = chat_button
        self.plugin = plugin
        self._es_expanded_states = {}

    def _es_is_expanded(self, key):
        return self._es_expanded_states.get(key, False)

    def _es_toggle_and_reload(self, key):
        self._es_expanded_states[key] = not self._es_expanded_states.get(key, False)
        logx(f"OtherSettings: _es_toggle_and_reload key={key} expanded={self._es_expanded_states[key]}", True)
        from elyx import settings as _s
        _s.set("_es_dummy", not _s.get("_es_dummy", False), reload_settings=True)

    def _make_expandable_switch(self, key, text, children):
        try:
            from org.telegram.ui.Components import UItem
            from android_utils import OnClickListener as _OCL
            from elyx import settings as _s
            checked_count = sum(1 for ck, cd in children if _s.get(ck, cd))
            total_count = len(children)
            subtext = f"{checked_count}/{total_count}"
            is_checked = checked_count > 0
            is_expanded = self._es_is_expanded(key)

            def switch_click(view, ch=children):
                currently_any = any(_s.get(ck, cd) for ck, cd in ch)
                new_val = not currently_any
                for ck, _ in ch:
                    _s.set(ck, new_val, reload_settings=False)
                _s.set("_es_dummy", not _s.get("_es_dummy", False), reload_settings=True)

            item = UItem.asExteraExpandableSwitch(hash(key) & 0x7FFFFFFF, text, subtext, _OCL(switch_click))
            item.setChecked(is_checked)
            item.setCollapsed(not is_expanded)
            return Custom(item=item, on_click=lambda v, k=key: self._es_toggle_and_reload(k))
        except Exception as e:
            logx(f"OtherSettings: _make_expandable_switch error: {e}", False)
            return None

    def _make_es_child(self, key, text, default=False):
        try:
            from org.telegram.ui.Components import UItem
            from elyx import settings as _s
            is_checked = _s.get(key, default)
            item = UItem.asRoundCheckbox(hash(key) & 0x7FFFFFFF, text)
            item.setChecked(is_checked)
            item.pad()

            def on_click(view, k=key, d=default):
                _s.set(k, not _s.get(k, d), reload_settings=False)
                _s.set("_es_dummy", not _s.get("_es_dummy", False), reload_settings=True)

            return Custom(item=item, on_click=on_click)
        except Exception as e:
            logx(f"OtherSettings: _make_es_child error: {e}", False)
            return None

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
            logx("other: _build_dialogs_btn_item falling back to Text", True)
        except Exception as e:
            logx(f"other: _build_dialogs_btn_item error: {e}", False)
        return Text(
            text=strings.button_in_dialogs_menu,
            icon="msg_addbot",
            on_click=self._open_main_menu_settings
        )

    def _build_dialogs_menu_toggle_item(self, ctx):
        try:
            if ctx:
                from elyx import settings as _s
                # value that is currently applied (captured at settings open time)
                applied_value = _s.get("dialogs_menu_button", 0)

                def onDialogsMenuChange(idx):
                    if idx == applied_value:
                        return
                    try:
                        from ui.bulletin import BulletinHelper
                        from client_utils import get_last_fragment
                        from hook_utils import find_class
                        frag = get_last_fragment()
                        icon = None
                        try:
                            R_tg = find_class("org.telegram.messenger.R")
                            icon = int(R_tg.raw.chats_infotip)
                        except Exception:
                            pass
                        BulletinHelper.show_with_button(
                            str(strings.bulletin_hook_restart_required),
                            icon,
                            str(strings.bulletin_restart_button),
                            self._killProcess,
                            frag
                        )
                    except Exception as e:
                        logx(f"other: dialogs menu bulletin error: {e}", False)

                view = _buildDialogsMenuToggle(ctx, key="dialogs_menu_button", default=0, on_change=onDialogsMenuChange)
                if view is not None:
                    return Custom(view=view)
            logx("other: _build_dialogs_menu_toggle_item falling back", True)
        except Exception as e:
            logx(f"other: _build_dialogs_menu_toggle_item error: {e}", False)
        return None

    def _build_sort_menu_design_item(self, ctx):
        try:
            if ctx:
                view = _buildSortMenuDesignToggle(ctx, key="old_sort_menu_design", default=False)
                if view is not None:
                    return Custom(view=view)
            logx("other: _build_sort_menu_design_item falling back to Switch", True)
        except Exception as e:
            logx(f"other: _build_sort_menu_design_item error: {e}", False)
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
            logx("other: _build_search_engine_item falling back to Text", True)
        except Exception as e:
            logx(f"other: _build_search_engine_item error: {e}", False)
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
            logx("other: _build_hash_function_item falling back to Text", True)
        except Exception as e:
            logx(f"other: _build_hash_function_item error: {e}", False)
        return Text(
            text=strings.hash_function,
            icon="msg_sendfile",
        )

    def _build_sfx_volume_slider(self, ctx):
        # slider 0-100 for sfx_volume setting, shown as a separate row under sfx section
        try:
            if not ctx:
                return None
            slider = SfxVolumeSlider.new_instance(ctx)
            slider.bind()
            return Custom(view=slider.java)
        except Exception as e:
            logx(f"other: _build_sfx_volume_slider error: {e}", False)
            return None


    def _open_main_menu_settings(self, view):
        try:
            from hook_utils import find_class
            frag = get_last_fragment()
            if frag:
                MainMenuPreferencesActivity = find_class("com.exteragram.messenger.preferences.appearance.AppNavigationPreferencesActivity")
                frag.presentFragment(MainMenuPreferencesActivity())
        except Exception as e:
            logx(f"OtherSettings: _open_main_menu_settings error: {e}", False)

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
            logx("other: _build_pill_stack_item falling back to Text", True)
        except Exception as e:
            logx(f"other: _build_pill_stack_item error: {e}", False)
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
            logx("other: _build_font_picker_item falling back to Text", True)
        except Exception as e:
            logx(f"other: _build_font_picker_item error: {e}", False)
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
            logx(f"OtherSettings: _open_font_picker error: {e}", False)

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
            logx(f"OtherSettings: _open_pill_stack_settings error: {e}", False)

    def _open_files_browser(self):
        try:
            from ..ui.FilesActivity.fragment import show_files_browser
            show_files_browser(plugin=self.plugin)
        except Exception as e:
            logx(f"OtherSettings: _open_files_browser error: {e}", False)

    def _getCacheDir(self) -> str:
        from ..utils.paths import getCacheRoot
        return getCacheRoot()

    def _killProcess(self, *_):
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGKILL)

    def _onClearCacheClick(self, view, update_callback=None):
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
                    logx(f"clear cache error: {e}", False)

                if update_callback:
                    try:
                        update_callback()
                    except Exception as e:
                        logx(f"clear cache update callback error: {e}", False)

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
                    logx(f"clear cache restart dialog error: {e}", False)

            builder.set_positive_button(strings.clear_cache_button, onConfirm)
            builder.set_negative_button(strings.cancel_button, lambda b, w: b.dismiss())
            try:
                builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
            except Exception as e:
                logx(f"make_button_red error: {e}", False)
            builder.show()
        except Exception as e:
            logx(f"clear cache dialog error: {e}", False)

    def _onClearPluginCacheClick(self, view, update_callback=None):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return

            builder = AlertDialogBuilder(act)
            builder.set_title(strings.clear_plugin_cache)
            builder.set_message(strings.clear_cache_confirm_message)

            def onConfirm(b, w):
                b.dismiss()
                try:
                    from ..utils.paths import getCacheRoot
                    plugin_cache_dir = getCacheRoot() + "/.cache/plugins"
                    if os.path.exists(plugin_cache_dir):
                        shutil.rmtree(plugin_cache_dir)
                        logx("other: plugin cache cleared", True)
                except Exception as e:
                    logx(f"other: clear plugin cache error: {e}", False)
                if update_callback:
                    try:
                        update_callback()
                    except Exception as e:
                        logx(f"other: clear plugin cache update callback error: {e}", False)

            builder.set_positive_button(strings.clear_cache_button, onConfirm)
            builder.set_negative_button(strings.cancel_button, lambda b, w: b.dismiss())
            try:
                builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
            except Exception as e:
                logx(f"make_button_red error: {e}", False)
            builder.show()
        except Exception as e:
            logx(f"other: clear plugin cache dialog error: {e}", False)

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
                logx(f"other: _onRestartRequiredSwitch error: {e}", False)

        from android_utils import run_on_ui_thread
        run_on_ui_thread(show)

    def _open_card_editor(self):
        try:
            from .SubSettings.PluginCardEditor import build_card_editor_page
            return build_card_editor_page()
        except Exception as e:
            logx(f"OtherSettings: _open_card_editor error: {e}", False)
            return []

    def _open_interface_page(self):
        try:
            from .SubSettings.interface import build_interface_page
            return build_interface_page(self, self._getContext())
        except Exception as e:
            logx(f"OtherSettings: _open_interface_page error: {e}", False)
            return []

    def _open_sfx_page(self):
        try:
            from .SubSettings.sfx import build_sfx_page
            return build_sfx_page(self, self._getContext())
        except Exception as e:
            logx(f"OtherSettings: _open_sfx_page error: {e}", False)
            return []

    def _open_comps_page(self):
        try:
            from .SubSettings.comps import build_comps_page
            return build_comps_page(self, self._getContext())
        except Exception as e:
            logx(f"OtherSettings: _open_comps_page error: {e}", False)
            return []

    def _open_hotkeys_page(self):
        try:
            from .SubSettings.hotkeys import build_hotkeys_page
            return build_hotkeys_page(self, self._getContext())
        except Exception as e:
            logx(f"OtherSettings: _open_hotkeys_page error: {e}", False)
            return []

    def _open_plugin_profile_page(self):
        try:
            from .SubSettings.pluginProfile import build_plugin_profile_page
            return build_plugin_profile_page()
        except Exception as e:
            logx(f"OtherSettings: _open_plugin_profile_page error: {e}", False)
            return []

    def _open_inline_page(self):
        try:
            from .SubSettings.inline import build_inline_page
            return build_inline_page(self, _fmt_inline_str, _reload_plugin_settings, _open_url)
        except Exception as e:
            logx(f"OtherSettings: _open_inline_page error: {e}", False)
            return []

    def _open_file_settings_page(self):
        try:
            from .SubSettings.fileSettings import build_file_settings_page
            return build_file_settings_page(self)
        except Exception as e:
            logx(f"OtherSettings: _open_file_settings_page error: {e}", False)
            return []

    def _open_misc_page(self):
        try:
            from .SubSettings.misc import build_misc_page
            return build_misc_page(self)
        except Exception as e:
            logx(f"OtherSettings: _open_misc_page error: {e}", False)
            return []

    def _open_apikeys_page(self):
        try:
            from .SubSettings.apikeys import build_apikeys_page
            return build_apikeys_page()
        except Exception as e:
            logx(f"OtherSettings: _open_apikeys_page error: {e}", False)
            return []

    def _open_updplugins_page(self):
        try:
            from .SubSettings.updplugins import build_updplugins_page
            return build_updplugins_page(self)
        except Exception as e:
            logx(f"OtherSettings: _open_updplugins_page error: {e}", False)
            return []

    def _open_debug_page(self):
        try:
            from .SubSettings.debug import build_debug_page
            return build_debug_page()
        except Exception as e:
            logx(f"OtherSettings: _open_debug_page error: {e}", False)
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
            logx(f"OtherSettings: _onClearIgnoreListClick error: {e}", False)

    def build(self):
        ctx = self._getContext()

        items = [
            Header(text=strings.navigating_through_settings),
            Text(
                text=strings.interface_header,
                subtext=strings.interface_header_desc,
                icon="msg_theme",
                create_sub_fragment=self._open_interface_page
            ),
            Text(
                text=strings.sfx_settings,
                subtext=strings.sfx_settings_desc,
                icon="msg_voicechat",
                create_sub_fragment=self._open_sfx_page
            ),
            Text(
                text=strings.plugin_components,
                subtext=strings.plugin_components_desc,
                icon="msg_photo_settings",
                create_sub_fragment=self._open_comps_page
            ),
            Text(
                text=strings.hotkeys_header,
                subtext=strings.hotkeys_subtext,
                icon="msg_addbot",
                create_sub_fragment=self._open_hotkeys_page
            ),
            Text(
                text=strings.inline_search_nav,
                subtext=strings.inline_search_nav_desc,
                icon="msg_search",
                create_sub_fragment=self._open_inline_page
            ),
            Text(
                text=strings.plugin_profile_header,
                subtext=strings.plugin_profile_subtext,
                icon="msg_info",
                create_sub_fragment=self._open_plugin_profile_page
            ),
            Text(
                text=strings.updplugins_nav,
                subtext=strings.updplugins_nav_desc,
                icon="msg_download",
                create_sub_fragment=self._open_updplugins_page
            ),
            Text(
                text=strings.api_keys_nav,
                subtext=strings.api_keys_nav_desc,
                icon="msg_secret",
                create_sub_fragment=self._open_apikeys_page,
                link_alias="api_keys"
            ),
            Text(
                text=strings.misc_nav,
                subtext=strings.misc_nav_desc,
                icon="msg_settings_old",
                create_sub_fragment=self._open_misc_page
            ),
            Text(
                text=strings.debug_menu,
                subtext=strings.debug_menu_desc,
                icon="msg_log",
                create_sub_fragment=self._open_debug_page
            ),
        ]

        items.append(Divider())

        # filesystem section should always be at the bottom of the page
        items.append(Header(text=strings.filesystem_header))
        if ctx:
            openDirView = _buildTextSubtextCellIconRight(
                ctx,
                text=strings.open_directory,
                subtext=strings.open_directory_desc,
                icon="msg_folders",
                on_click=lambda v: self._open_files_browser()
            )
            if openDirView is not None:
                items.append(Custom(view=openDirView))
            else:
                items.append(Text(
                    text=strings.open_directory,
                    icon="msg_folders",
                    on_click=lambda v: self._open_files_browser()
                ))
        else:
            items.append(Text(
                text=strings.open_directory,
                icon="msg_folders",
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
                logx("OtherSettings.build: _buildDownloadPathCard returned None", True)

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
            cacheCard, cacheUpdateFunc = _buildCacheCard(ctx, cacheDir, lambda v: self._onClearCacheClick(v, cacheUpdateFunc))
            if cacheCard is not None:
                items.append(Custom(view=cacheCard))
            else:
                items.append(Text(
                    text=strings.clear_cache,
                    icon="msg_delete",
                    on_click=lambda v: self._onClearCacheClick(v, None),
                    red=True
                ))

            from ..utils.paths import getCacheRoot
            pluginCacheDir = getCacheRoot() + "/.cache/plugins"
            pluginCacheCard, pluginCacheUpdateFunc = _buildCacheCard(ctx, pluginCacheDir, lambda v: self._onClearPluginCacheClick(v, pluginCacheUpdateFunc), title=strings.clear_plugin_cache)
            if pluginCacheCard is not None:
                items.append(Custom(view=pluginCacheCard))
            else:
                items.append(Text(
                    text=strings.clear_plugin_cache,
                    icon="msg_delete",
                    on_click=lambda v: self._onClearPluginCacheClick(v, None),
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

        items.append(Text(
            text=strings.file_system_settings_header,
            subtext=strings.file_system_settings_nav_desc,
            icon="msg_filehq",
            create_sub_fragment=self._open_file_settings_page
        ))

        return items
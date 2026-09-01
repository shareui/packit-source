# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Switch, Divider, Custom, Text
from elyx import strings


def _buildScrollButtonToggle(context, key, default):
    try:
        from android.widget import LinearLayout, TextView, FrameLayout, ImageView
        from android.view import Gravity, View
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from android.graphics import Color
        from android.animation import ValueAnimator
        from android.view.animation import DecelerateInterpolator
        from android_utils import OnClickListener
        from java import dynamic_proxy
        from hook_utils import find_class
        from elyx import settings as _settings
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import LayoutHelper
        from org.telegram.messenger import AndroidUtilities

        dp = AndroidUtilities.dp
        accentColor = Theme.getColor(Theme.key_featuredStickers_addButton)
        inactiveStroke = Color.argb(40, 128, 128, 128)
        dialogBg = Theme.getColor(Theme.key_dialogBackground)
        grayText = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        buttonText = Theme.getColor(Theme.key_featuredStickers_buttonText)

        try:
            R = find_class("org.telegram.messenger.R")
            arrowIconId = int(getattr(R.drawable, "msg_to_beginning", 0))
        except Exception:
            arrowIconId = 0

        cur = [bool(_settings.get(key, default))]
        card_refs = [None, None]
        bg_refs = [None, None]

        def makeCardBg(active):
            bg = GradientDrawable()
            bg.setCornerRadius(dp(12))
            bg.setColor(0x00000000)
            bg.setStroke(dp(2) if active else dp(1), accentColor if active else inactiveStroke)
            return bg

        def lerpColor(c1, c2, t):
            a = int(((c1 >> 24) & 0xFF) + t * (((c2 >> 24) & 0xFF) - ((c1 >> 24) & 0xFF)))
            r = int(((c1 >> 16) & 0xFF) + t * (((c2 >> 16) & 0xFF) - ((c1 >> 16) & 0xFF)))
            g = int(((c1 >> 8) & 0xFF) + t * (((c2 >> 8) & 0xFF) - ((c1 >> 8) & 0xFF)))
            b = int((c1 & 0xFF) + t * ((c2 & 0xFF) - (c1 & 0xFF)))
            return Color.argb(a, r, g, b)

        def animateCard(card, bg, toActive):
            fromStroke = inactiveStroke if toActive else accentColor
            toStroke = accentColor if toActive else inactiveStroke
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

        def buildPreview(isBottomRight):
            container = FrameLayout(context)
            container.setMinimumHeight(dp(80))

            previewBg = GradientDrawable()
            previewBg.setCornerRadius(dp(8))
            previewBg.setColor(dialogBg)
            container.setBackground(previewBg)
            container.setClipChildren(True)
            container.setClipToPadding(True)

            # two blocks: top half and bottom half, small gap in center
            rowColor = Color.argb(50, 128, 128, 128)
            gap = dp(4)

            topBlock = FrameLayout(context)
            topBg = GradientDrawable()
            topBg.setCornerRadius(dp(6))
            topBg.setColor(rowColor)
            topBlock.setBackground(topBg)
            topLp = FrameLayout.LayoutParams(-1, -1)
            topLp.leftMargin = dp(6)
            topLp.rightMargin = dp(6)
            topLp.bottomMargin = dp(40) + gap // 2
            container.addView(topBlock, topLp)

            bottomBlock = FrameLayout(context)
            botBg = GradientDrawable()
            botBg.setCornerRadius(dp(6))
            botBg.setColor(rowColor)
            bottomBlock.setBackground(botBg)
            botLp = FrameLayout.LayoutParams(-1, -1)
            botLp.leftMargin = dp(6)
            botLp.rightMargin = dp(6)
            botLp.topMargin = dp(40) + gap // 2
            container.addView(bottomBlock, botLp)

            if isBottomRight:
                btn = FrameLayout(context)
                btnBg = GradientDrawable()
                btnBg.setShape(GradientDrawable.OVAL)
                btnBg.setColor(accentColor)
                btn.setBackground(btnBg)
                btnSize = dp(26)
                if arrowIconId:
                    arrow = ImageView(context)
                    arrow.setImageResource(arrowIconId)
                    arrow.setColorFilter(buttonText)
                    arrow.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    btn.addView(arrow, FrameLayout.LayoutParams(dp(14), dp(14), Gravity.CENTER))
                lp = FrameLayout.LayoutParams(btnSize, btnSize, Gravity.BOTTOM | Gravity.END)
                lp.rightMargin = dp(9)
                lp.bottomMargin = dp(9)
                container.addView(btn, lp)
            else:
                btn = LinearLayout(context)
                btn.setOrientation(LinearLayout.HORIZONTAL)
                btn.setGravity(Gravity.CENTER_VERTICAL)
                btnBg = GradientDrawable()
                btnBg.setCornerRadius(dp(12))
                btnBg.setColor(accentColor)
                btn.setBackground(btnBg)
                btn.setPadding(dp(7), dp(4), dp(9), dp(4))
                if arrowIconId:
                    arrow = ImageView(context)
                    arrow.setImageResource(arrowIconId)
                    arrow.setColorFilter(buttonText)
                    arrow.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    arrowLp = LinearLayout.LayoutParams(dp(10), dp(10))
                    arrowLp.rightMargin = dp(3)
                    btn.addView(arrow, arrowLp)
                pillLabel = TextView(context)
                pillLabel.setText(str(strings.to_the_beginning))
                pillLabel.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 7)
                pillLabel.setTextColor(buttonText)
                try:
                    pillLabel.setTypeface(AndroidUtilities.bold())
                except Exception:
                    pass
                btn.addView(pillLabel, LinearLayout.LayoutParams(-2, -2))
                lp = FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.CENTER_HORIZONTAL)
                lp.topMargin = dp(9)
                container.addView(btn, lp)

            return container

        root = LinearLayout(context)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(dp(16), dp(8), dp(16), dp(8))
        root.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        root.addView(row, LayoutHelper.createLinear(-1, -2))

        def makeCardClick(idx):
            isRight = (idx == 1)
            def onClick(v):
                prev = cur[0]
                if prev == isRight:
                    return
                cur[0] = isRight
                _settings.set(key, isRight)
                prevIdx = 1 if prev else 0
                animateCard(card_refs[prevIdx], bg_refs[prevIdx], False)
                animateCard(card_refs[idx], bg_refs[idx], True)
            return onClick

        for i in range(2):
            isRight = (i == 1)
            active = (cur[0] == isRight)

            col = LinearLayout(context)
            col.setOrientation(LinearLayout.VERTICAL)
            col.setGravity(Gravity.CENTER_HORIZONTAL)

            card = LinearLayout(context)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setClickable(True)
            card.setFocusable(True)
            card.setPadding(dp(10), dp(10), dp(10), dp(10))
            cardBg = makeCardBg(active)
            card.setBackground(cardBg)
            card.setOnClickListener(OnClickListener(makeCardClick(i)))
            card_refs[i] = card
            bg_refs[i] = cardBg

            preview = buildPreview(isBottomRight=isRight)
            card.addView(preview, LayoutHelper.createLinear(-1, -2))

            col.addView(card, LayoutHelper.createLinear(-1, -2))

            if i == 0:
                row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 6, 0))
            else:
                row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.TOP, 0, 0, 0, 0))

        return root
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"interface: _buildScrollButtonToggle error: {e}", False)
        return None


def build_interface_page(other_settings, ctx):
    scroll_btn_item = None
    if ctx:
        try:
            view = _buildScrollButtonToggle(ctx, key="scroll_button_bottom_right", default=False)
            if view is not None:
                scroll_btn_item = Custom(view=view)
        except Exception:
            pass
    if scroll_btn_item is None:
        scroll_btn_item = Switch(
            key="scroll_button_bottom_right",
            text=strings.scroll_button_bottom_right,
            subtext=strings.scroll_button_bottom_right_desc,
            default=False,
            icon="msg_to_beginning",
            link_alias="scroll_button_bottom_right"
        )

    items = [
        Header(text=strings.interface_header),
        other_settings._build_sort_menu_design_item(ctx),
        other_settings._build_font_picker_item(ctx),
        Text(
            text=strings.edit_plugin_card,
            subtext=strings.edit_plugin_card_desc,
            icon="msg_edit",
            create_sub_fragment=other_settings._open_card_editor,
            link_alias="card_editor"
        ),
        Switch(
            key="hide_unavailable_plugins",
            text=strings.hide_unavailable_plugins,
            subtext=strings.hide_unavailable_plugins_desc,
            default=False,
            icon="msg_block",
            link_alias="hide_unavailable_plugins"
        ),
        scroll_btn_item,
    ]
    return [item for item in items if item is not None]
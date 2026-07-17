// SPDX-License-Identifier: GPL-3.0-or-later
package kawaii.packetik.catalog

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * Static chrome skeleton of the plugins catalog, built entirely on the java
 * side: the same tree costs hundreds of python->java bridge calls when built
 * from Python and used to stall catalog entry for ~half a second.
 *
 * Python receives the tree, looks up the interactive children by tag
 * (search_slot, clear_btn, search_btn, ai_pill, subtitle, tag_filter_btn,
 * sort_btn, scroll), inserts the telegram EditTextBoldCursor into
 * search_slot and wires all listeners/logic itself.
 */
object CatalogChromeNative {

    private fun dp(ctx: Context, v: Float): Int =
        (ctx.resources.displayMetrics.density * v + 0.5f).toInt()

    private fun rounded(color: Int, radiusPx: Float, strokeW: Int = 0, strokeColor: Int = 0): GradientDrawable {
        val d = GradientDrawable()
        d.shape = GradientDrawable.RECTANGLE
        d.cornerRadius = radiusPx
        d.setColor(color)
        if (strokeW > 0) d.setStroke(strokeW, strokeColor)
        return d
    }

    private fun selector(base: Int, pressed: Int, radiusPx: Float): Drawable {
        val content = rounded(base, radiusPx)
        return try {
            RippleDrawable(ColorStateList.valueOf(pressed), content, null)
        } catch (t: Throwable) {
            content
        }
    }

    private fun iconButton(
        ctx: Context, bg: Drawable, iconRes: Int, iconTint: Int, padPx: Int, tag: String
    ): FrameLayout {
        val btn = FrameLayout(ctx)
        btn.tag = tag
        btn.isClickable = true
        btn.isFocusable = true
        btn.background = bg
        btn.setPadding(padPx, padPx, padPx, padPx)
        val icon = ImageView(ctx)
        if (iconRes != 0) icon.setImageResource(iconRes)
        icon.setColorFilter(iconTint)
        icon.scaleType = ImageView.ScaleType.CENTER
        btn.addView(icon, FrameLayout.LayoutParams(dp(ctx, 20f), dp(ctx, 20f), Gravity.CENTER))
        return btn
    }

    @JvmStatic
    fun createPluginsChrome(
        ctx: Context,
        mainBg: Int,
        cardBg: Int,
        cardPressed: Int,
        textColor: Int,
        accent: Int,
        accentPressed: Int,
        buttonText: Int,
        iconClear: Int,
        iconSearch: Int,
        iconAi: Int,
        iconFilter: Int,
        iconSort: Int,
        aiLabel: String,
        subtitleText: String,
        showSearchBtn: Boolean,
        boldTypeface: Typeface?
    ): LinearLayout {
        val bold = boldTypeface ?: Typeface.DEFAULT_BOLD

        val main = LinearLayout(ctx)
        main.orientation = LinearLayout.VERTICAL
        main.setPadding(dp(ctx, 16f), 0, dp(ctx, 16f), dp(ctx, 14f))

        // -------- search pill
        val searchContainer = FrameLayout(ctx)
        searchContainer.background =
            rounded(cardBg, dp(ctx, 50f).toFloat(), dp(ctx, 2f), accent)
        searchContainer.setPadding(dp(ctx, 16f), dp(ctx, 5f), dp(ctx, 8f), dp(ctx, 5f))

        val searchRow = LinearLayout(ctx)
        searchRow.orientation = LinearLayout.HORIZONTAL
        searchRow.gravity = Gravity.CENTER_VERTICAL

        // python drops the telegram EditTextBoldCursor in here
        val searchSlot = FrameLayout(ctx)
        searchSlot.tag = "search_slot"
        searchRow.addView(searchSlot, LinearLayout.LayoutParams(-1, dp(ctx, 36f), 1f))

        val clearBtn = iconButton(
            ctx, selector(0x00000000, 0x1F000000, dp(ctx, 25f).toFloat()),
            iconClear, textColor, dp(ctx, 8f), "clear_btn"
        )
        clearBtn.visibility = View.GONE
        clearBtn.alpha = 0f
        searchRow.addView(clearBtn, LinearLayout.LayoutParams(dp(ctx, 52f), dp(ctx, 36f), 0f))

        val searchBtn = iconButton(
            ctx, selector(accent, accentPressed, dp(ctx, 25f).toFloat()),
            iconSearch, buttonText, dp(ctx, 8f), "search_btn"
        )
        if (!showSearchBtn) searchBtn.visibility = View.GONE
        searchRow.addView(searchBtn, LinearLayout.LayoutParams(dp(ctx, 52f), dp(ctx, 36f), 0f))

        searchContainer.addView(searchRow, FrameLayout.LayoutParams(-1, -2))
        val scLp = LinearLayout.LayoutParams(-1, -2)
        scLp.bottomMargin = dp(ctx, 8f)
        main.addView(searchContainer, scLp)

        // -------- header row: AI pill / centered count / filter + sort
        val header = FrameLayout(ctx)
        val hLp = LinearLayout.LayoutParams(-1, dp(ctx, 44f))
        hLp.topMargin = dp(ctx, 2f)
        hLp.bottomMargin = dp(ctx, 6f)
        main.addView(header, hLp)

        val aiPill = LinearLayout(ctx)
        aiPill.tag = "ai_pill"
        aiPill.orientation = LinearLayout.HORIZONTAL
        aiPill.gravity = Gravity.CENTER_VERTICAL
        aiPill.isClickable = true
        aiPill.isFocusable = true
        aiPill.background = selector(cardBg, cardPressed, dp(ctx, 16f).toFloat())
        aiPill.setPadding(dp(ctx, 12f), dp(ctx, 8f), dp(ctx, 12f), dp(ctx, 8f))
        val aiIcon = ImageView(ctx)
        if (iconAi != 0) aiIcon.setImageResource(iconAi)
        aiIcon.setColorFilter(textColor)
        val aiIconLp = LinearLayout.LayoutParams(dp(ctx, 20f), dp(ctx, 20f))
        aiIconLp.rightMargin = dp(ctx, 6f)
        aiPill.addView(aiIcon, aiIconLp)
        val aiText = TextView(ctx)
        aiText.text = aiLabel
        aiText.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14f)
        aiText.typeface = bold
        aiText.setTextColor(textColor)
        aiPill.addView(aiText, LinearLayout.LayoutParams(-2, -2))
        header.addView(
            aiPill,
            FrameLayout.LayoutParams(-2, -2, Gravity.LEFT or Gravity.CENTER_VERTICAL)
        )

        val subtitle = TextView(ctx)
        subtitle.tag = "subtitle"
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16f)
        subtitle.text = subtitleText
        subtitle.gravity = Gravity.CENTER
        subtitle.setPadding(dp(ctx, 12f), dp(ctx, 7f), dp(ctx, 12f), dp(ctx, 7f))
        subtitle.isClickable = false
        subtitle.isFocusable = false
        subtitle.background = rounded(cardBg, dp(ctx, 16f).toFloat())
        subtitle.setTextColor(textColor)
        header.addView(subtitle, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))

        val tagBtn = iconButton(
            ctx, selector(cardBg, cardPressed, dp(ctx, 16f).toFloat()),
            iconFilter, textColor, dp(ctx, 8f), "tag_filter_btn"
        )
        val tagLp = FrameLayout.LayoutParams(-2, -2, Gravity.RIGHT or Gravity.CENTER_VERTICAL)
        tagLp.rightMargin = dp(ctx, 40f)
        header.addView(tagBtn, tagLp)

        val sortBtn = iconButton(
            ctx, selector(cardBg, cardPressed, dp(ctx, 16f).toFloat()),
            iconSort, textColor, dp(ctx, 8f), "sort_btn"
        )
        header.addView(
            sortBtn,
            FrameLayout.LayoutParams(-2, -2, Gravity.RIGHT or Gravity.CENTER_VERTICAL)
        )

        // -------- results scroll
        val scroll = ScrollView(ctx)
        scroll.tag = "scroll"
        scroll.isFillViewport = true
        scroll.isVerticalScrollBarEnabled = false
        scroll.setBackgroundColor(mainBg)
        scroll.setFadingEdgeLength(dp(ctx, 24f))
        scroll.isVerticalFadingEdgeEnabled = true
        try {
            scroll.isNestedScrollingEnabled = true
        } catch (t: Throwable) {
        }
        main.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))

        return main
    }
}

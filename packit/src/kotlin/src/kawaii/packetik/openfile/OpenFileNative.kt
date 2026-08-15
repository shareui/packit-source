// SPDX-License-Identifier: GPL-3.0-or-later
//
// Precompiled Kotlin port of the load/display path of PackIt's file viewer
// (packit/src/ui/FilesActivity/openFileFragment.py). Loaded at runtime from
// packit/dex/<abi>/openfile.dex by packit/src/dexLoader.py.
//
// The Python impl read the file in chunks and TextView.append()'d each on the UI
// thread (O(n²) relayout) with a sleep between chunks, and had no loading
// animation. This owns loading + display only: it reads the file off-thread and
// shows a *virtualized* line list (ListView), so only the lines near the scroll
// are laid out and highlighted — nothing is rendered "all at once". Tokenization
// stays in Python (packlight); token ranges + a type→color map are passed in and
// applied per visible line. The Python side keeps the toolbar and edit mode.
//
// Compiles against android-all.jar only (no Xposed, no host classes): all UI is
// android.widget.*, so no reflection is needed.

package kawaii.packetik.openfile

import android.content.Context
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.os.Handler
import android.os.Looper
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.TextView
import java.io.File

object OpenFileNative {

    private val mainHandler = Handler(Looper.getMainLooper())

    // one active viewer at a time; keyed by the root view returned to Python
    private val sessions = HashMap<View, Session>()

    private class Session(
        val listView: ListView,
        val spinner: ProgressBar,
        val textSizePx: Float,
        val padL: Int,
        val padR: Int,
        val textColor: Int
    ) {
        @Volatile var cancelled = false
        var lines: List<String> = emptyList()
        // per line: flat [relStart, relEnd, color, ...] (char offsets within the line)
        var lineSpans: Array<IntArray?> = emptyArray()
        var rowWidthPx: Int = 0
        var fullText: String = ""
    }

    @JvmStatic
    fun create(
        ctx: Context,
        path: String,
        textSizePx: Float,
        padL: Int, padT: Int, padR: Int, padB: Int,
        bgColor: Int, textColor: Int,
        tokenTypes: IntArray, tokenStarts: IntArray, tokenEnds: IntArray,
        colorKeys: IntArray, colorVals: IntArray
    ): View {
        val root = FrameLayout(ctx)
        root.setBackgroundColor(bgColor)

        val hScroll = HorizontalScrollView(ctx)
        hScroll.isFillViewport = true
        hScroll.isHorizontalScrollBarEnabled = true

        val listView = ListView(ctx)
        listView.divider = null
        listView.dividerHeight = 0
        listView.isVerticalScrollBarEnabled = true
        listView.clipToPadding = false
        listView.setPadding(0, padT, 0, padB)
        try {
            listView.selector = ColorDrawable(Color.TRANSPARENT)
            listView.cacheColorHint = Color.TRANSPARENT
        } catch (_: Throwable) {
        }
        hScroll.addView(
            listView,
            FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.MATCH_PARENT)
        )
        root.addView(hScroll, FrameLayout.LayoutParams(-1, -1))

        val spinner = ProgressBar(ctx)
        val sp = FrameLayout.LayoutParams(-2, -2)
        sp.gravity = Gravity.CENTER
        root.addView(spinner, sp)

        val session = Session(listView, spinner, textSizePx, padL, padR, textColor)
        sessions[root] = session

        val colorMap = HashMap<Int, Int>(colorKeys.size * 2)
        var ci = 0
        while (ci < colorKeys.size && ci < colorVals.size) {
            colorMap[colorKeys[ci]] = colorVals[ci]
            ci++
        }

        val worker = Thread {
            try {
                val text = try {
                    File(path).readText(Charsets.UTF_8)
                } catch (t: Throwable) {
                    ""
                }
                if (session.cancelled) return@Thread
                session.fullText = text

                // split into lines, remembering each line's char start offset
                val lines = ArrayList<String>()
                val lineStart = ArrayList<Int>()
                val n = text.length
                var start = 0
                lineStart.add(0)
                var i = 0
                while (i < n) {
                    if (text[i] == '\n') {
                        lines.add(text.substring(start, i))
                        start = i + 1
                        lineStart.add(start)
                    }
                    i++
                }
                lines.add(text.substring(start, n))

                // widest line -> fixed row width so all rows align under h-scroll
                val paint = Paint()
                paint.textSize = textSizePx
                paint.typeface = Typeface.MONOSPACE
                var maxW = 0f
                var li = 0
                val lc = lines.size
                while (li < lc) {
                    val w = paint.measureText(lines[li])
                    if (w > maxW) maxW = w
                    li++
                }
                val rowWidth = (maxW + padL + padR + 4f).toInt()

                // bin tokens onto their line (packlight char offsets are absolute)
                val lineTokens = arrayOfNulls<ArrayList<Int>>(lc)
                val cnt = minOf(tokenTypes.size, tokenStarts.size, tokenEnds.size)
                var k = 0
                while (k < cnt) {
                    val cs = tokenStarts[k]
                    val ce = tokenEnds[k]
                    k++
                    if (cs < 0 || ce <= cs) continue
                    val color = colorMap[tokenTypes[k - 1]] ?: continue
                    val line = lineIndexOf(lineStart, cs)
                    if (line < 0 || line >= lc) continue
                    val ls = lineStart[line]
                    val lineLen = lines[line].length
                    val relStart = cs - ls
                    var relEnd = ce - ls
                    if (relEnd > lineLen) relEnd = lineLen
                    if (relStart < 0 || relEnd <= relStart) continue
                    var lst = lineTokens[line]
                    if (lst == null) {
                        lst = ArrayList()
                        lineTokens[line] = lst
                    }
                    lst.add(relStart)
                    lst.add(relEnd)
                    lst.add(color)
                }
                val lineSpans = Array<IntArray?>(lc) { idx -> lineTokens[idx]?.toIntArray() }

                if (session.cancelled) return@Thread
                session.lines = lines
                session.lineSpans = lineSpans
                session.rowWidthPx = rowWidth

                mainHandler.post {
                    if (session.cancelled) return@post
                    try {
                        spinner.visibility = View.GONE
                        val lp = listView.layoutParams
                        lp.width = rowWidth
                        listView.layoutParams = lp
                        listView.adapter = LineAdapter(ctx, session)
                    } catch (_: Throwable) {
                    }
                }
            } catch (_: Throwable) {
                mainHandler.post {
                    try {
                        spinner.visibility = View.GONE
                    } catch (_: Throwable) {
                    }
                }
            }
        }
        worker.isDaemon = true
        worker.start()

        return root
    }

    // largest index i with lineStart[i] <= pos (binary search)
    private fun lineIndexOf(lineStart: ArrayList<Int>, pos: Int): Int {
        var lo = 0
        var hi = lineStart.size - 1
        var ans = 0
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (lineStart[mid] <= pos) {
                ans = mid
                lo = mid + 1
            } else {
                hi = mid - 1
            }
        }
        return ans
    }

    private class LineAdapter(val ctx: Context, val session: Session) : BaseAdapter() {
        override fun getCount(): Int = session.lines.size
        override fun getItem(position: Int): Any = position
        override fun getItemId(position: Int): Long = position.toLong()

        override fun getView(position: Int, convertView: View?, parent: ViewGroup?): View {
            val tv: TextView = (convertView as? TextView) ?: TextView(ctx).also {
                it.setTextSize(TypedValue.COMPLEX_UNIT_PX, session.textSizePx)
                it.setTextColor(session.textColor)
                it.typeface = Typeface.MONOSPACE
                it.setSingleLine(true)
                it.setHorizontallyScrolling(true)
                it.includeFontPadding = false
                it.gravity = Gravity.CENTER_VERTICAL
                it.setPadding(session.padL, 0, session.padR, 0)
                if (session.rowWidthPx > 0) it.width = session.rowWidthPx
            }
            val line = session.lines[position]
            val spans = if (position < session.lineSpans.size) session.lineSpans[position] else null
            if (spans == null || spans.isEmpty()) {
                tv.text = line
            } else {
                val ss = SpannableString(line)
                val len = line.length
                var k = 0
                while (k + 2 < spans.size) {
                    val s = spans[k]
                    val e = spans[k + 1]
                    val c = spans[k + 2]
                    if (s in 0 until len && e in (s + 1)..len) {
                        ss.setSpan(ForegroundColorSpan(c), s, e, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    }
                    k += 3
                }
                tv.text = ss
            }
            return tv
        }
    }

    @JvmStatic
    fun cancel(view: View?) {
        if (view == null) return
        val s = sessions.remove(view) ?: return
        s.cancelled = true
    }

    @JvmStatic
    fun getText(view: View?): String? {
        if (view == null) return null
        return sessions[view]?.fullText
    }
}

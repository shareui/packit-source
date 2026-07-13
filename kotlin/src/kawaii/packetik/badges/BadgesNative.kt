// SPDX-License-Identifier: GPL-3.0-or-later
//
// Precompiled Kotlin port of the PackIt badge system (previously packit/src/other/
// badges.py, chatBadge.py, chatTitleIcon.py, profileTitleIcon.py). Loaded at
// runtime from packit/dex/<abi>/badges.dex by packit/src/dexLoader.py.
//
// Config fetch + prefs cache + language + lookup now live here (Kotlin). Python
// only loads the dex and calls init(), passing the app ClassLoader, the app
// Context and the current on/off state of the "packit_verification" setting.
// Hooks are installed with the host Xposed runtime (XposedBridge); all host
// classes are accessed reflectively (XposedHelpers), like the Python original.
//
// Любая попытка неправомерного использования системы бейджей автоматически лишает
// ваш плагин права на публикацию через официальные источники и приводит к
// перманентной блокировке во всех ресурсах exteraGram и AyuGram.

package kawaii.packetik.badges

import android.content.Context
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.util.Log
import android.view.View
import de.robv.android.xposed.XC_MethodHook
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.XposedHelpers
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.lang.reflect.Array as JArray

object BadgesNative {

    private const val TAG = "PackitBadges"
    private const val SHADOW_TEXT_TYPE = 26
    private const val CONFIG_URL =
        "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/internal_cfg.json"
    private const val PREFS = "packit_badges"
    private const val PREF_KEY = "badges_config"

    private class Badge(val emojiId: Long, val text: String)

    @Volatile private var enabled: Boolean = true
    @Volatile private var badges: HashMap<Long, Badge> = HashMap()

    private lateinit var cl: ClassLoader
    private var appContext: Context? = null
    private val unhooks = ArrayList<XC_MethodHook.Unhook>()
    private var installed = false

    // diagnostics surfaced to Python via status() (visible in latestlog)
    @Volatile private var lastError: String? = null

    private fun err(where: String, t: Throwable) {
        Log.e(TAG, where, t)
        if (lastError == null) lastError = "$where: ${t.message}"
    }

    // profileTitleIcon lazy-resolved constants
    private var swapDrawableClass: Class<*>? = null
    private var cacheStatus = 4
    private var cacheKeyboard = 3

    // ---- entrypoints called from Python (dexLoader.py) -----------------------

    @JvmStatic
    fun init(classLoader: ClassLoader, context: Any?, isEnabled: Boolean) {
        try {
            cl = classLoader
            enabled = isEnabled
            appContext = context as? Context
            val lang = getLang()
            // 1) prime from prefs cache so badges show instantly
            badges = buildCache(parseBadges(loadFromPrefs()), lang)
            Log.i(TAG, "loaded ${badges.size} badge(s) from prefs")
            // 2) refresh from URL in the background
            refreshAsync(lang)
            // 3) install hooks
            installHooks()
        } catch (t: Throwable) {
            err("init error", t)
        }
    }

    @JvmStatic
    fun setEnabled(isEnabled: Boolean) {
        enabled = isEnabled
    }

    @JvmStatic
    fun refresh() {
        refreshAsync(getLang())
    }

    @JvmStatic
    fun status(): String =
        "enabled=$enabled badges=${badges.size} hooks=${unhooks.size} installed=$installed err=${lastError ?: "-"}"

    @JvmStatic
    fun deinit() {
        try {
            for (u in unhooks) {
                try { u.unhook() } catch (_: Throwable) {}
            }
            unhooks.clear()
            installed = false
        } catch (t: Throwable) {
            err("deinit error", t)
        }
    }

    // ---- config: fetch / cache / lang ---------------------------------------

    private fun getLang(): String = try {
        val l = Locale.getDefault().language
        if (l == "ru" || l == "en") l else "en"
    } catch (_: Throwable) {
        "en"
    }

    private fun loadFromPrefs(): String? = try {
        appContext?.getSharedPreferences(PREFS, 0)?.getString(PREF_KEY, null)
    } catch (_: Throwable) {
        null
    }

    private fun saveToPrefs(raw: String) {
        try {
            appContext?.getSharedPreferences(PREFS, 0)?.edit()?.putString(PREF_KEY, raw)?.apply()
        } catch (_: Throwable) {
        }
    }

    private fun refreshAsync(lang: String) {
        Thread {
            try {
                val raw = fetchConfig() ?: return@Thread
                val map = buildCache(parseBadges(raw), lang)
                if (map.isEmpty()) {
                    Log.i(TAG, "url config empty/unparsed, keeping ${badges.size} cached")
                    return@Thread
                }
                badges = map
                saveToPrefs(raw)
                Log.i(TAG, "updated ${map.size} badge(s) from url")
            } catch (t: Throwable) {
                err("refresh error", t)
            }
        }.apply { isDaemon = true }.start()
    }

    private fun fetchConfig(): String? = try {
        val conn = URL(CONFIG_URL).openConnection() as HttpURLConnection
        conn.connectTimeout = 10000
        conn.readTimeout = 10000
        conn.setRequestProperty("User-Agent", "PackIt/1.0 (Android; github.com/shareui/packit)")
        try {
            conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    } catch (_: Throwable) {
        null
    }

    private fun parseBadges(raw: String?): JSONArray? {
        if (raw.isNullOrEmpty()) return null
        return try {
            val t = raw.trim()
            if (t.startsWith("[")) JSONArray(t) else JSONObject(t).optJSONArray("badges")
        } catch (_: Throwable) {
            null
        }
    }

    private fun buildCache(arr: JSONArray?, lang: String): HashMap<Long, Badge> {
        val map = HashMap<Long, Badge>()
        if (arr == null) return map
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val emojiId = o.optLong("emoji_id", 0L)
            var text = o.optString("text_$lang", "")
            if (text.isEmpty()) text = o.optString("text_en", "")
            if (emojiId == 0L || text.isEmpty()) continue
            val userId = o.optLong("user_id", 0L)
            val chatId = o.optLong("chat_id", 0L)
            val id = if (userId != 0L) userId else if (chatId != 0L) chatId else continue
            map[id] = Badge(emojiId, text)
        }
        return map
    }

    // ---- helpers -------------------------------------------------------------

    private fun fc(name: String): Class<*>? =
        try { XposedHelpers.findClass(name, cl) } catch (_: Throwable) { null }

    private fun lookup(entityId: Long): Badge? = badges[entityId]

    private fun asLong(v: Any?): Long? = when (v) {
        is Long -> v
        is Int -> v.toLong()
        is Number -> v.toLong()
        else -> null
    }

    private fun entityIdOf(userId: Any?, chatId: Any?): Long? {
        val uid = asLong(userId) ?: 0L
        val cid = asLong(chatId) ?: 0L
        return when {
            uid != 0L -> uid
            cid != 0L -> Math.abs(cid)
            else -> null
        }
    }

    private fun buildEmojiText(emojiId: Long, text: String, fontMetrics: Any?): SpannableStringBuilder {
        val span = XposedHelpers.newInstance(
            fc("org.telegram.ui.Components.AnimatedEmojiSpan"), emojiId, fontMetrics
        )
        val sb = SpannableStringBuilder()
        sb.append("x")
        sb.setSpan(span, 0, 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        sb.append(" ")
        sb.append(text)
        return sb
    }

    // ---- hook installation ---------------------------------------------------

    private fun installHooks() {
        if (installed) return
        installed = true
        hookProfileInfoCell()
        hookChatTopPanel()
        hookChatTitleIcon()
        hookProfileTitleIcon()
    }

    private fun add(set: Set<XC_MethodHook.Unhook>?) {
        if (set != null) unhooks.addAll(set)
    }

    // badges.py :: _BindHook / _apply_cell
    private fun hookProfileInfoCell() {
        try {
            val adapter = fc("org.telegram.ui.ProfileActivity\$ListAdapter") ?: return
            add(XposedBridge.hookAllMethods(adapter, "onBindViewHolder", object : XC_MethodHook() {
                override fun afterHookedMethod(param: MethodHookParam) {
                    if (!enabled) return
                    try {
                        val holder = param.args[0] ?: return
                        if ((XposedHelpers.callMethod(holder, "getItemViewType") as Int) != SHADOW_TEXT_TYPE) return
                        val profile = XposedHelpers.getObjectField(param.thisObject, "this\$0") ?: return
                        val infoRow = asLong(XposedHelpers.getObjectField(profile, "infoSectionRow")) ?: return
                        val position = asLong(param.args[1]) ?: return
                        if (infoRow != position) return
                        val entityId = entityIdOf(
                            XposedHelpers.getObjectField(profile, "userId"),
                            XposedHelpers.getObjectField(profile, "chatId")
                        ) ?: return
                        val entry = lookup(entityId) ?: return
                        val cell = XposedHelpers.getObjectField(holder, "itemView") ?: return
                        val tv = XposedHelpers.callMethod(cell, "getTextView")
                        val fm = XposedHelpers.callMethod(XposedHelpers.callMethod(tv, "getPaint"), "getFontMetricsInt")
                        val sb = buildEmojiText(entry.emojiId, entry.text, fm)
                        XposedHelpers.callMethod(cell, "setFixedSize", 0)
                        XposedHelpers.callMethod(cell, "setText", sb)
                    } catch (t: Throwable) {
                        err("profile info cell hook", t)
                    }
                }
            }))
        } catch (t: Throwable) {
            err("hookProfileInfoCell", t)
        }
    }

    // chatBadge.py :: _TopPanelHook
    private fun hookChatTopPanel() {
        try {
            val chat = fc("org.telegram.ui.ChatActivity") ?: return
            add(XposedBridge.hookAllMethods(chat, "updateTopPanel", object : XC_MethodHook() {
                override fun afterHookedMethod(param: MethodHookParam) {
                    if (!enabled) return
                    try {
                        val activity = param.thisObject
                        val did = asLong(XposedHelpers.getObjectField(activity, "dialog_id")) ?: return
                        val entityId = if (did > 0) did else Math.abs(did)
                        val entry = lookup(entityId) ?: return
                        val hint = XposedHelpers.getObjectField(activity, "emojiStatusSpamHint") ?: return
                        if ((XposedHelpers.callMethod(hint, "getVisibility") as Int) != View.VISIBLE) return
                        val fm = XposedHelpers.callMethod(XposedHelpers.callMethod(hint, "getPaint"), "getFontMetricsInt")
                        val sb = buildEmojiText(entry.emojiId, entry.text, fm)
                        XposedHelpers.callMethod(hint, "setText", sb)
                    } catch (t: Throwable) {
                        err("chat top panel hook", t)
                    }
                }
            }))
        } catch (t: Throwable) {
            err("hookChatTopPanel", t)
        }
    }

    // chatTitleIcon.py :: _SetTitleIconsHook + _UpdateTitleIconsHook
    private fun hookChatTitleIcon() {
        try {
            val container = fc("org.telegram.ui.Components.ChatAvatarContainer")
            if (container != null) {
                add(XposedBridge.hookAllMethods(container, "setTitleIcons", object : XC_MethodHook() {
                    override fun beforeHookedMethod(param: MethodHookParam) {
                        try {
                            val right = if (param.args.size > 1) param.args[1] else null
                            XposedHelpers.callMethod(param.thisObject, "setTag", right)
                        } catch (t: Throwable) {
                            err("setTitleIcons hook", t)
                        }
                    }
                }))
            }
            val chat = fc("org.telegram.ui.ChatActivity") ?: return
            add(XposedBridge.hookAllMethods(chat, "updateTitleIcons", object : XC_MethodHook() {
                override fun afterHookedMethod(param: MethodHookParam) {
                    if (!enabled) return
                    try {
                        val activity = param.thisObject
                        val did = asLong(XposedHelpers.getObjectField(activity, "dialog_id")) ?: return
                        val entityId = if (did > 0) did else Math.abs(did)
                        val entry = lookup(entityId) ?: return
                        val avatar = XposedHelpers.getObjectField(activity, "avatarContainer") ?: return
                        val drawable = XposedHelpers.callMethod(
                            avatar, "getBotVerificationDrawable", entry.emojiId, false
                        ) ?: return
                        val right = XposedHelpers.callMethod(avatar, "getTag")
                        XposedHelpers.callMethod(avatar, "setTitleIcons", drawable, right)
                    } catch (t: Throwable) {
                        err("updateTitleIcons hook", t)
                    }
                }
            }))
        } catch (t: Throwable) {
            err("hookChatTitleIcon", t)
        }
    }

    // profileTitleIcon.py :: _UpdateProfileDataHook
    private fun initSwapClasses(): Boolean {
        if (swapDrawableClass != null) return true
        val animated = fc("org.telegram.ui.Components.AnimatedEmojiDrawable") ?: return false
        val swap = fc("org.telegram.ui.Components.AnimatedEmojiDrawable\$SwapAnimatedEmojiDrawable") ?: return false
        try {
            cacheStatus = XposedHelpers.getStaticIntField(animated, "CACHE_TYPE_EMOJI_STATUS")
            cacheKeyboard = XposedHelpers.getStaticIntField(animated, "CACHE_TYPE_KEYBOARD")
        } catch (_: Throwable) {
        }
        swapDrawableClass = swap
        return true
    }

    private fun makeSwapDrawable(nameView: Any?, index: Int): Any? {
        return try {
            val cacheType = if (index == 0) cacheStatus else cacheKeyboard
            val au = fc("org.telegram.messenger.AndroidUtilities")
            val size = XposedHelpers.callStaticMethod(au, "dp", 17) as Int
            val d = XposedHelpers.newInstance(swapDrawableClass, nameView, size, cacheType)
            XposedHelpers.callMethod(d, "offset", 0, XposedHelpers.callStaticMethod(au, "dp", 1) as Int)
            d
        } catch (t: Throwable) {
            err("makeSwapDrawable[$index]", t)
            null
        }
    }

    private fun hookProfileTitleIcon() {
        try {
            val profile = fc("org.telegram.ui.ProfileActivity") ?: return
            add(XposedBridge.hookAllMethods(profile, "updateProfileData", object : XC_MethodHook() {
                override fun afterHookedMethod(param: MethodHookParam) {
                    if (!enabled) return
                    try {
                        if (!initSwapClasses()) return
                        val obj = param.thisObject
                        val entityId = entityIdOf(
                            XposedHelpers.getObjectField(obj, "userId"),
                            XposedHelpers.getObjectField(obj, "chatId")
                        ) ?: return
                        val entry = lookup(entityId) ?: return
                        val drawables = XposedHelpers.getObjectField(obj, "botVerificationDrawable") ?: return
                        val nameViews = XposedHelpers.getObjectField(obj, "nameTextView") ?: return
                        val attached = XposedHelpers.getObjectField(obj, "fragmentViewAttached") as? Boolean ?: false
                        val count = JArray.getLength(drawables)
                        for (i in 0 until count) {
                            val nameView = JArray.get(nameViews, i) ?: continue
                            var d = JArray.get(drawables, i)
                            if (d == null) {
                                d = makeSwapDrawable(nameView, i) ?: continue
                                JArray.set(drawables, i, d)
                                if (attached) XposedHelpers.callMethod(d, "attach")
                            }
                            XposedHelpers.callMethod(d, "set", entry.emojiId, false)
                            XposedHelpers.callMethod(nameView, "setLeftDrawableOutside", true)
                            XposedHelpers.callMethod(nameView, "setLeftDrawable", d)
                        }
                    } catch (t: Throwable) {
                        err("updateProfileData hook", t)
                    }
                }
            }))
        } catch (t: Throwable) {
            err("hookProfileTitleIcon", t)
        }
    }
}

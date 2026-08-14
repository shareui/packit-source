// SPDX-License-Identifier: GPL-3.0-or-later
//
// Native builders for the SFX settings page. Host-only classes (UItem,
// SlideIntChooseView and Theme) are resolved through reflection so this source
// still compiles against the public Android SDK.

package kawaii.packetik.sfx

import android.content.Context
import android.graphics.Color
import android.graphics.PorterDuff
import android.graphics.PorterDuffColorFilter
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import java.lang.reflect.InvocationHandler
import java.lang.reflect.Method
import java.lang.reflect.Modifier
import java.lang.reflect.Proxy

object SfxNative {

    private const val UITEM_CLASS = "org.telegram.ui.Components.UItem"

    @JvmStatic
    fun createExpandable(
        classLoader: ClassLoader,
        id: Int,
        text: String,
        subtext: String,
        checked: Boolean,
        collapsed: Boolean,
        switchClick: View.OnClickListener?
    ): Any? {
        return try {
            val cls = Class.forName(UITEM_CLASS, true, classLoader)
            val factory = findStatic(cls, "asExteraExpandableSwitch", 4)
            val item = factory.invoke(null, id, text, subtext, switchClick) ?: return null
            call(item, "setChecked", checked)
            call(item, "setCollapsed", collapsed)
            item
        } catch (_: Throwable) {
            null
        }
    }

    @JvmStatic
    fun createChild(
        classLoader: ClassLoader,
        id: Int,
        text: String,
        checked: Boolean
    ): Any? {
        return try {
            val cls = Class.forName(UITEM_CLASS, true, classLoader)
            val factory = findStatic(cls, "asRoundCheckbox", 2)
            val item = factory.invoke(null, id, text) ?: return null
            call(item, "setChecked", checked)
            call(item, "pad")
            item
        } catch (_: Throwable) {
            null
        }
    }

    @JvmStatic
    fun createVolumeSlider(
        context: Context,
        initial: Int,
        title: String,
        offLabel: String,
        maximumLabel: String,
        onChange: InvocationHandler?
    ): View {
        return VolumeSlider(
            context,
            initial.coerceIn(0, 100),
            title,
            offLabel,
            maximumLabel,
            onChange
        )
    }

    private fun findStatic(cls: Class<*>, name: String, count: Int): Method {
        return cls.methods.firstOrNull {
            it.name == name && it.parameterCount == count && Modifier.isStatic(it.modifiers)
        }?.apply { isAccessible = true }
            ?: throw NoSuchMethodException("$name/$count on ${cls.name}")
    }

    private fun findMethod(cls: Class<*>, name: String, count: Int): Method {
        var current: Class<*>? = cls
        while (current != null) {
            current.declaredMethods.firstOrNull {
                it.name == name && it.parameterCount == count
            }?.let {
                it.isAccessible = true
                return it
            }
            current = current.superclass
        }
        throw NoSuchMethodException("$name/$count on ${cls.name}")
    }

    private fun call(target: Any, name: String, vararg args: Any?): Any? {
        return findMethod(target.javaClass, name, args.size).invoke(target, *args)
    }

    private fun callbackMarker(value: Int) = value

    private class VolumeSlider(
        context: Context,
        initial: Int,
        private val titleText: String,
        private val offLabel: String,
        private val maximumLabel: String,
        private val onChange: InvocationHandler?
    ) : LinearLayout(context) {

        private val hostLoader = context.classLoader
        private val callbackMethod = SfxNative::class.java.getDeclaredMethod(
            "callbackMarker",
            Int::class.javaPrimitiveType
        ).apply { isAccessible = true }

        init {
            orientation = VERTICAL
            setBackgroundColor(themeColor("key_windowBackgroundWhite", Color.WHITE))
            if (!buildMd3(context, initial)) {
                buildSeekBar(context, initial)
            }
        }

        override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
            super.onMeasure(
                MeasureSpec.makeMeasureSpec(
                    MeasureSpec.getSize(widthMeasureSpec),
                    MeasureSpec.EXACTLY
                ),
                MeasureSpec.makeMeasureSpec(dp(104), MeasureSpec.EXACTLY)
            )
        }

        private fun buildMd3(context: Context, initial: Int): Boolean {
            return try {
                val slideClass = Class.forName(
                    "org.telegram.ui.Cells.SlideIntChooseView",
                    true,
                    hostLoader
                )
                val optionsClass = Class.forName(
                    "org.telegram.ui.Cells.SlideIntChooseView\$Options",
                    true,
                    hostLoader
                )
                val utilitiesClass = Class.forName(
                    "org.telegram.messenger.Utilities",
                    true,
                    hostLoader
                )
                val plainInterface = Class.forName(
                    "org.telegram.messenger.Utilities\$CallbackReturn",
                    true,
                    hostLoader
                )
                val formatInterface = Class.forName(
                    "org.telegram.messenger.Utilities\$Callback2Return",
                    true,
                    hostLoader
                )
                val changeInterface = Class.forName(
                    "org.telegram.messenger.Utilities\$Callback",
                    true,
                    hostLoader
                )

                val plain = Proxy.newProxyInstance(
                    hostLoader,
                    arrayOf(plainInterface)
                ) { _, method, args ->
                    if (method.name == "run") args?.getOrNull(0)?.toString() ?: ""
                    else defaultProxyValue(method.returnType)
                }
                val make = optionsClass.methods.firstOrNull {
                    it.name == "make" && it.parameterCount == 4 &&
                        Modifier.isStatic(it.modifiers)
                } ?: return false
                val options = make.invoke(null, 0, 0, 100, plain) ?: return false

                val formatter = Proxy.newProxyInstance(
                    hostLoader,
                    arrayOf(formatInterface)
                ) { _, method, args ->
                    if (method.name == "run") {
                        val type = (args?.getOrNull(0) as? Number)?.toInt() ?: 0
                        val value = (args?.getOrNull(1) as? Number)?.toInt() ?: 0
                        if (type == 0) volumeLabel(value) else "$value%"
                    } else {
                        defaultProxyValue(method.returnType)
                    }
                }
                options.javaClass.getDeclaredField("toString").apply {
                    isAccessible = true
                    set(options, formatter)
                }

                val callback = Proxy.newProxyInstance(
                    hostLoader,
                    arrayOf(changeInterface)
                ) { _, method, args ->
                    if (method.name == "run") {
                        notifyChanged((args?.getOrNull(0) as? Number)?.toInt() ?: initial)
                    }
                    defaultProxyValue(method.returnType)
                }

                val ctor = slideClass.declaredConstructors.firstOrNull {
                    it.parameterCount == 2
                } ?: slideClass.declaredConstructors.firstOrNull {
                    it.parameterCount == 1
                } ?: return false
                ctor.isAccessible = true
                val slider = if (ctor.parameterCount == 2) {
                    ctor.newInstance(context, null)
                } else {
                    ctor.newInstance(context)
                } as? View ?: return false

                val setMethod = slideClass.methods.firstOrNull {
                    it.name == "set" && it.parameterCount == 3
                } ?: return false
                setMethod.invoke(slider, initial, options, callback)

                setPadding(0, dp(6), 0, 0)
                addView(makeText(titleText, 16f, "key_windowBackgroundWhiteBlackText"),
                    linearParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, 22, 0, 22, 0))
                addView(slider, LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
                true
            } catch (_: Throwable) {
                false
            }
        }

        private fun buildSeekBar(context: Context, initial: Int) {
            setPadding(dp(21), dp(8), dp(21), dp(8))
            gravity = Gravity.CENTER_VERTICAL

            val row = LinearLayout(context).apply {
                orientation = HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            addView(row, linearParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 6))

            row.addView(
                makeText(titleText, 16f, "key_windowBackgroundWhiteBlackText"),
                LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            )
            val value = makeText(
                volumeLabel(initial),
                14f,
                "key_windowBackgroundWhiteGrayText"
            )
            row.addView(value, LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT))

            val seekBar = SeekBar(context).apply {
                max = 100
                progress = initial
            }
            try {
                val accent = themeColor("key_featuredStickers_addButton", Color.BLUE)
                val filter = PorterDuffColorFilter(accent, PorterDuff.Mode.SRC_IN)
                seekBar.progressDrawable?.colorFilter = filter
                seekBar.thumb?.colorFilter = filter
            } catch (_: Throwable) {
            }
            seekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(bar: SeekBar?, progress: Int, fromUser: Boolean) {
                    value.text = volumeLabel(progress)
                    if (fromUser) notifyChanged(progress)
                }

                override fun onStartTrackingTouch(bar: SeekBar?) = Unit
                override fun onStopTrackingTouch(bar: SeekBar?) = Unit
            })
            addView(seekBar, LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }

        private fun notifyChanged(value: Int) {
            try {
                onChange?.invoke(this, callbackMethod, arrayOf(value.coerceIn(0, 100)))
            } catch (_: Throwable) {
            }
        }

        private fun volumeLabel(value: Int): String {
            return when (value) {
                0 -> offLabel
                100 -> maximumLabel
                else -> "$value%"
            }
        }

        private fun makeText(textValue: String, size: Float, colorKey: String): TextView {
            return TextView(context).apply {
                text = textValue
                setTextSize(TypedValue.COMPLEX_UNIT_DIP, size)
                setTextColor(themeColor(colorKey, Color.DKGRAY))
                gravity = Gravity.CENTER_VERTICAL
            }
        }

        private fun themeColor(keyName: String, fallback: Int): Int {
            return try {
                val theme = Class.forName(
                    "org.telegram.ui.ActionBar.Theme",
                    true,
                    hostLoader
                )
                val key = theme.getDeclaredField(keyName).apply {
                    isAccessible = true
                }.get(null)
                val method = theme.methods.firstOrNull {
                    it.name == "getColor" && it.parameterCount == 1 &&
                        Modifier.isStatic(it.modifiers)
                } ?: return fallback
                (method.invoke(null, key) as? Number)?.toInt() ?: fallback
            } catch (_: Throwable) {
                fallback
            }
        }

        private fun linearParams(
            width: Int,
            height: Int,
            left: Int,
            top: Int,
            right: Int,
            bottom: Int
        ): LayoutParams {
            return LayoutParams(width, height).apply {
                setMargins(dp(left), dp(top), dp(right), dp(bottom))
            }
        }

        private fun dp(value: Int): Int {
            return (value * resources.displayMetrics.density + 0.5f).toInt()
        }

        private fun defaultProxyValue(type: Class<*>): Any? {
            if (!type.isPrimitive || type == Void.TYPE) return null
            return when (type) {
                java.lang.Boolean.TYPE -> false
                java.lang.Character.TYPE -> '\u0000'
                java.lang.Byte.TYPE -> 0.toByte()
                java.lang.Short.TYPE -> 0.toShort()
                java.lang.Integer.TYPE -> 0
                java.lang.Long.TYPE -> 0L
                java.lang.Float.TYPE -> 0f
                java.lang.Double.TYPE -> 0.0
                else -> null
            }
        }
    }
}

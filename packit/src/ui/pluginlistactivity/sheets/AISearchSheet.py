# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ....utils.Ripple import safe_ripple as _safe_ripple
from ....utils.Bulletins import factory as _pbf
import ctypes
import json
import base64
import os
import threading
from android.view import Gravity, View
from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.util import TypedValue
from android.text import InputType
from android.graphics.drawable import GradientDrawable
try:
    from android.graphics.drawable import RippleDrawable
except Exception:
    RippleDrawable = None
try:
    from android.content.res import ColorStateList as AColorStateList
except Exception:
    AColorStateList = None
from android_utils import OnClickListener, run_on_ui_thread, R
from client_utils import get_last_fragment
try:
    from elyx import strings, settings
except Exception as e:
    logx(f"AISearchSheet: import strings/settings failed: {e}", False)
    strings = {}
    settings = None

_GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-pro-preview"]
_GEMINI_MODEL_LABELS = ["3.5 Flash", "3.1 Flash Lite", "3.1 Pro (Preview)"]


def _load_gemini_cache() -> dict:
    try:
        from ....utils.Paths import getGeminiCachePath
        path = getGeminiCachePath()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logx(f"AISearchSheet: _load_gemini_cache error: {e}", False)
        return {}


def _save_gemini_cache(cache: dict) -> None:
    try:
        from ....utils.Paths import getGeminiCachePath
        path = getGeminiCachePath()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        logx(f"AISearchSheet: _save_gemini_cache error: {e}", False)


def _cache_key(model: str, query: str) -> str:
    return f"{model}|{query.lower().strip()}"


def _get_cached_result(model: str, query: str) -> "list | None":
    cache = _load_gemini_cache()
    entry = cache.get(_cache_key(model, query))
    if isinstance(entry, dict):
        return entry.get("names")
    return None


def _put_cached_result(model: str, query: str, names: list) -> None:
    cache = _load_gemini_cache()
    cache[_cache_key(model, query)] = {"model": model, "query": query, "names": names}
    _save_gemini_cache(cache)


def _get_device_id() -> str:
    try:
        from android.provider import Settings
        from org.telegram.messenger import ApplicationLoader
        ctx = ApplicationLoader.applicationContext
        return str(Settings.Secure.getString(ctx.getContentResolver(), Settings.Secure.ANDROID_ID)) or "default"
    except Exception as e:
        logx(f"AISearchSheet: _get_device_id error: {e}", False)
        return "default"


def _load_gemini_key() -> "str | None":
    # returns full key string or None
    try:
        from ....NativeLoader import loadPackitKey
        from ....utils.Paths import getKeysDir
    except Exception as e:
        logx(f"AISearchSheet: _load_gemini_key import failed: {e}", False)
        return None
    try:
        lib = loadPackitKey()
        if not lib:
            return None
        keysDir = getKeysDir()
        deviceId = _get_device_id()
        exists = lib.packitkey_exists(
            keysDir.encode("utf-8"),
            deviceId.encode("utf-8"),
            b"gemini",
        )
        if exists != 1:
            return None
        buf = (ctypes.c_uint8 * 4096)()
        length = ctypes.c_uint32(4096)
        result = lib.packitkey_load(
            keysDir.encode("utf-8"),
            deviceId.encode("utf-8"),
            b"gemini",
            buf,
            ctypes.byref(length),
        )
        if result != 0:
            return None
        return bytes(buf[:length.value]).decode("utf-8", errors="replace")
    except Exception as e:
        logx(f"AISearchSheet: _load_gemini_key error: {e}", False)
        return None


def _get_ai_key_preview() -> "str | None":
    key = _load_gemini_key()
    if key is None:
        return None
    return key[:2] + ".." + key[-3:] if len(key) > 5 else key


def _get_selected_model() -> str:
    try:
        idx = settings.get("gemini_model", 0)
        if isinstance(idx, int) and 0 <= idx < len(_GEMINI_MODELS):
            return _GEMINI_MODELS[idx]
    except Exception:
        pass
    return _GEMINI_MODELS[0]


def _get_selected_model_label() -> str:
    try:
        idx = settings.get("gemini_model", 0)
        if isinstance(idx, int) and 0 <= idx < len(_GEMINI_MODEL_LABELS):
            return _GEMINI_MODEL_LABELS[idx]
    except Exception:
        pass
    return _GEMINI_MODEL_LABELS[0]


def _build_plugins_file_content(plugins: list) -> str:
    # build plain-text catalog: one plugin per line "name: <name> | description: <desc>"
    lines = []
    for p in plugins:
        name = str(p.get("name") or p.get("id") or "").strip()
        about = p.get("about", [])
        if isinstance(about, list) and about:
            desc = str(about[0]).strip()
        else:
            desc = str(p.get("description") or "").strip()
        if name:
            lines.append(f"name: {name} | description: {desc}")
    return "\n".join(lines)


class _GeminiQuotaError(Exception):
    pass

class _GeminiGeoError(Exception):
    pass


def _call_gemini(apiKey: str, model: str, pluginsCatalog: str, userQuery: str) -> "list | None":
    # uploads plugins catalog as inline text/plain file, asks gemini to rank matching plugins
    # returns list of dicts with "name" key, or None on error
    import requests

    prompt = (
        "You are a plugin search assistant. "
        "Below is a catalog of plugins, one per line in the format: name: <name> | description: <desc>\n\n"
        "User is looking for: \"" + userQuery + "\"\n\n"
        "Return ONLY a valid JSON array (no markdown, no explanation) of 1 to 5 most relevant plugin objects, "
        "sorted from most to least relevant. "
        "Each object must have exactly these keys: "
        "\"name\" (string, exact plugin name from catalog). "
        "Example output: [{\"name\": \"PluginA\"}, {\"name\": \"PluginB\"}]"
    )

    catalog_b64 = base64.b64encode(pluginsCatalog.encode("utf-8")).decode("ascii")

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "text/plain",
                            "data": catalog_b64,
                        }
                    },
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": apiKey}

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code == 429:
        logx(f"AISearchSheet: gemini quota exceeded (429)", True)
        raise _GeminiQuotaError()
    if resp.status_code in (400, 403):
        logx(f"AISearchSheet: gemini HTTP {resp.status_code}: {resp.text[:200]}", True)
        raise _GeminiGeoError()
    if resp.status_code != 200:
        logx(f"AISearchSheet: gemini HTTP {resp.status_code}: {resp.text[:200]}", True)
        raise Exception(f"gemini HTTP {resp.status_code}")

    body = resp.text
    logx(f"AISearchSheet: gemini response status={resp.status_code} body_len={len(body)} body_preview='{body[:200]}'", True)
    data = resp.json()
    logx(f"AISearchSheet: gemini data keys={list(data.keys())}", True)
    candidate = data["candidates"][0]
    finish = candidate.get("finishReason", "UNKNOWN")
    logx(f"AISearchSheet: gemini finishReason={finish}", True)
    content = candidate.get("content", {})
    parts = content.get("parts")
    if not parts:
        logx(f"AISearchSheet: unexpected gemini response shape: 'parts', data={data}", True)
        raise Exception(f"gemini returned no parts (finishReason={finish})")
    text = parts[0]["text"]
    text = text.strip()
    # strip possible json fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    logx(f"AISearchSheet: gemini text to parse='{text}'", True)
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        return None
    return parsed


try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    logx(f"AISearchSheet: import BottomSheet/Theme failed: {e}", False)
try:
    from org.telegram.ui.Components import LayoutHelper, EditTextBoldCursor
except Exception as e:
    logx(f"AISearchSheet: import LayoutHelper/EditTextBoldCursor failed: {e}", False)
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    logx(f"AISearchSheet: import AndroidUtilities failed: {e}", False)


def _c(color: int) -> int:
    return ctypes.c_int32(color).value


def _alpha(color: int, alpha: int) -> int:
    return _c((alpha << 24) | (color & 0x00FFFFFF))


def _rounded_bg(color: int, radius_dp: int, stroke_color: int = None, stroke_dp: int = 1):
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(float(AndroidUtilities.dp(radius_dp)))
    bg.setColor(_c(color))
    if stroke_color is not None:
        bg.setStroke(AndroidUtilities.dp(stroke_dp), _c(stroke_color))
    return bg


def _ripple_bg(base_drawable, ripple_color: int = 0x20000000, radius_dp: int = 0):
    # always give the ripple an explicit mask (the host's own selector helpers
    # do the same): with a null mask the patterned-ripple path on Android 12+
    # ROMs crashed inside RippleDrawable.updateRipplePaint while drawing
    if RippleDrawable is not None and AColorStateList is not None:
        try:
            mask = GradientDrawable()
            mask.setShape(GradientDrawable.RECTANGLE)
            mask.setCornerRadius(float(AndroidUtilities.dp(radius_dp)))
            mask.setColor(_c(0xFFFFFFFF))
            return _safe_ripple(AColorStateList.valueOf(_c(ripple_color)), base_drawable, mask)
        except Exception:
            pass
    return base_drawable


# full alias path from the settings root: each segment before the last must be
# the link_alias of the Text row opening the next sub-screen (host joins with ':').
# The old value "::gemini_api_key" had empty parent segments (rows had no
# link_alias), so the engine's alias walker silently bailed and nothing opened.
_SETTINGS_URL = "https://t.me/exteraSettings?p=shareui_packit&s=other:api_keys:gemini_api_key"


def _open_settings_url(act):
    try:
        from android.net import Uri
        from org.telegram.messenger.browser import Browser
        Browser.openUrl(act, Uri.parse(_SETTINGS_URL), True, True, True, None, None, False, False, False)
    except Exception as e:
        logx(f"AISearchSheet: _open_settings_url error: {e}", False)


def _icon_btn(act, install_ui, icon_name: str, size_dp: int = 20, btn_size_dp: int = 36, radius_dp: int = 10):
    btn = FrameLayout(act)
    btn.setClickable(True)
    btn.setFocusable(True)
    try:
        surface = _alpha(Theme.getColor(Theme.key_dialogTextBlack), 0x14)
        bg = _rounded_bg(surface, radius_dp)
        btn.setBackground(_ripple_bg(bg, 0x20000000, radius_dp))
    except Exception as e:
        logx(f"AISearchSheet: _icon_btn bg failed: {e}", False)
    icon = ImageView(act)
    try:
        icon.setImageResource(install_ui._resolve_icon(icon_name))
    except Exception as e:
        logx(f"AISearchSheet: _icon_btn icon failed: {e}", False)
    try:
        icon.setColorFilter(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception as e:
        logx(f"AISearchSheet: _icon_btn colorFilter failed: {e}", False)
    # CENTER_INSIDE: scales down oversized icon-pack drawables so they never clip
    icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    padding = AndroidUtilities.dp(8)
    icon.setPadding(padding, padding, padding, padding)
    btn.addView(icon, FrameLayout.LayoutParams(-1, -1, Gravity.CENTER))
    btn_lp = FrameLayout.LayoutParams(AndroidUtilities.dp(btn_size_dp), AndroidUtilities.dp(btn_size_dp))
    return btn, btn_lp


def _make_header(act, install_ui, sheet):
    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)

    ic_wrap = FrameLayout(act)
    try:
        surface = _alpha(Theme.getColor(Theme.key_dialogTextBlack), 0x10)
        ic_wrap.setBackground(_rounded_bg(surface, 12))
    except Exception as e:
        logx(f"AISearchSheet: header ic_wrap bg failed: {e}", False)
    ai_icon = ImageView(act)
    try:
        ai_icon.setImageResource(install_ui._resolve_icon("premium_ai_editor"))
    except Exception:
        try:
            ai_icon.setImageResource(install_ui._resolve_icon("msg_search"))
        except Exception as e:
            logx(f"AISearchSheet: header ai_icon failed: {e}", False)
    try:
        ai_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    except Exception as e:
        logx(f"AISearchSheet: header ai_icon color failed: {e}", False)
    ai_icon.setScaleType(ImageView.ScaleType.CENTER)
    ic_wrap.addView(ai_icon, FrameLayout.LayoutParams(
        AndroidUtilities.dp(22), AndroidUtilities.dp(22), Gravity.CENTER
    ))
    ic_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(38), AndroidUtilities.dp(38))
    ic_lp.rightMargin = AndroidUtilities.dp(12)
    row.addView(ic_wrap, ic_lp)

    titles = LinearLayout(act)
    titles.setOrientation(LinearLayout.VERTICAL)
    title_tv = TextView(act)
    try:
        title_tv.setText(strings["ai_search_title"])
    except Exception:
        title_tv.setText("AI Search")
    title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
    try:
        title_tv.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    try:
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception as e:
        logx(f"AISearchSheet: title color failed: {e}", False)
    titles.addView(title_tv, LinearLayout.LayoutParams(-2, -2))

    key_tv = TextView(act)
    try:
        key_preview = _get_ai_key_preview()
        if key_preview is not None:
            key_tv.setText(f"Gemini {_get_selected_model_label()}")
        else:
            key_tv.setText("Not configured")
    except Exception as e:
        logx(f"AISearchSheet: key_tv setText failed: {e}", False)
        key_tv.setText("Not configured")
    key_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    try:
        key_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    except Exception as e:
        logx(f"AISearchSheet: key_tv color failed: {e}", False)
    titles.addView(key_tv, LinearLayout.LayoutParams(-2, -2))

    row.addView(titles, LinearLayout.LayoutParams(0, -2, 1.0))

    settings_btn, settings_lp = _icon_btn(act, install_ui, "msg_settings")
    settings_lp.rightMargin = AndroidUtilities.dp(8)
    row.addView(settings_btn, settings_lp)

    close_btn, close_lp = _icon_btn(act, install_ui, "msg_close")
    close_btn.setOnClickListener(OnClickListener(lambda v: sheet.dismiss()))
    settings_btn.setOnClickListener(OnClickListener(lambda v: (sheet.dismiss(), _open_settings_url(act))))
    row.addView(close_btn, close_lp)

    install_ui._apply_press_scale(settings_btn)
    install_ui._apply_press_scale(close_btn)

    row_lp = LinearLayout.LayoutParams(-1, AndroidUtilities.dp(48))
    row_lp.bottomMargin = AndroidUtilities.dp(16)
    return row, row_lp


def _make_input_field(act):
    container = FrameLayout(act)
    try:
        fill = _alpha(Theme.getColor(Theme.key_dialogTextBlack), 0x0C)
        stroke = _alpha(Theme.getColor(Theme.key_dialogTextBlack), 0x1A)
        bg = _rounded_bg(fill, 14, stroke, 1)
        container.setBackground(bg)
    except Exception as e:
        logx(f"AISearchSheet: input bg failed: {e}", False)

    try:
        hint_str = strings["ai_search_input_hint"]
    except Exception:
        hint_str = "Describe the plugin and AI will find it..."

    search_input = EditTextBoldCursor(act)
    search_input.setHint(hint_str)
    search_input.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    search_input.setMinLines(3)
    search_input.setMaxLines(8)
    search_input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE)
    search_input.setGravity(Gravity.TOP | Gravity.LEFT)
    search_input.setBackground(None)
    search_input.setPadding(
        AndroidUtilities.dp(16), AndroidUtilities.dp(14),
        AndroidUtilities.dp(16), AndroidUtilities.dp(14)
    )
    try:
        search_input.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
    except Exception as e:
        logx(f"AISearchSheet: input text color failed: {e}", False)
    try:
        search_input.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    except Exception as e:
        logx(f"AISearchSheet: input hint color failed: {e}", False)
    try:
        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        search_input.setCursorColor(accent)
        search_input.setCursorWidth(1.5)
    except Exception as e:
        logx(f"AISearchSheet: input cursor failed: {e}", False)

    container.addView(search_input, FrameLayout.LayoutParams(-1, -2))
    container_lp = LinearLayout.LayoutParams(-1, -2)
    container_lp.bottomMargin = AndroidUtilities.dp(12)
    return container, container_lp, search_input


def _add_icon_balance_spacer(act, inner):
    # right-side spacer equal to the leading icon block (icon width + its right
    # margin) so the "Найти" label ends up dead-centre of the button instead of
    # being pushed to the right by the search icon on its left
    try:
        inner.addView(View(act), LinearLayout.LayoutParams(
            AndroidUtilities.dp(20) + AndroidUtilities.dp(8), AndroidUtilities.dp(1)
        ))
    except Exception:
        pass


def _make_search_button(act, install_ui):
    btn = FrameLayout(act)
    btn.setClickable(True)
    btn.setFocusable(True)
    try:
        base = Theme.getColor(Theme.key_featuredStickers_addButton)
        pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base, pressed
        ))
    except Exception as e:
        logx(f"AISearchSheet: search_btn bg failed: {e}", False)
    btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))

    inner = LinearLayout(act)
    inner.setOrientation(LinearLayout.HORIZONTAL)
    inner.setGravity(Gravity.CENTER)

    icon = ImageView(act)
    try:
        icon.setImageResource(install_ui._resolve_icon("ic_ab_search"))
    except Exception as e:
        logx(f"AISearchSheet: search_btn icon failed: {e}", False)
    try:
        icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
    except Exception as e:
        logx(f"AISearchSheet: search_btn icon color failed: {e}", False)
    icon.setScaleType(ImageView.ScaleType.CENTER)
    icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
    icon_lp.rightMargin = AndroidUtilities.dp(8)
    inner.addView(icon, icon_lp)

    label = TextView(act)
    try:
        label.setText(strings["ai_search_button"])
    except Exception:
        label.setText("Search")
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    try:
        label.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    label.setGravity(Gravity.CENTER)
    try:
        label.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    except Exception as e:
        logx(f"AISearchSheet: search_btn label color failed: {e}", False)
    inner.addView(label, LinearLayout.LayoutParams(-2, -2))
    _add_icon_balance_spacer(act, inner)

    btn.addView(inner, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
    install_ui._apply_press_scale(btn)
    return btn


def _set_btn_loading(btn, loading: bool, install_ui):
    # swap search button content to show spinner or label
    try:
        inner = btn.getChildAt(0)
        if inner is None:
            return
        inner.removeAllViews()
        act = btn.getContext()
        if loading:
            from org.telegram.ui.Components import CircularProgressDrawable
            color = Theme.getColor(Theme.key_featuredStickers_buttonText)
            size = AndroidUtilities.dp(20)
            d = CircularProgressDrawable(float(size), float(AndroidUtilities.dp(2)), color)
            d.setBounds(0, 0, size, size)
            spinner = ImageView(act)
            spinner.setImageDrawable(d)
            spinner.setScaleType(ImageView.ScaleType.CENTER)
            inner.addView(spinner, LinearLayout.LayoutParams(size, size))
        else:
            icon = ImageView(act)
            try:
                icon.setImageResource(install_ui._resolve_icon("ic_ab_search"))
                icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            icon.setScaleType(ImageView.ScaleType.CENTER)
            icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
            icon_lp.rightMargin = AndroidUtilities.dp(8)
            inner.addView(icon, icon_lp)
            label = TextView(act)
            try:
                label.setText(strings["ai_search_button"])
            except Exception:
                label.setText("Search")
            label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            try:
                label.setTypeface(AndroidUtilities.bold())
            except Exception:
                pass
            label.setGravity(Gravity.CENTER)
            try:
                label.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass
            inner.addView(label, LinearLayout.LayoutParams(-2, -2))
            _add_icon_balance_spacer(act, inner)
    except Exception as e:
        logx(f"AISearchSheet: _set_btn_loading error: {e}", False)


def show_ai_search_sheet(install_ui, act, on_ai_results=None):
    # on_ai_results(plugin_names: list[str], query: str) — callback when results arrive
    logx("AISearchSheet: show_ai_search_sheet called", True)
    try:
        sheet = BottomSheet(act, True, get_last_fragment().getResourceProvider())
        sheet.setApplyBottomPadding(False)
        sheet.setApplyTopPadding(False)
        logx("AISearchSheet: sheet created", True)

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setClipChildren(False)
        root.setClipToPadding(False)
        root.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), AndroidUtilities.dp(20)
        )
        try:
            root.setBackground(install_ui._create_rounded_bg(Theme.getColor(Theme.key_dialogBackground)))
        except Exception as e:
            logx(f"AISearchSheet: root bg failed: {e}", False)
            try:
                root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
            except Exception as e2:
                logx(f"AISearchSheet: root bg color failed: {e2}", True)

        header_row, header_lp = _make_header(act, install_ui, sheet)
        root.addView(header_row, header_lp)

        input_container, input_lp, search_input = _make_input_field(act)
        root.addView(input_container, input_lp)

        search_btn = _make_search_button(act, install_ui)
        root.addView(search_btn, LayoutHelper.createLinear(-1, -2))

        # state: is request in progress
        _searching = [False]

        def _shake_input():
            # shake animation: move input container left-right rapidly
            try:
                from android.animation import ObjectAnimator, ValueAnimator
                from android.animation import AnimatorSet
                anim = ObjectAnimator.ofFloat(input_container, "translationX", 0.0, -20.0, 20.0, -14.0, 14.0, -8.0, 8.0, 0.0)
                anim.setDuration(500)
                anim.start()
            except Exception as e:
                logx(f"AISearchSheet: _shake_input error: {e}", False)

        # guard: True while attention hint is active, prevents stacking on rapid taps
        _hint_animating = [False]

        def _swap_hint_attention():
            if _hint_animating[0]:
                return
            _hint_animating[0] = True
            try:
                try:
                    original_hint = strings["ai_search_input_hint"]
                except Exception:
                    original_hint = "Describe the plugin and AI will find it..."
                attention_text = strings.get("ai_search_empty_hint", "Pay attention to me!!")

                def _fade_to_attention():
                    try:
                        search_input.animate().alpha(0.0).setDuration(150).withEndAction(
                            R(lambda: _set_attention_hint(attention_text))
                        ).start()
                    except Exception as e:
                        logx(f"AISearchSheet: fade_to_attention error: {e}", False)

                def _set_attention_hint(attn):
                    try:
                        search_input.setHint(attn)
                        search_input.animate().alpha(1.0).setDuration(150).start()
                        run_on_ui_thread(_restore_hint, 1500)
                    except Exception as e:
                        logx(f"AISearchSheet: set_attention_hint error: {e}", False)

                def _restore_hint():
                    try:
                        search_input.animate().alpha(0.0).setDuration(150).withEndAction(
                            R(_finish_restore)
                        ).start()
                    except Exception as e:
                        logx(f"AISearchSheet: restore_hint error: {e}", False)

                def _finish_restore():
                    try:
                        search_input.setHint(original_hint)
                        search_input.animate().alpha(1.0).setDuration(150).start()
                    except Exception as e:
                        logx(f"AISearchSheet: finish_restore error: {e}", False)
                    finally:
                        _hint_animating[0] = False

                _fade_to_attention()
            except Exception as e:
                logx(f"AISearchSheet: _swap_hint_attention error: {e}", False)
                _hint_animating[0] = False

        def _do_search():
            if _searching[0]:
                return
            query = search_input.getText().toString().strip()
            if not query:
                _shake_input()
                _swap_hint_attention()
                return

            apiKey = _load_gemini_key()
            if not apiKey:
                sheet.dismiss()
                try:
                    from org.telegram.ui.Components import BulletinFactory
                    frag = get_last_fragment()
                    container = frag.getParentActivity().getWindow().getDecorView()
                    rp = frag.getResourceProvider()
                    _pbf(container, rp).createErrorBulletin(
                        str(strings.get("ai_search_no_key", "Add the API key in the settings"))
                    ).show()
                except Exception as be:
                    logx(f"AISearchSheet: no key bulletin error: {be}", True)
                return

            plugins = getattr(getattr(install_ui, '_active_delegate', None), 'plugins', None) or []
            if not plugins:
                logx("AISearchSheet: no plugins loaded yet", True)
                return

            model = _get_selected_model()
            catalog = _build_plugins_file_content(plugins)

            _searching[0] = True
            run_on_ui_thread(lambda: _set_btn_loading(search_btn, True, install_ui))

            # close keyboard before network request
            try:
                imm = act.getSystemService("input_method")
                imm.hideSoftInputFromWindow(search_input.getWindowToken(), 0)
            except Exception:
                pass

            def _task():
                try:
                    try:
                        cache_enabled = settings.get("gemini_cache_enabled", True)
                    except Exception:
                        cache_enabled = True
                    cached = _get_cached_result(model, query) if cache_enabled else None
                    if cached is not None:
                        logx(f"AISearchSheet: cache hit for query '{query}', {len(cached)} results", True)
                        names = cached
                    else:
                        catalog_lines = len(catalog.splitlines())
                        logx(f"AISearchSheet: calling gemini model={model} query='{query}' catalog_lines={catalog_lines}", True)
                        results = _call_gemini(apiKey, model, catalog, query)
                        if results is None:
                            raise Exception("null result from gemini")
                        names = [r.get("name", "") for r in results if isinstance(r, dict) and r.get("name")]
                        logx(f"AISearchSheet: got {len(names)} results: {names}", True)
                        try:
                            if settings.get("gemini_cache_enabled", True):
                                _put_cached_result(model, query, names)
                        except Exception:
                            _put_cached_result(model, query, names)

                    def _on_done():
                        _searching[0] = False
                        _set_btn_loading(search_btn, False, install_ui)
                        sheet.dismiss()
                        if on_ai_results:
                            on_ai_results(names, query)

                    run_on_ui_thread(_on_done)
                except _GeminiQuotaError:
                    def _on_quota():
                        _searching[0] = False
                        sheet.dismiss()
                        try:
                            from org.telegram.ui.Components import BulletinFactory
                            frag = get_last_fragment()
                            container = frag.getParentActivity().getWindow().getDecorView()
                            rp = frag.getResourceProvider()
                            _pbf(container, rp).createErrorBulletin(
                                str(strings.get("ai_search_quota", "Gemini API quota exceeded. Try again later."))
                            ).show()
                        except Exception as be:
                            logx(f"AISearchSheet: quota bulletin error: {be}", True)
                    run_on_ui_thread(_on_quota)
                except _GeminiGeoError:
                    def _on_geo():
                        _searching[0] = False
                        sheet.dismiss()
                        try:
                            from org.telegram.ui.Components import BulletinFactory
                            frag = get_last_fragment()
                            container = frag.getParentActivity().getWindow().getDecorView()
                            rp = frag.getResourceProvider()
                            _pbf(container, rp).createErrorBulletin(
                                str(strings.get("ai_search_geo_error", "Turn on VPN and try again"))
                            ).show()
                        except Exception as be:
                            logx(f"AISearchSheet: geo bulletin error: {be}", True)
                    run_on_ui_thread(_on_geo)
                except Exception as e:
                    logx(f"AISearchSheet: search task error: {e}", False)
                    def _on_error():
                        _searching[0] = False
                        sheet.dismiss()
                        try:
                            from org.telegram.ui.Components import BulletinFactory
                            frag = get_last_fragment()
                            container = frag.getParentActivity().getWindow().getDecorView()
                            rp = frag.getResourceProvider()
                            _pbf(container, rp).createErrorBulletin(
                                str(strings.get("ai_search_error", "Search error. Check the logs."))
                            ).show()
                        except Exception as be:
                            logx(f"AISearchSheet: error bulletin error: {be}", True)
                    run_on_ui_thread(_on_error)

            threading.Thread(target=_task, daemon=True).start()

        search_btn.setOnClickListener(OnClickListener(lambda v: _do_search()))

        sheet.setCustomView(root)
        try:
            from ...ViewUtils import applyFontToTree
            applyFontToTree(root)
        except Exception as e:
            logx(f"AISearchSheet: applyFontToTree failed: {e}", False)
        sheet.show()
        logx("AISearchSheet: sheet shown", True)
    except Exception as e:
        logx(f"AISearchSheet: show error: {e}", False)

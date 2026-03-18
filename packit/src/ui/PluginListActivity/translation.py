from android_utils import log
from client_utils import get_last_fragment
from hook_utils import find_class
from java import dynamic_proxy
from android.view import View, MotionEvent
import threading
import requests
from java.util import Locale
from android_utils import run_on_ui_thread
from ui.alert import AlertDialogBuilder
from android.widget import LinearLayout, TextView, FrameLayout
from android.view import Gravity
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import OnClickListener
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities, R as R_tg failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ...utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser
except Exception:
    Browser = None



BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self):
                super().__init__()
            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.93).scaleY(0.93).setDuration(100).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
                except Exception:
                    pass
                return False
        view.setOnTouchListener(_TouchListener())
    except Exception:
        pass


def _get_localized_description(plugin):
    about = plugin.get("about", [])
    if isinstance(about, list) and len(about) >= 2:
        try:
            current_lang = Locale.getDefault().getLanguage()
            if current_lang == "ru":
                return about[1] if len(about) > 1 else about[0]
            else:
                return about[0]
        except Exception:
            return about[0]
    return str(plugin.get("description") or "")


_TRANSLATE_CHUNK_SIZE = 4000


def _translate_text(text: str, target_lang: str) -> str:
    # splits text into chunks and translates each, preserving newlines between them
    chunks = []
    while text:
        chunks.append(text[:_TRANSLATE_CHUNK_SIZE])
        text = text[_TRANSLATE_CHUNK_SIZE:]

    translated_parts = []
    for chunk in chunks:
        try:
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={requests.utils.quote(chunk)}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                part = "".join(
                    item[0] for item in data[0] if item and item[0]
                ) if data and data[0] else chunk
            else:
                part = chunk
        except Exception as e:
            log(f"translate: chunk error: {e}")
            part = chunk
        translated_parts.append(part)

    return "".join(translated_parts)


def translate_plugin(plugin_info: dict, text_override: str = None):
    def _do_translate():
        try:
            target_lang = Locale.getDefault().getLanguage()
            if not target_lang:
                target_lang = "en"

            description = text_override if text_override is not None else _get_localized_description(plugin_info)
            if not description.strip():
                run_on_ui_thread(lambda: BulletinFactory.of(get_last_fragment().getParentActivity().getWindow().getDecorView(), None).createErrorBulletin(strings["no_description_to_translate"]).show())
                return

            fragment = get_last_fragment()
            if not fragment:
                return
            act = fragment.getParentActivity()
            if not act:
                return
            dlg_ref = [None]

            def show_spinner():
                try:
                    loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
                    loading.set_cancelable(False)
                    dlg_ref[0] = loading.create()
                    dlg_ref[0].show()
                except Exception as e:
                    log(f"translate: show_spinner error: {e}")

            def dismiss_spinner():
                try:
                    if dlg_ref[0]:
                        dlg_ref[0].dismiss()
                except Exception as e:
                    log(f"translate: dismiss_spinner error: {e}")

            run_on_ui_thread(show_spinner)

            translated = _translate_text(description, target_lang)

            run_on_ui_thread(dismiss_spinner)
            run_on_ui_thread(lambda: _show_translate_sheet(act, plugin_info, target_lang, translated))

        except Exception as e:
            log(f"translate: error: {e}")
            try:
                run_on_ui_thread(lambda: BulletinFactory.of(get_last_fragment().getParentActivity().getWindow().getDecorView(), None).createErrorBulletin(strings["translation_failed"]).show())
            except Exception:
                pass

    threading.Thread(target=_do_translate, daemon=True).start()


def _show_translate_sheet(act, plugin_info, lang, translated_text):
    try:
        try:
            from elyx import strings
        except Exception:
            strings = lambda key: key
        try:
            from org.telegram.ui.ActionBar import BottomSheet, Theme
        except Exception:
            return
        try:
            from org.telegram.ui.Components import LayoutHelper
        except Exception:
            return
        try:
            from org.telegram.messenger import AndroidUtilities
        except Exception:
            return

        translate_sheet = BottomSheet(act, False, get_last_fragment().getResourceProvider())
        translate_sheet.setApplyBottomPadding(False)
        translate_sheet.setApplyTopPadding(False)
        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(8))
        try:
            root.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(18), Theme.getColor(Theme.key_dialogBackground)
            ))
        except Exception:
            pass

        header = TextView(act)
        header.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        header.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            header.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            header.setTypeface(AndroidUtilities.bold())
        plugin_name = plugin_info.get("name") or plugin_info.get("id") or "Unknown"
        header.setText(f"{plugin_name} → {lang.upper()}")
        header.setGravity(Gravity.CENTER)
        root.addView(header, LayoutHelper.createLinear(-1, -2, 0, 16, 16, 16, 16))

        translated_container = FrameLayout(act)
        translated_container.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(12), AndroidUtilities.dp(12), AndroidUtilities.dp(12))
        border_bg = GradientDrawable()
        border_bg.setShape(GradientDrawable.RECTANGLE)
        border_bg.setCornerRadius(AndroidUtilities.dp(12))
        border_bg.setStroke(AndroidUtilities.dp(2), Theme.getColor(Theme.key_featuredStickers_addButton))
        border_bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        translated_container.setBackground(border_bg)

        translated_tv = TextView(act)
        translated_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        translated_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        try:
            from com.exteragram.messenger.utils.text import LocaleUtils
            from android.text.method import LinkMovementMethod
            translated_tv.setText(LocaleUtils.fullyFormatText(translated_text))
            translated_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
            translated_tv.setMovementMethod(LinkMovementMethod.getInstance())
        except Exception:
            translated_tv.setText(translated_text)
        translated_container.addView(translated_tv, FrameLayout.LayoutParams(-1, -1))
        root.addView(translated_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 16))

        close_btn = FrameLayout(act)
        try:
            base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception:
            base_color = Theme.getColor(Theme.key_dialogTextBlue)
        try:
            pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            pressed_color = base_color
        close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), base_color, pressed_color
        ))
        close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_text = TextView(act)
        close_text.setText(strings["close_button"])
        close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_text.setTypeface(AndroidUtilities.bold())
        close_text.setGravity(Gravity.CENTER)
        close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))

        _apply_press_scale(close_btn)

        def on_close(v):
            try:
                translate_sheet.dismiss()
            except Exception:
                pass

        close_btn.setOnClickListener(OnClickListener(on_close))
        root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 16, 0, 8))

        translate_sheet.setCustomView(root)
        translate_sheet.show()
    except Exception as e:
        log(f"translate: show sheet error: {e}")
# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Adding and editing a source.
#
# Built in the shape of the api-key dialog (SettingsActivity/service/
# AddKeyDialog.py): dimmed overlay, a card that springs in, bold title, gray
# subtitle, outlined field, one accent button. That dialog's overlay, back
# handling, keyboard tracking and animations are imported rather than copied —
# there is no reason for a second implementation of any of them.
#
# What this one adds: a field can refuse to submit and say why in place (the
# old add dialog dismissed itself and then dropped a bulletin, so a typo cost
# you the whole form), the button carries a spinner while the repomap is being
# fetched, and the same dialog serves editing.

from packutil import logx
import ctypes

from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment, run_on_queue
from java import dynamic_proxy

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"repos dialog: import elyx strings failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
    from org.telegram.ui.Components import LayoutHelper, EditTextBoldCursor, OutlineTextContainerView
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"repos dialog: import telegram classes failed: {e}")

from ...SettingsActivity.service.AddKeyDialog import (
    _register_back_cb, _unregister_back_cb, _animate_in, _animate_out,
    _attach_keyboard_listener, _detach_keyboard_listener,
)
from ...utils.bulletins import factory as _pbf

# addRepositoryWithUrl answers in lowercase english; the user gets their own
# language and, where possible, a hint at what to do about it
_REASONS = {
    "file not found": "repo_err_not_found",
    "forbidden": "repo_err_forbidden",
    "unauthorized": "repo_err_forbidden",
    "rate limited, try again later": "repo_err_rate_limited",
    "redirected": "repo_err_redirect",
    "permanently redirected": "repo_err_redirect",
    "temporarily redirected": "repo_err_redirect",
    "see other": "repo_err_redirect",
    "request timeout": "repo_err_timeout",
    "gateway timeout": "repo_err_timeout",
    "server error": "repo_err_server",
    "bad gateway": "repo_err_server",
    "service unavailable": "repo_err_server",
    "resource gone": "repo_err_not_found",
    "invalid json": "repo_err_json",
    "missing repometa": "repo_err_meta",
    "missing rm_rid": "repo_err_rid",
    "missing rm_name": "repo_err_name",
    "cache write failed": "repo_err_cache",
}


def _c(color: int) -> int:
    return ctypes.c_int32(color).value


def _theme(key: str, fallback: int = 0):
    try:
        return Theme.getColor(getattr(Theme, key))
    except Exception:
        return fallback


def _s(key: str, fallback: str = "") -> str:
    try:
        return str(strings[key])
    except Exception:
        return fallback


def _localize_reason(reason: str) -> str:
    text = str(reason or "").strip()
    low = text.lower()
    key = _REASONS.get(low)
    if key:
        return _s(key, text)
    if "connection" in low or "max retries" in low or "resolve" in low:
        return _s("repo_err_network", text)
    return _s("repo_err_http", "{0}").replace("{0}", text)


def _make_field(act, label: str, hint: str, value: str, uri: bool):
    from android.util import TypedValue
    from android.text import InputType, TextUtils
    from android.view import View

    dp = AndroidUtilities.dp
    outline = OutlineTextContainerView(act)
    outline.setText(label)
    outline.animateSelection(0, False)
    outline.setClipChildren(True)
    outline.setClipToPadding(True)

    edit = EditTextBoldCursor(act)
    edit.setHint(hint)
    edit.setHintTextColor(_theme("key_windowBackgroundWhiteGrayText"))
    edit.setTextColor(_theme("key_windowBackgroundWhiteBlackText"))
    edit.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    edit.setBackground(None)
    edit.setSingleLine(True)
    edit.setHorizontallyScrolling(True)
    edit.setInputType(
        InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI if uri else InputType.TYPE_CLASS_TEXT
    )
    if value:
        edit.setText(value)
        # cursor stays at the start: putting it at the end scrolls a long url so
        # that its tail is what you see, and the beginning is the part worth
        # reading
        try:
            edit.setSelection(0)
        except Exception:
            pass
    try:
        edit.setCursorColor(_theme("key_featuredStickers_addButton"))
        edit.setCursorWidth(1.5)
    except Exception:
        pass
    edit.setPadding(dp(4), dp(14), dp(4), dp(14))
    try:
        edit.setEllipsize(TextUtils.TruncateAt.END)
    except Exception:
        pass

    class _FocusListener(dynamic_proxy(View.OnFocusChangeListener)):
        def onFocusChange(self, v, hasFocus):
            outline.animateSelection(1 if hasFocus else 0)

    edit.setOnFocusChangeListener(_FocusListener())

    # A scrolled single-line TextView paints over its own padding, so a long url
    # ran out from under the outline and over the border. The inset lives on a
    # wrapper that clips to it instead, which the text cannot escape.
    from android.widget import FrameLayout as _FrameLayout
    holder = _FrameLayout(act)
    holder.setPadding(dp(12), 0, dp(12), 0)
    holder.setClipToPadding(True)
    holder.setClipChildren(True)
    holder.addView(edit, LayoutHelper.createFrame(-1, -2))

    outline.addView(holder, LayoutHelper.createFrame(-1, -2))
    outline.attachEditText(edit)
    return outline, edit


def _show_form_dialog(act, title: str, subtitle: str, fields: list, button_text: str, on_submit):
    """
    fields   — [{"label","hint","value","uri"}]
    on_submit(values: list[str], ui) — ui.error(text) / ui.loading(bool) / ui.dismiss()
    """
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.view import Gravity, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()
        accent = _theme("key_featuredStickers_addButton")

        overlay_ref = [None]
        back_cb_ref = [None]
        kb_listener_ref = [None]
        orig_mode_ref = [None]
        busy = [False]

        overlay = FrameLayout(act)
        overlay_ref[0] = overlay
        overlay.setBackgroundColor(_c(0x99000000))
        overlay.setClickable(True)
        overlay.setFocusable(True)

        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        card.setClickable(True)
        card.setFocusable(True)
        card.setOnClickListener(OnClickListener(lambda v: None))
        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(16))
        card_bg.setColor(_theme("key_dialogBackground"))
        card.setBackground(card_bg)
        card.setPadding(dp(20), dp(24), dp(20), dp(20))

        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = dp(32)
        card_lp.rightMargin = dp(32)
        overlay.addView(card, card_lp)

        def _dismiss(on_end=None):
            _unregister_back_cb(back_cb_ref[0])
            back_cb_ref[0] = None
            _detach_keyboard_listener(act, decor, kb_listener_ref[0], orig_mode_ref[0])
            kb_listener_ref[0] = None
            orig_mode_ref[0] = None
            _animate_out(overlay_ref, card, decor, on_end=on_end)

        def _dismiss_from_overlay(v):
            if busy[0]:
                return
            try:
                AndroidUtilities.hideKeyboard(edits[0])
            except Exception:
                pass
            _dismiss()

        overlay.setOnClickListener(OnClickListener(_dismiss_from_overlay))

        title_tv = TextView(act)
        title_tv.setText(title)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        title_tv.setTextColor(_theme("key_dialogTextBlack"))
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        card.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        subtitle_tv = TextView(act)
        subtitle_tv.setText(subtitle)
        subtitle_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        subtitle_tv.setTextColor(_theme("key_windowBackgroundWhiteGrayText"))
        subtitle_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        card.addView(subtitle_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        edits = []
        for i, spec in enumerate(fields):
            outline, edit = _make_field(
                act, spec.get("label", ""), spec.get("hint", ""),
                spec.get("value", ""), bool(spec.get("uri"))
            )
            card.addView(outline, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 10))
            edits.append(edit)

        error_tv = TextView(act)
        error_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        error_tv.setTextColor(_theme("key_text_RedRegular", _c(0xFFEC5044)))
        error_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        error_tv.setVisibility(8)  # GONE
        card.addView(error_tv, LayoutHelper.createLinear(-1, -2, 4, 0, 4, 6))

        button_box = FrameLayout(act)
        button_box.setClickable(True)
        button_box.setFocusable(True)
        try:
            button_box.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                dp(12), accent, _theme("key_featuredStickers_addButtonPressed", accent)))
        except Exception:
            pass

        button_tv = TextView(act)
        button_tv.setText(button_text)
        button_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        button_tv.setGravity(Gravity.CENTER)
        button_tv.setPadding(dp(16), dp(14), dp(16), dp(14))
        button_tv.setTextColor(_theme("key_featuredStickers_buttonText"))
        try:
            button_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        button_box.addView(button_tv, FrameLayout.LayoutParams(-1, -2))

        spinner_holder = FrameLayout(act)
        spinner_holder.setVisibility(8)
        button_box.addView(spinner_holder, FrameLayout.LayoutParams(-1, -1))
        card.addView(button_box, LayoutHelper.createLinear(-1, -2, 0, 6, 0, 0))

        class _Ui:
            def error(self, text):
                def _apply():
                    try:
                        if not text:
                            error_tv.setVisibility(8)
                            return
                        error_tv.setText(str(text))
                        error_tv.setVisibility(0)
                        error_tv.setAlpha(0.0)
                        error_tv.animate().alpha(1.0).setDuration(160).start()
                    except Exception as e:
                        logx(f"repos dialog: error paint failed: {e}", False)
                run_on_ui_thread(_apply)

            def loading(self, value):
                busy[0] = bool(value)

                def _apply():
                    try:
                        button_box.setEnabled(not value)
                        button_tv.setAlpha(0.35 if value else 1.0)
                        if value and spinner_holder.getChildCount() == 0:
                            try:
                                from ..PluginListActivity.helpers.uiHelpers import create_circular_loading
                                spin = create_circular_loading(act, 20)
                                spinner_holder.addView(spin, FrameLayout.LayoutParams(
                                    AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
                            except Exception as e:
                                logx(f"repos dialog: spinner unavailable: {e}", True)
                        spinner_holder.setVisibility(0 if value else 8)
                    except Exception as e:
                        logx(f"repos dialog: loading paint failed: {e}", False)
                run_on_ui_thread(_apply)

            def dismiss(self, on_end=None):
                def _apply():
                    try:
                        AndroidUtilities.hideKeyboard(edits[0] if edits else None)
                    except Exception:
                        pass
                    _dismiss(on_end=on_end)
                run_on_ui_thread(_apply)

        ui = _Ui()

        def _submit(v):
            if busy[0]:
                return
            values = []
            for edit in edits:
                try:
                    values.append(str(edit.getText()).strip())
                except Exception:
                    values.append("")
            ui.error(None)
            try:
                on_submit(values, ui)
            except Exception as e:
                logx(f"repos dialog: submit error: {e}", False)
                ui.loading(False)
                ui.error(_s("repo_err_unknown", "{0}").replace("{0}", str(e)))

        button_box.setOnClickListener(OnClickListener(_submit))

        overlay.setAlpha(0.0)
        card.setAlpha(0.0)
        card.setScaleX(0.92)
        card.setScaleY(0.92)

        decor.addView(overlay, ViewGroup.LayoutParams(-1, -1))
        back_cb_ref[0] = _register_back_cb(act, lambda: None if busy[0] else _dismiss())

        listener, orig_mode = _attach_keyboard_listener(act, decor, card)
        kb_listener_ref[0] = listener
        orig_mode_ref[0] = orig_mode

        def _open():
            if edits:
                edits[0].requestFocus()
            _animate_in(overlay, card, on_end=lambda: (
                AndroidUtilities.showKeyboard(edits[0]) if edits else None))

        run_on_ui_thread(_open)
    except Exception as e:
        logx(f"repos dialog: show error: {e}", False)


def _normalize_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if "://" in text:
        return text  # some other scheme, let the validator complain
    return "https://" + text


def show_add_repo_dialog(act, delegate):
    def _submit(values, ui):
        url = _normalize_url(values[0])
        if not url:
            ui.error(_s("repo_err_empty", "Enter a link"))
            return
        if not url.startswith(("http://", "https://")):
            ui.error(_s("repo_err_scheme", "The link must start with https://"))
            return
        repos = delegate.repoManager.getRepositories()
        if any(str(r.get("url") or "").strip() == url for r in repos):
            ui.error(_s("repo_err_duplicate", "Already added"))
            return

        ui.loading(True)

        def _task():
            repometa, reason = delegate.repoManager.addRepositoryWithUrl(url)

            def _done():
                ui.loading(False)
                if reason:
                    ui.error(_localize_reason(reason))
                    return
                ui.dismiss(on_end=lambda: _added(delegate))

            run_on_ui_thread(_done)

        run_on_queue(_task)

    _show_form_dialog(
        act,
        _s("repo_add_sheet_title", "New source"),
        _s("repo_add_sheet_subtitle", "Paste a link to repomap.json"),
        [{"label": _s("repo_add_field_url", "Link"), "hint": "https://…/repomap.json",
          "value": "", "uri": True}],
        str(strings.add_repository),
        _submit,
    )


def _added(delegate):
    try:
        frag = get_last_fragment()
        container = frag.getParentActivity().getWindow().getDecorView()
        rp = frag.getResourceProvider()
        _pbf(container, rp).createSimpleBulletin(
            R_tg.raw.shared_link_enter, str(strings.repository_added)).show()
    except Exception as e:
        logx(f"repos dialog: added bulletin error: {e}", True)
    try:
        delegate.reload()
    except Exception:
        pass


def show_edit_repo_dialog(act, delegate, repo: dict):
    def _submit(values, ui):
        name = values[0]
        url = _normalize_url(values[1]) if len(values) > 1 else ""
        if not url:
            ui.error(_s("repo_err_empty", "Enter a link"))
            return
        if not url.startswith(("http://", "https://")):
            ui.error(_s("repo_err_scheme", "The link must start with https://"))
            return

        idx, repos = delegate._index_of(repo)
        if idx < 0:
            ui.error(_s("repo_err_unknown", "{0}").replace("{0}", "gone"))
            return
        if any(i != idx and str(r.get("url") or "").strip() == url for i, r in enumerate(repos)):
            ui.error(_s("repo_err_duplicate", "Already added"))
            return

        changed_url = str(repo.get("url") or "").strip() != url
        if name != str(repo.get("name") or ""):
            delegate.repoManager.updateRepoField(idx, "name", name)
        if not changed_url:
            ui.dismiss(on_end=delegate.reload)
            return

        # a new url is a new repomap: validate it before it replaces the old one
        ui.loading(True)

        def _task():
            repometa, reason = delegate.repoManager.addRepositoryWithUrl(url)

            def _done():
                ui.loading(False)
                if reason:
                    ui.error(_localize_reason(reason))
                    return
                # addRepositoryWithUrl appended a fresh entry; drop the old one
                fresh_idx, _ = delegate._index_of(repo)
                if fresh_idx >= 0:
                    delegate.repoManager.removeRepository(fresh_idx)
                ui.dismiss(on_end=delegate.reload)

            run_on_ui_thread(_done)

        run_on_queue(_task)

    _show_form_dialog(
        act,
        _s("repo_sheet_edit_title", "Edit source"),
        _s("repo_sheet_edit_sub", "Name and link"),
        [
            {"label": str(strings.repo_name), "hint": str(strings.repo_name),
             "value": str(repo.get("name") or ""), "uri": False},
            {"label": str(strings.repo_url), "hint": "https://…/repomap.json",
             "value": str(repo.get("url") or ""), "uri": True},
        ],
        _s("save_button", "Save"),
        _submit,
    )

# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ..utils.bulletins import factory as _pbf
import ctypes
import json
import os
from android_utils import run_on_ui_thread, OnClickListener
from java import dynamic_proxy

try:
    from elyx import strings
except Exception as e:
    logx(f"reportDialog: import elyx.strings failed: {e}", False)
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    logx(f"reportDialog: import Theme failed: {e}", False)
try:
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    logx(f"reportDialog: import AndroidUtilities/LayoutHelper failed: {e}", False)

_ANIM_DURATION = 220
_SPRING_DURATION = 380


def _register_back_cb(act, on_back):
    try:
        from androidx.activity import OnBackPressedCallback
        from extera_utils.classes import Base, java_subclass, joverride

        @java_subclass(OnBackPressedCallback)
        class _Cb(Base):
            @joverride()
            def handleOnBackPressed(self):
                on_back()

        cb = _Cb.new_instance(True)
        act.getOnBackPressedDispatcher().addCallback(act, cb.java)
        return cb
    except Exception as e:
        logx(f"reportDialog: _register_back_cb error: {e}", False)
        return None


def _unregister_back_cb(cb):
    try:
        if cb is not None:
            cb.remove()
    except Exception as e:
        logx(f"reportDialog: _unregister_back_cb error: {e}", False)


def _animate_in(overlay, card):
    try:
        from android.animation import AnimatorSet, ObjectAnimator
        from android.view.animation import OvershootInterpolator, DecelerateInterpolator

        fade_overlay = ObjectAnimator.ofFloat(overlay, "alpha", 0.0, 1.0)
        fade_overlay.setDuration(_ANIM_DURATION)
        fade_overlay.setInterpolator(DecelerateInterpolator())

        fade_card = ObjectAnimator.ofFloat(card, "alpha", 0.0, 1.0)
        fade_card.setDuration(_ANIM_DURATION)
        fade_card.setInterpolator(DecelerateInterpolator())

        scale_x = ObjectAnimator.ofFloat(card, "scaleX", 0.88, 1.0)
        scale_x.setDuration(_SPRING_DURATION)
        scale_x.setInterpolator(OvershootInterpolator(2.0))

        scale_y = ObjectAnimator.ofFloat(card, "scaleY", 0.88, 1.0)
        scale_y.setDuration(_SPRING_DURATION)
        scale_y.setInterpolator(OvershootInterpolator(2.0))

        s = AnimatorSet()
        s.playTogether(fade_overlay, fade_card, scale_x, scale_y)
        s.start()
    except Exception as e:
        logx(f"reportDialog: _animate_in error: {e}", False)


def _animate_out(overlay_ref, card, decor):
    try:
        from android.animation import AnimatorSet, ObjectAnimator, Animator

        fade_overlay = ObjectAnimator.ofFloat(overlay_ref[0], "alpha", overlay_ref[0].getAlpha(), 0.0)
        fade_overlay.setDuration(_ANIM_DURATION)

        fade_card = ObjectAnimator.ofFloat(card, "alpha", card.getAlpha(), 0.0)
        fade_card.setDuration(_ANIM_DURATION)

        scale_x = ObjectAnimator.ofFloat(card, "scaleX", card.getScaleX(), 0.92)
        scale_x.setDuration(_ANIM_DURATION)

        scale_y = ObjectAnimator.ofFloat(card, "scaleY", card.getScaleY(), 0.92)
        scale_y.setDuration(_ANIM_DURATION)

        class _EndListener(dynamic_proxy(Animator.AnimatorListener)):
            def onAnimationEnd(self, a, *args):
                try:
                    decor.removeView(overlay_ref[0])
                except Exception:
                    pass

            def onAnimationStart(self, a, *args): pass
            def onAnimationCancel(self, a, *args): pass
            def onAnimationRepeat(self, a, *args): pass

        s = AnimatorSet()
        s.playTogether(fade_overlay, fade_card, scale_x, scale_y)
        s.addListener(_EndListener())
        s.start()
    except Exception as e:
        logx(f"reportDialog: _animate_out error: {e}", False)
        try:
            decor.removeView(overlay_ref[0])
        except Exception:
            pass


def _load_reasons(repo_id: str) -> list:
    # loads reasons from cached repomap for given repo_id
    if not repo_id:
        return []
    try:
        from ..utils.paths import getRepoCachePath
        cache_path = getRepoCachePath(repo_id)
        if not os.path.exists(cache_path):
            return []
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        reasons = cached.get("reasons", {}).get("reasons", [])
        if isinstance(reasons, list):
            return [str(r) for r in reasons if r]
        return []
    except Exception as e:
        logx(f"reportDialog: _load_reasons error: {e}", False)
        return []


def _load_report_settings(repo_id: str):
    # returns (forum_username, topic_msg_id) or (None, None)
    if not repo_id:
        return None, None
    try:
        from ..utils.paths import getRepoCachePath
        cache_path = getRepoCachePath(repo_id)
        if not os.path.exists(cache_path):
            return None, None
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        settings = cached.get("reasons", {}).get("settings", [])
        if isinstance(settings, list) and len(settings) >= 2:
            return str(settings[0]), int(settings[1])
        return None, None
    except Exception as e:
        logx(f"reportDialog: _load_report_settings error: {e}", False)
        return None, None


def _submit_report(forum_username: str, topic_msg_id: int, plugin_name: str, plugin_id: str, repo_id: str, reason: str, description: str, act, on_done):
    # resolves forum, joins if needed, sends report to topic
    try:
        from client_utils import send_request, RequestCallback, get_messages_controller, run_on_queue, PLUGINS_QUEUE
        from org.telegram.tgnet import TLRPC

        def _show_success():
            try:
                from org.telegram.ui.Components import BulletinFactory
                from hook_utils import find_class
                from elyx import strings
                R_tg = find_class("org.telegram.messenger.R")
                decor = act.getWindow().getDecorView()
                _pbf(decor, None).createSimpleBulletin(
                    R_tg.raw.done,
                    str(strings["report_dialog_sent"])
                ).show()
            except Exception as e:
                logx(f"reportDialog: _show_success bulletin error: {e}", False)

        def _show_failure():
            try:
                from org.telegram.ui.Components import BulletinFactory
                from elyx import strings
                decor = act.getWindow().getDecorView()
                _pbf(decor, None).createErrorBulletin(
                    str(strings["report_dialog_failed"])
                ).show()
            except Exception as e:
                logx(f"reportDialog: _show_failure bulletin error: {e}", False)

        def _do_submit():
            try:
                mc = get_messages_controller()

                def _send_to_topic(channel_id, access_hash):
                    try:
                        from org.telegram.tgnet import TLRPC
                        import random

                        req = TLRPC.TL_messages_sendMessage()

                        peer = TLRPC.TL_inputPeerChannel()
                        peer.channel_id = channel_id
                        peer.access_hash = access_hash
                        req.peer = peer

                        reply_to = TLRPC.TL_inputReplyToMessage()
                        reply_to.reply_to_msg_id = topic_msg_id
                        reply_to.flags |= 1  # top_msg_id flag
                        reply_to.top_msg_id = topic_msg_id
                        req.reply_to = reply_to
                        req.flags |= 1  # reply_to present flag

                        from org.telegram.tgnet import TLRPC as _TLRPC
                        from hook_utils import find_class as _fc

                        def _u16(s):
                            return len(s.encode("utf-16-le")) // 2

                        # each segment: (item_name, build_fn) -> appends to parts/pending_entities
                        # parts: list of str chunks; pending_entities: list of (label, value, extra_builder)
                        # we build incrementally so a failing item is skipped gracefully

                        plain_parts = []
                        pending_bold_labels = []  # (label_text, value_text, extra_fn_or_None)
                        item_errors = []

                        def _cur_offset():
                            return _u16("".join(plain_parts))

                        # header: "New report!\n" — always present, no try needed
                        plain_parts.append("New report!\n")

                        # Plugin — always present (name comes from caller, no external call)
                        try:
                            plain_parts.append("Plugin: ")
                            _name_off = _cur_offset()
                            plain_parts.append(plugin_name)
                            pending_bold_labels.append(("Plugin:", _name_off - _u16("Plugin: "), None, plugin_name))
                        except Exception as _ie:
                            item_errors.append(("Plugin", _ie))

                        # Status — may fail
                        try:
                            from com.exteragram.messenger.plugins import PluginsController as _PC
                            _plugin_obj = _PC.getInstance().plugins.get(plugin_id)
                            if _plugin_obj is None:
                                _status = "not installed"
                            elif _plugin_obj.isEnabled():
                                _status = "installed, enabled"
                            else:
                                _status = "installed, disabled"
                            plain_parts.append("\nStatus: ")
                            plain_parts.append(_status)
                            pending_bold_labels.append(("Status:", None, None, None))
                        except Exception as _ie:
                            logx(f"reportDialog: status item error: {_ie}", True)
                            item_errors.append(("Status", _ie))

                        # Reason — always present
                        try:
                            plain_parts.append("\nReason: ")
                            plain_parts.append(reason)
                            pending_bold_labels.append(("Reason:", None, None, None))
                        except Exception as _ie:
                            item_errors.append(("Reason", _ie))

                        # Report description — always present
                        try:
                            plain_parts.append("\nReport description:\n")
                            plain_parts.append(description)
                            pending_bold_labels.append(("Report description:", None, None, None))
                        except Exception as _ie:
                            item_errors.append(("Description", _ie))

                        # item errors footer
                        for _iname, _ierr in item_errors:
                            plain_parts.append(f"\n\nAn error occurred while generating item {_iname}: {_ierr}")

                        if not plain_parts:
                            raise RuntimeError("all items failed, nothing to send")

                        plain = "".join(plain_parts)

                        # now build entities with correct offsets from final plain
                        ArrayList = _fc("java.util.ArrayList")
                        entities_list = ArrayList()

                        # walk plain to find label offsets
                        def _find_label_off(label, after=0):
                            # finds first occurrence of label in plain at or after `after` (utf-16 units)
                            idx = plain.find(label, after)
                            if idx == -1:
                                return None
                            return _u16(plain[:idx])

                        # "New report!" — bold
                        _off = _find_label_off("New report!")
                        if _off is not None:
                            e = _TLRPC.TL_messageEntityBold()
                            e.offset = _off
                            e.length = _u16("New report!")
                            entities_list.add(e)

                        # "Plugin:" label — bold; plugin name — bold + link
                        _plugin_label_char = plain.find("Plugin: ")
                        if _plugin_label_char != -1:
                            _plugin_label_off = _u16(plain[:_plugin_label_char])
                            e_lbl = _TLRPC.TL_messageEntityBold()
                            e_lbl.offset = _plugin_label_off
                            e_lbl.length = _u16("Plugin:")
                            entities_list.add(e_lbl)
                            _name_char = _plugin_label_char + len("Plugin: ")
                            _name_off = _u16(plain[:_name_char])
                            _name_len = _u16(plugin_name)
                            plugin_link = f"tg://packit?plugin={plugin_id}&repo={repo_id}"
                            e_link = _TLRPC.TL_messageEntityTextUrl()
                            e_link.offset = _name_off
                            e_link.length = _name_len
                            e_link.url = plugin_link
                            entities_list.add(e_link)
                            e_bold = _TLRPC.TL_messageEntityBold()
                            e_bold.offset = _name_off
                            e_bold.length = _name_len
                            entities_list.add(e_bold)

                        # remaining bold labels: Status, Reason, Report description
                        for _lbl in ("Status:", "Reason:", "Report description:"):
                            _lchar = plain.find(_lbl)
                            if _lchar != -1:
                                e = _TLRPC.TL_messageEntityBold()
                                e.offset = _u16(plain[:_lchar])
                                e.length = _u16(_lbl)
                                entities_list.add(e)

                        # description blockquote — text after "Report description:\n"
                        _desc_marker = "Report description:\n"
                        _desc_char = plain.find(_desc_marker)
                        if _desc_char != -1:
                            _desc_start_char = _desc_char + len(_desc_marker)
                            _desc_off = _u16(plain[:_desc_start_char])
                            # ends at start of error footer (if any) or end of string
                            if item_errors:
                                _footer_marker = "\n\nAn error occurred"
                                _footer_char = plain.find(_footer_marker)
                                _desc_end_char = _footer_char if _footer_char != -1 else len(plain)
                            else:
                                _desc_end_char = len(plain)
                            _desc_len = _u16(plain[_desc_start_char:_desc_end_char])
                            if _desc_len > 0:
                                e_bq = _TLRPC.TL_messageEntityBlockquote()
                                e_bq.collapsed = True
                                e_bq.offset = _desc_off
                                e_bq.length = _desc_len
                                entities_list.add(e_bq)

                        req.message = plain
                        req.entities = entities_list
                        req.flags |= 8  # entities present flag
                        req.random_id = random.randint(-(2**63), 2**63 - 1)
                        req.clear_draft = False

                        dialog_id = int(f"-100{channel_id}")
                        logx(f"reportDialog: sending report to dialog={dialog_id} topic={topic_msg_id}", True)

                        def _on_sent(r, e):
                            logx(f"reportDialog: send result error={e.text if e else None}", True)
                            if e:
                                run_on_ui_thread(lambda: (on_done(), _show_failure()))
                            else:
                                run_on_ui_thread(lambda: (on_done(), _show_success()))

                        send_request(req, RequestCallback(_on_sent))
                        logx("reportDialog: report request sent", True)
                    except Exception as e:
                        logx(f"reportDialog: _send_to_topic error: {e}", False)
                        run_on_ui_thread(lambda: (on_done(), _show_failure()))

                def _on_resolved(response, error):
                    try:
                        if error:
                            logx(f"reportDialog: resolve error: {error.text}", True)
                            run_on_ui_thread(lambda: (on_done(), _show_failure()))
                            return
                        if not response.chats:
                            logx("reportDialog: resolved peer has no chats", True)
                            run_on_ui_thread(lambda: (on_done(), _show_failure()))
                            return
                        chat = response.chats.get(0)
                        channel_id = chat.id
                        logx(f"reportDialog: resolved forum channel_id={channel_id} left={chat.left}", True)

                        if chat.left:
                            logx("reportDialog: not in forum, joining...", True)
                            join_req = TLRPC.TL_channels_joinChannel()
                            input_ch = TLRPC.TL_inputChannel()
                            input_ch.channel_id = channel_id
                            input_ch.access_hash = chat.access_hash

                            def _on_joined(join_resp, join_err, _cid=channel_id, _ah=chat.access_hash):
                                if join_err:
                                    logx(f"reportDialog: join error: {join_err.text}", True)
                                    run_on_ui_thread(lambda: (on_done(), _show_failure()))
                                    return
                                logx("reportDialog: joined forum successfully", True)
                                _send_to_topic(_cid, _ah)

                            join_req.channel = input_ch
                            send_request(join_req, RequestCallback(_on_joined))
                        else:
                            _send_to_topic(channel_id, chat.access_hash)
                    except Exception as e:
                        logx(f"reportDialog: _on_resolved error: {e}", False)

                resolve_req = TLRPC.TL_contacts_resolveUsername()
                resolve_req.username = forum_username
                logx(f"reportDialog: resolving forum @{forum_username}", True)
                send_request(resolve_req, RequestCallback(_on_resolved))
            except Exception as e:
                logx(f"reportDialog: _do_submit error: {e}", False)

        run_on_queue(_do_submit, PLUGINS_QUEUE)
    except Exception as e:
        logx(f"reportDialog: _submit_report error: {e}", False)


def _make_round_bg(dp, corner: int, color):
    from android.graphics.drawable import GradientDrawable
    d = GradientDrawable()
    d.setShape(GradientDrawable.RECTANGLE)
    d.setCornerRadius(dp(corner))
    d.setColor(color)
    return d


def show_report_dialog(act, plugin_name: str, repo_id: str, plugin_id: str = ""):
    try:
        from android.widget import LinearLayout, TextView, FrameLayout, EditText, ImageView
        from android.view import Gravity, ViewGroup, View
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from android.text import InputType

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()
        overlay_ref = [None]
        back_cb_ref = [None]
        selected_reason = [None]
        dropdown_ref = [None]
        list_expanded = [False]
        arrow_iv_ref = [None]
        header_tv_ref = [None]
        selector_row_ref = [None]
        input_field_ref = [None]
        submit_btn_ref = [None]
        submit_tv_ref = [None]
        error_anim_ref = {}  # view id -> active AnimatorSet
        row_entries = []

        reasons = _load_reasons(repo_id)
        forum_username, topic_msg_id = _load_report_settings(repo_id)

        def _close_dropdown():
            if dropdown_ref[0] is None:
                return
            try:
                from android.animation import AnimatorSet, ObjectAnimator, Animator

                fade = ObjectAnimator.ofFloat(dropdown_ref[0], "alpha", 1.0, 0.0)
                fade.setDuration(150)
                scale = ObjectAnimator.ofFloat(dropdown_ref[0], "scaleY", 1.0, 0.85)
                scale.setDuration(150)

                _popup = dropdown_ref[0]

                class _End(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        try:
                            decor.removeView(_popup)
                        except Exception:
                            pass
                        if dropdown_ref[0] is _popup:
                            dropdown_ref[0] = None
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                s = AnimatorSet()
                s.playTogether(fade, scale)
                s.addListener(_End())
                s.start()
            except Exception as e:
                logx(f"reportDialog: close_dropdown error: {e}", False)
                try:
                    decor.removeView(dropdown_ref[0])
                except Exception:
                    pass
                dropdown_ref[0] = None

        def _dismiss():
            _close_dropdown()
            list_expanded[0] = False
            try:
                arrow_iv_ref[0].animate().rotation(0.0).setDuration(150).start()
            except Exception:
                pass
            try:
                if input_field_ref[0] is not None:
                    AndroidUtilities.hideKeyboard(input_field_ref[0])
            except Exception:
                pass
            _unregister_back_cb(back_cb_ref[0])
            back_cb_ref[0] = None
            _animate_out(overlay_ref, card, decor)

        # dim overlay
        overlay = FrameLayout(act)
        overlay_ref[0] = overlay
        overlay.setBackgroundColor(ctypes.c_int32(0x99000000).value)
        overlay.setClickable(True)
        overlay.setFocusable(True)

        def _on_overlay_click(v):
            if list_expanded[0]:
                list_expanded[0] = False
                _close_dropdown()
                try:
                    arrow_iv_ref[0].animate().rotation(0.0).setDuration(150).start()
                except Exception:
                    pass
            else:
                _dismiss()

        overlay.setOnClickListener(OnClickListener(_on_overlay_click))

        # card
        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        card.setClickable(True)
        card.setFocusable(True)
        card.setOnClickListener(OnClickListener(lambda v: None))

        bg_color = Theme.getColor(Theme.key_dialogBackground)
        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(16))
        card_bg.setColor(bg_color)
        card.setBackground(card_bg)
        card.setPadding(dp(20), dp(20), dp(20), dp(20))

        margin_h = dp(24)
        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = margin_h
        card_lp.rightMargin = margin_h
        overlay.addView(card, card_lp)

        text_color = Theme.getColor(Theme.key_dialogTextBlack)
        gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        try:
            field_color = Theme.getColor(Theme.key_windowBackgroundGray)
        except Exception:
            field_color = 0xFF303030

        # title row: centered title + cancel button top-right
        title_row = FrameLayout(act)
        title_tv = TextView(act)
        title_tv.setText(str(strings["report_dialog_title"]))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        title_tv.setTextColor(text_color)
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        title_row.addView(title_tv, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))

        cancel_btn = ImageView(act)
        cancel_btn.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        cancel_btn.setColorFilter(gray_color)
        try:
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            cancel_btn.setImageResource(int(getattr(R_tg.drawable, "msg_cancel", 0)))
        except Exception:
            pass
        cancel_btn.setClickable(True)
        cancel_btn.setFocusable(True)
        cancel_btn.setOnClickListener(OnClickListener(lambda v: _dismiss()))
        cancel_lp = FrameLayout.LayoutParams(dp(28), dp(28), Gravity.END | Gravity.CENTER_VERTICAL)
        title_row.addView(cancel_btn, cancel_lp)

        title_row_lp = LinearLayout.LayoutParams(-1, -2)
        title_row_lp.bottomMargin = dp(16)
        card.addView(title_row, title_row_lp)

        # reason selector row
        selector_row = LinearLayout(act)
        selector_row.setOrientation(LinearLayout.HORIZONTAL)
        selector_row.setGravity(Gravity.CENTER_VERTICAL)
        selector_row.setPadding(dp(16), dp(14), dp(12), dp(14))
        selector_row.setClickable(True)
        selector_row.setFocusable(True)
        selector_row.setBackground(_make_round_bg(dp, 18, field_color))
        selector_row_ref[0] = selector_row
        selector_lp = LinearLayout.LayoutParams(-1, -2)
        selector_lp.bottomMargin = dp(12)
        card.addView(selector_row, selector_lp)

        header_tv = TextView(act)
        header_tv.setText(str(strings["report_dialog_select_reason"]))
        header_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        header_tv.setTextColor(gray_color)
        try:
            header_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        header_tv_ref[0] = header_tv
        selector_row.addView(header_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        arrow_iv = ImageView(act)
        arrow_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        try:
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            arrow_iv.setImageResource(int(getattr(R_tg.drawable, "arrow_more", 0)))
        except Exception:
            pass
        arrow_iv.setColorFilter(gray_color)
        arrow_iv.setRotation(0.0)
        arrow_iv_ref[0] = arrow_iv
        selector_row.addView(arrow_iv, LinearLayout.LayoutParams(dp(20), dp(20)))

        def _repaint_rows():
            try:
                checked_bg = Theme.getColor(Theme.key_dialogRadioBackgroundChecked)
            except Exception:
                checked_bg = Theme.getColor(Theme.key_featuredStickers_addButton)
            try:
                checked_text = Theme.getColor(Theme.key_dialogBackground)
            except Exception:
                checked_text = 0xFFFFFFFF
            for _row, _reason, _tv in row_entries:
                if selected_reason[0] == _reason:
                    _row.setBackground(_make_round_bg(dp, 12, checked_bg))
                    _tv.setTextColor(checked_text)
                else:
                    _row.setBackground(_make_round_bg(dp, 12, field_color))
                    _tv.setTextColor(text_color)

        def _open_dropdown():
            row_entries.clear()
            try:
                row_loc = [0, 0]
                selector_row_ref[0].getLocationInWindow(row_loc)
                decor_loc = [0, 0]
                decor.getLocationInWindow(decor_loc)
                anchor_x = row_loc[0] - decor_loc[0]
                anchor_y = row_loc[1] - decor_loc[1]
                anchor_w = selector_row_ref[0].getWidth()
                anchor_h = selector_row_ref[0].getHeight()
            except Exception as e:
                logx(f"reportDialog: dropdown position error: {e}", False)
                return

            from android.widget import ScrollView

            _max_visible = 5
            _row_h = dp(12) * 2 + dp(14) * 2  # padding top+bottom + approx text height
            _needs_scroll = len(reasons) > _max_visible

            popup = FrameLayout(act)
            popup.setBackground(_make_round_bg(dp, 18, field_color))
            popup.setElevation(float(dp(8)))
            popup.setClickable(True)
            popup.setFocusable(True)
            popup.setOnClickListener(OnClickListener(lambda v: None))
            dropdown_ref[0] = popup

            scroll_view = ScrollView(act)
            scroll_view.setVerticalScrollBarEnabled(False)
            scroll_view.setOverScrollMode(ScrollView.OVER_SCROLL_NEVER)

            rows_layout = LinearLayout(act)
            rows_layout.setOrientation(LinearLayout.VERTICAL)
            rows_layout.setPadding(dp(8), dp(8), dp(8) if not _needs_scroll else dp(20), dp(8))

            for i, reason in enumerate(reasons):
                row = FrameLayout(act)
                row.setClickable(True)
                row.setFocusable(True)
                row.setBackground(_make_round_bg(dp, 12, field_color))

                row_tv = TextView(act)
                row_tv.setText(reason)
                row_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                row_tv.setGravity(Gravity.CENTER_VERTICAL | Gravity.START)
                row_tv.setPadding(dp(14), dp(12), dp(14), dp(12))
                row_tv.setTextColor(text_color)
                try:
                    row_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                except Exception:
                    pass
                row.addView(row_tv, FrameLayout.LayoutParams(-1, -2))
                row_entries.append((row, reason, row_tv))

                def _make_select(_r=reason):
                    def _on_select(v):
                        selected_reason[0] = _r
                        header_tv_ref[0].setText(_r)
                        header_tv_ref[0].setTextColor(text_color)
                        _repaint_rows()
                        list_expanded[0] = False
                        _close_dropdown()
                        try:
                            arrow_iv_ref[0].animate().rotation(0.0).setDuration(150).start()
                        except Exception:
                            pass
                    return _on_select

                row.setOnClickListener(OnClickListener(_make_select()))

                row_lp = LinearLayout.LayoutParams(-1, -2)
                row_lp.bottomMargin = dp(4) if i < len(reasons) - 1 else 0
                rows_layout.addView(row, row_lp)

            _repaint_rows()

            scroll_view.addView(rows_layout, FrameLayout.LayoutParams(-1, -2))

            scroll_lp = FrameLayout.LayoutParams(-1, -2)
            if _needs_scroll:
                # cap height to show exactly 5 rows
                _row_item_h = dp(12 + 14 + 14 + 12)
                _visible_h = _max_visible * _row_item_h + dp(8) * 2
                scroll_lp.height = _visible_h
            popup.addView(scroll_view, scroll_lp)

            if _needs_scroll:
                # custom rounded scrollbar, visible only when >5 items
                from android.graphics.drawable import GradientDrawable
                from android.view import View as _View

                scrollbar_track = _View(act)
                try:
                    track_d = GradientDrawable()
                    track_d.setShape(GradientDrawable.RECTANGLE)
                    track_d.setCornerRadius(dp(4))
                    track_d.setColor(ctypes.c_int32(0x18808080).value)
                    scrollbar_track.setBackground(track_d)
                except Exception:
                    pass

                scrollbar_thumb = _View(act)
                scrollbar_thumb_d = GradientDrawable()
                scrollbar_thumb_d.setShape(GradientDrawable.RECTANGLE)
                scrollbar_thumb_d.setCornerRadius(dp(4))
                try:
                    scrollbar_thumb_d.setColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                except Exception:
                    scrollbar_thumb_d.setColor(ctypes.c_int32(0x60808080).value)
                scrollbar_thumb.setBackground(scrollbar_thumb_d)

                track_w = dp(4)
                track_margin = dp(6)
                _sv_h = _visible_h - dp(8) * 2

                track_lp = FrameLayout.LayoutParams(track_w, _sv_h)
                track_lp.gravity = Gravity.END | Gravity.TOP
                track_lp.rightMargin = track_margin
                track_lp.topMargin = dp(8)
                popup.addView(scrollbar_track, track_lp)

                thumb_lp = FrameLayout.LayoutParams(track_w, dp(24))
                thumb_lp.gravity = Gravity.END | Gravity.TOP
                thumb_lp.rightMargin = track_margin
                thumb_lp.topMargin = dp(8)
                popup.addView(scrollbar_thumb, thumb_lp)

                from java import dynamic_proxy
                from android.view import ViewTreeObserver

                def _update_thumb(sv=scroll_view, thumb=scrollbar_thumb, sv_h=_sv_h):
                    try:
                        content_h = sv.getChildAt(0).getHeight()
                        if content_h == 0:
                            return
                        viewport_h = sv.getHeight() if sv.getHeight() > 0 else sv_h
                        max_scroll = content_h - viewport_h
                        if max_scroll <= 0:
                            thumb.setAlpha(0.0)
                            return
                        track_h = sv_h
                        ratio = float(viewport_h) / float(content_h)
                        thumb_h = max(int(track_h * ratio), dp(20))
                        # resize thumb height only once via tag to avoid repeated setLayoutParams
                        if thumb.getTag() != thumb_h:
                            lp = thumb.getLayoutParams()
                            lp.height = thumb_h
                            thumb.setLayoutParams(lp)
                            thumb.setTag(thumb_h)
                        progress = float(sv.getScrollY()) / float(max_scroll)
                        thumb_top = max(0, min(int(progress * (track_h - thumb_h)), track_h - thumb_h))
                        # setTranslationY avoids layout pass on every scroll frame
                        thumb.setTranslationY(float(thumb_top))
                        thumb.setAlpha(1.0)
                    except Exception as e:
                        logx(f"reportDialog: scrollbar update error: {e}", False)

                class _ScrollListener(dynamic_proxy(ViewTreeObserver.OnScrollChangedListener)):
                    def onScrollChanged(self):
                        _update_thumb()

                scroll_view.getViewTreeObserver().addOnScrollChangedListener(_ScrollListener())
                # single deferred call after first layout to set initial thumb size
                from java.lang import Runnable as _Runnable
                class _InitThumb(dynamic_proxy(_Runnable)):
                    def run(self):
                        _update_thumb()
                scroll_view.post(_InitThumb())

            popup_lp = FrameLayout.LayoutParams(anchor_w, -2)
            popup_lp.leftMargin = anchor_x
            popup_lp.topMargin = anchor_y + anchor_h + dp(4)
            popup.setAlpha(0.0)
            popup.setScaleY(0.85)
            popup.setPivotY(0.0)

            decor.addView(popup, popup_lp)

            try:
                from android.animation import AnimatorSet, ObjectAnimator
                from android.view.animation import DecelerateInterpolator
                fade = ObjectAnimator.ofFloat(popup, "alpha", 0.0, 1.0)
                fade.setDuration(160)
                fade.setInterpolator(DecelerateInterpolator())
                scale = ObjectAnimator.ofFloat(popup, "scaleY", 0.85, 1.0)
                scale.setDuration(160)
                scale.setInterpolator(DecelerateInterpolator())
                s = AnimatorSet()
                s.playTogether(fade, scale)
                s.start()
            except Exception as e:
                logx(f"reportDialog: dropdown open anim error: {e}", False)
                popup.setAlpha(1.0)
                popup.setScaleY(1.0)

        def _toggle_dropdown(v=None):
            if list_expanded[0]:
                list_expanded[0] = False
                _close_dropdown()
                try:
                    arrow_iv_ref[0].animate().rotation(0.0).setDuration(150).start()
                except Exception:
                    pass
            else:
                list_expanded[0] = True
                try:
                    if input_field_ref[0] is not None:
                        AndroidUtilities.hideKeyboard(input_field_ref[0])
                except Exception:
                    pass
                _open_dropdown()
                try:
                    arrow_iv_ref[0].animate().rotation(180.0).setDuration(150).start()
                except Exception:
                    pass

        selector_row.setOnClickListener(OnClickListener(_toggle_dropdown))

        # text input
        input_field = EditText(act)
        input_field.setHint(str(strings["report_dialog_describe"]))
        input_field.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText))
        input_field.setTextColor(text_color)
        input_field.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        input_field.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE)
        input_field.setMinLines(3)
        input_field.setMaxLines(6)
        input_field.setGravity(Gravity.TOP | Gravity.START)
        input_field.setPadding(dp(14), dp(12), dp(14), dp(12))
        input_field.setBackground(_make_round_bg(dp, 14, field_color))
        try:
            input_field.setTypeface(AndroidUtilities.getTypeface("fonts/rregular.ttf"))
        except Exception:
            pass
        input_field_ref[0] = input_field
        input_lp = LinearLayout.LayoutParams(-1, -2)
        input_lp.bottomMargin = dp(16)
        card.addView(input_field, input_lp)

        # submit button
        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        accent_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)

        submit_btn = FrameLayout(act)
        submit_btn.setClickable(True)
        submit_btn.setFocusable(True)
        submit_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(12), accent, accent_pressed))

        submit_tv = TextView(act)
        submit_tv.setText(str(strings["report_dialog_submit"]))
        submit_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        submit_tv.setGravity(Gravity.CENTER)
        submit_tv.setPadding(dp(16), dp(14), dp(16), dp(14))
        submit_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        try:
            submit_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        submit_btn.addView(submit_tv, FrameLayout.LayoutParams(-1, -2))
        submit_btn_ref[0] = submit_btn
        submit_tv_ref[0] = submit_tv

        def _set_submit_loading():
            try:
                submit_btn_ref[0].setEnabled(False)
                submit_btn_ref[0].setClickable(False)
                submit_btn_ref[0].removeAllViews()
                from org.telegram.ui.Components import CircularProgressDrawable
                btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                d = CircularProgressDrawable(btn_text_color)
                try:
                    d.size = float(dp(20))
                    d.thickness = float(dp(2))
                except Exception:
                    pass
                spinner = ImageView(act)
                spinner.setImageDrawable(d)
                spinner.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                spinner.setPadding(0, dp(14), 0, dp(14))
                submit_btn_ref[0].addView(spinner, FrameLayout.LayoutParams(-1, dp(20 + 28), Gravity.CENTER))
            except Exception as e:
                logx(f"reportDialog: _set_submit_loading error: {e}", False)
                try:
                    from android.widget import ProgressBar
                    submit_btn_ref[0].removeAllViews()
                    pb = ProgressBar(act)
                    pb.setIndeterminate(True)
                    submit_btn_ref[0].addView(pb, FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
                except Exception:
                    pass

        def _to_signed32(c):
            # ArgbEvaluator needs signed 32-bit java.lang.Integer
            from java.lang import Integer
            v = int(c)
            return Integer(v if v < 0x80000000 else v - 0x100000000)

        def _shake_error(view, normal_color, hint_color=None):
            # cancel previous anim (resets cooldown), then shake + recolor from current state
            try:
                from android.animation import AnimatorSet, ObjectAnimator, ArgbEvaluator, ValueAnimator, Animator
                from java import dynamic_proxy

                vid = id(view)

                # cancel previous without triggering cleanup yet
                prev = error_anim_ref.pop(vid, None)
                if prev is not None:
                    try:
                        prev.cancel()
                    except Exception:
                        pass

                err = _to_signed32(0xFFE53935)
                src = _to_signed32(normal_color)

                shake = ObjectAnimator.ofFloat(view, "translationX", 0.0, 14.0, -14.0, 10.0, -10.0, 6.0, -6.0, 0.0)
                shake.setDuration(333)

                animators = [shake]

                if hint_color is not None:
                    hint_src = _to_signed32(hint_color)

                    hint_to_red = ValueAnimator.ofObject(ArgbEvaluator(), hint_src, err)
                    hint_to_red.setDuration(100)

                    hint_back = ValueAnimator.ofObject(ArgbEvaluator(), err, hint_src)
                    hint_back.setDuration(400)
                    hint_back.setStartDelay(933)

                    class _HintToRed(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                        def onAnimationUpdate(self, a):
                            try:
                                view.setHintTextColor(int(a.getAnimatedValue()))
                            except Exception:
                                pass

                    class _HintBack(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                        def onAnimationUpdate(self, a):
                            try:
                                view.setHintTextColor(int(a.getAnimatedValue()))
                            except Exception:
                                pass

                    hint_to_red.addUpdateListener(_HintToRed())
                    hint_back.addUpdateListener(_HintBack())
                    animators += [hint_to_red, hint_back]
                else:
                    color_to_red = ObjectAnimator.ofObject(view, "textColor", ArgbEvaluator(), src, err)
                    color_to_red.setDuration(100)

                    color_back = ObjectAnimator.ofObject(view, "textColor", ArgbEvaluator(), err, src)
                    color_back.setDuration(400)
                    color_back.setStartDelay(933)

                    animators += [color_to_red, color_back]

                s = AnimatorSet()
                s.playTogether(animators)

                class _EndCb(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        error_anim_ref.pop(vid, None)
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                s.addListener(_EndCb())
                error_anim_ref[vid] = s
                s.start()
            except Exception as e:
                logx(f"reportDialog: _shake_error error: {e}", False)

        def _on_submit(v):
            reason = selected_reason[0]
            description = str(input_field.getText()).strip()
            logx(f"reportDialog: submit clicked reason={reason!r} description={description!r}", True)
            try:
                if input_field_ref[0] is not None:
                    AndroidUtilities.hideKeyboard(input_field_ref[0])
            except Exception:
                pass

            has_reason = bool(reason)
            has_description = bool(description)
            if not has_reason or not has_description:
                if not has_reason and header_tv_ref[0] is not None:
                    _shake_error(header_tv_ref[0], gray_color)
                if not has_description and input_field_ref[0] is not None:
                    hint_c = Theme.getColor(Theme.key_windowBackgroundWhiteHintText)
                    _shake_error(input_field_ref[0], text_color, hint_color=hint_c)
                return

            if forum_username and topic_msg_id:
                _set_submit_loading()
                _submit_report(forum_username, topic_msg_id, plugin_name, plugin_id, repo_id, reason or "", description, act, _dismiss)
            else:
                logx("reportDialog: no forum settings found, skipping report send", True)
                _dismiss()

        submit_btn.setOnClickListener(OnClickListener(_on_submit))
        card.addView(submit_btn, LayoutHelper.createLinear(-1, -2))

        overlay.setAlpha(0.0)
        card.setAlpha(0.0)
        card.setScaleX(0.92)
        card.setScaleY(0.92)

        try:
            from .viewUtils import applyFontToTree
            applyFontToTree(card)
        except Exception:
            pass

        try:
            title_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass

        decor.addView(overlay, ViewGroup.LayoutParams(-1, -1))
        back_cb_ref[0] = _register_back_cb(act, _dismiss)
        run_on_ui_thread(lambda: _animate_in(overlay, card))
    except Exception as e:
        logx(f"reportDialog: show_report_dialog error: {e}", False)
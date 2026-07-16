# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from java import dynamic_proxy
from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment, run_on_queue
from hook_utils import find_class as _fc
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import elyx strings failed: {e}")
try:
    from android.widget import FrameLayout, LinearLayout, TextView, ImageView, ScrollView
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import android.widget failed: {e}")
try:
    from android.view import View, Gravity
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import android.view failed: {e}")
try:
    from android.util import TypedValue
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import android.util failed: {e}")
try:
    from android.graphics.drawable import GradientDrawable
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import android.graphics failed: {e}")
try:
    from android.net import Uri
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import android.net failed: {e}")
try:
    from android.content import Intent
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import android.content failed: {e}")
try:
    from org.telegram.ui.Components import BackupImageView, LayoutHelper, AvatarDrawable
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import org.telegram.ui.Components failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, UserConfig, MessagesController
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import org.telegram.messenger failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import org.telegram.ui.ActionBar failed: {e}")
try:
    from org.telegram.messenger.browser import Browser
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import org.telegram.messenger.browser failed: {e}")
try:
    from org.telegram.ui import LaunchActivity
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import org.telegram.ui LaunchActivity failed: {e}")
try:
    from org.telegram.ui.Gifts import GiftSheet
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import org.telegram.ui.Gifts GiftSheet failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    import android_utils as _au; _au.log(f"contributors fragment: import UniversalFragment failed: {e}")

# user ids
_UID_SHAREUI = 400216230
_UID_VESTR   = 2037728749
_UID_WATCHA  = 1061520526
_UID_APPLE   = 6018596876
_UID_PIXWET  = 5184725450

# special thanks user ids
_THANKS_UIDS = [
    7382225582,
    8756697462,
    5887975295,
    5266659018,
    5758928467,
]

# sponsors user ids
_SPONSORS_UIDS = [
    1602207467,
]


def _get_username(user):
    """Return the best available username for a user, including NFT/collectible ones.

    TL_username.editable=False means it's a collectible (NFT) username —
    user.username only holds editable ones, so we must check user.usernames list.
    Priority: first active entry in usernames list (covers both editable and NFT),
    fallback to plain user.username field.
    """
    try:
        usernames = getattr(user, 'usernames', None)
        if usernames is not None:
            try:
                size = usernames.size()
                for i in range(size):
                    entry = usernames.get(i)
                    active = getattr(entry, 'active', False)
                    uname = getattr(entry, 'username', None)
                    if active and uname:
                        return str(uname)
            except Exception:
                pass
    except Exception:
        pass
    # fallback to plain field
    try:
        un = getattr(user, 'username', None)
        if un:
            return str(un)
    except Exception:
        pass
    return ""


def _open_profile_by_user(user_id, username):
    """Open Telegram profile. Prefers t.me/username link (works for NFT usernames too),
    falls back to ProfileActivity by user_id if username is absent."""
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return
        if username:
            uri = Uri.parse("https://t.me/" + username)
            Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        else:
            # no username at all — open ProfileActivity directly by id
            try:
                from android.os import Bundle
                ProfileActivity = _fc("org.telegram.ui.ProfileActivity")
                args = Bundle()
                args.putLong("user_id", int(user_id))
                profile = ProfileActivity(args)
                frag.presentFragment(profile)
            except Exception as _fe:
                logx(f"contributors fragment: _open_profile_by_user ProfileActivity fallback error: {_fe}", True)
    except Exception as _e:
        logx(f"contributors fragment: _open_profile_by_user error: {_e}", True)


def _show_bulletin(icon_raw_name, text, is_error=False):
    try:
        frag = get_last_fragment()
        if not frag:
            logx("contributors fragment: _show_bulletin: no fragment", True)
            return
        BulletinFactory = _fc("org.telegram.ui.Components.BulletinFactory")
        from org.telegram.messenger import R as R_tg
        container = frag.getParentActivity().getWindow().getDecorView()
        rp = frag.getResourceProvider()
        factory = BulletinFactory.of(container, rp)
        if is_error:
            factory.createErrorBulletin(str(text)).show()
        else:
            icon_raw = getattr(R_tg.raw, icon_raw_name, 0)
            factory.createSimpleBulletin(icon_raw, str(text)).show()
    except Exception as _e:
        logx(f"contributors fragment: _show_bulletin error: {_e}", True)


def _fetch_user(user_id, on_done):
    # fetch user by id via TL_users_getUsers; calls on_done(user) on ui thread
    def _do():
        try:
            from org.telegram.tgnet import TLRPC
            account = getattr(UserConfig, 'selectedAccount', 0)
            mc = MessagesController.getInstance(account)

            # try cache first
            cached = mc.getUser(user_id)
            if cached is not None and not getattr(cached, 'min', True):
                run_on_ui_thread(lambda: on_done(cached))
                return

            req = TLRPC.TL_users_getUsers()
            inp = TLRPC.TL_inputUser()
            inp.user_id = user_id
            inp.access_hash = 0
            req.id.add(inp)

            from client_utils import send_request
            def _on_resp(resp, err):
                if err or resp is None:
                    logx(f"contributors fragment: _fetch_user {user_id} error: {err}", True)
                    run_on_ui_thread(lambda: on_done(None))
                    return
                user = None
                try:
                    objects = resp.objects
                    if objects.size() > 0:
                        user = objects.get(0)
                        mc.putUser(user, False)
                except Exception as _e:
                    logx(f"contributors fragment: _fetch_user putUser error: {_e}", True)
                run_on_ui_thread(lambda: on_done(user))
            send_request(req, _on_resp)
        except Exception as _e:
            logx(f"contributors fragment: _fetch_user outer error: {_e}", True)
            run_on_ui_thread(lambda: on_done(None))
    run_on_queue(_do)


def _make_avatar_view(context, user_id, title_text):
    # builds header row; starts async user fetch for avatar + nickname
    try:
        dp = AndroidUtilities.dp

        container = FrameLayout(context)

        main_layout = LinearLayout(context)
        main_layout.setOrientation(LinearLayout.HORIZONTAL)
        main_layout.setGravity(Gravity.CENTER_VERTICAL)
        main_layout.setPadding(dp(20), dp(20), dp(20), dp(20))

        img = BackupImageView(context)
        img.setRoundRadius(dp(50))
        img.setClickable(True)
        main_layout.addView(img, LayoutHelper.createLinear(60, 60, Gravity.CENTER_VERTICAL, 0, 0, 16, 0))

        text_container = LinearLayout(context)
        text_container.setOrientation(LinearLayout.VERTICAL)
        text_container.setGravity(Gravity.CENTER_VERTICAL)

        title = TextView(context)
        title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        try:
            title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        title.setText(title_text)
        title.setSingleLine(True)
        title.setHorizontalFadingEdgeEnabled(True)
        title.setFadingEdgeLength(dp(24))
        text_container.addView(title, LayoutHelper.createLinear(-1, -2, 0, 0, 4, 0))

        nickname_tv = TextView(context)
        nickname_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        nickname_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        nickname_tv.setText(str(strings.sec_hash_loading))
        nickname_tv.setSingleLine(True)
        nickname_tv.setHorizontalFadingEdgeEnabled(True)
        nickname_tv.setFadingEdgeLength(dp(24))
        text_container.addView(nickname_tv, LayoutHelper.createLinear(-1, -2))

        main_layout.addView(text_container, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))
        container.addView(main_layout, LayoutHelper.createFrame(-1, -2, Gravity.CENTER))

        _username_holder = [None]

        def _open_profile(v):
            try:
                # scale-down animation on avatar
                try:
                    from android.animation import AnimatorSet, ObjectAnimator
                    scale_down_x = ObjectAnimator.ofFloat(img, "scaleX", 1.0, 0.82)
                    scale_down_y = ObjectAnimator.ofFloat(img, "scaleY", 1.0, 0.82)
                    scale_down_x.setDuration(120)
                    scale_down_y.setDuration(120)
                    scale_up_x = ObjectAnimator.ofFloat(img, "scaleX", 0.82, 1.0)
                    scale_up_y = ObjectAnimator.ofFloat(img, "scaleY", 0.82, 1.0)
                    scale_up_x.setDuration(120)
                    scale_up_y.setDuration(120)
                    down_set = AnimatorSet()
                    down_set.playTogether(scale_down_x, scale_down_y)
                    up_set = AnimatorSet()
                    up_set.playTogether(scale_up_x, scale_up_y)
                    full_set = AnimatorSet()
                    full_set.playSequentially(down_set, up_set)
                    full_set.start()
                except Exception as _ae:
                    logx(f"contributors fragment: avatar scale anim error: {_ae}", True)
                _open_profile_by_user(user_id, _username_holder[0])
            except Exception as _e:
                logx(f"contributors fragment: _open_profile (avatar) error: {_e}", True)

        img.setOnClickListener(OnClickListener(_open_profile))

        def _on_user(user):
            try:
                if user is None:
                    nickname_tv.setText("")
                    return
                # avatar
                try:
                    avatar_drawable = AvatarDrawable(user)
                    img.setForUserOrChat(user, avatar_drawable)
                except Exception as _e:
                    logx(f"contributors fragment: avatar set error: {_e}", True)
                # name: prefer first_name, fallback username (incl. NFT)
                username = _get_username(user)
                name = ""
                try:
                    fn = getattr(user, 'first_name', None)
                    if fn:
                        name = str(fn)
                except Exception:
                    pass
                if not name and username:
                    name = "@" + username
                _username_holder[0] = username
                nickname_tv.setText(name)
            except Exception as _e:
                logx(f"contributors fragment: _on_user error: {_e}", True)

        _fetch_user(user_id, _on_user)

        return container
    except Exception as _e:
        logx(f"contributors fragment: _make_avatar_view error: {_e}", True)
        return None


def _make_thanks_row(context, user_id):
    # compact row: small avatar + nickname; fetches user async; opens profile on click
    try:
        dp = AndroidUtilities.dp

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(dp(16), dp(8), dp(16), dp(8))
        row.setMinimumHeight(dp(44))
        row.setClickable(True)
        row.setFocusable(True)

        try:
            selector = Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2)
            row.setBackground(selector)
        except Exception as _se:
            logx(f"contributors fragment: thanks row selector error: {_se}", True)

        img = BackupImageView(context)
        img.setRoundRadius(dp(50))
        row.addView(img, LayoutHelper.createLinear(30, 30, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

        name_tv = TextView(context)
        name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            name_tv.setTypeface(AndroidUtilities.bold())
        name_tv.setText(str(strings.sec_hash_loading))
        name_tv.setSingleLine(True)
        name_tv.setHorizontalFadingEdgeEnabled(True)
        name_tv.setFadingEdgeLength(dp(24))
        row.addView(name_tv, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_VERTICAL))

        _username_holder = [None]  # mutable closure slot

        def _open_profile(v):
            try:
                _open_profile_by_user(user_id, _username_holder[0])
            except Exception as _e:
                logx(f"contributors fragment: _open_profile error: {_e}", True)

        row.setOnClickListener(OnClickListener(_open_profile))

        def _on_user(user):
            try:
                if user is None:
                    try:
                        row.setVisibility(View.GONE)
                    except Exception:
                        pass
                    return
                try:
                    avatar_drawable = AvatarDrawable(user)
                    img.setForUserOrChat(user, avatar_drawable)
                except Exception as _e:
                    logx(f"contributors fragment: thanks avatar error: {_e}", True)
                username = _get_username(user)
                name = ""
                try:
                    fn = getattr(user, 'first_name', None)
                    if fn:
                        name = str(fn)
                except Exception:
                    pass
                if not name and username:
                    name = "@" + username
                _username_holder[0] = username
                name_tv.setText(name)
            except Exception as _e:
                logx(f"contributors fragment: _thanks on_user error: {_e}", True)

        _fetch_user(user_id, _on_user)
        return row
    except Exception as _e:
        logx(f"contributors fragment: _make_thanks_row error: {_e}", True)
        return None


def _build_special_thanks_card(act, content, animate_idx=0):
    try:
        dp = AndroidUtilities.dp

        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        try:
            card.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                dp(18),
                Theme.getColor(Theme.key_windowBackgroundWhite),
                Theme.getColor(Theme.key_windowBackgroundWhite)
            ))
        except Exception:
            try:
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadius(dp(18))
                bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
                card.setBackground(bg)
            except Exception:
                pass

        # card title — same style as role label in contributor header
        title_tv = TextView(act)
        title_tv.setText(str(strings.special_thanks))
        title_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        title_tv.setPadding(dp(20), dp(20), dp(20), dp(12))
        card.addView(title_tv, LinearLayout.LayoutParams(-1, -2))

        sep = View(act)
        sep.setBackgroundColor(Theme.getColor(Theme.key_divider))
        sep_lp = LinearLayout.LayoutParams(-1, dp(1))
        sep_lp.setMargins(dp(16), 0, dp(16), 0)
        card.addView(sep, sep_lp)

        for uid in _THANKS_UIDS:
            row = _make_thanks_row(act, uid)
            if row is not None:
                card.addView(row, LinearLayout.LayoutParams(-1, -2))

        card.setPadding(0, 0, 0, dp(8))
        card_lp = LinearLayout.LayoutParams(-1, -2)
        card_lp.setMargins(dp(8), dp(4), dp(8), dp(8))
        try:
            card.setAlpha(0.0)
        except Exception:
            pass
        content.addView(card, card_lp)
        try:
            card.animate().alpha(1.0).setDuration(180).start()
        except Exception:
            pass
    except Exception as _e:
        logx(f"contributors fragment: _build_special_thanks_card error: {_e}", True)


def _build_sponsors_card(act, content, animate_idx=0):
    try:
        dp = AndroidUtilities.dp

        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        try:
            card.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                dp(18),
                Theme.getColor(Theme.key_windowBackgroundWhite),
                Theme.getColor(Theme.key_windowBackgroundWhite)
            ))
        except Exception:
            try:
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadius(dp(18))
                bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
                card.setBackground(bg)
            except Exception:
                pass

        title_tv = TextView(act)
        title_tv.setText(str(strings.sponsors))
        title_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        title_tv.setPadding(dp(20), dp(20), dp(20), dp(12))
        card.addView(title_tv, LinearLayout.LayoutParams(-1, -2))

        sep = View(act)
        sep.setBackgroundColor(Theme.getColor(Theme.key_divider))
        sep_lp = LinearLayout.LayoutParams(-1, dp(1))
        sep_lp.setMargins(dp(16), 0, dp(16), 0)
        card.addView(sep, sep_lp)

        for uid in _SPONSORS_UIDS:
            row = _make_thanks_row(act, uid)
            if row is not None:
                card.addView(row, LinearLayout.LayoutParams(-1, -2))

        card.setPadding(0, 0, 0, dp(8))
        card_lp = LinearLayout.LayoutParams(-1, -2)
        card_lp.setMargins(dp(8), dp(4), dp(8), dp(8))
        try:
            card.setAlpha(0.0)
        except Exception:
            pass
        content.addView(card, card_lp)
        try:
            card.animate().alpha(1.0).setDuration(180).start()
        except Exception:
            pass
    except Exception as _e:
        logx(f"contributors fragment: _build_sponsors_card error: {_e}", True)


def _make_link_row(context, icon_name, label_text, link_text, on_click):
    try:
        from org.telegram.messenger import R as R_tg
        from androidx.core.content import ContextCompat
        dp = AndroidUtilities.dp

        row = LinearLayout(context)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        row.setPadding(dp(20), dp(10), dp(16), dp(10))
        row.setMinimumHeight(dp(50))
        row.setClickable(True)
        row.setOnClickListener(OnClickListener(on_click))

        try:
            selector = Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2)
            row.setBackground(selector)
        except Exception:
            pass

        icon_view = ImageView(context)
        icon_view.setScaleType(ImageView.ScaleType.CENTER)
        try:
            res_id = getattr(R_tg.drawable, icon_name)
            drawable = ContextCompat.getDrawable(context, res_id)
            if drawable is not None:
                drawable.setTint(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
                icon_view.setImageDrawable(drawable)
        except Exception:
            pass
        row.addView(icon_view, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 0, 0, 24, 0))

        label = TextView(context)
        label.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        label.setText(label_text)
        label.setSingleLine(True)
        label.setHorizontalFadingEdgeEnabled(True)
        label.setFadingEdgeLength(AndroidUtilities.dp(24))
        row.addView(label, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        link = TextView(context)
        link.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteValueText))
        link.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        link.setText(link_text)
        link.setSingleLine(True)
        try:
            link.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        row.addView(link, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

        return row
    except Exception as e:
        logx(f"contributors fragment: _make_link_row error: {e}", False)
        return None


class _ContributorsDelegate(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):
    def __init__(self):
        super().__init__()
        self._root_view = None

    def onFragmentCreate(self, *_):
        pass

    def onFragmentDestroy(self, *_):
        try:
            if self._root_view is not None:
                parent = self._root_view.getParent()
                if parent is not None:
                    parent.removeView(self._root_view)
                self._root_view = None
        except Exception as e:
            logx(f"contributors fragment: onFragmentDestroy error: {e}", False)

    def beforeCreateView(self):
        try:
            if self._root_view is not None:
                parent = self._root_view.getParent()
                if parent is not None:
                    parent.removeView(self._root_view)
                self._root_view = None
        except Exception as e:
            logx(f"contributors fragment: beforeCreateView cleanup error: {e}", False)

        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return None

        try:
            root = FrameLayout(act)
            root.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))

            scroll = ScrollView(act)
            scroll.setVerticalScrollBarEnabled(False)
            try:
                scroll.setFillViewport(True)
            except Exception:
                pass

            content = LinearLayout(act)
            content.setOrientation(LinearLayout.VERTICAL)
            content.setPadding(0, AndroidUtilities.dp(8), 0, AndroidUtilities.dp(24))

            scroll.addView(content, ScrollView.LayoutParams(-1, -2))
            root.addView(scroll, FrameLayout.LayoutParams(-1, -1))
            self._root_view = root

            # schedule lazy card build after view is attached
            self._schedule_lazy_build(act, content)

            return root
        except Exception as e:
            logx(f"contributors fragment: beforeCreateView error: {e}", False)
            return None

    def _schedule_lazy_build(self, act, content):
        # collect card builder functions in order
        builders = [
            lambda: self._build_contributor_block(
                act, content,
                user_id=_UID_SHAREUI,
                title_text=str(strings.founder_shareui),
                links=[
                    {"icon": "msg_link", "label": str(strings.github), "text": "github.com/shareui", "on_click": lambda v: self._open_url("https://github.com/shareui")},
                    {"icon": "msg_message", "label": str(strings.direct_message), "text": "t.me/shareui", "on_click": lambda v: self._open_url("https://t.me/shareui")},
                    {"icon": "msg_channel", "label": str(strings.plugins_channel), "text": "t.me/doctashare", "on_click": lambda v: self._open_url("https://t.me/doctashare")},
                ],
                donations=[
                    {"text": strings.support_via_send, "icon": "filled_paid_suggest_24", "on_click": lambda v: (_show_bulletin("info", strings.donate_easter_egg), run_on_ui_thread(lambda: self._open_url("https://t.me/send?start=IV7kTHbP2iXp"), 1000))},
                    {"text": strings.support_via_ton, "icon": "menu_wallet", "on_click": lambda v: (_show_bulletin("copy", strings.copied_to_clipboard) if AndroidUtilities.addToClipboard("UQADRm0R1HNgMYuTfbHB3kdENuWt_Et5dFlEtrILK3LQ-KKL") else _show_bulletin("", strings.failed_to_copy, is_error=True))},
                ],
                animate_idx=0,
            ),
            lambda: self._build_contributor_block(
                act, content,
                user_id=_UID_VESTR,
                title_text=str(strings.lead_developer_vestr),
                links=[
                    {"icon": "msg_link", "label": str(strings.github), "text": "github.com/mr-vestr", "on_click": lambda v: self._open_url("https://github.com/mr-vestr")},
                    {"icon": "msg_message", "label": str(strings.direct_message), "text": "t.me/mr_Vestr", "on_click": lambda v: self._open_vestr_direct_message()},
                    {"icon": "msg_channel", "label": str(strings.plugins_channel), "text": "t.me/I_am_Vestr", "on_click": lambda v: self._open_url("https://t.me/I_am_Vestr")},
                ],
                donations=[
                    {"text": strings.support_with_stars, "icon": "menu_feature_reactions", "on_click": lambda v: self._open_gift_sheet_vestr()},
                ],
                animate_idx=1,
            ),
            lambda: self._build_contributor_block(
                act, content,
                user_id=_UID_WATCHA,
                title_text=str(strings["developer"]),
                links=[
                    {"icon": "msg_link", "label": str(strings.github), "text": "github.com/homewatcha", "on_click": lambda v: self._open_url("https://github.com/homewatcha")},
                    {"icon": "msg_message", "label": str(strings.direct_message), "text": "t.me/homewatcha", "on_click": lambda v: self._open_url("https://t.me/homewatcha")},
                    {"icon": "msg_channel", "label": str(strings.personal_channel), "text": "t.me/watchashitposts", "on_click": lambda v: self._open_url("https://t.me/watchashitposts")},
                ],
                donations=[],
                animate_idx=2,
            ),
            lambda: self._build_contributor_block(
                act, content,
                user_id=_UID_APPLE,
                title_text=str(strings["developer"]),
                links=[
                    {"icon": "msg_link", "label": str(strings.github), "text": "github.com/ageekapple", "on_click": lambda v: self._open_url("https://github.com/ageekapple")},
                    {"icon": "msg_message", "label": str(strings.direct_message), "text": "t.me/AGeekApple", "on_click": lambda v: self._open_url("https://t.me/AGeekApple")},
                    {"icon": "msg_channel", "label": str(strings.personal_channel), "text": "t.me/ApplePlugins", "on_click": lambda v: self._open_url("https://t.me/ApplePlugins")},
                    {"icon": "msg_channel", "label": str(strings.plugins_channel), "text": "t.me/TheDotted", "on_click": lambda v: self._open_url("https://t.me/TheDotted")},
                ],
                donations=[
                    {"text": strings.support_via_send, "icon": "filled_paid_suggest_24", "on_click": lambda v: (_show_bulletin("info", strings.donate_easter_egg), run_on_ui_thread(lambda: self._open_url("https://t.me/send?start=IVvAJkUxMF6Up"), 1000))},
                    {"text": strings.support_with_github_sponsors, "icon": "msg_link", "on_click": lambda v: (_show_bulletin("info", strings.donate_easter_egg), run_on_ui_thread(lambda: self._open_url("https://github.com/sponsors/ageekapple"), 1000))},                    
                ],
                animate_idx=3,
            ),
            lambda: self._build_contributor_block(
                act, content,
                user_id=_UID_PIXWET,
                title_text=str(strings.mentor),
                links=[
                    {"icon": "msg_link", "label": str(strings.github), "text": "github.com/pixwet", "on_click": lambda v: self._open_url("https://github.com/pixwet")},
                    {"icon": "msg_message", "label": str(strings.direct_message), "text": "t.me/pixwet", "on_click": lambda v: self._open_url("https://t.me/pixwet")},
                    {"icon": "msg_channel", "label": str(strings.plugins_channel), "text": "t.me/CactusPlugins", "on_click": lambda v: self._open_url("https://t.me/CactusPlugins")},
                    {"icon": "msg_channel", "label": str(strings.personal_channel), "text": "t.me/exteraFeatures", "on_click": lambda v: self._open_url("https://t.me/exteraFeatures")},
                ],
                donations=[
                    {"text": strings.support_via_send, "icon": "filled_paid_suggest_24", "on_click": lambda v: (_show_bulletin("info", strings.donate_easter_egg), run_on_ui_thread(lambda: self._open_url("https://t.me/send?start=IVwvWMdWfPCE"), 1000))},
                    {"text": strings.support_via_ton, "icon": "menu_wallet", "on_click": lambda v: (_show_bulletin("copy", strings.copied_to_clipboard) if AndroidUtilities.addToClipboard("UQBZCTLurgR5KiyvV5o8AchUQSsz-5o_mvehtuf08c8DuDMI") else _show_bulletin("", strings.failed_to_copy, is_error=True))},
                ],
                animate_idx=4,
            ),
            lambda: _build_special_thanks_card(act, content, animate_idx=5),
            lambda: _build_sponsors_card(act, content, animate_idx=6),
        ]

        def _post_builder(idx):
            if idx >= len(builders):
                return
            def _run():
                try:
                    builders[idx]()
                except Exception as _e:
                    logx(f"contributors fragment: lazy builder {idx} error: {_e}", True)
                # schedule next card
                _post_builder(idx + 1)
            run_on_ui_thread(_run, idx * 60)

        _post_builder(0)

    def afterCreateView(self, view):
        return view

    def getTitle(self):
        try:
            return str(strings.contributors)
        except Exception:
            return "Contributors"

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, item_id):
        if item_id == -1:
            try:
                frag = get_last_fragment()
                if frag:
                    frag.finishFragment()
            except Exception as e:
                logx(f"contributors fragment: finishFragment error: {e}", False)
            return True
        return False

    def onBackPressed(self):
        return False

    def _open_url(self, url):
        try:
            if url.startswith("https://t.me/"):
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if act:
                    uri = Uri.parse(url)
                    Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
            else:
                from org.telegram.messenger import ApplicationLoader
                context = ApplicationLoader.applicationContext
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse(url))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
        except Exception:
            _show_bulletin("", strings.failed_to_open_link, is_error=True)

    def _open_vestr_direct_message(self):
        try:
            from java.util import Locale
            current_lang = Locale.getDefault().getLanguage()
            if current_lang == "ru":
                url = "https://t.me/mr_vestr/?text=%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82%21+%D0%9F%D0%B8%D1%88%D1%83+%D0%BF%D0%BE+%D0%BF%D0%BE%D0%B2%D0%BE%D0%B4%D1%83+%D0%BF%D0%BB%D0%B0%D0%B3%D0%B8%D0%BD%D0%B0+%C2%ABPackit%C2%BB%3A%0D%0A"
            else:
                url = "https://t.me/mr_vestr/?text=Hello%21+I%27m+writing+regarding+the+%22Packit%22+plugin%3A%0D%0A"
            self._open_url(url)
        except Exception:
            self._open_url("https://t.me/mr_Vestr")

    def _open_gift_sheet_vestr(self):
        try:
            if not hasattr(LaunchActivity, 'instance') or LaunchActivity.instance is None:
                return
            launch_activity = LaunchActivity.instance
            getSafeLastFragment_method = launch_activity.getClass().getDeclaredMethod("getSafeLastFragment")
            getSafeLastFragment_method.setAccessible(True)
            last_fragment = getSafeLastFragment_method.invoke(launch_activity)
            if last_fragment is None or last_fragment.getContext() is None:
                return
            current_account = UserConfig.selectedAccount
            gift_sheet = GiftSheet(
                last_fragment.getContext(),
                current_account,
                _UID_VESTR,
                None,
                None
            )
            gift_sheet.show()
        except Exception:
            pass

    def _make_avatar_item(self, act, user_id, title_text):
        return _make_avatar_view(act, user_id, title_text)

    def _make_small_divider(self, act):
        try:
            divider = View(act)
            divider.setMinimumHeight(AndroidUtilities.dp(1))
            divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
            container = FrameLayout(act)
            params = FrameLayout.LayoutParams(-1, AndroidUtilities.dp(1))
            params.setMargins(AndroidUtilities.dp(68), AndroidUtilities.dp(4), AndroidUtilities.dp(16), 0)
            container.addView(divider, params)
            return container
        except Exception:
            return None

    def _make_link_item(self, act, icon_name, label_text, link_text, on_click):
        return _make_link_row(act, icon_name, label_text, link_text, on_click)

    def _make_donation_row(self, act, text, icon_name, on_click):
        try:
            from org.telegram.messenger import R as R_tg
            from androidx.core.content import ContextCompat
            dp = AndroidUtilities.dp

            row = LinearLayout(act)
            row.setOrientation(LinearLayout.HORIZONTAL)
            row.setGravity(Gravity.CENTER_VERTICAL)
            row.setPadding(dp(20), dp(12), dp(16), dp(12))
            row.setMinimumHeight(dp(50))
            row.setClickable(True)
            row.setOnClickListener(OnClickListener(on_click))

            try:
                selector = Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2)
                row.setBackground(selector)
            except Exception:
                pass

            icon_view = ImageView(act)
            icon_view.setScaleType(ImageView.ScaleType.CENTER)
            try:
                res_id = getattr(R_tg.drawable, icon_name)
                drawable = ContextCompat.getDrawable(act, res_id)
                if drawable is not None:
                    drawable.setTint(Theme.getColor(Theme.key_featuredStickers_addButton))
                    icon_view.setImageDrawable(drawable)
            except Exception:
                pass
            row.addView(icon_view, LayoutHelper.createLinear(24, 24, Gravity.CENTER_VERTICAL, 0, 0, 24, 0))

            label = TextView(act)
            label.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            label.setText(str(text))
            label.setSingleLine(True)
            row.addView(label, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            return row
        except Exception as e:
            logx(f"contributors fragment: _make_donation_row error: {e}", False)
            return None

    def _add_divider_line(self, content):
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if not act:
                return
            divider = View(act)
            divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
            content.addView(divider, LinearLayout.LayoutParams(-1, AndroidUtilities.dp(1)))
        except Exception:
            pass

    def _build_contributor_block(self, act, content, user_id, title_text, links, donations, animate_idx=0):
        dp = AndroidUtilities.dp

        # card container with rounded background
        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        try:
            card.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                dp(18),
                Theme.getColor(Theme.key_windowBackgroundWhite),
                Theme.getColor(Theme.key_windowBackgroundWhite)
            ))
        except Exception:
            try:
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadius(dp(18))
                bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
                card.setBackground(bg)
            except Exception:
                pass

        avatar_view = self._make_avatar_item(act, user_id, title_text)
        if avatar_view is not None:
            card.addView(avatar_view, LinearLayout.LayoutParams(-1, -2))
        else:
            header = TextView(act)
            header.setText(title_text)
            header.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            header.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
            header.setPadding(dp(20), dp(12), dp(20), dp(12))
            card.addView(header, LinearLayout.LayoutParams(-1, -2))

        if links or donations:
            # separator between header and links inside card
            sep = View(act)
            sep.setBackgroundColor(Theme.getColor(Theme.key_divider))
            sep_lp = LinearLayout.LayoutParams(-1, dp(1))
            sep_lp.setMargins(dp(16), 0, dp(16), 0)
            card.addView(sep, sep_lp)

        first_link = True
        for item in links:
            if not first_link:
                divider = self._make_small_divider(act)
                if divider is not None:
                    card.addView(divider, LinearLayout.LayoutParams(-1, -2))
            first_link = False
            row = self._make_link_item(act, item["icon"], item["label"], item["text"], item["on_click"])
            if row is not None:
                card.addView(row, LinearLayout.LayoutParams(-1, -2))

        for item in donations:
            row = self._make_donation_row(act, item["text"], item["icon"], item["on_click"])
            if row is not None:
                card.addView(row, LinearLayout.LayoutParams(-1, -2))

        card_lp = LinearLayout.LayoutParams(-1, -2)
        card_lp.setMargins(dp(8), dp(4), dp(8), dp(4))
        try:
            card.setAlpha(0.0)
        except Exception:
            pass
        content.addView(card, card_lp)
        try:
            card.animate().alpha(1.0).setDuration(180).start()
        except Exception:
            pass

def show_contributors_fragment():
    try:
        frag = get_last_fragment()
        if not frag:
            return
        delegate = _ContributorsDelegate()
        new_frag = UniversalFragment(delegate)
        frag.presentFragment(new_frag)
        try:
            new_frag.setTitle(str(strings.contributors), False, 0)
            action_bar = new_frag.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                try:
                    from org.telegram.messenger import R as R_tg
                    back_icon = getattr(R_tg.drawable, 'ic_ab_back', 0)
                    if back_icon:
                        action_bar.setBackButtonImage(back_icon)
                        action_bar.setBackButtonContentDescription("Back")
                        try:
                            back_button = action_bar.getBackButton()
                            if back_button:
                                def _on_back(v):
                                    f = get_last_fragment()
                                    if f:
                                        f.finishFragment()
                                back_button.setOnClickListener(OnClickListener(_on_back))
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception as e:
            logx(f"contributors fragment: actionbar setup error: {e}", False)
    except Exception as e:
        logx(f"contributors fragment: show_contributors_fragment error: {e}", False)

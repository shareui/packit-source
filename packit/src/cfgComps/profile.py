from ui.settings import Header, Text, Divider, Custom
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log
import time
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from ..other.achievements import get_all_with_progress, get_stats


def _get_greeting(first_name: str) -> str:
    t = time.localtime()
    h = t.tm_hour
    m = t.tm_min

    if 5 <= h < 7:
        key = "greeting_0500"
    elif h == 7 or (h == 8 and m < 30):
        key = "greeting_0700"
    elif (h == 8 and m >= 30) or h == 9:
        key = "greeting_0830"
    elif h == 10:
        key = "greeting_1000"
    elif h == 11:
        key = "greeting_1100"
    elif h == 12:
        key = "greeting_1200"
    elif h == 13:
        key = "greeting_1300"
    elif h == 14:
        key = "greeting_1400"
    elif h == 15:
        key = "greeting_1500"
    elif h == 16:
        key = "greeting_1600"
    elif h == 17:
        key = "greeting_1700"
    elif h == 18:
        key = "greeting_1800"
    elif h == 19:
        key = "greeting_1900"
    elif h == 20:
        key = "greeting_2000"
    elif h == 21:
        key = "greeting_2100"
    elif h == 22:
        key = "greeting_2200"
    elif h == 23 and m < 30:
        key = "greeting_2300"
    elif h == 23:
        key = "greeting_2330"
    elif 0 <= h < 2:
        key = "greeting_0000"
    else:
        key = "greeting_0200"

    try:
        return str(strings[key]).format(first_name=first_name)
    except Exception:
        return ""


def _make_profile_header(context):
    try:
        from android.widget import FrameLayout, LinearLayout, TextView
        from android.view import Gravity
        from android.util import TypedValue
        from org.telegram.messenger import AndroidUtilities, UserConfig, MessagesController
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import LayoutHelper, BackupImageView, AvatarDrawable

        container = FrameLayout(context)

        content = LinearLayout(context)
        content.setOrientation(LinearLayout.VERTICAL)

        user = None
        try:
            account = getattr(UserConfig, 'selectedAccount', 0)
            mc = MessagesController.getInstance(account)
            uc = UserConfig.getInstance(account)
            if mc and uc:
                user = mc.getUser(uc.getClientUserId())
        except Exception:
            pass

        if user:
            img = BackupImageView(context)
            img.setRoundRadius(AndroidUtilities.dp(40))
            avatar_drawable = AvatarDrawable(user)
            img.setForUserOrChat(user, avatar_drawable)
            content.addView(img, LayoutHelper.createLinear(100, 100, Gravity.CENTER_HORIZONTAL, 0, 24, 0, 16))

        title = TextView(context)
        title.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        title.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title.setTypeface(AndroidUtilities.getTypeface(AndroidUtilities.TYPEFACE_ROBOTO_MEDIUM))
        except Exception:
            pass
        first_name = str(user.first_name) if user and user.first_name else "User"
        first_name = first_name[0].upper() + first_name[1:] if first_name else "User"
        title.setText(strings("profile_title", first_name=first_name))
        title.setGravity(Gravity.CENTER)
        content.addView(title, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 16, 0, 16, 4))

        subtitle = TextView(context)
        subtitle.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        subtitle.setText(_get_greeting(first_name))
        subtitle.setGravity(Gravity.CENTER)
        content.addView(subtitle, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 24, 0, 24, 24))

        container.addView(content, LayoutHelper.createFrame(-1, -2, Gravity.CENTER))
        return container
    except Exception as e:
        log(f"profile._make_profile_header: error: {e}")
        return None


class ProfileSettings:
    def _get_act(self):
        frag = get_last_fragment()
        return frag.getParentActivity() if frag else None

    def _make_header_item(self):
        try:
            frag = get_last_fragment()
            ctx = frag.getParentActivity() if frag else None
            if not ctx:
                return None
            view = _make_profile_header(ctx)
            if view is None:
                return None
            item = Custom(view=view)
            try:
                item.setTransparent(True)
            except Exception:
                pass
            return item
        except Exception as e:
            log(f"profile._make_header_item: error: {e}")
            return None

    def _show_hint(self, achievement: dict):
        try:
            act = self._get_act()
            if not act:
                return
            builder = AlertDialogBuilder(act)
            builder.set_title(achievement["title"])
            builder.set_message(achievement["hint"])
            builder.set_positive_button(strings["ok_button"], lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"profile._show_hint: error: {e}")

    def _show_category(self, category: str, achievements: list):
        try:
            act = self._get_act()
            if not act:
                return

            labels = []
            for a in achievements:
                if a.get("secret") and not a.get("unlocked"):
                    labels.append("???")
                else:
                    progress = a["progress"]
                    goal = a["goal"]
                    completed = progress >= goal
                    if a.get("secret"):
                        status = "✅" if completed else ""
                        labels.append(f"{a['title']} {status}".rstrip())
                    else:
                        counter = f"[{goal}/{goal}]" if completed else f"[{progress}/{goal}]"
                        status = "✅" if completed else ""
                        labels.append(f"{counter} {a['title']} {status}".rstrip())

            def onItemClick(bld, which: int):
                bld.dismiss()
                a = achievements[which]
                if a.get("secret") and not a.get("unlocked"):
                    return
                self._show_hint(a)

            builder = AlertDialogBuilder(act)
            builder.set_title(category)
            builder.set_items(labels, onItemClick)
            builder.set_negative_button(strings["close_button"], lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"profile._show_category: error: {e}")

    def _show_achievements(self, view):
        try:
            act = self._get_act()
            if not act:
                return

            items = get_all_with_progress()

            categories = {}
            for a in items:
                cat = a["category"]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(a)

            cat_names = list(categories.keys())

            def onCategoryClick(bld, which: int):
                bld.dismiss()
                cat = cat_names[which]
                self._show_category(cat, categories[cat])

            builder = AlertDialogBuilder(act)
            builder.set_title(strings["profile_achievements"])
            builder.set_items(cat_names, onCategoryClick)
            builder.set_negative_button(strings["close_button"], lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"profile._show_achievements: error: {e}")

    def _show_export_not_ready(self, view):
        try:
            BulletinHelper.show_info(strings.not_ready_yet)
        except Exception as e:
            log(f"profile._show_export_not_ready: error: {e}")

    def _show_statistics(self, view):
        try:
            act = self._get_act()
            if not act:
                return

            s = get_stats()
            level, xp_a, xp_b = s["level_info"]

            try:
                from ..other.localConfig import days_since_install
                days = days_since_install()
            except Exception:
                days = 0

            if level >= 100:
                level_line = strings["stat_account_level_max"]
                xp_line = strings("stat_xp_total", xp_a=xp_a, xp_b=xp_b)
            else:
                level_line = strings("stat_account_level", level=level)
                xp_line = strings("stat_xp_to_next", xp_a=xp_a, xp_b=xp_b)

            lines = [
                level_line,
                xp_line,
                "",
                strings("stat_achievements", completed=s['completed'], total=s['total']),
                strings("stat_days_of_use", days=days),
                "",
                strings("stat_installed_plugins", count=s['installed_plugins']),
                strings("stat_repositories_added", count=s['repositories_added']),
                strings("stat_plugins_shared", count=s['plugins_shared']),
                strings("stat_plugins_downloaded", count=s['plugins_downloaded']),
                strings("stat_code_views", count=s['code_views']),
                strings("stat_reports_sent", count=s['reports_sent']),
                strings("stat_links_copied", count=s['links_copied']),
            ]

            builder = AlertDialogBuilder(act)
            builder.set_title(strings["profile_statistics"])
            builder.set_message("\n".join(lines))
            builder.set_positive_button(strings["ok_button"], lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"profile._show_statistics: error: {e}")

    def build(self):
        items = []

        header = self._make_header_item()
        if header is not None:
            items.append(header)

        items += [
            Text(
                text=strings["profile_achievements"],
                icon="msg_fave",
                on_click=self._show_achievements
            ),
            Text(
                text=strings["profile_statistics"],
                icon="msg_stats",
                on_click=self._show_statistics
            ),
            Text(
                text=strings["profile_export_db"],
                icon="files_storage",
                on_click=self._show_export_not_ready
            ),
            Divider(text=strings["profile_template_divider"]),
        ]

        return items

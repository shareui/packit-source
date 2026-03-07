from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from client_utils import get_last_fragment
from android_utils import log
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
from ..other.achievements import get_all_with_progress, get_stats


class ProfileSettings:
    def _get_act(self):
        frag = get_last_fragment()
        return frag.getParentActivity() if frag else None

    def _show_hint(self, achievement: dict):
        try:
            act = self._get_act()
            if not act:
                return
            builder = AlertDialogBuilder(act)
            builder.set_title(achievement["title"])
            builder.set_message(achievement["hint"])
            builder.set_positive_button("OK", lambda b, w: b.dismiss())
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
                        # no counter for secret achievements
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
            builder.set_negative_button("Close", lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"profile._show_category: error: {e}")

    def _show_achievements(self, view):
        try:
            act = self._get_act()
            if not act:
                return

            items = get_all_with_progress()

            # group by category preserving order
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
            builder.set_title("Achievements")
            builder.set_items(cat_names, onCategoryClick)
            builder.set_negative_button("Close", lambda b, w: b.dismiss())
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
                level_line = "Account level: 100"
                xp_line = f"Total points: {xp_a}/{xp_b}"
            else:
                level_line = f"Account level: {level}"
                xp_line = f"To the next level: {xp_a}/{xp_b} points"

            lines = [
                level_line,
                xp_line,
                "",
                f"Achievements: {s['completed']}/{s['total']}",
                f"Days of use: {days}",
                "",
                f"Installed plugins: {s['installed_plugins']}",
                f"Repositories added: {s['repositories_added']}",
                f"Plugins shared: {s['plugins_shared']}",
                f"Plugins downloaded: {s['plugins_downloaded']}",
                f"Code views: {s['code_views']}",
                f"Reports sent: {s['reports_sent']}",
                f"Links copied: {s['links_copied']}",
            ]

            builder = AlertDialogBuilder(act)
            builder.set_title("Statistics")
            builder.set_message("\n".join(lines))
            builder.set_positive_button("OK", lambda b, w: b.dismiss())
            builder.show()
        except Exception as e:
            log(f"profile._show_statistics: error: {e}")

    def build(self):
        return [
            Header(text="Profile"),
            Text(
                text="Achievements",
                icon="msg_fave",
                on_click=self._show_achievements
            ),
            Text(
                text="Statistics",
                icon="msg_stats",
                on_click=self._show_statistics
            ),
            Text(
                text="Export database",
                icon="files_storage",
                on_click=self._show_export_not_ready
            ),
            Divider(text="THIS IS AN INTERFACE TEMPLATE, A FULL UI WILL BE IMPLEMENTED LATER"),
        ]


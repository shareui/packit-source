from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import log, run_on_ui_thread, OnClickListener
from android.widget import LinearLayout, TextView, FrameLayout, ImageView, ScrollView
from android.util import TypedValue
from android.view import Gravity
from android.graphics.drawable import GradientDrawable
from android.text.method import LinkMovementMethod
from java import dynamic_proxy
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from hook_utils import find_class
try:
    from org.telegram.messenger import R as R_tg, ApplicationLoader
    from org.telegram.ui.ActionBar import Theme, BottomSheet
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
    from org.telegram.ui.Stories.recorder import ButtonWithCounterView
except Exception as e:
    import android_utils as _au; _au.log(f"repo deeplink: import tg classes failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.utils.text import LocaleUtils
except Exception as e:
    import android_utils as _au; _au.log(f"repo deeplink: import LocaleUtils failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from urllib.parse import urlparse, parse_qs
import requests
import json
import os

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")

# repo=add: required: link — optional: name, icon
_REPO_ADD_REQUIRED = {"link"}
_REPO_ADD_OPTIONAL = {"name", "icon"}
_REPO_ADD_ALL = _REPO_ADD_REQUIRED | _REPO_ADD_OPTIONAL


def _get_cache_dir() -> str:
    from ..utils.paths import getReposCacheDir
    return getReposCacheDir()


def handle(url, repoManager):
    try:
        if "repo=add" not in url:
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        argKeys = {k for k in query.keys() if k != "repo"}

        if not _REPO_ADD_REQUIRED.issubset(argKeys):
            BulletinHelper.show_error(strings.deeplink_too_few_args)
            return

        if not argKeys.issubset(_REPO_ADD_ALL):
            BulletinHelper.show_error(strings.deeplink_too_many_args)
            return

        name = query.get("name", [""])[0].strip()
        link = query.get("link", [""])[0].strip()
        icon = query.get("icon", [""])[0].strip()

        if not link:
            BulletinHelper.show_error(strings.repo_add_invalid)
            return

        repos = repoManager.getRepositories()
        if len(repos) >= 10:
            BulletinHelper.show_error(strings.repo_add_limit)
            return

        try:
            frag = get_last_fragment()
            container = frag.getParentActivity().getWindow().getDecorView()
            resourceProvider = frag.getResourceProvider()
            BulletinFactory.of(container, resourceProvider).createSimpleBulletin(
                R_tg.raw.camera_flip,
                strings.repo_add_fetching
            ).show()
        except Exception as e:
            log(f"repo deeplink: bulletin error: {e}")

        def fetch_task():
            repometa = None
            pluginCount = 0
            try:
                response = requests.get(link, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    repometa = data.get("repometa")

                    if repometa and repometa.get("rm_rid"):
                        try:
                            cache_dir = _get_cache_dir()
                            os.makedirs(cache_dir, exist_ok=True)
                            cache_path = os.path.join(cache_dir, f"{repometa['rm_rid']}.json")
                            with open(cache_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            log(f"repo deeplink: cache error: {e}")

                    repomap = data.get("repomap", {})
                    plugins_url = repomap.get("plugins") if repomap else None
                    if plugins_url:
                        try:
                            pr = requests.get(plugins_url, timeout=10)
                            if pr.status_code == 200:
                                pdata = pr.json()
                                plugins = pdata.get("plugins", [])
                                pluginCount = len(plugins) if isinstance(plugins, (list, dict)) else 0
                        except Exception as e:
                            log(f"repo deeplink: plugins count error: {e}")
                    else:
                        plugins = data.get("plugins", [])
                        if isinstance(plugins, (list, dict)):
                            pluginCount = len(plugins)
            except Exception as e:
                log(f"repo deeplink: fetch error: {e}")

            run_on_ui_thread(lambda: _show_confirm_sheet(repometa, pluginCount, name, link, icon, repoManager))

        run_on_queue(fetch_task)
    except Exception as e:
        log(f"repo deeplink: handle error: {e}")


def _show_confirm_sheet(repometa, pluginCount, name, link, icon, repoManager):
    try:
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return

        if not repometa or not repometa.get("rm_rid"):
            BulletinHelper.show_error(str(strings["dl_repo_no_metadata"]))
            return

        rm_url = str(repometa.get("rm_url") or link)
        rm_url_display = rm_url.removeprefix("https://").removeprefix("http://")
        rm_maintainer = str(repometa.get("rm_maintainer") or name)
        rm_icon = icon if icon else str(repometa.get("rm_icon") or "msg_folders")
        disclaimer_text = strings("repo_add_disclaimer", rm_url_display, rm_maintainer, pluginCount)

        sheet = BottomSheet(act, False, frag.getResourceProvider())
        sheet.fixNavigationBar()

        frame = FrameLayout(act)
        linear = LinearLayout(act)
        linear.setOrientation(LinearLayout.VERTICAL)
        frame.addView(linear)

        # icon centered
        try:
            icon_view = ImageView(act)
            icon_id = getattr(R_tg.drawable, rm_icon, 0)
            if not icon_id:
                icon_id = getattr(R_tg.drawable, "msg_folders", 0)
            if icon_id:
                icon_view.setImageResource(icon_id)
            icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
            linear.addView(icon_view, LayoutHelper.createLinear(48, 48, Gravity.CENTER_HORIZONTAL, 0, 20, 0, 0))
        except Exception as e:
            log(f"repo deeplink: icon error: {e}")

        # title
        title_tv = TextView(act)
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            title_tv.setTypeface(AndroidUtilities.bold())
        title_tv.setText(strings.repo_add_title)
        title_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
        linear.addView(title_tv, LayoutHelper.createFrame(-1, -2, 0, 21.0, 16.0, 21.0, 0.0))

        # disclaimer with accent links
        msg_tv = TextView(act)
        msg_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        try:
            msg_tv.setText(LocaleUtils.fullyFormatText(disclaimer_text))
            msg_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
            msg_tv.setMovementMethod(LinkMovementMethod.getInstance())
        except Exception:
            msg_tv.setText(disclaimer_text)
        msg_tv.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteGrayText))
        msg_tv.setLineSpacing(AndroidUtilities.dp(2), 1.0)
        linear.addView(msg_tv, LayoutHelper.createFrame(-1, -2, 0, 21.0, 12.0, 21.0, 0.0))

        # add button
        add_btn = ButtonWithCounterView(act, True, frag.getResourceProvider())
        add_btn.setRound()
        add_btn.setText(strings.repo_add_button, False)

        from android.view import View as _View
        class _AddClickSimple(dynamic_proxy(_View.OnClickListener)):
            def onClick(self, v):
                try:
                    rm_rid = repometa.get("rm_rid")
                    repo_name = repometa.get("rm_name") or name

                    currentRepos = repoManager.getRepositories()
                    for existing in currentRepos:
                        if existing.get("id") == rm_rid or existing.get("url") == link:
                            BulletinHelper.show_error(str(strings["dl_repo_already_added"]))
                            sheet.dismiss()
                            return

                    newRepo = {
                        "id": rm_rid,
                        "name": repo_name,
                        "url": link,
                        "enabled": True,
                        "collapsed": False,
                        "icon": icon if icon else "msg_folders"
                    }
                    currentRepos.append(newRepo)
                    repoManager.setRepositories(currentRepos)
                    BulletinHelper.show_success(strings.repo_add_success)
                    try:
                        from ..ui.AchievementsActivity.service.AchivementsEngine import increment_category
                        increment_category("Repositories")
                    except Exception as e:
                        log(f"repo deeplink: achievements increment error: {e}")
                except Exception as e:
                    log(f"repo deeplink: on_add error: {e}")
                sheet.dismiss()

        add_btn.setOnClickListener(_AddClickSimple())
        linear.addView(add_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 20.0, 16.0, 8.0))

        # close button
        close_btn = ButtonWithCounterView(act, False, frag.getResourceProvider())
        close_btn.setRound()
        close_btn.setNeutral()
        close_btn.setText(strings.close_button, False)

        class _CloseClick(dynamic_proxy(_View.OnClickListener)):
            def onClick(self, v):
                sheet.dismiss()

        close_btn.setOnClickListener(_CloseClick())
        linear.addView(close_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 0.0, 16.0, 0.0))

        scroll = ScrollView(act)
        scroll.addView(frame)
        sheet.setCustomView(scroll)
        sheet.show()
    except Exception as e:
        log(f"repo deeplink: _show_confirm_sheet error: {e}")

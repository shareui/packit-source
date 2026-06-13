# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Input, Divider, Switch, Text
try:
    from elyx import strings, settings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings, settings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
from ui.alert import AlertDialogBuilder
from .icons import IconSelector

from hook_utils import find_class
try:
    from org.telegram.messenger import R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import R as R_tg failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")


def _showAddRepoDialog(context, repoManager):
    try:
        from android.text import InputType
        from android.content import DialogInterface
        from android.view import View
        from android.widget import ScrollView, LinearLayout, TextView, FrameLayout, ImageView
        from android.view import Gravity
        from android.util import TypedValue
        from java import dynamic_proxy
        from org.telegram.ui.ActionBar import AlertDialog, Theme
        from org.telegram.ui.Components import EditTextBoldCursor, OutlineTextContainerView, RLottieImageView, LayoutHelper, CircularProgressDrawable
        from org.telegram.messenger import AndroidUtilities
        from client_utils import run_on_queue
        from android_utils import run_on_ui_thread, OnClickListener

        dp = AndroidUtilities.dp

        builder = AlertDialog.Builder(context)

        frameLayout = FrameLayout(context)
        builder.setView(frameLayout)

        scrollView = ScrollView(context)
        scrollView.setFillViewport(True)
        frameLayout.addView(scrollView, LayoutHelper.createFrame(-1, -1))

        linear = LinearLayout(context)
        linear.setOrientation(LinearLayout.VERTICAL)
        linear.setGravity(Gravity.CENTER_HORIZONTAL)
        scrollView.addView(linear, LayoutHelper.createFrame(-1, -2, Gravity.TOP))

        try:
            anim = RLottieImageView(context)
            anim.setAnimation(R_tg.raw.shared_link_enter, 100, 100)
            anim.playAnimation()
            linear.addView(anim, LayoutHelper.createLinear(100, 100, Gravity.CENTER_HORIZONTAL, 0, 16, 0, 0))
        except Exception as e:
            logx(f"repos: add repo dialog anim error: {e}", False)

        titleView = TextView(context)
        titleView.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        titleView.setGravity(Gravity.CENTER_HORIZONTAL)
        titleView.setTypeface(AndroidUtilities.bold())
        titleView.setText(str(strings.add_repository))
        linear.addView(titleView, LayoutHelper.createFrame(-2, -2, Gravity.CENTER_HORIZONTAL, 24, 8, 24, 0))

        outlineView = OutlineTextContainerView(context)
        outlineView.setText(str(strings.repo_url))
        outlineView.animateSelection(1, False)
        linear.addView(outlineView, LayoutHelper.createLinear(-1, -2, Gravity.CENTER_HORIZONTAL, 24, 24, 24, 16))

        inputField = EditTextBoldCursor(context)
        inputField.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        inputField.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        inputField.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText))
        inputField.setBackground(None)
        inputField.setSingleLine(True)
        inputField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI)
        inputField.setCursorColor(Theme.getColor(Theme.key_windowBackgroundWhiteInputFieldActivated))
        inputField.setCursorWidth(1.5)
        padding = dp(16)
        inputField.setPadding(padding, padding, padding, padding)
        outlineView.addView(inputField, LayoutHelper.createFrame(-1, -2))
        outlineView.attachEditText(inputField)

        class _FocusListener(dynamic_proxy(View.OnFocusChangeListener)):
            def onFocusChange(self, v, hasFocus):
                outlineView.animateSelection(1 if hasFocus else 0)

        inputField.setOnFocusChangeListener(_FocusListener())

        # button: LinearLayout with TextView inside, same pattern as installUi details button
        doneBtn = LinearLayout(context)
        doneBtn.setOrientation(LinearLayout.HORIZONTAL)
        doneBtn.setGravity(Gravity.CENTER)
        doneBtn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(6),
            Theme.getColor(Theme.key_featuredStickers_addButton),
            Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        ))
        doneBtn.setClickable(True)
        doneBtn.setFocusable(True)

        btnLabel = TextView(context)
        btnLabel.setText(str(strings.add_repository))
        btnLabel.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        btnLabel.setGravity(Gravity.CENTER)
        btnLabel.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        doneBtn.addView(btnLabel, LayoutHelper.createLinear(-2, -2, Gravity.CENTER))

        linear.addView(doneBtn, LayoutHelper.createFrame(-1, 44, Gravity.TOP, 30, 0, 30, 16))

        dialog = builder.create()

        def _setLoading(isLoading):
            try:
                doneBtn.setEnabled(not isLoading)
                doneBtn.removeAllViews()
                if isLoading:
                    color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                    spinnerDrawable = CircularProgressDrawable(color)
                    try:
                        spinnerDrawable.size = float(dp(20))
                        spinnerDrawable.thickness = float(dp(2))
                    except Exception:
                        pass
                    spinnerView = ImageView(context)
                    spinnerView.setImageDrawable(spinnerDrawable)
                    spinnerView.setScaleType(ImageView.ScaleType.CENTER)
                    doneBtn.addView(spinnerView, LayoutHelper.createLinear(20, 20, Gravity.CENTER))
                else:
                    doneBtn.addView(btnLabel, LayoutHelper.createLinear(-2, -2, Gravity.CENTER))
            except Exception as e:
                logx(f"repos: _setLoading error: {e}", False)

        def onAdd():
            url = str(inputField.getText()).strip()
            if not url:
                return
            AndroidUtilities.hideKeyboard(inputField)
            run_on_ui_thread(lambda: _setLoading(True))

            def task():
                repometa, reason = repoManager.addRepositoryWithUrl(url)

                def onDone():
                    dialog.dismiss()
                    if reason is not None:
                        try:
                            BulletinHelper.show_error(f"{strings.invalid_repository}: {reason}")
                        except Exception as e:
                            logx(f"repos: add repo error bulletin error: {e}", False)
                    else:
                        try:
                            frag = get_last_fragment()
                            container = frag.getParentActivity().getWindow().getDecorView()
                            resourceProvider = frag.getResourceProvider()
                            BulletinFactory.of(container, resourceProvider).createSimpleBulletin(
                                R_tg.raw.shared_link_enter,
                                str(strings.repository_added)
                            ).show()
                            if frag and hasattr(frag, "rebuildAllItems"):
                                frag.rebuildAllItems()
                        except Exception as e:
                            logx(f"repos: add repo success bulletin error: {e}", False)

                run_on_ui_thread(onDone)

            run_on_queue(task)

        doneBtn.setOnClickListener(OnClickListener(lambda v: onAdd()))

        class _DismissListener(dynamic_proxy(DialogInterface.OnDismissListener)):
            def onDismiss(self, d):
                AndroidUtilities.hideKeyboard(inputField)

        class _ShowListener(dynamic_proxy(DialogInterface.OnShowListener)):
            def onShow(self, d):
                inputField.requestFocus()
                AndroidUtilities.showKeyboard(inputField)

        dialog.setOnDismissListener(_DismissListener())
        dialog.setOnShowListener(_ShowListener())
        dialog.show()
    except Exception as e:
        logx(f"repos: _showAddRepoDialog error: {e}", False)


class RepositoriesSettings:
    def __init__(self, repoManager):
        self.repoManager = repoManager
    
    def build(self):
        repos = self.repoManager.getRepositories()

        if not repos:
            self.repoManager.addRepository(isFirst=True)
            repos = self.repoManager.getRepositories()
            try:
                fragment = get_last_fragment()
                if fragment and hasattr(fragment, "rebuildAllItems"):
                    fragment.rebuildAllItems()
            except Exception as e:
                logx(f"{e}", False)
        
        def add_new_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    BulletinHelper.show_error(strings.max_repositories_allowed)
                except Exception as e:
                    logx(f"{e}", False)
                return

            try:
                frag = get_last_fragment()
                ctx = frag.getParentActivity() if frag else None
                if not ctx:
                    return
                _showAddRepoDialog(ctx, self.repoManager)
            except Exception as e:
                logx(f"repos: add_new_repository error: {e}", False)
        
        def restore_default_repository(view):
            repos = self.repoManager.getRepositories()
            if len(repos) >= 10:
                try:
                    logx("Default repository restore failed: max limit reached (10)", True)
                    BulletinHelper.show_error(strings.max_repositories_allowed)
                except Exception as e:
                    logx(f"{e}", False)
                return
            
            self.repoManager.restoreDefaultRepository()
            try:
                BulletinHelper.show_success(strings.default_repo_restored)
            except Exception as e:
                logx(f"{e}", False)
        
        def reset_repositories(view):
            repos = self.repoManager.getRepositories()
            if len(repos) <= 1:
                try:
                    frag = get_last_fragment()
                    act = frag.getParentActivity() if frag else None
                    if not act:
                        return
                    
                    builder = AlertDialogBuilder(act)
                    builder.set_title(strings.easter_egg_title)
                    builder.set_message(strings.easter_egg_reset_message)
                    builder.set_positive_button(strings.close_button, lambda b, w: b.dismiss())
                    builder.show()
                except Exception as e:
                    logx(f"{e}", False)
                return
            
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return
                
                builder = AlertDialogBuilder(act)
                builder.set_title(strings.reset_repositories_title)
                builder.set_message(strings.reset_repositories_message)
                
                def on_yes(b, w):
                    self.repoManager.resetRepositories()
                    try:
                        frag = get_last_fragment()
                        container = frag.getParentActivity().getWindow().getDecorView()
                        resourceProvider = frag.getResourceProvider()
                        BulletinFactory.of(container, resourceProvider).createSimpleBulletin(R_tg.raw.group_pip_delete_icon, strings.repositories_reset).show()
                    except Exception as e:
                        logx(f"{e}", False)
                
                builder.set_positive_button(strings.reset_button, on_yes)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                try:
                    builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                except Exception as e:
                    logx(f"{e}", False)
                builder.show()
            except Exception as e:
                logx(f"{e}", False)
        
        def clear_all_except_first(view):
            repos = self.repoManager.getRepositories()
            if len(repos) <= 1:
                try:
                    frag = get_last_fragment()
                    act = frag.getParentActivity() if frag else None
                    if not act:
                        return
                    
                    builder = AlertDialogBuilder(act)
                    builder.set_title(strings.easter_egg_title)
                    builder.set_message(strings.easter_egg_clear_message)
                    builder.set_positive_button(strings.close_button, lambda b, w: b.dismiss())
                    builder.show()
                except Exception as e:
                    logx(f"{e}", False)
                return
            
            try:
                frag = get_last_fragment()
                act = frag.getParentActivity() if frag else None
                if not act:
                    return
                
                builder = AlertDialogBuilder(act)
                builder.set_title(strings.clear_all_title)
                builder.set_message(strings.clear_all_message)
                
                def on_yes(b, w):
                    self.repoManager.clearAllExceptFirst()
                    try:
                        frag = get_last_fragment()
                        container = frag.getParentActivity().getWindow().getDecorView()
                        resourceProvider = frag.getResourceProvider()
                        BulletinFactory.of(container, resourceProvider).createSimpleBulletin(R_tg.raw.utyan_cache, strings.repositories_cleared).show()
                    except Exception as e:
                        logx(f"{e}", False)
                
                builder.set_positive_button(strings.clear_button, on_yes)
                builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                try:
                    builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                except Exception as e:
                    logx(f"{e}", False)
                builder.show()
            except Exception as e:
                logx(f"{e}", False)
        
        def update_repositories(view):
            from client_utils import run_on_queue
            from android_utils import run_on_ui_thread
            import requests
            import json
            import os
            try:
                from org.telegram.messenger import ApplicationLoader
            except Exception as e:
                import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
                from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()

            def task():
                try:
                    repos = self.repoManager.getRepositories()
                    from ..utils.paths import getReposCacheDir
                    cache_dir = getReposCacheDir()
                    os.makedirs(cache_dir, exist_ok=True)
                    changed = False
                    to_remove = []
                    seen_rids = set()

                    for i, repo in enumerate(repos):
                        url = (repo.get("url") or "").strip()
                        if not url:
                            continue
                        try:
                            r = requests.get(url, timeout=10)
                            if r.status_code != 200:
                                logx(f"update_repositories: HTTP {r.status_code} for {url}", True)
                                continue
                            data = r.json()
                            repometa = data.get("repometa")
                            rm_rid = repometa.get("rm_rid") if repometa else None

                            if not repometa or not rm_rid:
                                logx(f"update_repositories: no repometa for '{url}', removing repo", True)
                                to_remove.append(i)
                                changed = True
                                continue

                            if rm_rid in seen_rids:
                                logx(f"update_repositories: duplicate rm_rid='{rm_rid}', removing repo", True)
                                to_remove.append(i)
                                changed = True
                                continue
                            seen_rids.add(rm_rid)

                            if repo.get("id") != rm_rid:
                                repos[i]["id"] = rm_rid
                                changed = True
                                logx(f"update_repositories: set id='{rm_rid}' for repo '{repo.get('name')}'", True)

                            cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
                            with open(cache_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                            logx(f"update_repositories: updated cache for '{rm_rid}'", True)
                        except Exception as e:
                            logx(f"update_repositories: error for {url}: {e}", False)

                    for i in sorted(to_remove, reverse=True):
                        repos.pop(i)

                    if changed:
                        self.repoManager.setRepositories(repos)

                    run_on_ui_thread(lambda: BulletinHelper.show_success(strings.update_repos_success))
                except Exception as e:
                    logx(f"update_repositories: task error: {e}", False)

            run_on_queue(task)

        isActionsCollapsed = settings.get("actions_collapsed", True)
        actionsCollapseIcon = "msg_go_up" if not isActionsCollapsed else "arrow_more_solar"

        def toggle_actions_collapsed(view):
            current = settings.get("actions_collapsed", True)
            settings.set("actions_collapsed", not current, reload_settings=True)

        def export_repositories(view):
            repos = self.repoManager.getRepositories()
            links = []
            for repo in repos:
                name = repo.get('name', '').strip()
                url = repo.get('url', '').strip()
                icon = repo.get('icon', '').strip()
                if not url:
                    continue
                links.append(f"tg://packit?repo=add&name={name}&link={url}&icon={icon}")

            if not links:
                BulletinHelper.show_error(strings.no_repositories_to_export)
                return

            share_text = "\n\n".join(links)

            try:
                from java import jclass, dynamic_proxy
                from hook_utils import find_class
                from android_utils import run_on_ui_thread

                frag = get_last_fragment()
                if not frag:
                    return
                act = frag.getParentActivity()
                if not act:
                    return

                ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")
                _fragment = frag

                class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                    def __init__(self):
                        super().__init__()

                    def didShare(self):
                        def _show_bulletin():
                            try:
                                from org.telegram.messenger import R as R_tg
                                BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                                container = _fragment.getParentActivity().getWindow().getDecorView()
                                rp = _fragment.getResourceProvider()
                                BulletinFactory.of(container, rp).createSimpleBulletin(R_tg.raw.voip_invite, strings.repositories_exported).show()
                            except Exception as _be:
                                logx(f"repos.export_repositories.ShareDelegate.didShare: {_be}", True)
                        run_on_ui_thread(_show_bulletin)

                    def didCopy(self):
                        return False

                share_alert = ShareAlert(
                    act,
                    None,
                    share_text,
                    True,
                    share_text,
                    False
                )
                share_alert.setDelegate(ShareDelegate())
                frag.showDialog(share_alert)
            except Exception as e:
                logx(f"Export failed: {e}", False)
                BulletinHelper.show_error(strings.failed_to_copy)

        def toggle_all_repositories(view):
            repos = self.repoManager.getRepositories()
            anyEnabled = any(r.get('enabled', True) for r in repos)
            for repo in repos:
                repo['enabled'] = not anyEnabled
            self.repoManager.setRepositories(repos)

        anyEnabled = any(r.get('enabled', True) for r in repos)
        toggleAllText = strings.disable_all_repositories if anyEnabled else strings.enable_all_repositories

        actionItems = [
            Text(
                text=strings.update_repositories,
                icon="msg_retry",
                on_click=update_repositories,
                link_alias="update_repos"
            ),
            Text(
                text=strings.export_repositories,
                icon="msg_share",
                on_click=export_repositories,
                link_alias="export_repos"
            ),
            Text(
                text=toggleAllText,
                icon="msg_customize",
                on_click=toggle_all_repositories,
                link_alias="toggle_all_repos"
            ),
            Text(
                text=strings.restore_default_repository,
                icon="msg_reset",
                on_click=restore_default_repository,
                link_alias="restore_repo"
            ),
            Text(
                text=strings.clear_all_except_first,
                icon="msg_clear",
                red=True,
                on_click=clear_all_except_first,
                link_alias="clear_all"
            ),
            Text(
                text=strings.reset_repositories,
                icon="msg_delete",
                red=True,
                on_click=reset_repositories,
                link_alias="reset_repo"
            ),
        ]

        settingsList = [
            Header(text=strings.repositories),
            Text(
                text=strings.add_repository,
                icon="msg_add",
                accent=True,
                on_click=add_new_repository,
                link_alias="new_repo"
            ),
            Text(
                text=strings.additional_actions,
                icon=actionsCollapseIcon,
                accent=True,
                on_click=toggle_actions_collapsed
            ),
            *(actionItems if not isActionsCollapsed else []),
            Divider()
        ]
        
        def makeOnChange(field, i):
            return lambda value: self.repoManager.updateRepoField(i, field, value)
        
        def makeOnRemove(i):
            def show_confirm_dialog(view):
                try:
                    frag = get_last_fragment()
                    act = frag.getParentActivity() if frag else None
                    if not act:
                        return
                    
                    builder = AlertDialogBuilder(act)
                    builder.set_title(strings.delete_repository_title)
                    builder.set_message(strings.delete_repository_message)
                    
                    def on_yes(b, w):
                        self.repoManager.removeRepository(i)
                    
                    builder.set_positive_button(strings.delete_button, on_yes)
                    builder.set_negative_button(strings.close_button, lambda b, w: b.dismiss())
                    try:
                        builder.make_button_red(AlertDialogBuilder.BUTTON_POSITIVE)
                    except Exception as e:
                        logx(f"{e}", False)
                    builder.show()
                except Exception as e:
                    logx(f"{e}", False)
                    self.repoManager.removeRepository(i)
            
            return show_confirm_dialog
        
        def makeOnShare(i):
            def share_repository(view):
                current_repos = self.repoManager.getRepositories()
                if i >= len(current_repos):
                    BulletinHelper.show_error(strings.failed_to_copy)
                    return
                repo = current_repos[i]
                name = repo.get('name', '').strip()
                url = repo.get('url', '').strip()
                icon = repo.get('icon', '').strip()

                share_url = f"tg://packit?repo=add&name={name}&link={url}&icon={icon}"

                try:
                    from java import jclass, dynamic_proxy
                    from android_utils import run_on_ui_thread

                    frag = get_last_fragment()
                    if not frag:
                        return
                    act = frag.getParentActivity()
                    if not act:
                        return

                    ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                    ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")
                    _fragment = frag

                    class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                        def __init__(self):
                            super().__init__()

                        def didShare(self):
                            def _show_bulletin():
                                try:
                                    from org.telegram.messenger import R as R_tg
                                    BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                                    container = _fragment.getParentActivity().getWindow().getDecorView()
                                    rp = _fragment.getResourceProvider()
                                    BulletinFactory.of(container, rp).createSimpleBulletin(R_tg.raw.voip_invite, strings.repo_link_copied).show()
                                except Exception as _be:
                                    logx(f"repos.ShareDelegate.didShare: {_be}", True)
                            run_on_ui_thread(_show_bulletin)

                        def didCopy(self):
                            return False

                    share_alert = ShareAlert(
                        act,
                        None,
                        share_url,
                        True,
                        share_url,
                        False
                    )
                    share_alert.setDelegate(ShareDelegate())
                    frag.showDialog(share_alert)
                except Exception as e:
                    logx(f"Share failed: {e}", False)
                    BulletinHelper.show_error(strings.failed_to_copy)
            
            return share_repository
        
        def makeOnToggleCollapse(i):
            def toggle(view):
                repos = self.repoManager.getRepositories()
                if i < len(repos):
                    repos[i]['collapsed'] = not repos[i].get('collapsed', False)
                    self.repoManager.setRepositories(repos)
            return toggle
        
        def makeOnSelectIcon(i):
            def open_icon_selector():
                def on_icon_selected(icon_name):
                    self.repoManager.updateRepoField(i, 'icon', icon_name)
                
                icon_selector = IconSelector(self.repoManager, on_icon_selected)
                settings_list = icon_selector.build()
                return settings_list
            
            return open_icon_selector
        
        for idx, repo in enumerate(repos):
            isCollapsed = repo.get("collapsed", False)
            isEnabled = repo.get("enabled", True)
            collapseIcon = "msg_go_up" if not isCollapsed else "arrow_more_solar"
            headerText = strings.repository_form.format(idx + 1)
            settingsList.append(Text(
                text=headerText,
                icon=collapseIcon,
                accent=isEnabled,
                on_click=makeOnToggleCollapse(idx)
            ))
            
            if not isCollapsed:
                current_icon = repo.get('icon', '')
                icon_text = strings.repo_icon_text.format(current_icon) if current_icon else strings.repo_icon_not_selected
                key_suffix = repo['id'] if repo.get('id') else f"idx_{idx}"
                settingsList.extend([
                    Switch(
                        key=f"repo_enabled_{key_suffix}",
                        text=strings.repo_enabled,
                        default=repo.get("enabled", True),
                        icon="msg_customize",
                        on_change=makeOnChange("enabled", idx)
                    ),
                    Input(
                        key=f"repo_name_{key_suffix}",
                        text=strings.repo_name,
                        default=repo.get("name", ""),
                        icon="msg_edit",
                        on_change=makeOnChange("name", idx)
                    ),
                    Input(
                        key=f"repo_url_{key_suffix}",
                        text=strings.repo_url,
                        default=repo.get("url", ""),
                        icon="msg_link",
                        on_change=makeOnChange("url", idx)
                    ),
                    Text(
                        text=icon_text,
                        icon="msg_folders",
                        create_sub_fragment=makeOnSelectIcon(idx)
                    )
                ])
                
                settingsList.extend([
                    Text(
                        text=strings.share_repository,
                        icon="msg_share",
                        accent=True,
                        on_click=makeOnShare(idx)
                    )
                ])
                
                if len(repos) > 1:
                    settingsList.append(Text(
                        text=strings.remove_repository,
                        icon="msg_filled_blocked_solar",
                        red=True,
                        on_click=makeOnRemove(idx)
                    ))

            settingsList.append(Divider())
        
        return settingsList
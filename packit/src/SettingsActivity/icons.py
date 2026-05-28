# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import AndroidUtilities failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from android_utils import run_on_ui_thread
from hook_utils import find_class
from client_utils import get_last_fragment
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()


class IconSelector:
    def __init__(self, repoManager, on_icon_selected_callback):
        self.repoManager = repoManager
        self.on_icon_selected_callback = on_icon_selected_callback
    
    def _refresh_settings_page(self):
        def action():
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllFragments"):
                fragment.rebuildAllFragments(True)
        run_on_ui_thread(action)

    def _copy_text(self, text_to_copy: str, message: str):
        if AndroidUtilities.addToClipboard(text_to_copy):
            BulletinHelper.show_success(message)

    def _select_icon(self, icon_name: str):
        self.on_icon_selected_callback(icon_name)
        BulletinHelper.show_success(strings.icon_selected.format(icon_name))
        def close_fragment():
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "finishFragment"):
                fragment.finishFragment()
        run_on_ui_thread(close_fragment)

    def build(self):
        try:
            icon_categories = {
                strings.arrows_navigation: [
                    "arrow_more_solar", "msg_go", "msg_go_up", "preview_arrow_left", "preview_arrow_right",
                    "ic_ab_back", "ic_ab_other", "ic_ab_search", "ic_go"
                ],
                strings.attachments_media: [
                    "attach_audio", "attach_contact", "attach_file", "attach_gallery", "attach_gif",
                    "attach_location", "attach_poll", "attach_send_solar", "attach_video", "attach_voice",
                    "msg_attach", "msg_audio", "msg_video", "msg_photo", "msg_gallery", "msg_gif",
                    "msg_file", "msg_doc", "msg_image", "msg_media"
                ],
                strings.avatar_profile: [
                    "avatar_add", "avatar_delete", "avatar_edit", "msg_photo_add", "msg_photo_crop",
                    "msg_photo_curve", "msg_photo_text_regular", "msg_photo_text2", "profile_calls",
                    "profile_newmsg", "profile_settings", "profile_share", "profile_video"
                ],
                strings.calls_voice: [
                    "calls_accept", "calls_decline", "calls_flip", "calls_mute", "calls_videocall",
                    "msg_call", "msg_videocall", "msg_videoplay", "msg_voice", "msg_voip",
                    "voip_accept", "voip_decline", "voip_group_add_user", "voip_group_invite",
                    "voip_group_leave", "voip_group_link", "voip_speaker"
                ],
                strings.chat_actions: [
                    "chats_archive", "chats_delete", "chats_delivered", "chats_error", "chats_markread",
                    "chats_mute", "chats_pin", "chats_read", "chats_sending", "chats_sent",
                    "chats_unarchive", "chats_unmute", "chats_unpin", "msg_chat", "msg_group",
                    "msg_channel", "msg_bot", "msg_user", "msg_contacts"
                ],
                strings.data_network: [
                    "data_network", "data_roaming", "data_wifi", "msg_filled_data_calls",
                    "msg_filled_data_files", "msg_filled_datausage", "msg_filled_storageusage"
                ],
                strings.dialog_creation: [
                    "dialogs_add", "dialogs_bot", "dialogs_broadcast", "dialogs_contacts",
                    "dialogs_group", "dialogs_newchannel", "dialogs_newgroup", "dialogs_newsecret",
                    "dialogs_proxy", "dialogs_search", "dialogs_settings"
                ],
                strings.fab_actions: [
                    "fab_add", "fab_camera", "fab_compose_small_solar", "fab_done", "fab_edit",
                    "msg_add_file", "msg_addbot", "msg_addfolder", "msg_addphoto"
                ],
                strings.files_storage: [
                    "files_storage", "gift_unpack", "msg_file", "msg_doc", "msg_folders_bots",
                    "msg_folders_channels", "msg_folders_groups", "msg_folders_requests",
                    "msg_folder", "msg_removefolder"
                ],
                strings.input_interface: [
                    "ic_attach_document", "ic_attach_gallery", "ic_attach_location", "ic_attach_music",
                    "ic_attach_poll", "ic_attach_video", "input_bot1", "input_bot1_remix",
                    "input_clear", "input_emoji", "input_schedule_solar", "input_send", "input_sticker",
                    "msg_input", "msg_instant", "msg_select", "msg_select_between"
                ],
                strings.location_maps: [
                    "location_current", "location_send", "location_zoom_in", "location_zoom_out",
                    "msg_location", "msg_map"
                ],
                strings.menu_items: [
                    "menu_account", "menu_add", "menu_archive", "menu_attach", "menu_back",
                    "menu_block", "menu_broadcast", "menu_calls", "menu_camera", "menu_cancel",
                    "menu_channel", "menu_chat", "menu_clear", "menu_close", "menu_contacts",
                    "menu_copy", "menu_create", "menu_crop", "menu_delete", "menu_done",
                    "menu_download", "menu_edit", "menu_emoji", "menu_end", "menu_exit",
                    "menu_export", "menu_fave", "menu_feature_premium", "menu_file", "menu_filter",
                    "menu_flag", "menu_folder", "menu_forward", "menu_gallery", "menu_gif",
                    "menu_group", "menu_help", "menu_hide", "menu_home", "menu_import",
                    "menu_info", "menu_intro_solar", "menu_invite", "menu_join", "menu_leave",
                    "menu_link", "menu_location", "menu_lock", "menu_logout", "menu_love",
                    "menu_map", "menu_mic", "menu_more", "menu_mute", "menu_new", "menu_next",
                    "menu_night", "menu_notifications", "menu_open", "menu_pause", "menu_phone",
                    "menu_photo", "menu_pin", "menu_play", "menu_plus", "menu_poll",
                    "menu_premium", "menu_premium_clock", "menu_premium_location", "menu_premium_star",
                    "menu_preview", "menu_previous", "menu_privacy", "menu_profile", "menu_qr",
                    "menu_question", "menu_quiz", "menu_read", "menu_redo", "menu_refresh",
                    "menu_remove", "menu_reorder", "menu_repeat", "menu_reply", "menu_report",
                    "menu_restart", "menu_restore", "menu_rotate", "menu_save", "menu_scan",
                    "menu_search", "menu_security", "menu_select_quote_solar", "menu_send",
                    "menu_settings", "menu_share", "menu_silent", "menu_skip", "menu_sort",
                    "menu_spam", "menu_star", "menu_stats", "menu_sticker", "menu_stop",
                    "menu_storage", "menu_stories", "menu_switch", "menu_sync", "menu_theme",
                    "menu_undo", "menu_unmute", "menu_unpin", "menu_unlock", "menu_unread",
                    "menu_update", "menu_upload", "menu_user", "menu_video", "menu_voice",
                    "menu_wallet", "menu_warning", "menu_zoom"
                ],
                strings.message_content: [
                    "msg_archive", "msg_autodelete_1d", "msg_autodelete_1m", "msg_autodelete_1w",
                    "msg_autodelete_badge2", "msg_block", "msg_broadcast", "msg_calendar",
                    "msg_calendar2", "msg_clock", "msg_code", "msg_colors", "msg_comment",
                    "msg_copy_filled", "msg_day", "msg_discussion", "msg_draft", "msg_draw",
                    "msg_font", "msg_games", "msg_gift_premium", "msg_header_draw",
                    "msg_header_share", "msg_help", "msg_history", "msg_info", "msg_invite",
                    "msg_join", "msg_leave", "msg_level", "msg_link2", "msg_link_1", "msg_link_2",
                    "msg_list", "msg_live", "msg_log", "msg_love", "msg_mention", "msg_menu",
                    "msg_message2", "msg_month", "msg_move", "msg_msgbubble2", "msg_music",
                    "msg_name", "msg_new", "msg_new_group", "msg_new_private", "msg_new_secret",
                    "msg_newphone", "msg_news", "msg_panel_forward", "msg_panel_reply",
                    "msg_payment_provider", "msg_phone", "msg_players", "msg_plugins",
                    "msg_poll", "msg_premium", "msg_preview", "msg_question", "msg_quote",
                    "msg_quiz", "msg_rate_down", "msg_reactions_filled", "msg_recent",
                    "msg_recents", "msg_record", "msg_saved", "msg_scheduled", "msg_secret",
                    "msg_send", "msg_separated", "msg_settings_art", "msg_settings_ny",
                    "msg_share", "msg_share_filled", "msg_shareout", "msg_sound", "msg_spam",
                    "msg_speed", "msg_start", "msg_stats", "msg_sticker", "msg_stories",
                    "msg_stories_add", "msg_stories_archive", "msg_stories_closefriends",
                    "msg_stories_my", "msg_stories_stealth", "msg_ton", "msg_topic_create",
                    "msg_translate", "msg_unarchive", "msg_user", "msg_video", "msg_view",
                    "msg_wallpaper", "msg_watch", "msg_wave", "msg_work"
                ],
                strings.message_controls: [
                    "msg_check", "msg_check2", "msg_clear", "msg_clear_recent", "msg_close",
                    "msg_customize", "msg_delete", "msg_delete_solar", "msg_done", "msg_download",
                    "msg_download_settings", "msg_edit", "msg_emoji", "msg_empty", "msg_error",
                    "msg_fave", "msg_favorite", "msg_filled_blocked_solar", "msg_filled_menu_channels",
                    "msg_filled_menu_groups", "msg_filled_menu_users", "msg_filled_shareout",
                    "msg_filled_storageusage", "msg_filter", "msg_flag", "msg_flash", "msg_flip",
                    "msg_folder", "msg_folders_bots", "msg_folders_channels", "msg_folders_groups",
                    "msg_folders_requests", "msg_forward", "msg_gift_premium", "msg_hide",
                    "msg_image", "msg_input", "msg_instant", "msg_location", "msg_lock",
                    "msg_map", "msg_media", "msg_mini_autodelete_empty", "msg_mini_customize",
                    "msg_mute", "msg_night", "msg_night_auto", "msg_no_sound", "msg_notifications",
                    "msg_online", "msg_open", "msg_openin", "msg_openprofile", "msg_pause",
                    "msg_pin", "msg_pin_mini", "msg_play", "msg_privacy", "msg_profile",
                    "msg_proxy", "msg_qrcode", "msg_qrcode_mini", "msg_read", "msg_rear_camera",
                    "msg_redo", "msg_refresh", "msg_remix", "msg_remove", "msg_removefolder",
                    "msg_replace", "msg_reply", "msg_reply_small", "msg_report", "msg_restore",
                    "msg_retry", "msg_rotate", "msg_save", "msg_search", "msg_security",
                    "msg_select", "msg_select_between", "msg_settings", "msg_silent",
                    "msg_speed", "msg_star", "msg_status_edit", "msg_status_set", "msg_stop",
                    "msg_stopwatch", "msg_unmute", "msg_unpin", "msg_unlock", "msg_unvote",
                    "msg_update", "msg_upload", "msg_videocall", "msg_videoplay", "msg_voice",
                    "msg_voip", "msg_warning", "msg_zoom"
                ],
                strings.passcode_security: [
                    "passcode_delete", "passcode_fingerprint", "passcode_logo", "ic_block_user",
                    "ic_lock", "ic_lock_white", "ic_unblock_user"
                ],
                strings.player_controls: [
                    "player_next", "player_pause", "player_play", "player_prev", "player_repeat",
                    "player_shuffle", "preview_play", "msg_play", "msg_pause", "msg_stop"
                ],
                strings.stickers: [
                    "stickers_add", "stickers_check", "stickers_delete", "stickers_fave",
                    "stickers_menu", "msg_sticker", "input_sticker"
                ],
                strings.stories: [
                    "stories_circle", "stories_seen", "stories_unseen", "msg_stories",
                    "msg_stories_add", "msg_stories_archive", "msg_stories_closefriends",
                    "msg_stories_my", "msg_stories_stealth", "menu_stories"
                ],
                strings.themes: [
                    "theme_auto", "theme_dark", "theme_day", "theme_light", "theme_night",
                    "msg_night", "msg_night_auto", "msg_brightness_high", "msg_brightness_low"
                ],
                strings.ui_elements: [
                    "tooltip_arrow", "undo_redo", "undo_undo", "window_close", "ic_comment",
                    "ic_delete", "ic_done", "ic_menu_more", "ic_mute", "ic_notifications",
                    "ic_pin", "ic_send", "ic_unmute"
                ]
            }

            try:
                R_drawable = find_class("org.telegram.messenger.R$drawable")
                def filter_icons(icon_list):
                    return [icon for icon in icon_list if getattr(R_drawable, icon, 0) != 0]
            except Exception:
                def filter_icons(icon_list):
                    return icon_list
            
            settings_list = []

            for category_name, category_icons in icon_categories.items():
                filtered_icons = filter_icons(category_icons)
                if filtered_icons:
                    settings_list.append(Header(text=category_name))
                    for icon_name in filtered_icons:
                        settings_list.append(Text(
                            text=icon_name,
                            icon=icon_name,
                            on_click=lambda view, name=icon_name: self._select_icon(name)
                        ))
                    settings_list.append(Divider())

            settings_list.append(Divider())
            return settings_list
            
        except Exception as e:
            return [Header(text=strings.error_header), Text(text=strings.failed_to_load_icons.format(e))]
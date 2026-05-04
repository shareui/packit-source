import ctypes
import os

from android_utils import log

try:
    from elyx import strings as _strings
except Exception:
    _strings = None

CHECK_SO_PATHS = False

_BASE = "/plugins/ElyxPlugins/shareui_packit/packit/native"


def _soPath(libName: str) -> str:
    from .utils.paths import _filesDir
    return _filesDir() + _BASE + "/" + libName + ".so"


def checkSoPaths():
    for name in ("libbithash", "libsearch", "libpacklight", "libpackitdb", "libexport"):
        path = _soPath(name)
        exists = os.path.exists(path)
        log(f"nativeLoader: {'Lib ' + path + ' exists!' if exists else 'Lib ' + path + ' NOT FOUND'}")


def showNativeErrorSheet(libName: str, error: str):
    try:
        import threading
        from android_utils import run_on_ui_thread

        def _show():
            try:
                from client_utils import get_last_fragment
                from android.view import Gravity, View
                from android.widget import FrameLayout, LinearLayout, TextView, ScrollView
                from android.graphics import Color
                from java import dynamic_proxy
                from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation
                from org.telegram.ui.ActionBar import BottomSheet, Theme
                from org.telegram.ui.Components import LayoutHelper, BackupImageView
                from org.telegram.ui.Stories.recorder import ButtonWithCounterView
                from android.net import Uri
                try:
                    from org.telegram.messenger.browser import Browser
                except Exception:
                    Browser = None

                frag = get_last_fragment()
                if not frag:
                    return
                activity = frag.getParentActivity()
                if not activity:
                    return
                rp = frag.getResourceProvider()

                try:
                    from org.telegram.messenger import BuildVars, ApplicationLoader
                    from android.os import Build
                    _context = ApplicationLoader.applicationContext
                    _app_ver = str(BuildVars.BUILD_VERSION_STRING)
                    _package = str(_context.getPackageName())
                    try:
                        _abi = str(Build.SUPPORTED_ABIS[0])
                    except Exception:
                        _abi = str(Build.CPU_ABI)
                    _android = str(Build.VERSION.RELEASE)
                except Exception as _ie:
                    log(f"nativeLoader: device info error: {_ie}")
                    _app_ver = "N/A"
                    _package = "N/A"
                    _abi = "N/A"
                    _android = "N/A"

                try:
                    from elyx import metainfo as _metainfo
                    _plugin_ver = str(_metainfo['version'])
                except Exception:
                    _plugin_ver = "N/A"

                clip_text = (
                    f"**Native lib error:**\n"
                    f"app version: {_app_ver}\n"
                    f"plugin version: {_plugin_ver}\n"
                    f"package: {_package}\n"
                    f"ABI: {_abi}\n"
                    f"android: {_android}\n"
                    f"error: {error}"
                )
                try:
                    AndroidUtilities.addToClipboard(clip_text)
                except Exception as _ce:
                    log(f"nativeLoader: clipboard copy error: {_ce}")

                sheet = BottomSheet(activity, False, rp)
                sheet.fixNavigationBar()

                linear = LinearLayout(activity)
                linear.setOrientation(LinearLayout.VERTICAL)

                # sticker
                iv = BackupImageView(activity)
                iv.setRoundRadius(AndroidUtilities.dp(16))
                try:
                    iv.getImageReceiver().setCrossfadeWithOldImage(True)
                except Exception:
                    pass

                def _try_sticker():
                    try:
                        mdc = MediaDataController.getInstance(0)
                        ss = None
                        try:
                            ss = mdc.getStickerSetByName("wtffffffffffDD")
                        except Exception:
                            pass
                        if not ss:
                            try:
                                ss = mdc.getStickerSetByEmojiOrName("wtffffffffffDD")
                            except Exception:
                                pass
                        if not ss:
                            try:
                                mdc.loadStickersByEmojiOrName("wtffffffffffDD", False, False)
                            except Exception:
                                pass
                            return False
                        docs_count = ss.documents.size() if getattr(ss, "documents", None) else 0
                        if docs_count <= 27:
                            return False
                        doc = ss.documents.get(27)
                        iv.setImage(
                            ImageLocation.getForDocument(doc),
                            "100_100",
                            None, None, 0, 1
                        )
                        return True
                    except Exception as _e:
                        log(f"nativeLoader: showNativeErrorSheet sticker error: {_e}")
                        return False

                if not _try_sticker():
                    def _retry():
                        import time
                        time.sleep(2.0)
                        run_on_ui_thread(_try_sticker)
                    threading.Thread(target=_retry, daemon=True).start()

                linear.addView(iv, LayoutHelper.createLinear(
                    100, 100, Gravity.CENTER_HORIZONTAL, 0, 20, 0, 0
                ))

                # title
                title = TextView(activity)
                title.setGravity(Gravity.CENTER_HORIZONTAL)
                title.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
                title.setTextSize(1, 20.0)
                title.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                title.setText(str(_strings["native_error_title"]) if _strings else "Error in native library!")
                linear.addView(title, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 12.0, 24.0, 0.0))

                # main text
                desc = TextView(activity)
                desc.setGravity(Gravity.CENTER_HORIZONTAL)
                desc.setTextColor(sheet.getThemedColor(Theme.key_windowBackgroundWhiteBlackText))
                desc.setTextSize(1, 15.0)
                desc.setText(str(_strings("native_error_desc", lib_name=libName)) if _strings else f"Unfortunately, an error occurred in the native library {libName} :(")
                linear.addView(desc, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 8.0, 24.0, 0.0))

                # error text (red)
                err_tv = TextView(activity)
                err_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                err_tv.setTextColor(sheet.getThemedColor(Theme.key_text_RedRegular))
                err_tv.setTextSize(1, 13.0)
                err_tv.setText(error)
                linear.addView(err_tv, LayoutHelper.createFrame(-1, -2.0, 0, 24.0, 6.0, 24.0, 0.0))

                # Report a bug button
                report_btn = ButtonWithCounterView(activity, True, rp)
                report_btn.setRound()
                report_btn.setText(str(_strings["native_report_bug"]) if _strings else "Report a bug", False)

                class _ReportClick(dynamic_proxy(View.OnClickListener)):
                    def onClick(self, v):
                        try:
                            uri = Uri.parse("https://github.com/shareui/packit-source/issues")
                            act = frag.getParentActivity()
                            if act and Browser:
                                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
                        except Exception as _e:
                            log(f"nativeLoader: showNativeErrorSheet report click error: {_e}")

                report_btn.setOnClickListener(_ReportClick())
                linear.addView(report_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 16.0, 16.0, 8.0))

                # Close button
                close_btn = ButtonWithCounterView(activity, False, rp)
                close_btn.setRound()
                close_btn.setNeutral()
                close_btn.setText(str(_strings["close_button"]) if _strings else "Close", False)

                class _CloseClick(dynamic_proxy(View.OnClickListener)):
                    def onClick(self, v):
                        sheet.dismiss()

                close_btn.setOnClickListener(_CloseClick())
                linear.addView(close_btn, LayoutHelper.createFrame(-1, 48.0, 0, 16.0, 0.0, 16.0, 0.0))

                scroll = ScrollView(activity)
                scroll.addView(linear)
                sheet.setCustomView(scroll)
                sheet.show()
            except Exception as _e:
                log(f"nativeLoader: showNativeErrorSheet _show error: {_e}")

        run_on_ui_thread(_show)
    except Exception as e:
        log(f"nativeLoader: showNativeErrorSheet error: {e}")


def loadBitHash() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libbithash"))
        lib.bitHash_oneshot.restype = ctypes.c_uint64
        lib.bitHash_oneshot.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64]
        return lib
    except Exception as e:
        log(f"nativeLoader: libbithash load error: {e}")
        showNativeErrorSheet("libbithash.so", str(e))
        return None


def loadSearch() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libsearch"))
        lib.search_build_index.restype = ctypes.c_int
        lib.search_build_index.argtypes = [ctypes.c_char_p]
        lib.search_score.restype = ctypes.c_void_p
        lib.search_score.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p,
                                     ctypes.c_int, ctypes.c_int]
        lib.search_free_index.restype = None
        lib.search_free_index.argtypes = [ctypes.c_int]
        lib.search_free_str.restype = None
        lib.search_free_str.argtypes = [ctypes.c_void_p]
        return lib
    except Exception as e:
        log(f"nativeLoader: libsearch load error: {e}")
        showNativeErrorSheet("libsearch.so", str(e))
        return None


def loadPackLight() -> "ctypes.CDLL | None":
    try:
        return ctypes.CDLL(_soPath("libpacklight"))
    except Exception as e:
        log(f"nativeLoader: libpacklight load error: {e}")
        showNativeErrorSheet("libpacklight.so", str(e))
        return None


def loadPackitDb() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libpackitdb"))
        vp   = ctypes.c_void_p
        cp   = ctypes.c_char_p
        i64  = ctypes.c_int64
        u32  = ctypes.c_uint32
        sz   = ctypes.c_size_t
        ci   = ctypes.c_int
        u8p  = ctypes.POINTER(ctypes.c_uint8)
        u32p = ctypes.POINTER(ctypes.c_uint32)
        lib.packdb_write_raw.restype = ci
        lib.packdb_write_raw.argtypes = [cp, cp, u8p, u32]
        lib.packdb_read_raw.restype = ci
        lib.packdb_read_raw.argtypes = [cp, cp, u8p, u32p]
        lib.packdb_open_from_payload.restype = vp
        lib.packdb_open_from_payload.argtypes = [cp, cp, u8p, u32]
        lib.packdb_serialize_to.restype = ci
        lib.packdb_serialize_to.argtypes = [vp, u8p, u32p]
        lib.packdb_open.restype = vp
        lib.packdb_open.argtypes = [cp, cp]
        lib.packdb_close.restype = ci
        lib.packdb_close.argtypes = [vp]
        lib.packdb_get.restype = i64
        lib.packdb_get.argtypes = [vp, cp, i64]
        lib.packdb_set.restype = ci
        lib.packdb_set.argtypes = [vp, cp, i64]
        lib.packdb_increment.restype = i64
        lib.packdb_increment.argtypes = [vp, cp, i64]
        lib.packdb_award_has.restype = ci
        lib.packdb_award_has.argtypes = [vp, cp]
        lib.packdb_award_add.restype = ci
        lib.packdb_award_add.argtypes = [vp, cp]
        lib.packdb_award_list.restype = ci
        lib.packdb_award_list.argtypes = [vp, cp, sz]
        lib.packdb_award_count.restype = ci
        lib.packdb_award_count.argtypes = [vp]
        lib.packdb_entry_count.restype = ci
        lib.packdb_entry_count.argtypes = [vp]
        return lib
    except Exception as e:
        log(f"nativeLoader: libpackitdb load error: {e}")
        showNativeErrorSheet("libpackitdb.so", str(e))
        return None


def loadExport() -> "ctypes.CDLL | None":
    try:
        lib = ctypes.CDLL(_soPath("libexport"))
        lib.packit_write_file.restype = ctypes.c_int
        lib.packit_write_file.argtypes = [
            ctypes.c_int64, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
        ]
        lib.packit_read_file.restype = ctypes.c_int
        lib.packit_read_file.argtypes = [
            ctypes.c_char_p, ctypes.c_int64, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_uint32),
        ]
        lib.packit_free_buf.restype = None
        lib.packit_free_buf.argtypes = [ctypes.c_char_p]
        lib.packit_last_error.restype = ctypes.c_char_p
        lib.packit_last_error.argtypes = []
        return lib
    except Exception as e:
        log(f"nativeLoader: libexport load error: {e}")
        showNativeErrorSheet("libexport.so", str(e))
        return None

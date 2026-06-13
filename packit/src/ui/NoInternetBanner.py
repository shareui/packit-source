# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# вача скажи ему пусть комментарии на английском пишет, без декораций, и без """ а то ты как чмо.

from packutil import logx
from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, TextView, ImageView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.view.animation import TranslateAnimation, AlphaAnimation, AnimationSet, DecelerateInterpolator, AccelerateInterpolator
from android_utils import run_on_ui_thread

try:
    from org.telegram.ui.ActionBar import Theme
except Exception:
    Theme = None

try:
    from org.telegram.messenger import AndroidUtilities, ApplicationLoader
except Exception:
    AndroidUtilities = None
    ApplicationLoader = None

try:
    from org.telegram.ui.Components import LayoutHelper
except Exception:
    LayoutHelper = None

try:
    from elyx import strings
except Exception:
    strings = {}

try:
    from android.net import ConnectivityManager, NetworkRequest, NetworkCapabilities
    from android.content import Context
except Exception:
    ConnectivityManager = None
    NetworkRequest = None
    NetworkCapabilities = None
    Context = None

try:
    from extera_utils.classes import Base, java_subclass, joverride
except Exception:
    Base = None
    java_subclass = None
    joverride = None


# ─── Единственный глобальный коллбек ───
_network_callback_instance = None
_callback_registered = False
_listeners = []  # list of banner instances to notify
_is_network_available = True  # assume available at start


def _on_network_available():
    global _is_network_available
    _is_network_available = True
    logx(f"NoInternetBanner: _on_network_available fired, notifying {len(_listeners)} listeners", True)
    for i, listener in enumerate(_listeners):
        try:
            logx(f"NoInternetBanner: calling on_network_restored on listener[{i}] id={id(listener)}", True)
            listener.on_network_restored()
        except Exception as e:
            logx(f"NoInternetBanner: _on_network_available listener error: {e}", False)


def _on_network_lost():
    global _is_network_available
    _is_network_available = False
    logx(f"NoInternetBanner: _on_network_lost fired, notifying {len(_listeners)} listeners", True)
    for i, listener in enumerate(_listeners):
        try:
            logx(f"NoInternetBanner: calling on_network_lost on listener[{i}] id={id(listener)}", True)
            listener.on_network_lost()
        except Exception as e:
            logx(f"NoInternetBanner: _on_network_lost listener error: {e}", False)


def _create_network_callback():
    """Create a ConnectivityManager.NetworkCallback via java_subclass."""
    global _network_callback_instance
    if _network_callback_instance is not None:
        return _network_callback_instance

    try:
        _NetworkCallbackCls = ConnectivityManager.NetworkCallback

        @java_subclass(_NetworkCallbackCls)
        class _PackItNetworkCallback(Base):
            @joverride()
            def onAvailable(self, *args, **kwargs):
                logx("NoInternetBanner: onAvailable", True)
                run_on_ui_thread(_on_network_available)

            @joverride()
            def onLost(self, *args, **kwargs):
                logx("NoInternetBanner: onLost", True)
                run_on_ui_thread(_on_network_lost)

        _network_callback_instance = _PackItNetworkCallback.new_instance()
        logx("NoInternetBanner: NetworkCallback created", True)
        return _network_callback_instance
    except Exception as e:
        logx(f"NoInternetBanner: _create_network_callback error: {e}", False)
        import traceback
        logx(traceback.format_exc(), True)
        return None


def _register_callback():
    """Register the global network callback with ConnectivityManager."""
    global _callback_registered
    if _callback_registered:
        return
    try:
        ctx = ApplicationLoader.applicationContext
        cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE)
        cb = _create_network_callback()
        if cb is None:
            return
        cm.registerDefaultNetworkCallback(cb.java)
        _callback_registered = True
        logx("NoInternetBanner: callback registered", True)
        
        # Check initial network state
        try:
            active_net = cm.getActiveNetwork()
            if active_net is None:
                global _is_network_available
                _is_network_available = False
                logx("NoInternetBanner: initial network is offline", True)
        except Exception as e:
            logx(f"NoInternetBanner: failed to get active network: {e}", False)
            
    except Exception as e:
        logx(f"NoInternetBanner: _register_callback error: {e}", False)
        import traceback
        logx(traceback.format_exc(), True)


def _poll_network_recovery(banner_id):
    """
    Fallback polling for devices (Honor MagicOS) where onAvailable is not reliably fired.
    Polls every 3s while network is marked unavailable and this banner is still registered.
    Stops as soon as network is detected or the listener is gone.
    """
    import time as _time
    logx(f"NoInternetBanner: poll thread started for banner_id={banner_id}", True)
    while True:
        _time.sleep(3)
        listener = next((l for l in _listeners if id(l) == banner_id), None)
        if listener is None:
            logx(f"NoInternetBanner: poll thread — listener {banner_id} gone, stopping", True)
            break
        if _is_network_available:
            logx(f"NoInternetBanner: poll thread — network already available, stopping", True)
            break
        try:
            ctx = ApplicationLoader.applicationContext
            cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE)
            active_net = cm.getActiveNetwork()
            logx(f"NoInternetBanner: poll — active_net={active_net is not None}", True)
            if active_net is not None:
                caps = cm.getNetworkCapabilities(active_net)
                has_inet = caps is not None and caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                logx(f"NoInternetBanner: poll — has_internet_cap={has_inet}", True)
                if has_inet:
                    logx("NoInternetBanner: poll — network restored detected, firing _on_network_available", True)
                    run_on_ui_thread(_on_network_available)
                    break
        except Exception as ex:
            logx(f"NoInternetBanner: poll error: {ex}", True)


def _unregister_callback():
    """Unregister the global network callback if no listeners remain."""
    global _callback_registered, _network_callback_instance
    if not _callback_registered or _network_callback_instance is None:
        return
    if len(_listeners) > 0:
        return  # still have active listeners
    try:
        ctx = ApplicationLoader.applicationContext
        cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE)
        cm.unregisterNetworkCallback(_network_callback_instance.java)
        _callback_registered = False
        _network_callback_instance = None
        logx("NoInternetBanner: callback unregistered", True)
    except Exception as e:
        logx(f"NoInternetBanner: _unregister_callback error: {e}", False)


# ─── Banner View ───

class NoInternetBanner:
    """
    Banner instance tied to a specific content_view (FrameLayout).
    Call register() in onFragmentCreate / afterCreateView and unregister() in onFragmentDestroy.
    """

    def __init__(self, content_view, z_index_above_blur=True):
        self.content_view = content_view
        self.banner_view = None
        self._visible = False
        self._config_loaded = False
        self._z_index_above_blur = z_index_above_blur
        logx("NoInternetBanner: instance created", True)

    def register(self):
        """Register this banner as a listener and start the global callback if needed."""
        if self not in _listeners:
            _listeners.append(self)
        _register_callback()
        logx(f"NoInternetBanner: registered id={id(self)}, listeners={len(_listeners)}, _callback_registered={_callback_registered}, _is_network_available={_is_network_available}", True)
        if not _is_network_available:
            import threading
            t = threading.Thread(target=_poll_network_recovery, args=(id(self),), daemon=True)
            t.start()
            logx(f"NoInternetBanner: poll thread launched for id={id(self)}", True)

    def unregister(self):
        """Unregister this banner and stop the global callback if no listeners remain."""
        if self in _listeners:
            _listeners.remove(self)
        self._hide_immediate()
        _unregister_callback()
        logx(f"NoInternetBanner: unregistered id={id(self)}, listeners={len(_listeners)}", True)

    def on_config_loaded(self):
        """Call this after config/data has loaded. Shows the banner if network is already lost."""
        self._config_loaded = True
        logx(f"NoInternetBanner: on_config_loaded id={id(self)}, _is_network_available={_is_network_available}", True)
        if not _is_network_available:
            self._show_banner()

    def on_network_restored(self):
        """Network restored — hide the banner with animation."""
        logx(f"NoInternetBanner: on_network_restored id={id(self)}, _visible={self._visible}, has_callback={hasattr(self, '_on_network_restored_callback') and self._on_network_restored_callback is not None}", True)
        if self._visible:
            self._hide_banner()
        if hasattr(self, '_on_network_restored_callback') and self._on_network_restored_callback:
            logx(f"NoInternetBanner: firing _on_network_restored_callback id={id(self)}", True)
            self._on_network_restored_callback()

    def on_network_lost(self):
        """Network lost — show the banner with animation (only if config already loaded)."""
        logx(f"NoInternetBanner: on_network_lost id={id(self)}, _config_loaded={self._config_loaded}, _visible={self._visible}", True)
        if self._config_loaded and not self._visible:
            self._show_banner()
        import threading
        t = threading.Thread(target=_poll_network_recovery, args=(id(self),), daemon=True)
        t.start()
        logx(f"NoInternetBanner: poll thread launched on_network_lost for id={id(self)}", True)

    # ─── Internal ───

    def _create_banner(self):
        """Build the banner view (a small bar at the top of content_view)."""
        try:
            ctx = self.content_view.getContext()

            # Outer container
            container = FrameLayout(ctx)

            # Background pill
            bg = GradientDrawable()
            bg.setShape(GradientDrawable.RECTANGLE)
            bg.setCornerRadius(AndroidUtilities.dp(12))

            # Use undo_background color (matches the existing HintView2 style)
            try:
                bg_color = Theme.getColor(Theme.key_undo_background)
            except Exception:
                bg_color = 0xCC333333  # fallback dark semi-transparent
            bg.setColor(bg_color)
            container.setBackground(bg)

            # Inner layout (icon + text)
            inner = LinearLayout(ctx)
            inner.setOrientation(LinearLayout.HORIZONTAL)
            inner.setGravity(Gravity.CENTER_VERTICAL)
            inner.setPadding(
                AndroidUtilities.dp(14), AndroidUtilities.dp(10),
                AndroidUtilities.dp(14), AndroidUtilities.dp(10)
            )

            # Warning icon
            try:
                icon = ImageView(ctx)
                from hook_utils import find_class
                R_tg = find_class("org.telegram.messenger.R")
                icon_res = getattr(R_tg.drawable, "msg_warning", 0)
                if icon_res:
                    icon.setImageResource(icon_res)
                else:
                    # Fallback: try another icon
                    icon_res2 = getattr(R_tg.drawable, "msg_retry", 0)
                    if icon_res2:
                        icon.setImageResource(icon_res2)
                try:
                    text_color = Theme.getColor(Theme.key_undo_infoColor)
                except Exception:
                    text_color = 0xFFFFFFFF
                from android.graphics import PorterDuff
                icon.setColorFilter(text_color, PorterDuff.Mode.SRC_IN)
                icon_lp = LinearLayout.LayoutParams(
                    AndroidUtilities.dp(20), AndroidUtilities.dp(20)
                )
                icon_lp.rightMargin = AndroidUtilities.dp(10)
                inner.addView(icon, icon_lp)
            except Exception as e:
                logx(f"NoInternetBanner: icon error: {e}", False)

            # Text
            tv = TextView(ctx)
            try:
                banner_text = str(strings.get("no_internet_banner", "No internet connection"))
            except Exception:
                banner_text = "No internet connection"
            tv.setText(banner_text)
            tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            try:
                text_color = Theme.getColor(Theme.key_undo_infoColor)
            except Exception:
                text_color = 0xFFFFFFFF
            tv.setTextColor(text_color)
            try:
                tv.setTypeface(AndroidUtilities.bold())
            except Exception:
                pass
            try:
                from ..viewUtils import applyFont
                applyFont(tv)
            except Exception:
                pass
            inner.addView(tv, LinearLayout.LayoutParams(-2, -2))

            # Retry button
            retry_tv = TextView(ctx)
            try:
                retry_text = str(strings.get("retry_button", "Retry"))
            except Exception:
                retry_text = "Retry"
            retry_tv.setText(retry_text.upper())
            retry_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            try:
                retry_color = Theme.getColor(Theme.key_undo_cancelColor)
            except Exception:
                retry_color = 0xFF88CCFF
            retry_tv.setTextColor(retry_color)
            try:
                retry_tv.setTypeface(AndroidUtilities.bold())
            except Exception:
                pass
            try:
                applyFont(retry_tv)
            except Exception:
                pass
            retry_lp = LinearLayout.LayoutParams(-2, -2)
            retry_lp.leftMargin = AndroidUtilities.dp(16)
            
            def _on_retry_click(v):
                logx(f"NoInternetBanner: retry clicked, _is_network_available={_is_network_available}, has_callback={hasattr(self, '_on_network_restored_callback') and self._on_network_restored_callback is not None}", True)
                if _is_network_available:
                    self._hide_banner()
                    if hasattr(self, '_on_network_restored_callback') and self._on_network_restored_callback:
                        logx("NoInternetBanner: retry — network available, firing _on_network_restored_callback", True)
                        self._on_network_restored_callback()
                else:
                    logx("NoInternetBanner: retry — network still down, re-showing banner", True)
                    self._hide_banner()
                    run_on_ui_thread(self._show_banner, 400)
                    import threading
                    t = threading.Thread(target=_poll_network_recovery, args=(id(self),), daemon=True)
                    t.start()
            
            from android_utils import OnClickListener
            retry_tv.setOnClickListener(OnClickListener(_on_retry_click))
            inner.addView(retry_tv, retry_lp)

            container.addView(inner, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))

            self.banner_view = container
            return container
        except Exception as e:
            logx(f"NoInternetBanner: _create_banner error: {e}", False)
            import traceback
            logx(traceback.format_exc(), True)
            return None

    def _show_banner(self):
        """Show the banner with a slide-down + fade-in animation."""
        if self._visible:
            return
        try:
            if self.content_view is None:
                return

            banner = self._create_banner()
            if banner is None:
                return

            # Position: bottom center, above blur, with margin
            lp = FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL)
            lp.bottomMargin = AndroidUtilities.dp(8)

            banner.setVisibility(View.VISIBLE)
            self.content_view.addView(banner, lp)

            # Bring to front so it's above blur
            if self._z_index_above_blur:
                banner.bringToFront()

            # Slide-up + fade-in animation
            try:
                anim_set = AnimationSet(True)
                anim_set.setInterpolator(DecelerateInterpolator())

                slide = TranslateAnimation(0, 0, AndroidUtilities.dp(60), 0)
                slide.setDuration(300)
                anim_set.addAnimation(slide)

                alpha = AlphaAnimation(0.0, 1.0)
                alpha.setDuration(300)
                anim_set.addAnimation(alpha)

                anim_set.setFillAfter(True)
                banner.startAnimation(anim_set)
            except Exception as e:
                logx(f"NoInternetBanner: show animation error: {e}", False)

            self._visible = True
            logx("NoInternetBanner: banner shown", True)
        except Exception as e:
            logx(f"NoInternetBanner: _show_banner error: {e}", False)
            import traceback
            logx(traceback.format_exc(), True)

    def _hide_banner(self):
        """Hide the banner with a slide-up + fade-out animation."""
        if not self._visible or self.banner_view is None:
            return
        try:
            banner = self.banner_view

            # Slide-down + fade-out animation
            try:
                from java import dynamic_proxy
                from hook_utils import find_class

                anim_set = AnimationSet(True)
                anim_set.setInterpolator(AccelerateInterpolator())

                slide = TranslateAnimation(0, 0, 0, AndroidUtilities.dp(60))
                slide.setDuration(250)
                anim_set.addAnimation(slide)

                alpha = AlphaAnimation(1.0, 0.0)
                alpha.setDuration(250)
                anim_set.addAnimation(alpha)

                anim_set.setFillAfter(True)

                _banner_ref = banner
                _self = self

                AnimationListenerCls = find_class("android.view.animation.Animation$AnimationListener")

                class _AnimEndListener(dynamic_proxy(AnimationListenerCls)):
                    def __init__(self):
                        super().__init__()

                    def onAnimationEnd(self, animation):
                        run_on_ui_thread(lambda: _self._remove_banner(_banner_ref))

                    def onAnimationStart(self, animation):
                        pass

                    def onAnimationRepeat(self, animation):
                        pass

                anim_set.setAnimationListener(_AnimEndListener())
                banner.startAnimation(anim_set)
            except Exception as e:
                logx(f"NoInternetBanner: hide animation error: {e}", False)
                self._remove_banner(banner)

            self._visible = False
            logx("NoInternetBanner: banner hiding", True)
        except Exception as e:
            logx(f"NoInternetBanner: _hide_banner error: {e}", False)

    def _remove_banner(self, banner):
        """Remove the banner view from its parent."""
        try:
            if banner is not None:
                parent = banner.getParent()
                if parent is not None:
                    parent.removeView(banner)
            if self.banner_view is banner:
                self.banner_view = None
        except Exception as e:
            logx(f"NoInternetBanner: _remove_banner error: {e}", False)

    def _hide_immediate(self):
        """Remove banner immediately without animation (for cleanup)."""
        self._visible = False
        try:
            if self.banner_view is not None:
                self._remove_banner(self.banner_view)
                self.banner_view = None
        except Exception:
            pass

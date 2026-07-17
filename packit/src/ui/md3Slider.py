# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Wrapper around the host's MD3 slider cell (org.telegram.ui.Cells.
# SlideIntChooseView): pill track, animated center value and min/max labels,
# step vibration — the slider used across the host's own settings. Callers
# get an Md3Slider holder (view + set_value) or None when the host has no
# SlideIntChooseView, in which case they keep their plain-SeekBar fallback.

from packutil import logx


class Md3Slider:
    def __init__(self, view, options, callback):
        self.view = view
        # keep the java-side refs alive and available for re-set fallback
        self._options = options
        self._callback = callback

    def set_value(self, value, animated=False):
        # programmatic update (bind/reset paths); user drags never come here
        try:
            f = self.view.getClass().getDeclaredField("seekBarView")
            f.setAccessible(True)
            f.get(self.view).setProgress(self.view.getProgress(int(value)), bool(animated))
            self.view.updateTexts(int(value), bool(animated))
            return
        except Exception as e:
            logx(f"md3Slider: set_value reflection failed: {e}", True)
        try:
            # non-animated re-set through the public API
            self.view.set(int(value), self._options, self._callback)
        except Exception as e:
            logx(f"md3Slider: set_value fallback failed: {e}", False)


def createMd3Slider(ctx, min_val, max_val, value, on_change, to_string=None):
    """Builds the native MD3 slider.

    on_change(int) fires on user drags (only on actual value change).
    to_string(label_type, value) formats labels: 0 = center value,
    -1 = left/min, 1 = right/max; plain numbers when omitted.
    Returns Md3Slider or None (host without SlideIntChooseView).
    """
    try:
        from org.telegram.ui.Cells import SlideIntChooseView
        from org.telegram.messenger import Utilities
        from java import dynamic_proxy

        class _PlainFmt(dynamic_proxy(Utilities.CallbackReturn)):
            def run(self, val):
                return str(val)

        options = SlideIntChooseView.Options.make(
            0, int(min_val), int(max_val), _PlainFmt()
        )

        if to_string is not None:
            class _Fmt2(dynamic_proxy(Utilities.Callback2Return)):
                def run(self, label_type, val):
                    try:
                        res = to_string(int(label_type), int(val))
                        if res is not None:
                            return str(res)
                    except Exception as e:
                        logx(f"md3Slider: to_string error: {e}", True)
                    return str(val)

            # the public field is named "toString" — chaquopy resolves that
            # attribute to java.lang.Object.toString(), so assign via
            # reflection instead
            try:
                field = options.getClass().getDeclaredField("toString")
                field.setAccessible(True)
                field.set(options, _Fmt2())
            except Exception as e:
                logx(f"md3Slider: toString field set failed: {e}", False)

        class _OnChange(dynamic_proxy(Utilities.Callback)):
            def run(self, val_obj):
                try:
                    on_change(int(val_obj))
                except Exception as e:
                    logx(f"md3Slider: on_change error: {e}", False)

        callback = _OnChange()
        view = SlideIntChooseView(ctx, None)
        view.set(int(value), options, callback)
        return Md3Slider(view, options, callback)
    except Exception as e:
        logx(f"md3Slider: create failed: {e}", False)
        return None

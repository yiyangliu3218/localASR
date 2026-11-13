# -*- coding: utf-8 -*-
"""Small floating HUD shown while dictating: a red dot plus a live level meter while
recording, a soft grey wave while transcribing.

The window is a non-activating, click-through panel: it never takes keyboard focus,
so text still goes to the app you were typing in. All AppKit calls must happen on
the main thread (the app routes them through run_on_main).
"""
import math
import time

BARS = 11
WIDTH, HEIGHT = 112, 34
BAR_W, BAR_GAP = 3.0, 3.0
FPS = 30
CHECK_AFTER = 0.3  # seconds after showing before verifying the panel is really on screen


def level_to_unit(rms: float) -> float:
    """Maps microphone RMS to 0..1 on a dB scale: room noise ~0.05, normal
    speech ~0.4-0.7, loud speech ~1."""
    db = 20 * math.log10(max(rms, 1e-9))
    return min(1.0, max(0.0, (db + 45) / 35))


class Meter:
    """Smoothed, scrolling level history (newest bar on the right)."""

    def __init__(self, bars: int = BARS):
        self.values = [0.0] * bars
        self._level = 0.0

    def reset(self):
        self.values = [0.0] * len(self.values)
        self._level = 0.0

    def push(self, rms: float):
        target = level_to_unit(rms)
        # Rise fast, fall slowly, so syllables read as distinct bumps
        k = 0.6 if target > self._level else 0.25
        self._level += (target - self._level) * k
        self.values = self.values[1:] + [self._level]


def wave(t: float, bars: int = BARS):
    """Idle "thinking" animation for the transcribing state."""
    return [0.2 + 0.3 * (math.sin(t * 6 - i * 0.7) + 1) / 2 for i in range(bars)]


_VIEW_CLASS = None


def _view_class():
    """Defined lazily: an Objective-C class can only be registered once, and tests
    import this module without AppKit."""
    global _VIEW_CLASS
    if _VIEW_CLASS is not None:
        return _VIEW_CLASS
    import objc
    from AppKit import NSBezierPath, NSColor, NSMakeRect, NSView

    class HUDView(NSView):
        def initWithFrame_(self, frame):
            self = objc.super(HUDView, self).initWithFrame_(frame)
            if self is None:
                return None
            self.values = [0.0] * BARS
            self.recording = True
            return self

        def isOpaque(self):
            return False

        def drawRect_(self, rect):
            b = self.bounds()
            h = b.size.height
            NSColor.colorWithCalibratedWhite_alpha_(0.08, 0.86).set()
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, h / 2, h / 2).fill()

            if self.recording:
                d = 8.0
                NSColor.systemRedColor().set()
                NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(14.0, (h - d) / 2, d, d)).fill()
                x = 30.0
            else:  # no dot: centre the bars
                x = (b.size.width - (len(self.values) * (BAR_W + BAR_GAP) - BAR_GAP)) / 2
            bar_color = NSColor.whiteColor() if self.recording else NSColor.colorWithCalibratedWhite_alpha_(0.75, 1.0)
            bar_color.set()
            max_h = h - 14.0
            for v in self.values:
                bh = max(3.0, v * max_h)
                r = NSMakeRect(x, (h - bh) / 2, BAR_W, bh)
                NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, BAR_W / 2, BAR_W / 2).fill()
                x += BAR_W + BAR_GAP

    _VIEW_CLASS = HUDView
    return HUDView


class Overlay:
    """show_recording(level_fn) -> show_transcribing() -> hide(). Main thread only."""

    def __init__(self):
        self._panel = self._view = None
        self._build()
        self._meter = Meter()
        self._level_fn = None
        self._timer = None
        self._t0 = 0.0
        self._shown_at = None  # set while a visibility check is pending

    def _build(self):
        from AppKit import (
            NSBackingStoreBuffered,
            NSColor,
            NSMakeRect,
            NSPanel,
            NSStatusWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorStationary,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )

        rect = NSMakeRect(0, 0, WIDTH, HEIGHT)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered, False,
        )
        panel.setLevel_(NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setIgnoresMouseEvents_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setCanHide_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        self._view = _view_class().alloc().initWithFrame_(rect)
        panel.setContentView_(self._view)
        if self._panel is not None:
            self._panel.orderOut_(None)
        self._panel = panel

    def _place(self):
        """Bottom centre of the screen the mouse is on, just above the Dock."""
        from AppKit import NSEvent, NSMakePoint, NSPointInRect, NSScreen

        mouse = NSEvent.mouseLocation()
        screen = next((s for s in NSScreen.screens() if NSPointInRect(mouse, s.frame())),
                      NSScreen.mainScreen())
        vf = screen.visibleFrame()
        x = vf.origin.x + (vf.size.width - WIDTH) / 2
        y = vf.origin.y + 28
        self._panel.setFrameOrigin_(NSMakePoint(x, y))

    def _start_timer(self):
        if self._timer is not None:
            return
        from Foundation import NSRunLoop, NSRunLoopCommonModes, NSTimer

        self._timer = NSTimer.timerWithTimeInterval_repeats_block_(1.0 / FPS, True, lambda t: self._tick())
        NSRunLoop.currentRunLoop().addTimer_forMode_(self._timer, NSRunLoopCommonModes)

    def _stop_timer(self):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None

    def _check_visible(self):
        """After a long run the window server sometimes stops putting the panel on
        screen while AppKit still reports it as shown. Detect that from the
        occlusion state and rebuild the panel once."""
        from AppKit import NSWindowOcclusionStateVisible

        if self._shown_at is None or time.monotonic() - self._shown_at < CHECK_AFTER:
            return
        self._shown_at = None
        p = self._panel
        if p.occlusionState() & NSWindowOcclusionStateVisible:
            return
        print(f"[overlay] not on screen after show (isVisible={p.isVisible()}, "
              f"onActiveSpace={p.isOnActiveSpace()}, occlusion={p.occlusionState()}, "
              f"window={p.windowNumber()}, frame={tuple(p.frame().origin)}); rebuilding", flush=True)
        recording, values = self._view.recording, self._view.values
        self._build()
        self._view.recording, self._view.values = recording, values
        self._place()
        self._panel.orderFrontRegardless()

    def _tick(self):
        self._check_visible()
        if self._view.recording:
            self._meter.push(self._level_fn() if self._level_fn else 0.0)
            self._view.values = list(self._meter.values)
        else:
            self._view.values = wave(time.monotonic() - self._t0)
        self._view.setNeedsDisplay_(True)

    def show_recording(self, level_fn):
        self._level_fn = level_fn
        self._meter.reset()
        self._view.recording = True
        self._view.values = list(self._meter.values)
        self._place()
        self._view.setNeedsDisplay_(True)
        self._panel.orderFrontRegardless()  # shows without activating our app
        self._shown_at = time.monotonic()
        self._start_timer()

    def show_transcribing(self):
        self._view.recording = False
        self._t0 = time.monotonic()
        self._view.setNeedsDisplay_(True)

    def hide(self):
        self._shown_at = None
        self._stop_timer()
        self._panel.orderOut_(None)

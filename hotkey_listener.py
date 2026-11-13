# -*- coding: utf-8 -*-
"""Globally listens for Fn key down/up events, regardless of which app has focus.

Uses an event tap on flagsChanged events, watching the SecondaryFn flag.
With SUPPRESS_FN_SYSTEM_ACTION the tap swallows only the events where the Fn
bit itself flips, so macOS doesn't also pop up the emoji picker / switch input
source on release. Every other event passes through unchanged. If an active tap
can't be created, it falls back to a read-only (ListenOnly) tap.
"""
import time

from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CGEventGetFlags,
    CGEventMaskBit,
    CGEventTapCreate,
    CGEventTapEnable,
    kCFRunLoopCommonModes,
    kCGEventFlagMaskSecondaryFn,
    kCGEventFlagsChanged,
    kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput,
    kCGEventTapOptionDefault,
    kCGEventTapOptionListenOnly,
    kCGHeadInsertEventTap,
    kCGHIDEventTap,
)

from config import MIN_PRESS_MS, SUPPRESS_FN_SYSTEM_ACTION


class FnHotkeyListener:
    def __init__(self, on_press, on_release):
        """on_press(): called right when Fn goes down.
        on_release(valid: bool): called when Fn is released; valid=False means the
        press was too short and this recording should be discarded.
        """
        self._on_press = on_press
        self._on_release = on_release
        self._fn_down = False
        self._press_time = 0.0
        self._tap = None
        self._swallow = False

    def _callback(self, proxy, event_type, event, refcon):
        if event_type in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput):
            CGEventTapEnable(self._tap, True)
            return event

        flags = CGEventGetFlags(event)
        is_down = bool(flags & kCGEventFlagMaskSecondaryFn)

        fn_flipped = is_down != self._fn_down

        if is_down and not self._fn_down:
            self._fn_down = True
            self._press_time = time.monotonic()
            self._on_press()
        elif not is_down and self._fn_down:
            self._fn_down = False
            held_ms = (time.monotonic() - self._press_time) * 1000
            print(f"[诊断] Fn 按住 {held_ms:.0f} ms", flush=True)
            self._on_release(held_ms >= MIN_PRESS_MS)

        if fn_flipped and self._swallow:
            return None  # keep the globe-key action (emoji picker etc.) from firing
        return event

    def start(self):
        def create(option):
            return CGEventTapCreate(
                kCGHIDEventTap,
                kCGHeadInsertEventTap,
                option,
                CGEventMaskBit(kCGEventFlagsChanged),
                self._callback,
                None,
            )

        self._tap = None
        if SUPPRESS_FN_SYSTEM_ACTION:
            self._tap = create(kCGEventTapOptionDefault)
            self._swallow = self._tap is not None
            if self._tap is None:
                print("[hotkey] can't intercept Fn (no Accessibility permission?); "
                      "the system Fn action (e.g. emoji picker) will still fire", flush=True)
        if self._tap is None:
            self._tap = create(kCGEventTapOptionListenOnly)
        if self._tap is None:
            raise RuntimeError(
                "无法创建全局按键监听。请打开 系统设置 > 隐私与安全性，"
                "在「辅助功能」和「输入监控」里都允许当前使用的终端 App（如 Terminal / iTerm），"
                "然后重新运行本程序。"
            )
        run_loop_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)

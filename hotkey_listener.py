# -*- coding: utf-8 -*-
"""Globally listens for Fn key down/up events, regardless of which app has focus.

Uses a ListenOnly-mode event tap on flagsChanged events, watching the
SecondaryFn flag. It's read-only and never intercepts the event, so it
doesn't interfere with any other system use of the Fn key.
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
    kCGEventTapOptionListenOnly,
    kCGHeadInsertEventTap,
    kCGHIDEventTap,
)

from config import MIN_PRESS_MS


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

    def _callback(self, proxy, event_type, event, refcon):
        if event_type in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput):
            CGEventTapEnable(self._tap, True)
            return event

        flags = CGEventGetFlags(event)
        is_down = bool(flags & kCGEventFlagMaskSecondaryFn)

        if is_down and not self._fn_down:
            self._fn_down = True
            self._press_time = time.monotonic()
            self._on_press()
        elif not is_down and self._fn_down:
            self._fn_down = False
            held_ms = (time.monotonic() - self._press_time) * 1000
            self._on_release(held_ms >= MIN_PRESS_MS)

        return event

    def start(self):
        self._tap = CGEventTapCreate(
            kCGHIDEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            CGEventMaskBit(kCGEventFlagsChanged),
            self._callback,
            None,
        )
        if self._tap is None:
            raise RuntimeError(
                "无法创建全局按键监听。请打开 系统设置 > 隐私与安全性，"
                "在「辅助功能」和「输入监控」里都允许当前使用的终端 App（如 Terminal / iTerm），"
                "然后重新运行本程序。"
            )
        run_loop_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)

# -*- coding: utf-8 -*-
"""全局监听 Fn 键的按下 / 松开，不管当前焦点在哪个 App 上都能收到。

用 ListenOnly 模式的事件龙头 (event tap) 监听 flagsChanged 事件里的
SecondaryFn 标志位，只读不拦截，不会影响系统自身对 Fn 键的其他用途。
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
        """on_press(): Fn 刚按下时调用
        on_release(valid: bool): Fn 松开时调用；valid=False 表示按下时间太短，应忽略本次录音
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

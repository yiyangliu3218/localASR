# -*- coding: utf-8 -*-
"""把转录出的文字输出出去：
一律尝试直接"打字"到当前光标所在的位置；
只有在检测不到可编辑光标时，才额外把文本放进剪贴板兜底。
"""
import pyperclip
from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateSystemWide,
    AXUIElementIsAttributeSettable,
    kAXFocusedApplicationAttribute,
    kAXFocusedUIElementAttribute,
    kAXValueAttribute,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventKeyboardSetUnicodeString,
    CGEventPost,
    kCGHIDEventTap,
)

_SYSTEM_WIDE = AXUIElementCreateSystemWide()


def _has_focused_editable_element() -> bool:
    """查询系统当前聚焦的 UI 元素，判断它是否是一个可以写入文字的输入框。
    仅用于决定要不要额外存一份到剪贴板，不用于决定要不要打字（打字总是会尝试）。
    """
    err, focused_app = AXUIElementCopyAttributeValue(
        _SYSTEM_WIDE, kAXFocusedApplicationAttribute, None
    )
    if err != 0 or focused_app is None:
        return False

    err, focused_elem = AXUIElementCopyAttributeValue(
        focused_app, kAXFocusedUIElementAttribute, None
    )
    if err != 0 or focused_elem is None:
        return False

    err, settable = AXUIElementIsAttributeSettable(focused_elem, kAXValueAttribute, None)
    return err == 0 and bool(settable)


def _type_text(text: str):
    """用模拟键盘事件把整段文字"打"到当前光标处，支持中英文 unicode。"""
    down = CGEventCreateKeyboardEvent(None, 0, True)
    CGEventKeyboardSetUnicodeString(down, len(text), text)
    CGEventPost(kCGHIDEventTap, down)

    up = CGEventCreateKeyboardEvent(None, 0, False)
    CGEventKeyboardSetUnicodeString(up, len(text), text)
    CGEventPost(kCGHIDEventTap, up)


def output_text(text: str, auto_type: bool = True, always_copy: bool = False) -> str:
    """返回值: "typed" / "typed_and_clipboard" / "clipboard_only" / "empty"，供调用方更新菜单栏状态用。"""
    text = text.strip()
    if not text:
        return "empty"

    if not auto_type:
        pyperclip.copy(text)
        return "clipboard_only"

    _type_text(text)

    if always_copy or not _has_focused_editable_element():
        pyperclip.copy(text)
        return "typed_and_clipboard"

    return "typed"

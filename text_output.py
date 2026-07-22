# -*- coding: utf-8 -*-
"""Delivers the transcribed text to the user:
always tries to "type" it directly at the current cursor position;
only additionally copies it to the clipboard when no editable cursor is found.
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
    """Checks the system's currently focused UI element to see whether it's a
    writable text field. Only used to decide whether to also copy to the
    clipboard, never to decide whether to type (typing is always attempted).
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
    """Types the whole string at the current cursor via synthetic keyboard
    events; supports arbitrary Unicode (Chinese, English, etc.)."""
    down = CGEventCreateKeyboardEvent(None, 0, True)
    CGEventKeyboardSetUnicodeString(down, len(text), text)
    CGEventPost(kCGHIDEventTap, down)

    up = CGEventCreateKeyboardEvent(None, 0, False)
    CGEventKeyboardSetUnicodeString(up, len(text), text)
    CGEventPost(kCGHIDEventTap, up)


def output_text(text: str, auto_type: bool = True, always_copy: bool = False) -> str:
    """Returns "typed" / "typed_and_clipboard" / "clipboard_only" / "empty",
    for the caller to update the menu bar status."""
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

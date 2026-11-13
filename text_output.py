# -*- coding: utf-8 -*-
"""Delivers the transcribed text to the user:
always tries to "type" it directly at the current cursor position;
only additionally copies it to the clipboard when no editable cursor is found.
"""
import time

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
    CGEventSetFlags,
    kCGHIDEventTap,
)

_SYSTEM_WIDE = AXUIElementCreateSystemWide()

# macOS silently truncates the string attached to one synthetic key event to
# 20 UTF-16 code units, so longer text must be sent as several events.
MAX_UTF16_PER_EVENT = 20


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


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def split_for_typing(text: str, limit: int = MAX_UTF16_PER_EVENT):
    """Splits text into pieces of at most `limit` UTF-16 code units without ever
    cutting a surrogate pair (emoji etc.) in half."""
    pieces, cur, cur_len = [], [], 0
    for ch in text:
        n = 2 if ord(ch) > 0xFFFF else 1
        if cur_len + n > limit:
            pieces.append("".join(cur))
            cur, cur_len = [], 0
        cur.append(ch)
        cur_len += n
    if cur:
        pieces.append("".join(cur))
    return pieces


def _type_text(text: str):
    """Types the string at the current cursor via synthetic keyboard events;
    supports arbitrary Unicode (Chinese, English, emoji)."""
    for piece in split_for_typing(text):
        n = utf16_len(piece)  # the API counts UTF-16 units, not Python code points
        for key_down in (True, False):
            ev = CGEventCreateKeyboardEvent(None, 0, key_down)
            # Don't inherit modifiers currently held (e.g. Fn while typing live)
            CGEventSetFlags(ev, 0)
            CGEventKeyboardSetUnicodeString(ev, n, piece)
            CGEventPost(kCGHIDEventTap, ev)
        time.sleep(0.002)  # let the target app keep up; avoids dropped/reordered chunks


def output_text(text: str, auto_type: bool = True, always_copy: bool = False) -> str:
    """Returns "typed" / "typed_and_clipboard" / "clipboard_only" / "empty",
    for the caller to update the menu bar status."""
    text = text.strip()
    if not text:
        return "empty"

    if not auto_type:
        pyperclip.copy(text)
        return "clipboard_only"

    # Check focus *before* typing: afterwards the answer can change under us
    editable = _has_focused_editable_element()
    _type_text(text)

    if always_copy or not editable:
        pyperclip.copy(text)
        return "typed_and_clipboard"

    return "typed"

# -*- coding: utf-8 -*-
from unittest import mock

import pytest

import text_output as to


def typed(events):
    downs = [e for e in events.posted if e["down"]]
    return "".join(e["text"] for e in downs)


@pytest.mark.parametrize("text", [
    "hello",
    "你好，今天我们 review 一下这个 PR 吧。" * 5,          # long mixed text (> 20 units)
    "emoji 😀 at the boundary 😀😀😀😀😀😀😀😀😀😀😀😀",       # surrogate pairs
])
def test_long_and_unicode_text_is_fully_typed(events, text):
    to._type_text(text)
    assert typed(events) == text
    for ev in events.posted:
        assert ev["len"] == to.utf16_len(ev["text"])            # UTF-16 length, not len()
        assert ev["len"] <= to.MAX_UTF16_PER_EVENT              # macOS truncates above 20
        assert ev["flags"] == 0                                 # never inherit Fn/Shift


def test_split_never_breaks_surrogate_pairs():
    pieces = to.split_for_typing("a" * 19 + "😀" + "b")
    assert pieces == ["a" * 19, "😀b"]


def test_every_key_down_has_matching_key_up(events):
    to._type_text("x" * 45)
    flags = [e["down"] for e in events.posted]
    assert flags == [True, False] * 3


def test_output_empty_text_does_nothing(events):
    assert to.output_text("   ") == "empty"
    assert events.posted == []


def test_clipboard_only_mode(events):
    with mock.patch.object(to.pyperclip, "copy") as copy:
        assert to.output_text(" hi ", auto_type=False) == "clipboard_only"
    copy.assert_called_once_with("hi")
    assert events.posted == []


def test_no_editable_focus_falls_back_to_clipboard(events):
    with mock.patch.object(to, "_has_focused_editable_element", return_value=False), \
         mock.patch.object(to.pyperclip, "copy") as copy:
        assert to.output_text("hi") == "typed_and_clipboard"
    copy.assert_called_once_with("hi")


def test_focus_is_checked_before_typing(events):
    order = []
    check = mock.patch.object(to, "_has_focused_editable_element",
                              side_effect=lambda: order.append("check") or True)
    with check, mock.patch.object(to, "_type_text", side_effect=lambda t: order.append("type")):
        assert to.output_text("hi") == "typed"
    assert order == ["check", "type"]

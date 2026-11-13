# -*- coding: utf-8 -*-
"""Installs fake macOS-only modules so the app's logic can be tested on any OS / CI."""
import os
import sys
import types
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _fake(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Events:
    """Records synthetic key events posted through the fake Quartz API."""

    def __init__(self):
        self.posted = []

    def create(self, src, keycode, down):
        return {"down": down, "text": None, "len": None, "flags": None}

    def set_unicode(self, ev, n, s):
        ev["len"], ev["text"] = n, s

    def set_flags(self, ev, f):
        ev["flags"] = f

    def post(self, tap, ev):
        self.posted.append(ev)


EVENTS = _Events()

for _name in ("Quartz", "ApplicationServices", "AppKit", "Foundation", "rumps", "sounddevice",
              "pyperclip"):
    if _name not in sys.modules or isinstance(sys.modules[_name], mock.MagicMock):
        sys.modules[_name] = mock.MagicMock(name=_name)

sys.modules["Quartz"].CGEventCreateKeyboardEvent = EVENTS.create
sys.modules["Quartz"].CGEventKeyboardSetUnicodeString = EVENTS.set_unicode
sys.modules["Quartz"].CGEventSetFlags = EVENTS.set_flags
sys.modules["Quartz"].CGEventPost = EVENTS.post
sys.modules["ApplicationServices"].AXUIElementCopyAttributeValue = lambda *a: (0, object())
sys.modules["ApplicationServices"].AXUIElementIsAttributeSettable = lambda *a: (0, True)


class _RumpsApp:
    def __init__(self, *a, title=None, **k):
        self.title = title
        self._menu = mock.MagicMock()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, items):  # rumps accepts a list on assignment
        pass


sys.modules["rumps"].App = _RumpsApp
# Main-queue dispatch runs inline in tests
sys.modules["Foundation"].NSOperationQueue.mainQueue.return_value.addOperationWithBlock_ = (
    lambda fn: fn()
)


@pytest.fixture
def events():
    EVENTS.posted.clear()
    return EVENTS


MODELS_ROOT = os.environ.get("LOCALASR_MODELS", os.path.expanduser("~/.cache/localasr/models"))

# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preference storage, against a stand-in FreeCAD parameter tree."""

from __future__ import annotations

import sys
import types

import pytest

from freecad_timeline import settings


class FakeParameterGroup:
    def __init__(self, store=None):
        self.store = {} if store is None else store
        self.reads = []

    def GetBool(self, name, default=False):
        self.reads.append(name)
        return self.store.get(name, default)

    def SetBool(self, name, value):
        self.store[name] = bool(value)


@pytest.fixture
def parameters(monkeypatch):
    group = FakeParameterGroup()
    module = types.ModuleType("FreeCAD")
    module.ParamGet = lambda path: group if path == settings.PARAMETER_PATH else None
    monkeypatch.setitem(sys.modules, "FreeCAD", module)
    return group


def test_round_trip(parameters):
    assert settings.get_bool(settings.VISIBLE, True) is True

    settings.set_bool(settings.VISIBLE, False)
    assert parameters.store[settings.VISIBLE] is False
    assert settings.get_bool(settings.VISIBLE, True) is False


def test_defaults_are_returned_for_unset_keys(parameters):
    assert settings.get_bool("Nope", True) is True
    assert settings.get_bool("Nope", False) is False


def test_uses_the_addon_parameter_path(parameters):
    assert settings.PARAMETER_PATH.endswith("Mod/Timeline")
    assert settings.parameter_group() is parameters


def test_degrades_without_freecad(monkeypatch):
    """Headless (or a broken parameter tree) must not raise."""
    monkeypatch.setitem(sys.modules, "FreeCAD", None)

    assert settings.parameter_group() is None
    assert settings.get_bool(settings.VISIBLE, True) is True
    settings.set_bool(settings.VISIBLE, False)  # no-op, no exception


def test_degrades_when_paramget_raises(monkeypatch):
    module = types.ModuleType("FreeCAD")

    def boom(_path):
        raise RuntimeError("parameter tree unavailable")

    module.ParamGet = boom
    monkeypatch.setitem(sys.modules, "FreeCAD", module)

    assert settings.get_bool(settings.SHOW_NON_SOLID, False) is False
    settings.set_bool(settings.SHOW_NON_SOLID, True)


def test_degrades_when_the_group_raises(monkeypatch):
    class Angry:
        def GetBool(self, name, default=False):
            raise RuntimeError("nope")

        def SetBool(self, name, value):
            raise RuntimeError("nope")

    module = types.ModuleType("FreeCAD")
    module.ParamGet = lambda _path: Angry()
    monkeypatch.setitem(sys.modules, "FreeCAD", module)

    assert settings.get_bool(settings.VISIBLE, True) is True
    settings.set_bool(settings.VISIBLE, False)

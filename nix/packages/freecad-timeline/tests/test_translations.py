# SPDX-License-Identifier: LGPL-2.1-or-later
"""Translation plumbing: catalogue discovery, registration, and that the
strings really do route through Qt's translator."""

from __future__ import annotations

import sys
import types

import pytest

from freecad_timeline import translations


def test_translations_directory_ships_with_the_addon():
    import os

    assert os.path.isdir(translations.TRANSLATIONS_DIRECTORY)


def test_available_locales_lists_compiled_catalogues(tmp_path):
    (tmp_path / "Timeline_de.qm").write_bytes(b"")
    (tmp_path / "Timeline_es-ES.qm").write_bytes(b"")
    (tmp_path / "Timeline_fr.ts").write_text("")  # source, not compiled
    (tmp_path / "Other_de.qm").write_bytes(b"")  # not ours

    assert translations.available_locales(str(tmp_path)) == ["de", "es-ES"]


def test_available_locales_of_a_missing_directory():
    assert translations.available_locales("/nonexistent/path") == []


def test_install_registers_the_path_with_freecad(monkeypatch, tmp_path):
    registered = []
    module = types.ModuleType("FreeCADGui")
    module.addLanguagePath = registered.append
    monkeypatch.setitem(sys.modules, "FreeCADGui", module)

    assert translations.install(str(tmp_path)) is True
    assert registered == [str(tmp_path)]


def test_install_is_a_noop_without_freecad(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "FreeCADGui", None)
    assert translations.install(str(tmp_path)) is False


def test_install_is_a_noop_without_a_directory():
    assert translations.install("/nonexistent/path") is False


# --------------------------------------------------------------------------
# the strings actually go through Qt
# --------------------------------------------------------------------------

pytest.importorskip("freecad_timeline.qtcompat", reason="no Qt binding available")

from freecad_timeline.qtcompat import CONTEXT, QtCore, translate  # noqa: E402


class RecordingTranslator(QtCore.QTranslator):
    """Answers every lookup so we can prove the call reached the translator."""

    def __init__(self):
        super().__init__()
        self.seen = []

    def translate(self, context, source, disambiguation=None, n=-1):
        self.seen.append((context, source))
        if context != CONTEXT:
            return ""
        return f"<<{source}>>"


def test_strings_route_through_the_translator(qapp):
    translator = RecordingTranslator()
    QtCore.QCoreApplication.installTranslator(translator)
    try:
        assert translate("Set tip here") == "<<Set tip here>>"
        assert (CONTEXT, "Set tip here") in translator.seen
    finally:
        QtCore.QCoreApplication.removeTranslator(translator)

    # Removed again, we are back to the source string.
    assert translate("Set tip here") == "Set tip here"


def test_menu_and_placeholder_strings_are_translated(qapp):
    from freecad_timeline.panel import placeholder_empty, placeholder_no_body

    translator = RecordingTranslator()
    QtCore.QCoreApplication.installTranslator(translator)
    try:
        assert placeholder_no_body().startswith("<<")
        assert placeholder_empty().startswith("<<")
    finally:
        QtCore.QCoreApplication.removeTranslator(translator)


def test_placeholders_are_resolved_per_call_not_at_import(qapp):
    """FreeCAD can set the language after the module is imported."""
    from freecad_timeline.panel import placeholder_no_body

    plain = placeholder_no_body()
    translator = RecordingTranslator()
    QtCore.QCoreApplication.installTranslator(translator)
    try:
        assert placeholder_no_body() != plain
    finally:
        QtCore.QCoreApplication.removeTranslator(translator)


def test_plural_forms_substitute_the_count(qapp):
    assert translate("Delete %n feature(s)?", None, 1) == "Delete 1 feature(s)?"
    assert translate("Delete %n feature(s)?", None, 4) == "Delete 4 feature(s)?"

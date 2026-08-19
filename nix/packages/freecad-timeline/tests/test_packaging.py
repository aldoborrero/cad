# SPDX-License-Identifier: LGPL-2.1-or-later
"""Packaging invariants.

The version lives in package.xml (the Addon Manager's canonical metadata) and
is read from there by the nix derivation. ``__version__`` is the one remaining
copy, so it gets pinned here rather than left to drift.
"""

from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ElementTree

import pytest

import freecad_timeline

ADDON = pathlib.Path(__file__).resolve().parent.parent
PACKAGE_XML = ADDON / "package.xml"
NIX_PACKAGE = (
    ADDON.parent.parent / "nix" / "packages" / "freecad-timeline" / "package.nix"
)


def _strip_namespace(tag: str) -> str:
    """``{https://wiki.freecad.org/Package_Metadata}version`` -> ``version``.

    package.xml declares a default namespace, so plain ``find("version")``
    silently returns None.
    """
    return tag.rpartition("}")[2]


def _child(element, name):
    for child in element:
        if _strip_namespace(child.tag) == name:
            return child
    return None


def _package_xml_version() -> str:
    root = ElementTree.parse(PACKAGE_XML).getroot()
    # The top-level <version>, not the one inside <content>.
    return _child(root, "version").text.strip()


def test_package_xml_version_matches_the_python_package():
    assert freecad_timeline.__version__ == _package_xml_version()


def test_content_item_version_matches_too():
    root = ElementTree.parse(PACKAGE_XML).getroot()
    content = _child(root, "content")
    assert content is not None, "the Addon Manager needs a <content> block"
    seen = 0
    for item in content:
        version = _child(item, "version")
        if version is not None:
            seen += 1
            # The nix derivation regexes the file, so a mismatch here would
            # make the store path disagree with the metadata.
            assert version.text.strip() == _package_xml_version()
    assert seen, "no versioned content item found"


@pytest.mark.skipif(not NIX_PACKAGE.exists(), reason="nix packaging not present")
def test_nix_does_not_hardcode_the_version():
    """It must read package.xml, not carry a fourth copy of the number."""
    text = NIX_PACKAGE.read_text()
    assert 'readFile (source + "/package.xml")' in text
    assert not re.search(r'version\s*=\s*"[0-9]+\.[0-9]+', text)


def test_declared_freecad_minimum_is_present():
    root = ElementTree.parse(PACKAGE_XML).getroot()
    assert _child(root, "freecadmin") is not None, "the Addon Manager needs a floor"


def test_shipped_files_exist():
    """What the nix derivation asserts at build time, checked here too."""
    for name in ("InitGui.py", "package.xml", "LICENSE", "freecad_timeline"):
        assert (ADDON / name).exists(), name


def test_test_scaffolding_is_excluded_from_the_package():
    """Anything listed as not-shipped in package.nix must really be scaffolding
    — if one of these ever becomes runtime code, the exclusion would break the
    addon silently."""
    if not NIX_PACKAGE.exists():
        pytest.skip("nix packaging not present")
    excluded = re.findall(r'^\s+"([^"]+)"$', NIX_PACKAGE.read_text(), re.M)
    runtime = {"InitGui.py", "package.xml", "freecad_timeline", "resources", "LICENSE"}
    assert runtime.isdisjoint(excluded)

"""KiCad's `.stpZ` — a ZIP holding one STEP file — for FreeCAD.

kicadStepUp calls `stepZ.insert(path, doc)` for every footprint model whose path ends in
`.stpZ`, and under Nix every model does: nixpkgs builds kicad-packages3d by running
`zip -j -9` over each `.step` and then rewrites the footprint library to match
(`pkgs/by-name/ki/kicad/libraries.nix`). All 7241 models in the library are `.stpZ` and
nothing else, and FreeCAD ships no importer for that extension — so without this module
a board imports with its outline and not one component.

Upstream's addon of the same name (easyw/stepZ, last touched 2018) cannot fill the gap,
twice over: it opens the container with gzip where nixpkgs writes a PKZIP archive, and
the `gzip_utf8` helper it imports at module scope begins `import __builtin__`, so on the
CPython 3.14 FreeCAD embeds it does not import at all. This is a reimplementation
against the three entry points kicadStepUp and FreeCAD's importer registry call.

`ImportGui` is imported inside the functions, not at module scope: it exists only in a
running FreeCAD GUI, and keeping it out of the import path is what lets the tests next
to this file exercise the packing and unpacking without one.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Sequence
from typing import Any

SUFFIX = ".stpZ"
_STEP_SUFFIXES = (".step", ".stp")


def _member(archive: zipfile.ZipFile) -> str:
    """The name of the STEP inside the archive.

    KiCad's archives hold exactly one file, stored under its bare basename because
    nixpkgs zips with `-j`. Preferring a STEP suffix over the first entry keeps a
    hand-made archive carrying a stray README working.
    """
    names = [n for n in archive.namelist() if not n.endswith("/")]
    if not names:
        raise ValueError(f"{archive.filename}: archive holds no file")
    steps = [n for n in names if n.lower().endswith(_STEP_SUFFIXES)]
    return steps[0] if steps else names[0]


def _unpack(filename: str) -> str:
    """Extract the STEP to a temporary file and return its path.

    The caller removes it. OCCT reads STEP from a path rather than from bytes, so
    there is no version of this that avoids the round trip through the filesystem.
    """
    with zipfile.ZipFile(filename) as archive:
        data = archive.read(_member(archive))
    fd, path = tempfile.mkstemp(prefix="stepz-", suffix=".step")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return path


def _pack(step: str, filename: str) -> None:
    """Zip `step` into `filename`, named as KiCad and `zip -j` both name it."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    with zipfile.ZipFile(
        filename, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.write(step, stem + ".step")


def open(filename: str) -> None:
    """Open a `.stpZ` as a new document.

    Shadows the builtin on purpose: this is the name FreeCAD's importer registry calls.
    Nothing in this module needs the builtin — the unpacking goes through os.fdopen.
    """
    import ImportGui

    path = _unpack(filename)
    try:
        ImportGui.open(path)
    finally:
        os.unlink(path)


def insert(filename: str, doc: str) -> None:
    """Insert a `.stpZ` into the named document.

    This is the one kicadStepUp's model loader calls, once per footprint.
    """
    import ImportGui

    path = _unpack(filename)
    try:
        ImportGui.insert(path, doc)
    finally:
        os.unlink(path)


def export(objs: Sequence[Any], filename: str) -> None:
    """Write the objects as a STEP, compressed into `filename`.

    Reached when kicadStepUp's `stpz_export_enabled` preference is on, and from
    File -> Export via the type `Init.py` registers.
    """
    import ImportGui

    fd, path = tempfile.mkstemp(prefix="stepz-", suffix=".step")
    os.close(fd)
    try:
        ImportGui.export(list(objs), path)
        _pack(path, filename)
    finally:
        os.unlink(path)

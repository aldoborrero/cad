"""Export the visible objects to 3MF and hand the file to the slicer."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import zipfile
from collections.abc import Callable, Sequence
from typing import Any

# A FreeCAD document object. There are no stubs for these, so the name is what
# carries the meaning.
DocumentObject = Any

MODEL_ENTRY = "3D/3dmodel.model"
_ITEM = re.compile(r"<item\b[^>]*>")
_TRANSFORM = re.compile(r'\btransform="([^"]*)"')

# What may stay in a filename. FreeCAD accepts anything in an object's Label,
# separators and ".." included, and joining one into a path wrote the file
# somewhere else entirely.
_UNSAFE = re.compile(r"[^\w .,()\[\]+#-]+", re.UNICODE)


class SlicerNotFound(Exception):
    """Neither the configured executable nor one on PATH."""


def safe_stem(label: str) -> str:
    """A label reduced to something that can only be a filename.

    Separators and traversal go, because FreeCAD lets a Label hold them and the
    file has to land in the directory it was promised to.
    """
    stem = _UNSAFE.sub("-", label).strip(" .-")
    return stem or "part"


def export_paths(labels: Sequence[str], directory: str, suffix: str) -> list[str]:
    """One path per label, inside `directory`, all distinct.

    Duplicate labels are allowed in FreeCAD behind a preference, and two parts
    sharing one had silently become one file sent twice.
    """
    paths = []
    taken: set[str] = set()
    for label in labels:
        stem = safe_stem(label)
        candidate = stem
        n = 2
        while candidate.casefold() in taken:
            candidate = f"{stem} ({n})"
            n += 1
        taken.add(candidate.casefold())
        paths.append(os.path.join(directory, candidate + suffix))
    return paths


def output_path(document_filename: str, document_label: str, tmpdir: str) -> str:
    """Where the 3MF goes: exports/ beside a saved document, tmpdir otherwise."""
    name = safe_stem(document_label) + ".3mf"
    if document_filename:
        return os.path.join(os.path.dirname(document_filename), "exports", name)
    return os.path.join(tmpdir, name)


# Bambu Studio first: it is the one that knows Bambu printers. OrcaSlicer is a
# fork of it, takes files the same way, and its GUI reads both 3MF and STEP —
# only its --info path is picky. It is also free software, so unlike Bambu Studio
# it can simply be installed alongside.
SLICERS: tuple[str, ...] = ("bambu-studio", "orca-slicer")
EXECUTABLES: dict[str, str] = {"bambu": "bambu-studio", "orca": "orca-slicer"}

Which = Callable[..., str | None]
Exists = Callable[[str], bool]


def slicer_command(
    preference: str,
    which: Which = shutil.which,
    preferred: str | None = None,
    exists: Exists = os.path.exists,
) -> list[str]:
    """How to start the slicer, as argv.

    The preference is a command line, not just a path: a slicer installed
    through flatpak is `flatpak run com.bambulab.BambuStudio`, and an AppImage
    usually sits behind a wrapper. A bare path is still a bare path — a name
    that exists on disk is taken whole, spaces and all, before any splitting,
    so "/opt/My Slicer/bin/slicer" does not become three arguments.
    """
    if preference:
        expanded = os.path.expanduser(os.path.expandvars(preference))
        if exists(expanded):
            return [expanded]
        parts = shlex.split(expanded)
        if not parts:
            raise SlicerNotFound("the configured slicer command is empty")
        head = parts[0] if exists(parts[0]) else which(parts[0])
        if not head:
            raise SlicerNotFound(
                f"{parts[0]} is neither a file nor on PATH; the preference takes "
                "a path or a command line"
            )
        return [head, *parts[1:]]

    order = list(SLICERS)
    if preferred in EXECUTABLES:
        order.remove(EXECUTABLES[preferred])
        order.insert(0, EXECUTABLES[preferred])
    for name in order:
        found = which(name)
        if found:
            return [found]
    raise SlicerNotFound(
        "none of " + ", ".join(SLICERS) + " on PATH; set a path or a command "
        "line in the addon preferences"
    )


def launch(command: Sequence[str], paths: Sequence[str]) -> None:
    """Start the slicer on those files, turning a bad path into a plain message.

    A configured executable that is not there is the likeliest way this fails, and
    an OSError traceback in the report view says nothing useful about it.
    """
    try:
        subprocess.Popen([*command, *paths])
    except OSError as exc:
        raise SlicerNotFound(
            f"could not run {shlex.join(command)}: {exc.strerror}"
        ) from exc


def export_and_open(
    objects: Sequence[DocumentObject],
    path: str,
    command: Sequence[str],
    transform: str | None = None,
    tolerance: float | None = None,
) -> str:
    """Write the objects to `path` as 3MF and hand the file to the slicer.

    FreeCAD is imported here, not at module scope, so the rest of this module
    stays importable under pytest with no FreeCAD around.
    """
    import Mesh

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if tolerance:
        Mesh.export(objects, path, tolerance=tolerance)
    else:
        Mesh.export(objects, path)
    if transform:
        lay_out(path, transform)
    launch(command, [path])
    return path


def export_step_and_open(
    objects: Sequence[DocumentObject], directory: str, command: Sequence[str]
) -> list[str]:
    """One STEP per object, all handed to the slicer at once.

    Exact geometry, tessellated by the slicer with its own setting, and each part
    arrives named — a foreign file with a single object takes its name from the
    filename, which is why one file per part is what earns the names.

    The layout does not survive: Plater.cpp re-centres every object that does not
    come from a 3MF or AMF, so this trades the bed arrangement for the other two.
    """
    import ImportGui

    os.makedirs(directory, exist_ok=True)
    paths = export_paths([obj.Label for obj in objects], directory, ".step")
    for obj, path in zip(objects, paths, strict=True):
        ImportGui.export([obj], path)
    launch(command, paths)
    return paths


Rows = list[list[float]]


def _unpack(transform: str) -> tuple[Rows, list[float]]:
    """Twelve 3MF numbers as (rotation rows, translation).

    Writer3MF::DumpMatrix writes the spec's transposed form: three numbers per
    column of the 3x3, then the translation. Reading it back row-wise is the
    silent bug this indirection exists to prevent.
    """
    n = [float(v) for v in transform.split()]
    if len(n) != 12:
        raise ValueError(f"expected twelve numbers, got {len(n)}")
    rows = [[n[0], n[3], n[6]], [n[1], n[4], n[7]], [n[2], n[5], n[8]]]
    return rows, [n[9], n[10], n[11]]


def _pack(rows: Rows, translation: Sequence[float]) -> str:
    numbers = [rows[i][j] for j in range(3) for i in range(3)] + list(translation)
    return " ".join(f"{v:g}" for v in numbers)


def compose_transform(outer: str, inner: str) -> str:
    """`outer` applied after `inner`, as one 3MF transform.

    A point goes x -> Ri x + ti -> Ro (Ri x + ti) + to.
    """
    ro, to = _unpack(outer)
    ri, ti = _unpack(inner)
    rows = [
        [sum(ro[i][k] * ri[k][j] for k in range(3)) for j in range(3)] for i in range(3)
    ]
    translation = [sum(ro[i][k] * ti[k] for k in range(3)) + to[i] for i in range(3)]
    return _pack(rows, translation)


def lay_out(path: str, transform: str) -> None:
    """Compose `transform` into every build item, leaving the meshes alone.

    This is how parts are laid out on the plate without touching the document.
    Mesh.export writes each object's placement into its item matrix and keeps the
    vertices local, and Bambu applies that matrix whole — Plater.cpp re-centres
    only non-3MF files, and normalises nothing but the height.
    """
    with zipfile.ZipFile(path) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries:
            if item.filename == MODEL_ENTRY:
                model = data.decode("utf-8")
                data = _ITEM.sub(
                    lambda m: _compose_into(m.group(0), transform), model
                ).encode("utf-8")
            archive.writestr(item, data)


def _compose_into(tag: str, transform: str) -> str:
    """`transform` composed into one `<item>` tag, whatever it carried before.

    An item with no transform of its own means the identity, so it takes the
    outer one whole. FreeCAD's writer always emits the attribute, but "every
    build item" has to mean every one.
    """
    attribute = _TRANSFORM.search(tag)
    if attribute:
        composed = compose_transform(transform, attribute.group(1))
        return tag[: attribute.start(1)] + composed + tag[attribute.end(1) :]
    close = "/>" if tag.endswith("/>") else ">"
    body = tag[: -len(close)].rstrip()
    return f'{body} transform="{transform}"{close}'

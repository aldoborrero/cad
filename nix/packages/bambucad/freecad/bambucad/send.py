"""Export the visible objects to 3MF and hand the file to the slicer."""

import os
import re
import shutil
import subprocess
import zipfile

MODEL_ENTRY = "3D/3dmodel.model"
_TRANSFORM = re.compile(r'(<item\b[^>]*\btransform=")([^"]*)(")')


class SlicerNotFound(Exception):
    """Neither the configured executable nor one on PATH."""


def output_path(document_filename, document_label, tmpdir):
    """Where the 3MF goes: exports/ beside a saved document, tmpdir otherwise."""
    if document_filename:
        return os.path.join(
            os.path.dirname(document_filename), "exports", document_label + ".3mf"
        )
    return os.path.join(tmpdir, document_label + ".3mf")


def slicer_executable(preference, which=shutil.which):
    """The configured executable if set, else whatever is on PATH."""
    if preference:
        return preference
    found = which("bambu-studio")
    if found:
        return found
    raise SlicerNotFound(
        "no bambu-studio on PATH; set its full path in the addon preferences"
    )


def export_and_open(objects, path, executable, offset=(0, 0)):
    """Write the objects to `path` as 3MF and hand the file to the slicer.

    FreeCAD is imported here, not at module scope, so the rest of this module
    stays importable under pytest with no FreeCAD around.
    """
    import Mesh

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    Mesh.export(objects, path)
    dx, dy = offset
    if dx or dy:
        lay_out(path, dx, dy)
    subprocess.Popen([executable, path])
    return path


def shift_transform(transform, dx, dy):
    """Translate a 3MF build item by (dx, dy).

    Writer3MF::DumpMatrix emits twelve numbers, the 3x3 rotation transposed per
    the spec and then the translation, so only the last three matter here.
    """
    numbers = [float(n) for n in transform.split()]
    if len(numbers) != 12:
        raise ValueError(f"expected twelve numbers, got {len(numbers)}")
    numbers[9] += dx
    numbers[10] += dy
    return " ".join(f"{n:g}" for n in numbers)


def lay_out(path, dx, dy):
    """Translate every build item in a 3MF, leaving the meshes where they are.

    This is how a part is laid out on the plate without touching the document:
    the transform lives in the build item, and Bambu honours it — Plater.cpp only
    re-centres non-3MF files, and drops Z to the bed either way.
    """
    with zipfile.ZipFile(path) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries:
            if item.filename == MODEL_ENTRY:
                model = data.decode("utf-8")
                data = _TRANSFORM.sub(
                    lambda m: (
                        m.group(1) + shift_transform(m.group(2), dx, dy) + m.group(3)
                    ),
                    model,
                ).encode("utf-8")
            archive.writestr(item, data)

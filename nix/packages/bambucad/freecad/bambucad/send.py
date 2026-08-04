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


def launch(executable, paths):
    """Start the slicer on those files, turning a bad path into a plain message.

    A configured executable that is not there is the likeliest way this fails, and
    an OSError traceback in the report view says nothing useful about it.
    """
    try:
        subprocess.Popen([executable, *paths])
    except OSError as exc:
        raise SlicerNotFound(f"could not run {executable}: {exc.strerror}") from exc


def export_and_open(objects, path, executable, transform=None, tolerance=None):
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
    launch(executable, [path])
    return path


def export_step_and_open(objects, directory, executable):
    """One STEP per object, all handed to the slicer at once.

    Exact geometry, tessellated by the slicer with its own setting, and each part
    arrives named — a foreign file with a single object takes its name from the
    filename, which is why one file per part is what earns the names.

    The layout does not survive: Plater.cpp re-centres every object that does not
    come from a 3MF or AMF, so this trades the bed arrangement for the other two.
    """
    import ImportGui

    os.makedirs(directory, exist_ok=True)
    paths = []
    for obj in objects:
        path = os.path.join(directory, f"{obj.Label}.step")
        ImportGui.export([obj], path)
        paths.append(path)
    launch(executable, paths)
    return paths


def _unpack(transform):
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


def _pack(rows, translation):
    numbers = [rows[i][j] for j in range(3) for i in range(3)] + list(translation)
    return " ".join(f"{v:g}" for v in numbers)


def compose_transform(outer, inner):
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


def lay_out(path, transform):
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
                data = _TRANSFORM.sub(
                    lambda m: (
                        m.group(1)
                        + compose_transform(transform, m.group(2))
                        + m.group(3)
                    ),
                    model,
                ).encode("utf-8")
            archive.writestr(item, data)

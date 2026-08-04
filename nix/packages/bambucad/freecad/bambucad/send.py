"""Export the visible objects to 3MF and hand the file to the slicer."""

import os
import shutil
import subprocess


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


def export_and_open(objects, path, executable):
    """Write the objects to `path` as 3MF and hand the file to the slicer.

    FreeCAD is imported here, not at module scope, so the rest of this module
    stays importable under pytest with no FreeCAD around.
    """
    import Mesh

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    Mesh.export(objects, path)
    subprocess.Popen([executable, path])
    return path

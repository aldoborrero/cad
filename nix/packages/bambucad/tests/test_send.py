import zipfile

import pytest

from freecad.bambucad import send

MODEL = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<model unit="millimeter">
 <resources><object id="1" type="model"><mesh/></object></resources>
 <build>
  <item objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0" />
  <item objectid="2" transform="1 0 0 0 1 0 0 0 1 5 5 0" />
 </build>
</model>
"""


def test_a_saved_document_exports_next_to_itself_under_exports():
    path = send.output_path(
        document_filename="/home/aldo/cad/freecad/marble-run/marble-run.FCStd",
        document_label="marble-run",
        tmpdir="/tmp/whatever",
    )

    assert path == "/home/aldo/cad/freecad/marble-run/exports/marble-run.3mf"


def test_an_unsaved_document_falls_back_to_a_temporary_file():
    path = send.output_path(
        document_filename="", document_label="Unnamed", tmpdir="/tmp/whatever"
    )

    assert path == "/tmp/whatever/Unnamed.3mf"


def test_the_configured_executable_wins_over_the_one_on_path():
    exe = send.slicer_executable(
        preference="/opt/bambu/bambu-studio", which=lambda name: "/usr/bin/" + name
    )

    assert exe == "/opt/bambu/bambu-studio"


def test_without_a_preference_it_looks_bambu_studio_up_on_path():
    exe = send.slicer_executable(
        preference="",
        which=lambda name: "/usr/bin/bambu-studio" if name == "bambu-studio" else None,
    )

    assert exe == "/usr/bin/bambu-studio"


def test_no_slicer_anywhere_raises_rather_than_returning_nothing():
    with pytest.raises(send.SlicerNotFound):
        send.slicer_executable(preference="", which=lambda name: None)


def test_composing_transforms_respects_the_transposed_layout():
    # The twelve numbers are column-major: three numbers per column of the 3x3,
    # then the translation. A 90 degree yaw applied after a translation of +10 in
    # X must land the part at +10 in Y. Getting the transpose wrong gives -10,
    # which no symmetric rotation would ever catch.
    yaw90 = "0 1 0 -1 0 0 0 0 1 0 0 0"
    moved_x = "1 0 0 0 1 0 0 0 1 10 0 0"

    assert send.compose_transform(yaw90, moved_x) == "0 1 0 -1 0 0 0 0 1 0 10 0"


def test_composing_with_the_identity_changes_nothing():
    identity = "1 0 0 0 1 0 0 0 1 0 0 0"
    item = "0.866025 0.5 0 -0.5 0.866025 0 0 0 1 10 20 5"

    assert send.compose_transform(identity, item) == item


def test_laying_out_composes_the_bed_transform_into_every_build_item(tmp_path):
    path = tmp_path / "parts.3mf"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("3D/3dmodel.model", MODEL)
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("Metadata/thumbnail.png", b"not really a png")

    send.lay_out(str(path), "1 0 0 0 1 0 0 0 1 128 128 0")

    with zipfile.ZipFile(path) as archive:
        model = archive.read("3D/3dmodel.model").decode()
        assert 'transform="1 0 0 0 1 0 0 0 1 128 128 0"' in model
        assert 'transform="1 0 0 0 1 0 0 0 1 133 133 0"' in model
        assert archive.read("Metadata/thumbnail.png") == b"not really a png"
        assert "[Content_Types].xml" in archive.namelist()


def test_a_slicer_path_that_does_not_exist_says_so_instead_of_raising_oserror():
    with pytest.raises(send.SlicerNotFound) as caught:
        send.launch("/nowhere/bambu-studio", ["/tmp/x.3mf"])

    assert "/nowhere/bambu-studio" in str(caught.value)


def test_orca_slicer_is_found_when_bambu_studio_is_not():
    exe = send.slicer_executable(
        preference="",
        which=lambda name: "/usr/bin/orca-slicer" if name == "orca-slicer" else None,
    )

    assert exe == "/usr/bin/orca-slicer"


def test_bambu_studio_wins_when_both_are_installed():
    # Its own slicer knows its printers; Orca is the fallback, not the preference.
    exe = send.slicer_executable(preference="", which=lambda name: "/usr/bin/" + name)

    assert exe == "/usr/bin/bambu-studio"

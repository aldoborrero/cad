from freecad.bambucad import send


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


import pytest


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


def test_shifting_a_build_item_moves_only_its_translation():
    # Writer3MF::DumpMatrix writes twelve numbers, the last three being the
    # translation, so laying parts out means touching those and nothing else.
    moved = send.shift_transform("1 0 0 0 1 0 0 0 1 5 7 0", 128, 128)

    assert moved == "1 0 0 0 1 0 0 0 1 133 135 0"


def test_shifting_keeps_a_rotation_untouched():
    moved = send.shift_transform("0 -1 0 1 0 0 0 0 1 0 0 3", 10, 20)

    assert moved == "0 -1 0 1 0 0 0 0 1 10 20 3"


import zipfile

MODEL = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<model unit="millimeter">
 <resources><object id="1" type="model"><mesh/></object></resources>
 <build>
  <item objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0" />
  <item objectid="2" transform="1 0 0 0 1 0 0 0 1 5 5 0" />
 </build>
</model>
"""


def test_laying_out_moves_every_build_item_and_leaves_the_rest_alone(tmp_path):
    path = tmp_path / "parts.3mf"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("3D/3dmodel.model", MODEL)
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("Metadata/thumbnail.png", b"not really a png")

    send.lay_out(str(path), 128, 128)

    with zipfile.ZipFile(path) as archive:
        model = archive.read("3D/3dmodel.model").decode()
        assert 'transform="1 0 0 0 1 0 0 0 1 128 128 0"' in model
        assert 'transform="1 0 0 0 1 0 0 0 1 133 133 0"' in model
        assert archive.read("Metadata/thumbnail.png") == b"not really a png"
        assert "[Content_Types].xml" in archive.namelist()

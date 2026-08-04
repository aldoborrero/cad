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

import os
import pathlib
import stat
import zipfile

import pytest

from freecad.slicercad import send

MODEL = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<model unit="millimeter">
 <resources><object id="1" type="model"><mesh/></object></resources>
 <build>
  <item objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0" />
  <item objectid="2" transform="1 0 0 0 1 0 0 0 1 5 5 0" />
 </build>
</model>
"""


def test_a_saved_document_exports_next_to_itself_under_exports() -> None:
    path = send.output_path(
        document_filename="/home/aldo/cad/freecad/marble-run/marble-run.FCStd",
        document_label="marble-run",
        tmpdir="/tmp/whatever",
    )

    assert path == "/home/aldo/cad/freecad/marble-run/exports/marble-run.3mf"


def test_an_unsaved_document_falls_back_to_a_temporary_file() -> None:
    path = send.output_path(
        document_filename="", document_label="Unnamed", tmpdir="/tmp/whatever"
    )

    assert path == "/tmp/whatever/Unnamed.3mf"


def test_composing_transforms_respects_the_transposed_layout() -> None:
    # The twelve numbers are column-major: three numbers per column of the 3x3,
    # then the translation. A 90 degree yaw applied after a translation of +10 in
    # X must land the part at +10 in Y. Getting the transpose wrong gives -10,
    # which no symmetric rotation would ever catch.
    yaw90 = "0 1 0 -1 0 0 0 0 1 0 0 0"
    moved_x = "1 0 0 0 1 0 0 0 1 10 0 0"

    assert send.compose_transform(yaw90, moved_x) == "0 1 0 -1 0 0 0 0 1 0 10 0"


def test_composing_with_the_identity_changes_nothing() -> None:
    identity = "1 0 0 0 1 0 0 0 1 0 0 0"
    item = "0.866025 0.5 0 -0.5 0.866025 0 0 0 1 10 20 5"

    assert send.compose_transform(identity, item) == item


def test_laying_out_composes_the_bed_transform_into_every_build_item(
    tmp_path: pathlib.Path,
) -> None:
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


def test_a_label_with_a_separator_cannot_write_outside_the_directory() -> None:
    # FreeCAD accepts "/" and ".." in an object's Label, and joining one straight
    # into a path put the file somewhere else entirely.
    paths = send.export_paths(["sub/pieza", "../fuera"], "/tmp/exports", ".step")

    assert [os.path.dirname(p) for p in paths] == ["/tmp/exports", "/tmp/exports"]


def test_an_ordinary_label_is_left_alone() -> None:
    paths = send.export_paths(["Bracket v2 (left)"], "/tmp/exports", ".step")

    assert paths == ["/tmp/exports/Bracket v2 (left).step"]


def test_two_parts_with_the_same_label_get_two_files() -> None:
    # FreeCAD allows duplicate labels behind a preference, and one file silently
    # overwrote the other — the slicer then received the same part twice.
    paths = send.export_paths(["Box", "Box", "Box"], "/tmp/exports", ".step")

    assert len(set(paths)) == 3


def test_a_label_made_only_of_separators_still_yields_a_filename() -> None:
    paths = send.export_paths(["///", ".."], "/tmp/exports", ".step")

    assert all(os.path.basename(p) not in ("", ".step") for p in paths)
    assert len(set(paths)) == 2


def test_an_item_without_a_transform_is_moved_too(tmp_path: pathlib.Path) -> None:
    # FreeCAD's own writer always emits transform=, so this is the contract
    # rather than a live bug: "compose into every build item" has to mean every.
    path = tmp_path / "parts.3mf"
    model = (
        '<model><build><item objectid="1"/>'
        '<item objectid="2" transform="1 0 0 0 1 0 0 0 1 5 5 0"/></build></model>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("3D/3dmodel.model", model)

    send.lay_out(str(path), "1 0 0 0 1 0 0 0 1 128 128 0")

    with zipfile.ZipFile(path) as archive:
        written = archive.read("3D/3dmodel.model").decode()
    assert written.count('transform="1 0 0 0 1 0 0 0 1 128 128 0"') == 1
    assert 'transform="1 0 0 0 1 0 0 0 1 133 133 0"' in written


def never(_: str) -> None:
    return None


def test_a_configured_path_wins_over_the_one_on_path() -> None:
    command = send.slicer_command(
        "/opt/bambu/bambu-studio",
        which=lambda n: "/usr/bin/" + n,
        exists=lambda p: True,
    )

    assert command == ["/opt/bambu/bambu-studio"]


def test_without_a_preference_bambu_studio_is_looked_up_on_path() -> None:
    command = send.slicer_command(
        "", which=lambda n: "/usr/bin/bambu-studio" if n == "bambu-studio" else None
    )

    assert command == ["/usr/bin/bambu-studio"]


def test_orca_slicer_is_found_when_bambu_studio_is_not() -> None:
    command = send.slicer_command(
        "", which=lambda n: "/usr/bin/orca-slicer" if n == "orca-slicer" else None
    )

    assert command == ["/usr/bin/orca-slicer"]


def test_bambu_studio_wins_when_both_are_installed() -> None:
    command = send.slicer_command("", which=lambda n: "/usr/bin/" + n)

    assert command == ["/usr/bin/bambu-studio"]


def test_the_chosen_slicer_is_preferred_over_the_other() -> None:
    command = send.slicer_command("", which=lambda n: "/usr/bin/" + n, preferred="orca")

    assert command == ["/usr/bin/orca-slicer"]


def test_no_slicer_anywhere_raises_rather_than_returning_nothing() -> None:
    with pytest.raises(send.SlicerNotFound):
        send.slicer_command("", which=never)


def test_the_executable_may_be_a_command_line_not_only_a_path() -> None:
    # How a slicer installed through flatpak, or an AppImage behind a wrapper,
    # is actually invoked. Taking the whole string as a filename cannot work.
    command = send.slicer_command(
        "flatpak run com.bambulab.BambuStudio",
        which=lambda n: "/usr/bin/flatpak" if n == "flatpak" else None,
        exists=lambda p: False,
    )

    assert command == ["/usr/bin/flatpak", "run", "com.bambulab.BambuStudio"]


def test_a_path_with_spaces_is_not_mistaken_for_a_command_line() -> None:
    command = send.slicer_command(
        "/opt/My Slicer/bin/slicer", which=never, exists=lambda p: True
    )

    assert command == ["/opt/My Slicer/bin/slicer"]


def test_a_quoted_path_with_arguments_survives() -> None:
    command = send.slicer_command(
        '"/opt/My Slicer/slicer" --single-instance',
        which=never,
        exists=lambda p: p == "/opt/My Slicer/slicer",
    )

    assert command == ["/opt/My Slicer/slicer", "--single-instance"]


def test_a_configured_command_that_is_nowhere_says_so() -> None:
    with pytest.raises(send.SlicerNotFound) as caught:
        send.slicer_command("nosuchslicer --flag", which=never, exists=lambda p: False)

    assert "nosuchslicer" in str(caught.value)


def test_a_slicer_path_that_does_not_exist_says_so_instead_of_raising_oserror() -> None:
    with pytest.raises(send.SlicerNotFound) as caught:
        send.launch(["/nowhere/bambu-studio"], ["/tmp/x.3mf"])

    assert "/nowhere/bambu-studio" in str(caught.value)


def test_the_scratch_directory_is_private_to_this_session(
    tmp_path: pathlib.Path,
) -> None:
    # /tmp is world-writable and "Unnamed.3mf" is a name anyone can guess, so
    # exporting there followed whatever symlink had been left in its place.
    send._session_dir = None
    try:
        directory = send.session_dir(str(tmp_path))

        assert stat.S_IMODE(os.stat(directory).st_mode) == 0o700
        assert os.path.basename(directory).startswith("slicercad-")
        assert os.path.dirname(directory) == str(tmp_path)
    finally:
        send._session_dir = None


def test_the_scratch_directory_is_made_once_and_reused(
    tmp_path: pathlib.Path,
) -> None:
    send._session_dir = None
    try:
        first = send.session_dir(str(tmp_path))
        second = send.session_dir(str(tmp_path))

        assert first == second
        assert len(list(tmp_path.iterdir())) == 1
    finally:
        send._session_dir = None


def test_an_unsaved_document_lands_inside_that_directory(
    tmp_path: pathlib.Path,
) -> None:
    send._session_dir = None
    try:
        directory = send.session_dir(str(tmp_path))
        path = send.output_path(
            document_filename="", document_label="Unnamed", tmpdir=directory
        )

        assert path == os.path.join(directory, "Unnamed.3mf")
    finally:
        send._session_dir = None


def test_the_upstream_spelling_of_the_binary_is_found_too() -> None:
    # BambuStudio's CMakeLists sets OUTPUT_NAME "bambu-studio" only for
    # "NOT WIN32 AND NOT APPLE"; the target keeps its own name elsewhere, which
    # is what an AppImage extraction leaves lying around.
    command = send.slicer_command(
        "", which=lambda n: "/opt/bin/BambuStudio" if n == "BambuStudio" else None
    )

    assert command == ["/opt/bin/BambuStudio"]


def test_orca_slicer_is_found_under_its_capitalised_name() -> None:
    command = send.slicer_command(
        "", which=lambda n: "/opt/bin/OrcaSlicer" if n == "OrcaSlicer" else None
    )

    assert command == ["/opt/bin/OrcaSlicer"]


def test_a_flatpak_install_is_found_when_nothing_is_on_path() -> None:
    # OrcaSlicer carries its own manifest under scripts/flatpak/, so the id
    # is theirs rather than a guess.
    command = send.slicer_command(
        "",
        which=lambda n: "/usr/bin/flatpak" if n == "flatpak" else None,
        exists=lambda p: p.endswith("/app/com.orcaslicer.OrcaSlicer"),
    )

    assert command == ["/usr/bin/flatpak", "run", "com.orcaslicer.OrcaSlicer"]


def test_a_binary_on_path_wins_over_the_flatpak() -> None:
    command = send.slicer_command(
        "",
        which=lambda n: "/usr/bin/" + n,
        exists=lambda p: p.endswith("/app/com.orcaslicer.OrcaSlicer"),
    )

    assert command == ["/usr/bin/bambu-studio"]

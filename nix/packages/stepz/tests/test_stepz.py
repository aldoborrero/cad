import pathlib
import sys
import types
import zipfile
from typing import Any

import pytest

import stepZ

STEP = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"


def _archive(path: pathlib.Path, members: dict[str, bytes]) -> pathlib.Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


class FakeImportGui(types.ModuleType):
    """FreeCAD's ImportGui, which exists only inside a running GUI.

    Every method records the path it was handed *and the bytes at that path*: the
    module deletes its temporary file in a `finally`, so a test that only kept the
    path would have nothing left to assert on.
    """

    def __init__(self) -> None:
        super().__init__("ImportGui")
        self.opened: list[bytes] = []
        self.inserted: list[tuple[bytes, str]] = []
        self.exported: list[list[Any]] = []

    def open(self, path: str) -> None:
        self.opened.append(pathlib.Path(path).read_bytes())

    def insert(self, path: str, doc: str) -> None:
        self.inserted.append((pathlib.Path(path).read_bytes(), doc))

    def export(self, objs: list[Any], path: str) -> None:
        self.exported.append(objs)
        pathlib.Path(path).write_bytes(STEP)


@pytest.fixture
def import_gui(monkeypatch: pytest.MonkeyPatch) -> FakeImportGui:
    fake = FakeImportGui()
    monkeypatch.setitem(sys.modules, "ImportGui", fake)
    return fake


def test_the_step_inside_a_kicad_archive_is_unpacked(tmp_path: pathlib.Path) -> None:
    # What `zip -j -9 R_0805.stpZ R_0805.step` leaves: one file, stored bare.
    src = _archive(tmp_path / "R_0805.stpZ", {"R_0805.step": STEP})

    path = stepZ._unpack(str(src))

    assert pathlib.Path(path).read_bytes() == STEP


def test_a_stray_file_beside_the_step_does_not_win(tmp_path: pathlib.Path) -> None:
    src = _archive(tmp_path / "part.stpZ", {"README.txt": b"notes", "part.step": STEP})

    path = stepZ._unpack(str(src))

    assert pathlib.Path(path).read_bytes() == STEP


def test_an_empty_archive_is_an_error_not_an_empty_model(
    tmp_path: pathlib.Path,
) -> None:
    src = _archive(tmp_path / "empty.stpZ", {})

    with pytest.raises(ValueError, match="holds no file"):
        stepZ._unpack(str(src))


def test_insert_hands_freecad_the_decompressed_step(
    tmp_path: pathlib.Path, import_gui: FakeImportGui
) -> None:
    src = _archive(tmp_path / "C_0402.stpZ", {"C_0402.step": STEP})

    stepZ.insert(str(src), "Board")

    assert import_gui.inserted == [(STEP, "Board")]


def test_open_hands_freecad_the_decompressed_step(
    tmp_path: pathlib.Path, import_gui: FakeImportGui
) -> None:
    src = _archive(tmp_path / "C_0402.stpZ", {"C_0402.step": STEP})

    stepZ.open(str(src))

    assert import_gui.opened == [STEP]


def test_the_temporary_step_does_not_outlive_the_import(
    tmp_path: pathlib.Path, import_gui: FakeImportGui
) -> None:
    src = _archive(tmp_path / "C_0402.stpZ", {"C_0402.step": STEP})
    seen: list[str] = []
    import_gui.insert = lambda path, doc: seen.append(path)  # type: ignore[method-assign]

    stepZ.insert(str(src), "Board")

    assert len(seen) == 1
    assert not pathlib.Path(seen[0]).exists()


def test_export_writes_an_archive_kicad_can_read_back(
    tmp_path: pathlib.Path, import_gui: FakeImportGui
) -> None:
    out = tmp_path / "board.stpZ"

    stepZ.export(["shape"], str(out))

    with zipfile.ZipFile(out) as archive:
        # Named after the archive, which is what `zip -j` and KiCad both produce.
        assert archive.namelist() == ["board.step"]
        assert archive.read("board.step") == STEP
    assert import_gui.exported == [["shape"]]


def test_export_round_trips_through_unpack(
    tmp_path: pathlib.Path, import_gui: FakeImportGui
) -> None:
    out = tmp_path / "board.stpZ"
    stepZ.export(["shape"], str(out))

    path = stepZ._unpack(str(out))

    assert pathlib.Path(path).read_bytes() == STEP

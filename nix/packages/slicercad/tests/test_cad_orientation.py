from __future__ import annotations

from dataclasses import dataclass

from freecad.slicercad import cad_orientation


@dataclass(frozen=True)
class Vector:
    x: float
    y: float
    z: float


class Surface:
    def __init__(self, planar: bool) -> None:
        self._planar = planar

    def isPlanar(self) -> bool:
        return self._planar


class Face:
    def __init__(
        self, normal: tuple[float, float, float], area: float, *, planar: bool = True
    ) -> None:
        self.Surface = Surface(planar)
        self.Area = area
        self._normal = Vector(*normal)

    def normalAt(self, _u: float, _v: float) -> Vector:
        return self._normal


@dataclass
class Bounds:
    XMin: float = 0.0
    YMin: float = 0.0
    ZMin: float = 0.0
    XMax: float = 1.0
    YMax: float = 1.0
    ZMax: float = 1.0


class Shape:
    def __init__(self, faces: list[Face], *, solid: bool = True) -> None:
        self.Faces = faces
        self.Solids = [object()] if solid else []
        self.BoundBox = Bounds()
        self.Volume = 1.0 / 6.0

    def isNull(self) -> bool:
        return False


@dataclass
class Object:
    Shape: Shape


class Result:
    Mesh = object()
    NodeNumbers: tuple[int, ...] = (1,)
    NodeStressXX: tuple[float, ...] = (0.0,)
    NodeStressYY: tuple[float, ...] = (0.0,)
    NodeStressZZ: tuple[float, ...] = (0.0,)
    NodeStressXY: tuple[float, ...] = (0.0,)
    NodeStressXZ: tuple[float, ...] = (0.0,)
    NodeStressYZ: tuple[float, ...] = (0.0,)

    def isDerivedFrom(self, kind: str) -> bool:
        return kind == "Fem::FemResultObject"


class EmptyResult(Result):
    NodeNumbers = ()
    NodeStressXX = ()
    NodeStressYY = ()
    NodeStressZZ = ()
    NodeStressXY = ()
    NodeStressXZ = ()
    NodeStressYZ = ()


class FemMesh:
    Volumes = (1,)

    def getElementNodes(self, _element_id: int) -> tuple[int, ...]:
        return (1, 2, 3, 4)

    def getNodeById(self, node_id: int) -> Vector:
        points = {
            1: Vector(0.0, 0.0, 0.0),
            2: Vector(1.0, 0.0, 0.0),
            3: Vector(0.0, 1.0, 0.0),
            4: Vector(0.0, 0.0, 1.0),
        }
        return points[node_id]


@dataclass
class ResultMesh:
    FemMesh: FemMesh


class LinkedResult(Result):
    NodeNumbers = (1, 2, 3, 4)
    NodeStressXX = (0.0, 0.0, 0.0, 0.0)
    NodeStressYY = (0.0, 0.0, 0.0, 0.0)
    NodeStressZZ = (0.0, 0.0, 0.0, 0.0)
    NodeStressXY = (0.0, 0.0, 0.0, 0.0)
    NodeStressXZ = (0.0, 0.0, 0.0, 0.0)
    NodeStressYZ = (0.0, 0.0, 0.0, 0.0)

    def __init__(self, mesh: FemMesh) -> None:
        self.Mesh = ResultMesh(mesh)


@dataclass
class SourceMesh:
    Shape: Object
    FemMesh: FemMesh


@dataclass
class Document:
    Objects: list[object]


def test_planar_faces_become_deduplicated_unoriented_candidates() -> None:
    part = Object(
        Shape(
            [
                Face((1.0, 0.0, 0.0), 10.0),
                Face((-1.0, 0.0, 0.0), 20.0),
                Face((0.0, 1.0, 0.0), 30.0),
                Face((0.0, 0.0, 1.0), 99.0, planar=False),
            ]
        )
    )

    candidates = cad_orientation.face_candidates((part,))

    assert [candidate.build for candidate in candidates] == [
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
    ]
    assert [candidate.area for candidate in candidates] == [30.0, 30.0]
    assert {candidate.source for candidate in candidates} == {"face"}


def test_document_discovery_separates_solids_and_solved_results() -> None:
    solid = Object(Shape([]))
    shell = Object(Shape([], solid=False))
    result = Result()
    empty_result = EmptyResult()
    document = Document([solid, shell, result, empty_result])

    assert cad_orientation.printable_solids(document) == [solid]
    assert cad_orientation.solved_results(document) == [result]


def test_result_part_association_requires_one_matching_source_mesh() -> None:
    part = Object(Shape([]))
    mesh = FemMesh()
    source = SourceMesh(part, mesh)
    result = LinkedResult(mesh)
    document = Document([part, source, result])

    assert cad_orientation.source_mesh_for(document, result, part) is source
    assert cad_orientation.result_parts(document, result) == [part]
    assert cad_orientation.has_linked_result_part(document, result)

    part.Shape.BoundBox.XMin = 2.0
    part.Shape.BoundBox.XMax = 3.0
    assert cad_orientation.source_mesh_for(document, result, part) is None
    part.Shape.BoundBox.XMin = 0.0
    part.Shape.BoundBox.XMax = 1.0

    part.Shape.Volume = 1.0
    assert cad_orientation.source_mesh_for(document, result, part) is None
    part.Shape.Volume = 1.0 / 6.0

    document.Objects.append(SourceMesh(part, mesh))
    assert cad_orientation.source_mesh_for(document, result, part) is None
    assert cad_orientation.result_parts(document, result) == []

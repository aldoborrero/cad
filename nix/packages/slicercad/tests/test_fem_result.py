from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from freecad.slicercad import fem_result, orient


@dataclass(frozen=True)
class Vector:
    x: float
    y: float
    z: float


class FakeMesh:
    def __init__(
        self,
        nodes: dict[int, tuple[float, float, float]],
        elements: dict[int, tuple[int, ...]],
    ) -> None:
        self.Volumes = tuple(elements)
        self._nodes = {node_id: Vector(*point) for node_id, point in nodes.items()}
        self._elements = elements

    def getElementNodes(self, element_id: int) -> tuple[int, ...]:
        return self._elements[element_id]

    def getNodeById(self, node_id: int) -> Vector:
        return self._nodes[node_id]


class FakeResult:
    SlicercadMeshSignature: str
    SlicercadAnalysisSignature: str

    def __init__(
        self,
        mesh: FakeMesh,
        node_ids: tuple[int, ...],
        xx: tuple[float, ...] | None = None,
    ) -> None:
        self.Mesh = FakeResultMesh(mesh)
        self.PropertiesList: list[str] = []
        self.NodeNumbers = node_ids
        self.NodeStressXX = (
            xx if xx is not None else tuple(float(node) for node in node_ids)
        )
        zero = tuple(0.0 for _ in node_ids)
        self.NodeStressYY = zero
        self.NodeStressZZ = zero
        self.NodeStressXY = zero
        self.NodeStressXZ = zero
        self.NodeStressYZ = zero

    def addProperty(
        self,
        _property_type: str,
        name: str,
        _group: str,
        _description: str,
        _hidden: bool,
    ) -> None:
        self.PropertiesList.append(name)


@dataclass(frozen=True)
class FakeResultMesh:
    FemMesh: FakeMesh


ANALYSIS_SIGNATURE = "analysis-input-v1"


def solved_result(
    mesh: FakeMesh,
    node_ids: tuple[int, ...],
    xx: tuple[float, ...] | None = None,
) -> FakeResult:
    result = FakeResult(mesh, node_ids, xx)
    fem_result.record_result_provenance(
        result,
        mesh,
        analysis_signature=ANALYSIS_SIGNATURE,
    )
    return result


def weighted_field(
    mesh: FakeMesh,
    result: FakeResult,
    *,
    transform: fem_result.RigidTransform | None = None,
) -> fem_result.A0StressField:
    return fem_result.volume_lumped_stress_field(
        mesh,
        result,
        analysis_signature=ANALYSIS_SIGNATURE,
        transform=transform,
    )


def unit_tetra_mesh() -> FakeMesh:
    return FakeMesh(
        {
            1: (0.0, 0.0, 0.0),
            2: (1.0, 0.0, 0.0),
            3: (0.0, 1.0, 0.0),
            4: (0.0, 0.0, 1.0),
        },
        {10: (1, 2, 3, 4)},
    )


def test_adapter_pairs_stress_by_node_id_and_preserves_provenance() -> None:
    mesh = unit_tetra_mesh()
    result = solved_result(mesh, (4, 2, 1, 3), xx=(40.0, 20.0, 10.0, 30.0))

    field = weighted_field(mesh, result)

    assert field.data_source == "nodal_volume_lumped"
    assert field.provenance_status == "verified"
    assert field.analysis_signature == ANALYSIS_SIGNATURE
    assert field.mesh_signature == fem_result.mesh_signature(mesh)
    assert field.mesh_volume == pytest.approx(1.0 / 6.0)
    assert math.fsum(sample.volume for sample in field.samples) == pytest.approx(
        field.mesh_volume
    )
    assert [sample.sample_id for sample in field.samples] == [1, 2, 3, 4]
    assert [sample.stress[0] for sample in field.samples] == [10.0, 20.0, 30.0, 40.0]
    assert all(sample.volume == pytest.approx(1.0 / 24.0) for sample in field.samples)
    assert field.samples[0].source_node_ids == (1,)
    assert field.samples[0].source_element_ids == (10,)


def test_adapter_remaps_compacted_result_node_and_element_ids() -> None:
    current = FakeMesh(
        {
            10: (0.0, 0.0, 0.0),
            20: (1.0, 0.0, 0.0),
            30: (0.0, 1.0, 0.0),
            40: (0.0, 0.0, 1.0),
        },
        {99: (10, 20, 30, 40)},
    )
    stored = FakeMesh(
        {
            1: (1.0, 0.0, 0.0),
            2: (0.0, 0.0, 0.0),
            3: (0.0, 0.0, 1.0),
            4: (0.0, 1.0, 0.0),
        },
        {1: (2, 1, 4, 3)},
    )
    result = FakeResult(stored, (1, 2, 3, 4), xx=(20.0, 10.0, 40.0, 30.0))
    fem_result.record_result_provenance(
        result,
        current,
        analysis_signature=ANALYSIS_SIGNATURE,
    )

    field = weighted_field(current, result)

    assert [sample.sample_id for sample in field.samples] == [10, 20, 30, 40]
    assert [sample.stress[0] for sample in field.samples] == [10.0, 20.0, 30.0, 40.0]


def test_adapter_rotates_positions_and_stress_into_the_ranking_frame() -> None:
    rotation = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    transform = fem_result.RigidTransform(
        rotation=rotation,
        translation=(10.0, 20.0, 30.0),
    )
    mesh = unit_tetra_mesh()
    result = solved_result(mesh, (1, 2, 3, 4), xx=(5.0, 5.0, 5.0, 5.0))

    field = weighted_field(mesh, result, transform=transform)

    node_two = field.samples[1]
    assert node_two.position == (10.0, 21.0, 30.0)
    assert node_two.stress == pytest.approx((0.0, 5.0, 0.0, 0.0, 0.0, 0.0))


def test_asymmetric_transformed_body_has_the_same_physical_ranking() -> None:
    source_nodes = {
        1: (0.0, 0.0, 0.0),
        2: (2.0, 0.0, 0.0),
        3: (0.0, 3.0, 0.0),
        4: (0.0, 0.0, 5.0),
    }
    elements: dict[int, tuple[int, ...]] = {10: (1, 2, 3, 4)}
    node_ids = (1, 2, 3, 4)
    source_stress = (2.0, 5.0, 11.0, 17.0)
    transform = fem_result.RigidTransform(
        rotation=((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        translation=(13.0, -7.0, 4.0),
    )
    transformed_nodes = {
        node_id: transform.point(point) for node_id, point in source_nodes.items()
    }
    source_mesh = FakeMesh(source_nodes, elements)
    transformed_mesh = FakeMesh(transformed_nodes, elements)
    transformed_result = solved_result(
        transformed_mesh, node_ids, xx=(0.0, 0.0, 0.0, 0.0)
    )
    transformed_result.NodeStressYY = source_stress

    transformed_by_adapter = weighted_field(
        source_mesh,
        solved_result(source_mesh, node_ids, xx=source_stress),
        transform=transform,
    )
    transformed_before_adapter = weighted_field(transformed_mesh, transformed_result)

    assert transformed_by_adapter.mesh_volume == pytest.approx(
        transformed_before_adapter.mesh_volume
    )
    for sample_left, sample_right in zip(
        transformed_by_adapter.samples,
        transformed_before_adapter.samples,
        strict=True,
    ):
        assert sample_left.position == pytest.approx(sample_right.position)
        assert sample_left.stress == pytest.approx(sample_right.stress)
        assert sample_left.volume == pytest.approx(sample_right.volume)

    candidates = (
        orient.Candidate((0.0, 1.0, 0.0), source="transformed_face"),
        orient.Candidate((1.0, 0.0, 0.0), source="transformed_face"),
        orient.Candidate((0.0, 0.0, 1.0), source="transformed_face"),
    )
    left_ranking = orient.rank(
        transformed_by_adapter.samples,
        candidates,
        ranking_tail_fraction=0.01,
    )
    right_ranking = orient.rank(
        transformed_before_adapter.samples,
        candidates,
        ranking_tail_fraction=0.01,
    )
    assert [score.build for score in left_ranking.scores] == [
        score.build for score in right_ranking.scores
    ]
    for score_left, score_right in zip(
        left_ranking.scores, right_ranking.scores, strict=True
    ):
        assert score_left.opening_cvar_1 == pytest.approx(score_right.opening_cvar_1)
        assert score_left.shear_cvar_1 == pytest.approx(score_right.shear_cvar_1)


def test_adapter_rejects_missing_or_extra_result_nodes() -> None:
    mesh = unit_tetra_mesh()
    with pytest.raises(ValueError, match="missing volume nodes"):
        weighted_field(mesh, solved_result(mesh, (1, 2, 3)))

    with pytest.raises(ValueError, match="outside its stored mesh"):
        weighted_field(mesh, solved_result(mesh, (1, 2, 3, 4, 5)))


def test_adapter_rejects_duplicate_result_nodes() -> None:
    mesh = unit_tetra_mesh()
    with pytest.raises(ValueError, match="must be unique"):
        weighted_field(mesh, solved_result(mesh, (1, 2, 3, 3)))


def test_adapter_rejects_an_unsupported_volume_element() -> None:
    nodes = {node_id: (float(node_id), 0.0, 0.0) for node_id in range(1, 9)}
    mesh = FakeMesh(nodes, {1: tuple(nodes)})
    result = FakeResult(mesh, tuple(nodes))
    result.SlicercadMeshSignature = "unsupported"
    result.SlicercadAnalysisSignature = ANALYSIS_SIGNATURE

    with pytest.raises(ValueError, match="supports only C3D4 and C3D10"):
        weighted_field(mesh, result)


def test_adapter_rejects_a_result_without_recorded_provenance() -> None:
    mesh = unit_tetra_mesh()

    with pytest.raises(ValueError, match="no SlicerCAD provenance"):
        weighted_field(mesh, FakeResult(mesh, (1, 2, 3, 4)))


def test_adapter_rejects_a_changed_analysis_with_the_same_mesh() -> None:
    mesh = unit_tetra_mesh()
    result = solved_result(mesh, (1, 2, 3, 4))

    with pytest.raises(ValueError, match="analysis signature has changed"):
        fem_result.volume_lumped_stress_field(
            mesh,
            result,
            analysis_signature="analysis-input-v2",
        )


def test_adapter_rejects_changed_coordinates_with_the_same_node_ids() -> None:
    original = unit_tetra_mesh()
    result = solved_result(original, (1, 2, 3, 4))
    moved = FakeMesh(
        {
            1: (1.0, 0.0, 0.0),
            2: (2.0, 0.0, 0.0),
            3: (1.0, 1.0, 0.0),
            4: (1.0, 0.0, 1.0),
        },
        {10: (1, 2, 3, 4)},
    )

    with pytest.raises(ValueError, match="mesh signature has changed"):
        weighted_field(moved, result)


def test_adapter_rejects_a_mismatched_mesh_embedded_in_the_result() -> None:
    current = unit_tetra_mesh()
    stored = FakeMesh(
        {
            1: (0.0, 0.0, 0.0),
            2: (2.0, 0.0, 0.0),
            3: (0.0, 1.0, 0.0),
            4: (0.0, 0.0, 1.0),
        },
        {10: (1, 2, 3, 4)},
    )
    result = FakeResult(stored, (1, 2, 3, 4))
    fem_result.record_result_provenance(
        result,
        current,
        analysis_signature=ANALYSIS_SIGNATURE,
    )

    with pytest.raises(ValueError, match="cannot be matched uniquely"):
        weighted_field(current, result)


def test_adapter_accepts_coordinate_rounding_from_the_frd_file() -> None:
    current = unit_tetra_mesh()
    stored = FakeMesh(
        {
            1: (0.0, 0.0, 0.0),
            2: (1.000005, 0.0, 0.0),
            3: (0.0, 1.0, 0.0),
            4: (0.0, 0.0, 1.0),
        },
        {10: (1, 2, 3, 4)},
    )
    result = FakeResult(stored, (1, 2, 3, 4))
    fem_result.record_result_provenance(
        result,
        current,
        analysis_signature=ANALYSIS_SIGNATURE,
    )

    assert weighted_field(current, result).provenance_status == "verified"


def test_transform_rejects_reflections_and_non_orthonormal_matrices() -> None:
    with pytest.raises(ValueError, match="proper rotation"):
        fem_result.RigidTransform(
            rotation=((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        )
    with pytest.raises(ValueError, match="orthonormal"):
        fem_result.RigidTransform(
            rotation=((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        )

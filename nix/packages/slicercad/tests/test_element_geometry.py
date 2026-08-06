from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from freecad.slicercad import element_geometry

PointMap = Callable[[element_geometry.Point3], element_geometry.Point3]


def mapped_c3d10(transform: PointMap) -> tuple[element_geometry.Point3, ...]:
    return tuple(transform(point) for point in element_geometry.reference_c3d10_nodes())


def test_c3d4_unit_tetrahedron_has_exact_volume() -> None:
    points = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

    assert element_geometry.c3d4_volume(points) == pytest.approx(1.0 / 6.0)


def test_c3d4_volume_is_independent_of_orientation_and_translation() -> None:
    points = ((3.0, 4.0, 5.0), (3.0, 5.0, 5.0), (4.0, 4.0, 5.0), (3.0, 4.0, 6.0))

    assert element_geometry.c3d4_volume(points) == pytest.approx(1.0 / 6.0)


def test_c3d4_rejects_a_singular_element() -> None:
    points = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0))

    with pytest.raises(ValueError, match="singular Jacobian"):
        element_geometry.c3d4_volume(points)


def test_affine_c3d10_matches_the_linear_tetrahedron() -> None:
    points = element_geometry.reference_c3d10_nodes()

    assert element_geometry.c3d10_volume(points) == pytest.approx(1.0 / 6.0)
    assert element_geometry.c3d10_midpoint_deviation(points) == 0.0


def test_c3d10_integrates_a_curved_quadratic_mapping() -> None:
    curvature = 0.8

    def curved(point: element_geometry.Point3) -> element_geometry.Point3:
        r, s, t = point
        return r, s, t * (1.0 + curvature * r)

    points = mapped_c3d10(curved)

    assert element_geometry.c3d10_volume(points) == pytest.approx(
        1.0 / 6.0 + curvature / 24.0,
        rel=1e-14,
    )
    assert element_geometry.c3d10_midpoint_deviation(points) == pytest.approx(
        curvature / 4.0
    )


def test_c3d10_accepts_a_consistently_negative_jacobian() -> None:
    points = mapped_c3d10(lambda point: (point[1], point[0], point[2]))

    assert element_geometry.c3d10_volume(points) == pytest.approx(1.0 / 6.0)


def test_c3d10_rejects_a_jacobian_that_changes_sign() -> None:
    curvature = -2.5
    points = mapped_c3d10(
        lambda point: (
            point[0],
            point[1],
            point[2] * (1.0 + curvature * point[0]),
        )
    )

    with pytest.raises(ValueError, match="changes sign"):
        element_geometry.c3d10_volume(points)


def test_lumping_conserves_volume_and_records_provenance() -> None:
    nodes = {
        1: (0.0, 0.0, 0.0),
        2: (1.0, 0.0, 0.0),
        3: (0.0, 1.0, 0.0),
        4: (0.0, 0.0, 1.0),
        5: (0.0, 0.0, -1.0),
    }
    elements = (
        element_geometry.MeshElement(10, "C3D4", (1, 2, 3, 4)),
        element_geometry.MeshElement(11, "C3D4", (1, 2, 3, 5)),
    )

    result = element_geometry.lump_nodal_volumes(nodes, elements)

    assert result.total_volume == pytest.approx(1.0 / 3.0)
    assert math.fsum(node.volume for node in result.nodes) == pytest.approx(
        result.total_volume
    )
    assert result.volume_for_node(1) == pytest.approx(1.0 / 12.0)
    assert result.volume_for_node(4) == pytest.approx(1.0 / 24.0)
    assert result.nodes[0].source_element_ids == (10, 11)
    assert result.nodes[3].source_element_ids == (10,)


def test_lumping_uses_all_ten_c3d10_nodes() -> None:
    nodes = dict(enumerate(element_geometry.reference_c3d10_nodes(), start=1))
    element = element_geometry.MeshElement(20, "C3D10", tuple(nodes))

    result = element_geometry.lump_nodal_volumes(nodes, (element,))

    assert len(result.nodes) == 10
    assert all(node.volume == pytest.approx(1.0 / 60.0) for node in result.nodes)


def test_lumping_rejects_a_missing_node() -> None:
    element = element_geometry.MeshElement(30, "C3D4", (1, 2, 3, 4))

    with pytest.raises(ValueError, match="missing node 4"):
        element_geometry.lump_nodal_volumes(
            {
                1: (0.0, 0.0, 0.0),
                2: (1.0, 0.0, 0.0),
                3: (0.0, 1.0, 0.0),
            },
            (element,),
        )


def test_mesh_element_rejects_bad_connectivity() -> None:
    with pytest.raises(ValueError, match="needs 4 nodes"):
        element_geometry.MeshElement(1, "C3D4", (1, 2, 3))
    with pytest.raises(ValueError, match="repeats a node"):
        element_geometry.MeshElement(1, "C3D4", (1, 2, 3, 3))


def test_geometry_rejects_non_finite_coordinates() -> None:
    points = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, math.nan))

    with pytest.raises(ValueError, match="finite"):
        element_geometry.c3d4_volume(points)

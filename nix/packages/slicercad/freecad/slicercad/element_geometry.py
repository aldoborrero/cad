"""Pure geometry and volume lumping for supported CalculiX solid elements."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

type Point3 = tuple[float, float, float]
type ElementType = Literal["C3D4", "C3D10"]

_C3D10_EDGES = ((0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3))
_REFERENCE_NODES: tuple[Point3, ...] = (
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.5, 0.0, 0.0),
    (0.5, 0.5, 0.0),
    (0.0, 0.5, 0.0),
    (0.0, 0.0, 0.5),
    (0.5, 0.0, 0.5),
    (0.0, 0.5, 0.5),
)

# Three-point Gauss-Legendre on [0, 1]. Under the Duffy transform its tensor
# product integrates the cubic C3D10 Jacobian determinant exactly: the resulting
# degrees are at most 5, 4 and 3 in the three cube coordinates.
_ROOT = math.sqrt(3.0 / 5.0)
_GAUSS_3 = (
    ((1.0 - _ROOT) / 2.0, 5.0 / 18.0),
    (0.5, 4.0 / 9.0),
    ((1.0 + _ROOT) / 2.0, 5.0 / 18.0),
)


@dataclass(frozen=True)
class MeshElement:
    element_id: int
    element_type: ElementType
    node_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.element_type not in ("C3D4", "C3D10"):
            raise ValueError(f"unsupported volume element type {self.element_type!r}")
        expected = 4 if self.element_type == "C3D4" else 10
        if len(self.node_ids) != expected:
            raise ValueError(
                f"{self.element_type} element {self.element_id} needs {expected} "
                f"nodes, got {len(self.node_ids)}"
            )
        if len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError(f"element {self.element_id} repeats a node id")


@dataclass(frozen=True)
class ElementVolume:
    element_id: int
    element_type: ElementType
    volume: float
    max_midpoint_deviation: float


@dataclass(frozen=True)
class NodalVolume:
    node_id: int
    volume: float
    source_element_ids: tuple[int, ...]


@dataclass(frozen=True)
class LumpedVolumes:
    total_volume: float
    elements: tuple[ElementVolume, ...]
    nodes: tuple[NodalVolume, ...]

    def volume_for_node(self, node_id: int) -> float:
        for node in self.nodes:
            if node.node_id == node_id:
                return node.volume
        raise KeyError(node_id)


def _point(point: Sequence[float]) -> Point3:
    if len(point) != 3:
        raise ValueError(f"a mesh point needs 3 coordinates, got {len(point)}")
    if any(not math.isfinite(value) for value in point):
        raise ValueError("mesh coordinates must be finite")
    x, y, z = point
    return x, y, z


def _subtract(left: Point3, right: Point3) -> Point3:
    return left[0] - right[0], left[1] - right[1], left[2] - right[2]


def _determinant(columns: tuple[Point3, Point3, Point3]) -> float:
    first, second, third = columns
    return (
        first[0] * (second[1] * third[2] - second[2] * third[1])
        - second[0] * (first[1] * third[2] - first[2] * third[1])
        + third[0] * (first[1] * second[2] - first[2] * second[1])
    )


def _distance(left: Point3, right: Point3) -> float:
    delta = _subtract(left, right)
    return math.sqrt(math.fsum(value * value for value in delta))


def _midpoint(left: Point3, right: Point3) -> Point3:
    return (
        (left[0] + right[0]) / 2.0,
        (left[1] + right[1]) / 2.0,
        (left[2] + right[2]) / 2.0,
    )


def c3d10_midpoint_deviation(points: Sequence[Sequence[float]]) -> float:
    """Return the largest midside-node departure from its straight edge."""
    coordinates = tuple(_point(point) for point in points)
    if len(coordinates) != 10:
        raise ValueError(f"C3D10 needs 10 points, got {len(coordinates)}")
    return max(
        _distance(
            coordinates[index + 4], _midpoint(coordinates[left], coordinates[right])
        )
        for index, (left, right) in enumerate(_C3D10_EDGES)
    )


def _c3d10_shape_derivatives(r: float, s: float, t: float) -> tuple[Point3, ...]:
    barycentric = (1.0 - r - s - t, r, s, t)
    derivatives: tuple[Point3, ...] = (
        (-1.0, -1.0, -1.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    result: list[Point3] = []
    for value, derivative in zip(barycentric, derivatives, strict=True):
        factor = 4.0 * value - 1.0
        result.append(
            (
                factor * derivative[0],
                factor * derivative[1],
                factor * derivative[2],
            )
        )
    for left, right in _C3D10_EDGES:
        values = tuple(
            4.0
            * (
                barycentric[right] * derivatives[left][axis]
                + barycentric[left] * derivatives[right][axis]
            )
            for axis in range(3)
        )
        result.append((values[0], values[1], values[2]))
    return tuple(result)


def _c3d10_jacobian_determinant(points: Sequence[Point3], reference: Point3) -> float:
    derivatives = _c3d10_shape_derivatives(*reference)
    columns: list[Point3] = []
    for axis in range(3):
        values = tuple(
            math.fsum(
                point[coordinate] * derivative[axis]
                for point, derivative in zip(points, derivatives, strict=True)
            )
            for coordinate in range(3)
        )
        columns.append((values[0], values[1], values[2]))
    return _determinant((columns[0], columns[1], columns[2]))


def c3d4_volume(points: Sequence[Sequence[float]]) -> float:
    coordinates = tuple(_point(point) for point in points)
    if len(coordinates) != 4:
        raise ValueError(f"C3D4 needs 4 points, got {len(coordinates)}")
    first, second, third, fourth = coordinates
    determinant = _determinant(
        (
            _subtract(second, first),
            _subtract(third, first),
            _subtract(fourth, first),
        )
    )
    volume = abs(determinant) / 6.0
    if volume == 0.0:
        raise ValueError("C3D4 has a singular Jacobian")
    return volume


def c3d10_volume(points: Sequence[Sequence[float]]) -> float:
    """Integrate a quadratic tetrahedron from all ten geometry nodes."""
    coordinates = tuple(_point(point) for point in points)
    if len(coordinates) != 10:
        raise ValueError(f"C3D10 needs 10 points, got {len(coordinates)}")
    weighted_determinants: list[float] = []
    determinant_sign = 0
    for u, weight_u in _GAUSS_3:
        for v, weight_v in _GAUSS_3:
            for w, weight_w in _GAUSS_3:
                reference = (u, (1.0 - u) * v, (1.0 - u) * (1.0 - v) * w)
                determinant = _c3d10_jacobian_determinant(coordinates, reference)
                if determinant == 0.0:
                    raise ValueError("C3D10 has a singular Jacobian")
                current_sign = 1 if determinant > 0.0 else -1
                if determinant_sign and current_sign != determinant_sign:
                    raise ValueError("C3D10 Jacobian changes sign inside the element")
                determinant_sign = current_sign
                duffy_jacobian = (1.0 - u) ** 2 * (1.0 - v)
                weighted_determinants.append(
                    abs(determinant) * weight_u * weight_v * weight_w * duffy_jacobian
                )
    volume = math.fsum(weighted_determinants)
    if volume == 0.0:
        raise ValueError("C3D10 has zero volume")
    return volume


def element_volume(
    element_type: ElementType, points: Sequence[Sequence[float]]
) -> float:
    if element_type == "C3D4":
        return c3d4_volume(points)
    if element_type == "C3D10":
        return c3d10_volume(points)
    raise ValueError(f"unsupported volume element type {element_type!r}")


def lump_nodal_volumes(
    node_positions: Mapping[int, Sequence[float]],
    elements: Sequence[MeshElement],
) -> LumpedVolumes:
    """Distribute each physical element volume equally among its nodes."""
    if not elements:
        raise ValueError("the volume mesh must not be empty")
    if len({element.element_id for element in elements}) != len(elements):
        raise ValueError("volume element ids must be unique")

    nodal: dict[int, float] = {}
    source_elements: dict[int, list[int]] = {}
    element_results: list[ElementVolume] = []
    for element in elements:
        try:
            points = tuple(node_positions[node_id] for node_id in element.node_ids)
        except KeyError as error:
            raise ValueError(
                f"element {element.element_id} references missing node {error.args[0]}"
            ) from error
        volume = element_volume(element.element_type, points)
        deviation = (
            0.0 if element.element_type == "C3D4" else c3d10_midpoint_deviation(points)
        )
        element_results.append(
            ElementVolume(
                element_id=element.element_id,
                element_type=element.element_type,
                volume=volume,
                max_midpoint_deviation=deviation,
            )
        )
        share = volume / len(element.node_ids)
        for node_id in element.node_ids:
            nodal[node_id] = nodal.get(node_id, 0.0) + share
            source_elements.setdefault(node_id, []).append(element.element_id)

    total_volume = math.fsum(element.volume for element in element_results)
    nodal_results = tuple(
        NodalVolume(
            node_id=node_id,
            volume=nodal[node_id],
            source_element_ids=tuple(source_elements[node_id]),
        )
        for node_id in sorted(nodal)
    )
    lumped_total = math.fsum(node.volume for node in nodal_results)
    tolerance = max(
        math.ulp(total_volume) * len(nodal_results) * 2.0, total_volume * 1e-12
    )
    if abs(lumped_total - total_volume) > tolerance:
        raise ValueError("lumped nodal volumes do not conserve mesh volume")
    return LumpedVolumes(
        total_volume=total_volume,
        elements=tuple(element_results),
        nodes=nodal_results,
    )


def reference_c3d10_nodes() -> tuple[Point3, ...]:
    """Expose the documented node order for fixtures and adapters."""
    return _REFERENCE_NODES

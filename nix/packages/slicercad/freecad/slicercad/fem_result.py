"""Convert FreeCAD FEM nodal results into volume-weighted stress samples."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from . import element_geometry, orient

type Matrix3 = tuple[
    element_geometry.Point3, element_geometry.Point3, element_geometry.Point3
]
type DataSource = Literal["nodal_volume_lumped"]


def _dot(left: element_geometry.Point3, right: element_geometry.Point3) -> float:
    return math.fsum(a * b for a, b in zip(left, right, strict=True))


def _determinant(matrix: Matrix3) -> float:
    first, second, third = matrix
    return (
        first[0] * (second[1] * third[2] - second[2] * third[1])
        - first[1] * (second[0] * third[2] - second[2] * third[0])
        + first[2] * (second[0] * third[1] - second[1] * third[0])
    )


@dataclass(frozen=True)
class RigidTransform:
    """A proper rotation and translation from FEM coordinates to ranking coordinates."""

    rotation: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    translation: element_geometry.Point3 = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        values = (
            *self.rotation[0],
            *self.rotation[1],
            *self.rotation[2],
            *self.translation,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("the FEM coordinate transform must be finite")
        for row in self.rotation:
            if not math.isclose(_dot(row, row), 1.0, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError("the FEM coordinate transform must be orthonormal")
        if any(
            not math.isclose(
                _dot(self.rotation[left], self.rotation[right]),
                0.0,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            for left, right in ((0, 1), (0, 2), (1, 2))
        ):
            raise ValueError("the FEM coordinate transform must be orthonormal")
        if not math.isclose(
            _determinant(self.rotation), 1.0, rel_tol=0.0, abs_tol=1e-9
        ):
            raise ValueError("the FEM coordinate transform must be a proper rotation")

    def point(self, source: element_geometry.Point3) -> element_geometry.Point3:
        rotated = tuple(_dot(row, source) for row in self.rotation)
        return (
            rotated[0] + self.translation[0],
            rotated[1] + self.translation[1],
            rotated[2] + self.translation[2],
        )

    def stress(self, source: orient.StressTuple) -> orient.StressTuple:
        xx, yy, zz, xy, xz, yz = source
        tensor = ((xx, xy, xz), (xy, yy, yz), (xz, yz, zz))

        def component(row: int, column: int) -> float:
            return math.fsum(
                self.rotation[row][left]
                * tensor[left][right]
                * self.rotation[column][right]
                for left in range(3)
                for right in range(3)
            )

        rotated = tuple(
            tuple(component(row, column) for column in range(3)) for row in range(3)
        )
        return (
            rotated[0][0],
            rotated[1][1],
            rotated[2][2],
            (rotated[0][1] + rotated[1][0]) / 2.0,
            (rotated[0][2] + rotated[2][0]) / 2.0,
            (rotated[1][2] + rotated[2][1]) / 2.0,
        )


@dataclass(frozen=True)
class A0StressField:
    samples: tuple[orient.WeightedStress, ...]
    mesh_volume: float
    element_volumes: tuple[element_geometry.ElementVolume, ...]
    max_midpoint_deviation: float
    data_source: DataSource = "nodal_volume_lumped"


def _attribute(source: Any, name: str) -> Any:
    try:
        return getattr(source, name)
    except AttributeError as error:
        raise ValueError(f"FreeCAD FEM object has no {name} data") from error


def _ids(values: Any, label: str) -> tuple[int, ...]:
    try:
        result = tuple(int(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a sequence of integer ids") from error
    if any(value <= 0 for value in result):
        raise ValueError(f"{label} must contain positive ids")
    return result


def _mesh_point(mesh: Any, node_id: int) -> element_geometry.Point3:
    try:
        point = mesh.getNodeById(node_id)
        return float(point.x), float(point.y), float(point.z)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(
            f"mesh node {node_id} has no finite xyz coordinates"
        ) from error


def _mesh_elements(mesh: Any) -> tuple[element_geometry.MeshElement, ...]:
    element_ids = _ids(_attribute(mesh, "Volumes"), "mesh volume element ids")
    if not element_ids:
        raise ValueError("the FreeCAD FEM mesh has no volume elements")
    elements: list[element_geometry.MeshElement] = []
    for element_id in element_ids:
        try:
            node_ids = _ids(
                mesh.getElementNodes(element_id),
                f"element {element_id} node ids",
            )
        except AttributeError as error:
            raise ValueError(
                "FreeCAD FEM mesh cannot provide element connectivity"
            ) from error
        if len(node_ids) == 4:
            element_type: element_geometry.ElementType = "C3D4"
        elif len(node_ids) == 10:
            element_type = "C3D10"
        else:
            raise ValueError(
                f"unsupported volume element {element_id} with {len(node_ids)} nodes; "
                "A0 supports only C3D4 and C3D10"
            )
        elements.append(
            element_geometry.MeshElement(element_id, element_type, node_ids)
        )
    return tuple(elements)


def _result_stresses(result: Any) -> dict[int, orient.StressTuple]:
    node_ids = _ids(_attribute(result, "NodeNumbers"), "result node ids")
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("result node ids must be unique")
    field = orient.field_from_lists(
        xx=_attribute(result, "NodeStressXX"),
        yy=_attribute(result, "NodeStressYY"),
        zz=_attribute(result, "NodeStressZZ"),
        xy=_attribute(result, "NodeStressXY"),
        xz=_attribute(result, "NodeStressXZ"),
        yz=_attribute(result, "NodeStressYZ"),
    )
    if len(node_ids) != len(field):
        raise ValueError(
            f"result has {len(node_ids)} node ids but {len(field)} stress tensors"
        )
    return dict(zip(node_ids, field, strict=True))


def lumped_mesh_volumes(mesh: Any) -> element_geometry.LumpedVolumes:
    """Integrate a FreeCAD volume mesh and distribute its volume to its nodes."""
    elements = _mesh_elements(mesh)
    volume_node_ids = {node_id for element in elements for node_id in element.node_ids}
    node_positions = {
        node_id: _mesh_point(mesh, node_id) for node_id in volume_node_ids
    }
    return element_geometry.lump_nodal_volumes(node_positions, elements)


def volume_lumped_stress_field(
    mesh: Any,
    result: Any,
    *,
    transform: RigidTransform | None = None,
) -> A0StressField:
    """Build A0 samples from a FreeCAD FemMesh and FemResultObject.

    FreeCAD's stresses are extrapolated nodal values. Each one receives the
    positive volume lumped to that node from every adjacent volume element.
    """
    lumped = lumped_mesh_volumes(mesh)
    volume_node_ids = {node.node_id for node in lumped.nodes}
    node_positions = {
        node_id: _mesh_point(mesh, node_id) for node_id in volume_node_ids
    }
    stresses = _result_stresses(result)
    result_node_ids = set(stresses)
    missing = sorted(volume_node_ids - result_node_ids)
    extra = sorted(result_node_ids - volume_node_ids)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing volume nodes {missing[:8]}")
        if extra:
            details.append(f"unexpected result nodes {extra[:8]}")
        raise ValueError(
            "result field does not match the volume mesh: " + "; ".join(details)
        )

    coordinate_transform = transform or RigidTransform()
    samples = tuple(
        orient.WeightedStress(
            stress=coordinate_transform.stress(stresses[node.node_id]),
            volume=node.volume,
            sample_id=node.node_id,
            position=coordinate_transform.point(node_positions[node.node_id]),
            source_node_ids=(node.node_id,),
            source_element_ids=node.source_element_ids,
        )
        for node in lumped.nodes
    )
    return A0StressField(
        samples=samples,
        mesh_volume=lumped.total_volume,
        element_volumes=lumped.elements,
        max_midpoint_deviation=max(
            element.max_midpoint_deviation for element in lumped.elements
        ),
    )

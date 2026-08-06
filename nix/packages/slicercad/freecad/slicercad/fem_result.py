"""Convert FreeCAD FEM nodal results into volume-weighted stress samples."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from . import element_geometry, orient

type Matrix3 = tuple[
    element_geometry.Point3, element_geometry.Point3, element_geometry.Point3
]
type DataSource = Literal["nodal_volume_lumped"]
type ProvenanceStatus = Literal["verified"]

_MESH_SIGNATURE_PROPERTY = "SlicercadMeshSignature"
_ANALYSIS_SIGNATURE_PROPERTY = "SlicercadAnalysisSignature"
_FRD_COORDINATE_TOLERANCE = 6e-6


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
    mesh_signature: str
    analysis_signature: str
    provenance_status: ProvenanceStatus = "verified"
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


def mesh_signature(mesh: Any) -> str:
    """Return a deterministic identity for volume connectivity and coordinates."""
    elements = _mesh_elements(mesh)
    node_ids = sorted({node_id for element in elements for node_id in element.node_ids})
    digest = hashlib.sha256()
    for node_id in node_ids:
        point = _mesh_point(mesh, node_id)
        digest.update(
            f"N:{node_id}:{point[0].hex()}:{point[1].hex()}:{point[2].hex()}\n".encode()
        )
    for element in elements:
        connectivity = ",".join(str(node_id) for node_id in element.node_ids)
        digest.update(
            f"E:{element.element_id}:{element.element_type}:{connectivity}\n".encode()
        )
    return digest.hexdigest()


def mesh_bounds(mesh: Any) -> tuple[float, float, float, float, float, float]:
    """Axis-aligned bounds of the volume nodes in source mesh coordinates."""
    elements = _mesh_elements(mesh)
    points = [
        _mesh_point(mesh, node_id)
        for node_id in {node for element in elements for node in element.node_ids}
    ]
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        min(point[2] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
        max(point[2] for point in points),
    )


def _set_string_property(result: Any, name: str, value: str) -> None:
    properties = getattr(result, "PropertiesList", ())
    if name not in properties and hasattr(result, "addProperty"):
        result.addProperty(
            "App::PropertyString",
            name,
            "SlicerCAD",
            "Identity recorded when the FEM result was produced",
            True,
        )
    setattr(result, name, value)


def record_result_provenance(
    result: Any,
    mesh: Any,
    *,
    analysis_signature: str,
) -> None:
    """Stamp a newly solved FreeCAD result with the inputs needed for reuse."""
    if not analysis_signature:
        raise ValueError("analysis signature must not be empty")
    _set_string_property(result, _MESH_SIGNATURE_PROPERTY, mesh_signature(mesh))
    _set_string_property(result, _ANALYSIS_SIGNATURE_PROPERTY, analysis_signature)


def _embedded_result_mesh(result: Any) -> Any:
    result_mesh_object = _attribute(result, "Mesh")
    return _attribute(result_mesh_object, "FemMesh")


def solved_result_signature(result: Any) -> str:
    """Identify the stored mesh and nodal tensor values of a solved result."""
    mesh = _embedded_result_mesh(result)
    stresses = _result_stresses(result)
    digest = hashlib.sha256()
    digest.update(f"mesh:{mesh_signature(mesh)}\n".encode())
    for node_id, stress in sorted(stresses.items()):
        values = ":".join(value.hex() for value in stress)
        digest.update(f"stress:{node_id}:{values}\n".encode())
    return digest.hexdigest()


def field_from_solved_result(
    result: Any,
    *,
    mesh: Any | None = None,
    transform: RigidTransform | None = None,
) -> A0StressField:
    """Adopt an ordinary solved FreeCAD result, then use the verified A0 path."""
    source_mesh = _embedded_result_mesh(result) if mesh is None else mesh
    has_mesh = hasattr(result, _MESH_SIGNATURE_PROPERTY)
    has_analysis = hasattr(result, _ANALYSIS_SIGNATURE_PROPERTY)
    if has_mesh != has_analysis:
        raise ValueError("FEM result has incomplete SlicerCAD provenance")
    if has_analysis:
        analysis_signature = str(getattr(result, _ANALYSIS_SIGNATURE_PROPERTY))
    else:
        analysis_signature = f"result:{solved_result_signature(result)}"
        record_result_provenance(
            result,
            source_mesh,
            analysis_signature=analysis_signature,
        )
    return volume_lumped_stress_field(
        source_mesh,
        result,
        analysis_signature=analysis_signature,
        transform=transform,
    )


def _verify_result_mesh(current_mesh: Any, result: Any) -> dict[int, int]:
    result_mesh = _embedded_result_mesh(result)
    current_elements = _mesh_elements(current_mesh)
    result_elements = _mesh_elements(result_mesh)
    current_node_ids = sorted(
        {node_id for element in current_elements for node_id in element.node_ids}
    )
    result_node_ids = sorted(
        {node_id for element in result_elements for node_id in element.node_ids}
    )
    if len(current_node_ids) != len(result_node_ids):
        raise ValueError("stale FEM result: result mesh node count has changed")
    current_nodes = {
        node_id: _mesh_point(current_mesh, node_id) for node_id in current_node_ids
    }
    result_nodes = {
        node_id: _mesh_point(result_mesh, node_id) for node_id in result_node_ids
    }
    coordinate_scale = max(
        1.0,
        max(abs(value) for point in current_nodes.values() for value in point),
        max(abs(value) for point in result_nodes.values() for value in point),
    )
    absolute_tolerance = coordinate_scale * _FRD_COORDINATE_TOLERANCE

    def bucket(point: element_geometry.Point3) -> tuple[int, int, int]:
        return (
            math.floor(point[0] / absolute_tolerance),
            math.floor(point[1] / absolute_tolerance),
            math.floor(point[2] / absolute_tolerance),
        )

    current_buckets: dict[
        tuple[int, int, int], list[tuple[int, element_geometry.Point3]]
    ] = {}
    for node_id, point in current_nodes.items():
        current_buckets.setdefault(bucket(point), []).append((node_id, point))

    result_to_current: dict[int, int] = {}
    matched_current: set[int] = set()
    for result_id, stored in result_nodes.items():
        centre = bucket(stored)
        candidates = [
            (current_id, current)
            for x_offset in (-1, 0, 1)
            for y_offset in (-1, 0, 1)
            for z_offset in (-1, 0, 1)
            for current_id, current in current_buckets.get(
                (
                    centre[0] + x_offset,
                    centre[1] + y_offset,
                    centre[2] + z_offset,
                ),
                (),
            )
            if current_id not in matched_current
            and all(
                math.isclose(
                    left,
                    right,
                    rel_tol=0.0,
                    abs_tol=absolute_tolerance,
                )
                for left, right in zip(current, stored, strict=True)
            )
        ]
        if len(candidates) != 1:
            raise ValueError(
                "stale FEM result: stored mesh node cannot be matched uniquely "
                f"({result_id} {stored!r}, {len(candidates)} candidates)"
            )
        current_id, _ = candidates[0]
        result_to_current[result_id] = current_id
        matched_current.add(current_id)

    current_connectivity = Counter(
        (element.element_type, tuple(sorted(element.node_ids)))
        for element in current_elements
    )
    result_connectivity = Counter(
        (
            element.element_type,
            tuple(sorted(result_to_current[node_id] for node_id in element.node_ids)),
        )
        for element in result_elements
    )
    if current_connectivity != result_connectivity:
        raise ValueError("stale FEM result: result mesh connectivity has changed")
    return result_to_current


def mesh_matches_result(mesh: Any, result: Any) -> bool:
    """Whether a source mesh matches the compacted mesh stored by FreeCAD."""
    try:
        _verify_result_mesh(mesh, result)
    except ValueError:
        return False
    return True


def _verify_result_provenance(
    mesh: Any,
    result: Any,
    analysis_signature: str,
) -> tuple[str, dict[int, int]]:
    if not analysis_signature:
        raise ValueError("analysis signature must not be empty")
    try:
        recorded_mesh = str(getattr(result, _MESH_SIGNATURE_PROPERTY))
        recorded_analysis = str(getattr(result, _ANALYSIS_SIGNATURE_PROPERTY))
    except AttributeError as error:
        raise ValueError(
            "FEM result has no SlicerCAD provenance; rerun the analysis"
        ) from error
    current_mesh = mesh_signature(mesh)
    if recorded_mesh != current_mesh:
        raise ValueError("stale FEM result: volume mesh signature has changed")
    if recorded_analysis != analysis_signature:
        raise ValueError("stale FEM result: analysis signature has changed")
    return current_mesh, _verify_result_mesh(mesh, result)


def volume_lumped_stress_field(
    mesh: Any,
    result: Any,
    *,
    analysis_signature: str,
    transform: RigidTransform | None = None,
) -> A0StressField:
    """Build A0 samples from a FreeCAD FemMesh and FemResultObject.

    FreeCAD's stresses are extrapolated nodal values. Each one receives the
    positive volume lumped to that node from every adjacent volume element.
    """
    verified_mesh_signature, result_to_mesh_node = _verify_result_provenance(
        mesh, result, analysis_signature
    )
    lumped = lumped_mesh_volumes(mesh)
    volume_node_ids = {node.node_id for node in lumped.nodes}
    node_positions = {
        node_id: _mesh_point(mesh, node_id) for node_id in volume_node_ids
    }
    result_stresses = _result_stresses(result)
    try:
        stresses = {
            result_to_mesh_node[node_id]: stress
            for node_id, stress in result_stresses.items()
        }
    except KeyError as error:
        raise ValueError(
            f"result stress references node {error.args[0]} outside its stored mesh"
        ) from error
    if len(stresses) != len(result_stresses):
        raise ValueError("result mesh maps multiple stress nodes to one volume node")
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
        mesh_signature=verified_mesh_signature,
        analysis_signature=analysis_signature,
    )

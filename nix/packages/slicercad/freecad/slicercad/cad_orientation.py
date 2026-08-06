"""FreeCAD geometry discovery for load-aware print orientation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from . import fem_result, orient


def _linked_source_meshes(document: Any, part: Any) -> list[Any]:
    return [
        obj
        for obj in document.Objects
        if getattr(obj, "Shape", None) is part and hasattr(obj, "FemMesh")
    ]


def _mesh_bounds_match_part(mesh: Any, part: Any) -> bool:
    mesh_bounds = fem_result.mesh_bounds(mesh)
    box = part.Shape.BoundBox
    shape_bounds = (
        float(box.XMin),
        float(box.YMin),
        float(box.ZMin),
        float(box.XMax),
        float(box.YMax),
        float(box.ZMax),
    )
    scale = max(1.0, *(abs(value) for value in (*mesh_bounds, *shape_bounds)))
    tolerance = scale * 1e-5
    return all(
        abs(left - right) <= tolerance
        for left, right in zip(mesh_bounds, shape_bounds, strict=True)
    )


def _mesh_volume_matches_part(mesh: Any, part: Any) -> bool:
    mesh_volume = fem_result.lumped_mesh_volumes(mesh).total_volume
    part_volume = float(part.Shape.Volume)
    if part_volume <= 0.0:
        return False
    return abs(mesh_volume - part_volume) / part_volume <= 0.01


def printable_solids(document: Any) -> list[Any]:
    """Return document objects containing at least one printable solid."""
    solids = []
    for obj in document.Objects:
        shape = getattr(obj, "Shape", None)
        if shape is None:
            continue
        try:
            if not shape.isNull() and bool(shape.Solids):
                solids.append(obj)
        except AttributeError:
            continue
    return solids


def solved_results(document: Any) -> list[Any]:
    """Return FEM result objects that expose a nodal stress tensor and mesh."""
    results = []
    required = (
        "Mesh",
        "NodeNumbers",
        "NodeStressXX",
        "NodeStressYY",
        "NodeStressZZ",
        "NodeStressXY",
        "NodeStressXZ",
        "NodeStressYZ",
    )
    for obj in document.Objects:
        try:
            is_result = bool(obj.isDerivedFrom("Fem::FemResultObject"))
        except AttributeError:
            is_result = False
        if not is_result or not all(hasattr(obj, name) for name in required):
            continue
        try:
            node_count = len(obj.NodeNumbers)
            has_complete_stress = node_count > 0 and all(
                len(getattr(obj, name)) == node_count for name in required[2:]
            )
        except TypeError:
            has_complete_stress = False
        if has_complete_stress:
            results.append(obj)
    return results


def source_mesh_for(document: Any, result: Any, part: Any) -> Any | None:
    """Find the original geometry-bearing mesh for one result and CAD part."""
    matches = []
    for obj in _linked_source_meshes(document, part):
        if (
            fem_result.mesh_matches_result(obj.FemMesh, result)
            and _mesh_bounds_match_part(obj.FemMesh, part)
            and _mesh_volume_matches_part(obj.FemMesh, part)
        ):
            matches.append(obj)
    if len(matches) != 1:
        return None
    return matches[0]


def result_parts(document: Any, result: Any) -> list[Any]:
    """Return printable parts unambiguously linked to a result source mesh."""
    return [
        part
        for part in printable_solids(document)
        if source_mesh_for(document, result, part) is not None
    ]


def has_linked_result_part(document: Any, result: Any) -> bool:
    """Cheap toolbar predicate; full mesh verification happens on activation."""
    return any(
        _linked_source_meshes(document, part) for part in printable_solids(document)
    )


def face_candidates(
    objects: Sequence[Any], *, tolerance_degrees: float = 5.0
) -> tuple[orient.Candidate, ...]:
    """Collect deterministic unoriented candidates from every planar face."""
    faces: list[tuple[orient.Vector3, float]] = []
    for obj in objects:
        shape = getattr(obj, "Shape", None)
        if shape is None:
            continue
        for face in getattr(shape, "Faces", ()):
            surface = getattr(face, "Surface", None)
            if surface is None or not bool(surface.isPlanar()):
                continue
            normal = face.normalAt(0.0, 0.0)
            faces.append(
                (
                    (float(normal.x), float(normal.y), float(normal.z)),
                    float(face.Area),
                )
            )
    return tuple(orient.candidates(faces, tolerance_degrees=tolerance_degrees))

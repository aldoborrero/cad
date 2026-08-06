"""Run the repeated-mesh Phase 3 orientation validation suite.

Full study, from the repository root inside the development environment::

    freecadcmd --module-path=nix/packages/slicercad/freecad \
        nix/packages/slicercad/tools/validate_phase3.py \
        --pass=--fixture --pass=cantilever

Use ``--smoke`` while changing fixtures. The command writes versioned JSON,
CSV and SVG artefacts below ``nix/packages/slicercad/validation/phase3``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Any

import FreeCAD
import ObjectsFem
import Part
from femmesh.gmshtools import GmshTools
from femtools import ccxtools

if TYPE_CHECKING:
    from freecad.slicercad import convergence, fem_result, orient
else:
    from slicercad import convergence, fem_result, orient

SCHEMA_VERSION = 1
TAIL_FRACTIONS = (0.01, 0.05)
RANKING_TAIL_FRACTION = 0.01
CANDIDATES = {
    "x": orient.Candidate((1.0, 0.0, 0.0), source="validation_axis"),
    "y": orient.Candidate((0.0, 1.0, 0.0), source="validation_axis"),
    "z": orient.Candidate((0.0, 0.0, 1.0), source="validation_axis"),
}
ELEMENT_CARD = re.compile(
    r"^\s*\*ELEMENT\s*,[^\n]*\bTYPE\s*=\s*([^,\s]+)", re.IGNORECASE | re.MULTILINE
)


@dataclass(frozen=True)
class FaceSelector:
    point: tuple[float, float, float]
    label: str


@dataclass(frozen=True)
class ForceSpec:
    face: FaceSelector
    vector: tuple[float, float, float]
    force_n: float


@dataclass(frozen=True)
class Fixture:
    name: str
    purpose: str
    shape: Any
    fixed_faces: tuple[FaceSelector, ...]
    forces: tuple[ForceSpec, ...]
    mesh_sizes: tuple[float, float, float, float]


class SeededGmshTools(GmshTools):  # type: ignore[misc]
    """Add the installed gmsh's documented random seed to FreeCAD's geo file."""

    def __init__(self, mesh: Any, seed: int):
        self.seed = seed
        super().__init__(mesh)

    def write_geo(self) -> None:
        super().write_geo()
        path = Path(self.temp_file_geo)
        source = path.read_text(encoding="utf-8")
        marker = "// min, max Characteristic Length\n"
        if marker not in source:
            raise RuntimeError("FreeCAD gmsh input has no mesh-parameter marker")
        source, thread_replacements = re.subn(
            r"General\.NumThreads\s*=\s*\d+;",
            "General.NumThreads = 1;",
            source,
            count=1,
        )
        if thread_replacements != 1:
            raise RuntimeError("FreeCAD gmsh input has no thread-count option")
        seeded = (
            f"// slicercad Phase 3 reproducibility\n"
            f"Mesh.RandomSeed = {self.seed};\n"
            "Mesh.Reproducible = 1;\n\n"
        )
        path.write_text(source.replace(marker, seeded + marker, 1), encoding="utf-8")


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"required FEM executable is not on PATH: {name}")
    return path


def command_version(command: list[str]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    output = (completed.stdout or completed.stderr).strip()
    if not output:
        raise RuntimeError(f"version command produced no output: {command}")
    return output.splitlines()[0]


def configure_fem(gmsh: str, ccx: str) -> None:
    FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Gmsh").SetString(
        "gmshBinaryPath", gmsh
    )
    FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Ccx").SetString(
        "ccxBinaryPath", ccx
    )


def signature(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def actual_element_cards(inp_path: str | Path) -> tuple[str, ...]:
    cards = tuple(
        sorted(
            {
                value.upper()
                for value in ELEMENT_CARD.findall(Path(inp_path).read_text())
            }
        )
    )
    if not cards:
        raise RuntimeError("CalculiX input contains no *ELEMENT TYPE card")
    return cards


def feature(document: Any, name: str, shape: Any) -> Any:
    obj = document.addObject("Part::Feature", name)
    obj.Shape = shape.removeSplitter()
    document.recompute()
    if obj.Shape.isNull() or not obj.Shape.Solids:
        raise RuntimeError(f"fixture {name} did not produce a solid")
    if len(obj.Shape.Solids) != 1:
        raise RuntimeError(f"fixture {name} must be one connected solid")
    return obj


def cantilever(document: Any) -> Fixture:
    shape = feature(document, "Cantilever", Part.makeBox(100.0, 10.0, 10.0))
    return Fixture(
        "cantilever",
        "bending with an analytic displacement trend and fixed-face singularity",
        shape,
        (FaceSelector((0.0, 5.0, 5.0), "fixed root"),),
        (ForceSpec(FaceSelector((100.0, 5.0, 5.0), "loaded tip"), (0, 0, -1), 50),),
        (8.0, 5.0, 3.0, 2.0),
    )


def l_bracket(document: Any) -> Fixture:
    vertical = Part.makeBox(15.0, 10.0, 80.0)
    horizontal = Part.makeBox(70.0, 10.0, 15.0, FreeCAD.Vector(0.0, 0.0, 65.0))
    shape = feature(document, "LBracket", vertical.fuse(horizontal))
    return Fixture(
        "l_bracket",
        "bending plus the local concentration at a realistic bracket root",
        shape,
        (FaceSelector((7.5, 5.0, 0.0), "fixed foot"),),
        (ForceSpec(FaceSelector((70.0, 5.0, 72.5), "loaded arm"), (0, 0, -1), 60),),
        (9.0, 6.0, 4.0, 3.0),
    )


def curved_beam(document: Any) -> Fixture:
    torus = Part.makeTorus(
        30.0,
        5.0,
        FreeCAD.Vector(),
        FreeCAD.Vector(0.0, 0.0, 1.0),
        0.0,
        360.0,
        180.0,
    )
    shape = feature(document, "CurvedBeam", torus)
    return Fixture(
        "curved_beam",
        "curved stress path where Cartesian face normals are not obvious",
        shape,
        (FaceSelector((30.0, 0.0, 0.0), "fixed end"),),
        (ForceSpec(FaceSelector((-30.0, 0.0, 0.0), "loaded end"), (0, 0, -1), 35),),
        (2.8, 2.4, 2.0, 1.6),
    )


def clamp(document: Any) -> Fixture:
    base = Part.makeBox(60.0, 10.0, 10.0)
    left = Part.makeBox(10.0, 10.0, 50.0)
    right = Part.makeBox(10.0, 10.0, 50.0, FreeCAD.Vector(50.0, 0.0, 0.0))
    shape = feature(document, "Clamp", base.fuse(left).fuse(right))
    return Fixture(
        "clamp",
        "opening load with a local concentration under clamping",
        shape,
        (FaceSelector((5.0, 5.0, 50.0), "fixed jaw"),),
        (ForceSpec(FaceSelector((55.0, 5.0, 50.0), "moving jaw"), (-1, 0, 0), 40),),
        (8.0, 5.5, 4.0, 3.0),
    )


def torsion_tab(document: Any) -> Fixture:
    shaft = Part.makeCylinder(8.0, 60.0)
    tab = Part.makeBox(50.0, 8.0, 10.0, FreeCAD.Vector(-25.0, -4.0, 55.0))
    shape = feature(document, "TorsionTab", shaft.fuse(tab))
    return Fixture(
        "torsion_tab",
        "opposed tab forces producing shaft torsion and interface shear",
        shape,
        (FaceSelector((0.0, 0.0, 0.0), "fixed shaft end"),),
        (
            ForceSpec(
                FaceSelector((25.0, 0.0, 60.0), "positive tab end"), (0, 1, 0), 30
            ),
            ForceSpec(
                FaceSelector((-25.0, 0.0, 60.0), "negative tab end"), (0, -1, 0), 30
            ),
        ),
        (7.0, 5.0, 3.8, 3.0),
    )


def three_axis_frame(document: Any) -> Fixture:
    stem = Part.makeBox(24.0, 24.0, 36.0, FreeCAD.Vector(-12.0, -12.0, -36.0))
    hub = Part.makeBox(24.0, 24.0, 24.0, FreeCAD.Vector(-12.0, -12.0, 0.0))
    arm_x = Part.makeBox(48.0, 8.0, 8.0, FreeCAD.Vector(12.0, -4.0, 8.0))
    arm_y = Part.makeBox(8.0, 48.0, 8.0, FreeCAD.Vector(-4.0, 12.0, 8.0))
    arm_z = Part.makeBox(8.0, 8.0, 48.0, FreeCAD.Vector(-4.0, -4.0, 24.0))
    frame = stem.fuse(hub).fuse(arm_x).fuse(arm_y).fuse(arm_z)
    shape = feature(document, "ThreeAxisFrame", frame)
    return Fixture(
        "three_axis_frame",
        "three non-coplanar competing load paths with separate arm roots",
        shape,
        (FaceSelector((0.0, 0.0, -36.0), "fixed stem"),),
        (
            ForceSpec(FaceSelector((60.0, 0.0, 12.0), "x arm"), (0, 0, 1), 16),
            ForceSpec(FaceSelector((0.0, 60.0, 12.0), "y arm"), (1, 0, 0), 16.5),
            ForceSpec(FaceSelector((0.0, 0.0, 72.0), "z arm"), (0, 1, 0), 16),
        ),
        (9.0, 6.0, 4.5, 3.5),
    )


FIXTURES = {
    "cantilever": cantilever,
    "l_bracket": l_bracket,
    "curved_beam": curved_beam,
    "clamp": clamp,
    "torsion_tab": torsion_tab,
    "three_axis_frame": three_axis_frame,
}


def face_reference(shape: Any, selector: FaceSelector) -> str:
    target = FreeCAD.Vector(*selector.point)
    distances = [
        face.CenterOfMass.distanceToPoint(target) for face in shape.Shape.Faces
    ]
    index = min(range(len(distances)), key=distances.__getitem__)
    tolerance = max(1e-6, shape.Shape.BoundBox.DiagonalLength * 1e-7)
    if distances[index] > tolerance:
        nearest = shape.Shape.Faces[index].CenterOfMass
        raise RuntimeError(
            f"cannot locate {selector.label} at {selector.point}; nearest face centre "
            f"is ({nearest.x}, {nearest.y}, {nearest.z}), distance {distances[index]}"
        )
    return f"Face{index + 1}"


def add_analysis(document: Any, fixture: Fixture) -> tuple[Any, Any]:
    analysis = ObjectsFem.makeAnalysis(document, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(document, "Solver")
    analysis.addObject(solver)
    material = ObjectsFem.makeMaterialSolid(document, "Material")
    card = material.Material
    card["Name"] = "PLA reference"
    card["YoungsModulus"] = "3500 MPa"
    card["PoissonRatio"] = "0.35"
    card["Density"] = "1240 kg/m^3"
    material.Material = card
    analysis.addObject(material)

    fixed = ObjectsFem.makeConstraintFixed(document, "Fixed")
    fixed.References = [
        (fixture.shape, face_reference(fixture.shape, selector))
        for selector in fixture.fixed_faces
    ]
    analysis.addObject(fixed)
    for index, force in enumerate(fixture.forces):
        load = ObjectsFem.makeConstraintForce(document, f"Force{index + 1}")
        load.References = [(fixture.shape, face_reference(fixture.shape, force.face))]
        load.Force = f"{force.force_n} N"
        load.DirectionVector = FreeCAD.Vector(*force.vector)
        analysis.addObject(load)
    document.recompute()
    return analysis, solver


def create_mesh(
    document: Any,
    analysis: Any,
    shape: Any,
    size: float,
    seed: int,
    element_order: str,
) -> tuple[Any, str]:
    mesh = ObjectsFem.makeMeshGmsh(document, "Mesh")
    mesh.Shape = shape
    mesh.CharacteristicLengthMax = f"{size} mm"
    mesh.ElementOrder = element_order
    mesh.SecondOrderLinear = False
    if element_order == "2nd":
        mesh.HighOrderOptimize = "Elastic+Optimization"
    analysis.addObject(mesh)
    document.recompute()
    tool = SeededGmshTools(mesh, seed)
    tool.create_mesh()
    if mesh.FemMesh.VolumeCount <= 0:
        raise RuntimeError(f"gmsh produced no volume mesh at {size} mm, seed {seed}")
    geo = Path(tool.temp_file_geo).read_text(encoding="utf-8")
    expected = f"Mesh.RandomSeed = {seed};"
    if (
        expected not in geo
        or "Mesh.Reproducible = 1;" not in geo
        or "General.NumThreads = 1;" not in geo
    ):
        raise RuntimeError(
            "generated gmsh input does not contain deterministic meshing options"
        )
    return mesh, hashlib.sha256(geo.encode()).hexdigest()


def result_object(document: Any) -> Any:
    results = [
        obj for obj in document.Objects if obj.isDerivedFrom("Fem::FemResultObject")
    ]
    if len(results) != 1:
        raise RuntimeError(f"expected one FEM result, found {len(results)}")
    return results[0]


def frd_signature(working_dir: str) -> str:
    files = tuple(Path(working_dir).glob("*.frd"))
    if len(files) != 1:
        raise RuntimeError(f"expected one CalculiX FRD file, found {len(files)}")
    return signature(files[0])


def solve_once(
    fem: Any,
    document: Any,
    mesh: Any,
    analysis_signature: str,
) -> tuple[Any, Any, str]:
    fem.purge_results()
    fem.ccx_run()
    fem.load_results()
    result = result_object(document)
    fem_result.record_result_provenance(
        result, mesh.FemMesh, analysis_signature=analysis_signature
    )
    field = fem_result.volume_lumped_stress_field(
        mesh.FemMesh, result, analysis_signature=analysis_signature
    )
    ranking = orient.rank(
        field.samples,
        tuple(CANDIDATES.values()),
        ranking_tail_fraction=RANKING_TAIL_FRACTION,
        tail_fractions=TAIL_FRACTIONS,
    )
    return field, ranking, frd_signature(fem.working_dir)


def score_signature(ranking: Any) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            score.build,
            *(
                score.value(channel, tail)
                for tail in TAIL_FRACTIONS
                for channel in orient.CHANNELS
            ),
        )
        for score in ranking.scores
    )


def tail_json(statistic: Any) -> dict[str, Any]:
    return {
        "value_mpa": statistic.value,
        "tail_fraction": statistic.tail_fraction,
        "total_volume_mm3": statistic.total_volume,
        "tail_volume_mm3": statistic.tail_volume,
        "weight_signature": statistic.weight_signature,
        "contributions": [
            {
                "sample_id": value.sample_id,
                "value_mpa": value.value,
                "tail_volume_mm3": value.tail_volume,
                "position_mm": value.position,
                "source_node_ids": value.source_node_ids,
                "source_element_ids": value.source_element_ids,
            }
            for value in statistic.contributions
        ],
    }


def ranking_json(ranking: Any, field: Any) -> dict[str, Any]:
    ids = {candidate: candidate_id for candidate_id, candidate in CANDIDATES.items()}
    return {
        "aggregation": ranking.aggregation,
        "ranking_tail_fraction": ranking.ranking_tail_fraction,
        "tail_fractions": ranking.tail_fractions,
        "pareto_front": [ids[score.candidate] for score in ranking.pareto_front],
        "pareto_layers": [
            [ids[score.candidate] for score in layer] for layer in ranking.pareto_layers
        ],
        "display_order": [ids[score.candidate] for score in ranking.scores],
        "scores": [
            {
                "candidate_id": ids[score.candidate],
                "build": score.build,
                "source": score.candidate.source,
                "metrics": {
                    f"{channel}_cvar_{tail:g}": tail_json(
                        score.tail_score(channel, tail).statistic
                    )
                    for tail in TAIL_FRACTIONS
                    for channel in orient.CHANNELS
                },
                "nodal_max_mpa": {
                    channel: max(
                        getattr(
                            orient.layer_traction(sample.stress, score.build), channel
                        )
                        for sample in field.samples
                    )
                    for channel in orient.CHANNELS
                },
            }
            for score in ranking.scores
        ],
        "margins": [
            {
                **asdict(margin),
                "candidate_a": ids[margin.candidate_a],
                "candidate_b": ids[margin.candidate_b],
            }
            for margin in ranking.margins
        ],
        "pairwise_overlaps": [
            {
                "candidate_a": ids[left.candidate],
                "candidate_b": ids[right.candidate],
                "channel": channel,
                "tail_fraction": tail,
                "value": orient.critical_region_overlap(
                    left.critical_samples(channel, tail),
                    right.critical_samples(channel, tail),
                ),
            }
            for left, right in combinations(ranking.scores, 2)
            for tail in TAIL_FRACTIONS
            for channel in orient.CHANNELS
        ],
        "principal_tension": [
            tail_json(value) for value in ranking.principal_tension_cvar
        ],
        "principal_nodal_max_mpa": max(
            max(orient.largest_principal_stress(sample.stress), 0.0)
            for sample in field.samples
        ),
        "orientation_sensitivity": [
            asdict(value) for value in ranking.orientation_sensitivity
        ],
    }


def run_mesh(
    fixture_factory: Any,
    fixture_name: str,
    level: int,
    size: float,
    repeat: int,
    seed: int,
    *,
    determinism_check: bool,
    element_order: str,
) -> tuple[dict[str, Any], convergence.ConvergenceRun]:
    document = FreeCAD.newDocument(f"phase3_{fixture_name}_{level}_{repeat}")
    try:
        fixture = fixture_factory(document)
        analysis, solver = add_analysis(document, fixture)
        mesh, geo_signature = create_mesh(
            document, analysis, fixture.shape, size, seed, element_order
        )
        fem = ccxtools.FemToolsCcx(analysis, solver)
        fem.update_objects()
        fem.setup_working_dir()
        fem.setup_ccx()
        prerequisites = fem.check_prerequisites()
        if prerequisites:
            raise RuntimeError(prerequisites)
        fem.write_inp_file()
        inp_signature = signature(fem.inp_file_name)
        cards = actual_element_cards(fem.inp_file_name)
        expected_card = "C3D10" if element_order == "2nd" else "C3D4"
        if cards != (expected_card,):
            raise RuntimeError(
                f"configured {element_order} but CalculiX input has {cards}"
            )
        field, ranking, first_frd = solve_once(fem, document, mesh, inp_signature)
        element_types = sorted(
            {element.element_type for element in field.element_volumes}
        )
        if element_types != [expected_card]:
            raise RuntimeError(
                f"parsed mesh disagrees with input card: {element_types}"
            )
        determinism: dict[str, Any] | None = None
        if determinism_check:
            first_scores = score_signature(ranking)
            second_field, second_ranking, second_frd = solve_once(
                fem, document, mesh, inp_signature
            )
            second_scores = score_signature(second_ranking)
            determinism = {
                "same_inp_signature": inp_signature == second_field.analysis_signature,
                "same_frd_signature": first_frd == second_frd,
                "scores_bitwise_equal": first_scores == second_scores,
            }
            if not (
                determinism["same_inp_signature"]
                and determinism["scores_bitwise_equal"]
            ):
                raise RuntimeError(f"same-mesh determinism failed: {determinism}")
            field, ranking = second_field, second_ranking

        run_id = f"seed-{seed}"
        convergence_run = convergence.run_from_ranking(
            level=level,
            requested_size=size,
            run_id=run_id,
            ranking=ranking,
            candidate_id=lambda candidate: next(
                key for key, value in CANDIDATES.items() if value == candidate
            ),
        )
        cad_volume = float(fixture.shape.Shape.Volume)
        row = {
            "fixture": fixture.name,
            "purpose": fixture.purpose,
            "level": level,
            "repeat": repeat,
            "run_id": run_id,
            "requested_size_mm": size,
            "gmsh_seed": seed,
            "gmsh_geo_signature": geo_signature,
            "mesh_signature": field.mesh_signature,
            "inp_signature": inp_signature,
            "frd_signature": frd_signature(fem.working_dir),
            "configured_order": element_order,
            "second_order_linear": False,
            "high_order_optimize": (
                "Elastic+Optimization" if element_order == "2nd" else None
            ),
            "actual_calculix_element_cards": cards,
            "node_count": len(mesh.FemMesh.Nodes),
            "element_count": len(field.element_volumes),
            "mesh_volume_mm3": field.mesh_volume,
            "cad_volume_mm3": cad_volume,
            "relative_volume_error": abs(field.mesh_volume - cad_volume) / cad_volume,
            "max_midpoint_deviation_mm": field.max_midpoint_deviation,
            "data_source": field.data_source,
            "provenance_status": field.provenance_status,
            "determinism": determinism,
            "boundary_regions": {
                "fixed": [asdict(value) for value in fixture.fixed_faces],
                "loads": [asdict(value) for value in fixture.forces],
            },
            "ranking": ranking_json(ranking, field),
        }
        return row, convergence_run
    finally:
        FreeCAD.closeDocument(document.Name)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def write_csv(path: Path, runs: list[dict[str, Any]]) -> None:
    fields = (
        "fixture",
        "level",
        "repeat",
        "requested_size_mm",
        "gmsh_seed",
        "mesh_signature",
        "node_count",
        "element_count",
        "mesh_volume_mm3",
        "relative_volume_error",
        "candidate_id",
        "channel",
        "tail_fraction",
        "cvar_mpa",
        "nodal_max_mpa",
        "pareto",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for run in runs:
            ranking = run["ranking"]
            for score in ranking["scores"]:
                for tail in TAIL_FRACTIONS:
                    for channel in orient.CHANNELS:
                        writer.writerow(
                            {
                                **{field: run[field] for field in fields[:10]},
                                "candidate_id": score["candidate_id"],
                                "channel": channel,
                                "tail_fraction": tail,
                                "cvar_mpa": score["metrics"][
                                    f"{channel}_cvar_{tail:g}"
                                ]["value_mpa"],
                                "nodal_max_mpa": score["nodal_max_mpa"][channel],
                                "pareto": score["candidate_id"]
                                in ranking["pareto_front"],
                            }
                        )


def write_svg(path: Path, fixture: str, runs: list[dict[str, Any]]) -> None:
    width, height = 960, 620
    margin = 70
    fixture_runs = [run for run in runs if run["fixture"] == fixture]
    if not fixture_runs:
        return
    levels = sorted({run["level"] for run in fixture_runs})
    series: dict[tuple[str, str], list[float]] = {}
    for candidate_id in CANDIDATES:
        for channel in orient.CHANNELS:
            values = []
            for level in levels:
                measured = [
                    score["metrics"][f"{channel}_cvar_{RANKING_TAIL_FRACTION:g}"][
                        "value_mpa"
                    ]
                    for run in fixture_runs
                    if run["level"] == level
                    for score in run["ranking"]["scores"]
                    if score["candidate_id"] == candidate_id
                ]
                values.append(statistics.median(measured))
            series[(candidate_id, channel)] = values
    maximum = max(value for values in series.values() for value in values)
    maximum = maximum if maximum > 0.0 else 1.0
    colours = ("#006d77", "#d1495b", "#edae49", "#00798c", "#5f4b8b", "#3d405b")
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{margin}" y="34" font-family="sans-serif" font-size="20">'
        f"{fixture}: weighted CVaR 1%</text>",
        f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" '
        f'y2="{height - margin}" stroke="#222"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" '
        f'y2="{height - margin}" stroke="#222"/>',
    ]
    for index, level in enumerate(levels):
        x = margin + index * (width - 2 * margin) / max(1, len(levels) - 1)
        lines.append(
            f'<text x="{x}" y="{height - margin + 24}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="12">L{level}</text>'
        )
    for candidate_index, candidate_id in enumerate(CANDIDATES):
        colour = colours[candidate_index]
        for channel in orient.CHANNELS:
            points = []
            for index, value in enumerate(series[(candidate_id, channel)]):
                x = margin + index * (width - 2 * margin) / max(1, len(levels) - 1)
                y = height - margin - value / maximum * (height - 2 * margin)
                points.append(f"{x:.2f},{y:.2f}")
            dash = "" if channel == "opening" else ' stroke-dasharray="6 4"'
            lines.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{colour}" stroke-width="2"{dash}/>'
            )
        lines.append(
            f'<text x="{width - margin + 8}" '
            f'y="{margin + candidate_index * 20}" font-family="sans-serif" '
            f'font-size="12" fill="{colour}">{candidate_id}</text>'
        )
    lines.append(
        '<text x="72" y="594" font-family="sans-serif" font-size="11">'
        "solid: opening; dashed: shear; each point is the median across remeshes"
        "</text>"
    )
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="append", choices=tuple(FIXTURES))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--levels", type=int, default=4)
    parser.add_argument("--element-order", choices=("1st", "2nd"), default="2nd")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("nix/packages/slicercad/validation/phase3/results.json"),
    )
    passed = [
        value.removeprefix("--pass=")
        for value in sys.argv[1:]
        if value.startswith("--pass=")
    ]
    return parser.parse_args(passed)


def main() -> None:
    args = parse_args()
    if args.repeats < 1 or not 1 <= args.levels <= 4:
        raise ValueError("repeats must be positive and levels must be in [1, 4]")
    selected = args.fixture or list(FIXTURES)
    if args.element_order == "1st" and selected != ["cantilever"]:
        raise ValueError("the documented C3D4 comparison is cantilever-only")
    repeats = 1 if args.smoke else args.repeats
    gmsh = executable("gmsh")
    ccx = executable("ccx")
    configure_fem(gmsh, ccx)
    tools = {
        "freecad": FreeCAD.Version(),
        "gmsh": command_version([gmsh, "--version"]),
        "calculix": command_version([ccx, "-v"]),
    }
    rows: list[dict[str, Any]] = []
    convergence_runs: dict[str, list[convergence.ConvergenceRun]] = {
        name: [] for name in selected
    }
    criteria = convergence.StudyCriteria(ranking_tail_fraction=RANKING_TAIL_FRACTION)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "configuration": {
            "fixtures": selected,
            "repeats": repeats,
            "levels": 1 if args.smoke else args.levels,
            "smoke": args.smoke,
            "tail_fractions": TAIL_FRACTIONS,
            "ranking_tail_fraction": RANKING_TAIL_FRACTION,
            "candidate_set": {key: value.build for key, value in CANDIDATES.items()},
            "gmsh_seed_option": "Mesh.RandomSeed",
            "gmsh_reproducible": True,
            "gmsh_threads": 1,
            "stress_source": "nodal_volume_lumped",
            "element_order": args.element_order,
            "convergence_criteria": asdict(criteria),
            "gap_uncertainty_method": (
                "max_finest_signed_gap_spread_or_last_median_gap_step_v1"
            ),
        },
        "tools": tools,
        "runs": rows,
        "convergence": {},
        "seed_reproducibility": {},
    }
    for fixture_name in selected:
        factory = FIXTURES[fixture_name]
        probe = FreeCAD.newDocument(f"phase3_probe_{fixture_name}")
        try:
            sizes: tuple[float, ...] = factory(probe).mesh_sizes
        finally:
            FreeCAD.closeDocument(probe.Name)
        sizes = sizes[:1] if args.smoke else sizes[: args.levels]
        for level, size in enumerate(sizes):
            for repeat in range(repeats):
                seed = 1009 + repeat * 17
                FreeCAD.Console.PrintMessage(
                    f"Phase 3: {fixture_name} level {level} size {size} seed {seed}\n"
                )
                row, measured = run_mesh(
                    factory,
                    fixture_name,
                    level,
                    size,
                    repeat,
                    seed,
                    determinism_check=level == 0 and repeat == 0,
                    element_order=args.element_order,
                )
                rows.append(row)
                convergence_runs[fixture_name].append(measured)
                if level == 0 and repeat == 0:
                    repeated_row, _ = run_mesh(
                        factory,
                        fixture_name,
                        level,
                        size,
                        999,
                        seed,
                        determinism_check=False,
                        element_order=args.element_order,
                    )
                    report["seed_reproducibility"][fixture_name] = {
                        "seed": seed,
                        "same_mesh_signature": (
                            row["mesh_signature"] == repeated_row["mesh_signature"]
                        ),
                        "same_ranking": row["ranking"] == repeated_row["ranking"],
                    }
                    reproducibility = report["seed_reproducibility"][fixture_name]
                    if not (
                        reproducibility["same_mesh_signature"]
                        and reproducibility["same_ranking"]
                    ):
                        raise RuntimeError(
                            "fixed-seed remeshing is not reproducible: "
                            f"{report['seed_reproducibility'][fixture_name]}"
                        )
                atomic_json(args.output, report)
        report["convergence"][fixture_name] = asdict(
            convergence.analyse(convergence_runs[fixture_name], criteria)
        )
        atomic_json(args.output, report)

    csv_path = args.output.with_suffix(".csv")
    write_csv(csv_path, rows)
    for fixture_name in selected:
        write_svg(args.output.with_name(f"{fixture_name}.svg"), fixture_name, rows)
    atomic_json(args.output, report)
    FreeCAD.Console.PrintMessage(
        json.dumps(
            {
                "results": str(args.output),
                "csv": str(csv_path),
                "runs": len(rows),
                "confidence": {
                    key: value["confidence"]
                    for key, value in report["convergence"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


# FreeCAD otherwise converts an uncaught macro exception into exit status zero.
try:
    main()
except Exception:
    traceback.print_exc()
    sys.stderr.flush()
    os._exit(1)

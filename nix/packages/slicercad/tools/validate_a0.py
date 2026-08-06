"""Run slicercad A0 through real gmsh, CalculiX and curved C3D10 meshes.

Run from the repository root inside the development environment:

    freecadcmd --module-path=nix/packages/slicercad/freecad \
        nix/packages/slicercad/tools/validate_a0.py
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import traceback
from typing import TYPE_CHECKING, Any

import FreeCAD
import ObjectsFem
from femmesh.gmshtools import GmshTools
from femtools import ccxtools

if TYPE_CHECKING:
    from freecad.slicercad import fem_result, orient
else:
    from slicercad import fem_result, orient


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"required FEM executable is not on PATH: {name}")
    return path


def version(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
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


def create_second_order_mesh(
    document: Any,
    analysis: Any,
    shape: Any,
    size: float,
    name: str,
) -> Any:
    mesh = ObjectsFem.makeMeshGmsh(document, name)
    mesh.Shape = shape
    mesh.CharacteristicLengthMax = f"{size} mm"
    mesh.ElementOrder = "2nd"
    mesh.SecondOrderLinear = False
    analysis.addObject(mesh)
    document.recompute()
    error = GmshTools(mesh).create_mesh()
    if error:
        raise RuntimeError(f"gmsh failed for {name} at {size} mm: {error}")
    return mesh


def curved_volume_study() -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    previous_error = math.inf
    for size in (4.0, 2.0, 1.0):
        document = FreeCAD.newDocument(f"a0_curved_{str(size).replace('.', '_')}")
        try:
            cylinder = document.addObject("Part::Cylinder", "Cylinder")
            cylinder.Radius = 5.0
            cylinder.Height = 20.0
            document.recompute()
            analysis = ObjectsFem.makeAnalysis(document, "Analysis")
            mesh = create_second_order_mesh(
                document, analysis, cylinder, size, "CurvedMesh"
            )
            lumped = fem_result.lumped_mesh_volumes(mesh.FemMesh)
            cad_volume = float(cylinder.Shape.Volume)
            error = abs(lumped.total_volume - cad_volume) / cad_volume
            midpoint_deviation = max(
                element.max_midpoint_deviation for element in lumped.elements
            )
            if midpoint_deviation <= 0.0:
                raise RuntimeError("curved C3D10 mesh has no curved midside nodes")
            if error >= previous_error:
                raise RuntimeError(
                    "curved C3D10 volume error did not decrease under refinement: "
                    f"{error} >= {previous_error}"
                )
            previous_error = error
            rows.append(
                {
                    "size_mm": size,
                    "elements": len(lumped.elements),
                    "integrated_volume_mm3": lumped.total_volume,
                    "cad_volume_mm3": cad_volume,
                    "relative_error": error,
                    "max_midpoint_deviation_mm": midpoint_deviation,
                }
            )
        finally:
            FreeCAD.closeDocument(document.Name)
    return rows


def cantilever_solve() -> dict[str, Any]:
    document = FreeCAD.newDocument("a0_cantilever")
    try:
        box = document.addObject("Part::Box", "Beam")
        box.Length = 100.0
        box.Width = 10.0
        box.Height = 10.0
        document.recompute()

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
        fixed.References = [(box, "Face1")]
        analysis.addObject(fixed)

        load = ObjectsFem.makeConstraintForce(document, "Force")
        load.References = [(box, "Face6")]
        load.Force = "50 N"
        load.DirectionVector = FreeCAD.Vector(0.0, 0.0, -1.0)
        analysis.addObject(load)

        mesh = create_second_order_mesh(document, analysis, box, 5.0, "BeamMesh")
        fem = ccxtools.FemToolsCcx(analysis, solver)
        fem.update_objects()
        fem.setup_working_dir()
        fem.setup_ccx()
        prerequisites = fem.check_prerequisites()
        if prerequisites:
            raise RuntimeError(prerequisites)
        fem.purge_results()
        fem.write_inp_file()
        fem.ccx_run()
        fem.load_results()

        results = [
            obj for obj in document.Objects if obj.isDerivedFrom("Fem::FemResultObject")
        ]
        if len(results) != 1:
            raise RuntimeError(f"expected one FEM result, found {len(results)}")
        field = fem_result.volume_lumped_stress_field(mesh.FemMesh, results[0])
        expected_volume = float(box.Shape.Volume)
        relative_volume_error = (
            abs(field.mesh_volume - expected_volume) / expected_volume
        )
        if relative_volume_error > 1e-10:
            raise RuntimeError(
                f"straight beam volume mismatch: relative error {relative_volume_error}"
            )
        if not all(
            math.isfinite(value)
            for sample in field.samples
            for value in (*sample.stress, sample.volume)
        ):
            raise RuntimeError("A0 produced a non-finite weighted sample")

        ranking = orient.rank(
            field.samples,
            (
                orient.Candidate((1.0, 0.0, 0.0), source="validation_axis"),
                orient.Candidate((0.0, 1.0, 0.0), source="validation_axis"),
                orient.Candidate((0.0, 0.0, 1.0), source="validation_axis"),
            ),
            ranking_tail_fraction=0.01,
        )
        if not all(
            math.isfinite(score.value(channel, fraction))
            for score in ranking.scores
            for channel in orient.CHANNELS
            for fraction in ranking.tail_fractions
        ):
            raise RuntimeError("A0 ranking produced a non-finite score")
        return {
            "elements": len(field.element_volumes),
            "element_types": sorted(
                {element.element_type for element in field.element_volumes}
            ),
            "samples": len(field.samples),
            "integrated_volume_mm3": field.mesh_volume,
            "cad_volume_mm3": expected_volume,
            "relative_volume_error": relative_volume_error,
            "max_midpoint_deviation_mm": field.max_midpoint_deviation,
            "pareto_front": [score.build for score in ranking.pareto_front],
            "scores_mpa": [
                {
                    "build": score.build,
                    "opening_cvar_1": score.opening_cvar_1,
                    "shear_cvar_1": score.shear_cvar_1,
                }
                for score in ranking.scores
            ],
        }
    finally:
        FreeCAD.closeDocument(document.Name)


def main() -> None:
    gmsh = executable("gmsh")
    ccx = executable("ccx")
    configure_fem(gmsh, ccx)
    report = {
        "gmsh": version([gmsh, "--version"]),
        "calculix": version([ccx, "-v"]),
        "curved_volume_study": curved_volume_study(),
        "cantilever": cantilever_solve(),
    }
    FreeCAD.Console.PrintMessage(json.dumps(report, indent=2, sort_keys=True) + "\n")


# FreeCAD executes macros with its own module name and otherwise converts an
# uncaught exception into a process exit status of zero, which is unsafe for CI.
try:
    main()
except Exception:
    traceback.print_exc()
    sys.stderr.flush()
    os._exit(1)

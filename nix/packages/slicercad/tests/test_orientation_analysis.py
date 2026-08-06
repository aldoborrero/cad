from __future__ import annotations

import json

import pytest

from freecad.slicercad import element_geometry, fem_result, orient
from freecad.slicercad import orientation_analysis as analysis


def field() -> fem_result.A0StressField:
    samples = (
        orient.WeightedStress(
            (10.0, 2.0, 1.0, 0.0, 0.0, 0.0),
            1.0,
            sample_id=1,
            position=(0.0, 0.0, 0.0),
        ),
        orient.WeightedStress(
            (5.0, 3.0, 1.0, 0.0, 0.0, 0.0),
            2.0,
            sample_id=2,
            position=(1.0, 0.0, 0.0),
        ),
    )
    element = element_geometry.ElementVolume(1, "C3D4", 3.0, 0.0)
    return fem_result.A0StressField(
        samples=samples,
        mesh_volume=3.0,
        element_volumes=(element,),
        max_midpoint_deviation=0.0,
        mesh_signature="mesh-sha",
        analysis_signature="result:field-sha",
    )


def test_analysis_record_keeps_scores_placements_and_comparative_scope() -> None:
    candidates = (
        orient.Candidate((1.0, 0.0, 0.0), area=10.0, source="face"),
        orient.Candidate((0.0, 1.0, 0.0), source="user"),
    )

    result = analysis.analyse(
        result_object="Result",
        part_objects=("Body",),
        field=field(),
        candidate_set=candidates,
    )

    assert result.record["confidence"] == "not_checked"
    assert result.record["ranking_tail_fraction"] == 0.05
    assert result.record["stress_source"] == "nodal_volume_lumped"
    assert result.record["element_type_counts"] == {"C3D4": 1}
    assert result.record["convergence"]["reason"] == "single FEM result"
    assert result.record["configured_allowables"] is None
    assert result.record["comparative_warning"] == analysis.COMPARATIVE_WARNING
    assert result.record["candidate_set_provenance"] == ["face", "user"]
    assert len(result.record["candidate_set_signature"]) == 64
    assert result.record["current_orientation"]["build_direction"] == (0.0, 0.0, 1.0)
    assert result.current_score.value("opening", 0.05) == pytest.approx(1.0)
    assert result.record["candidates"][0]["placements"] == [
        {"sign": 1, "build_direction": (1.0, 0.0, 0.0)},
        {"sign": -1, "build_direction": (-1.0, -0.0, -0.0)},
    ]
    assert len(result.record["scores"]) == 2
    assert all(
        value["outcome"] == "not_checked" for value in result.record["tie_diagnostics"]
    )
    assert json.loads(result.json())["mesh_signature"] == "mesh-sha"


def test_analysis_requires_a_result_part_and_candidate() -> None:
    candidate = (orient.Candidate((1.0, 0.0, 0.0)),)
    with pytest.raises(ValueError, match="result object"):
        analysis.analyse(
            result_object="",
            part_objects=("Body",),
            field=field(),
            candidate_set=candidate,
        )
    with pytest.raises(ValueError, match="part object"):
        analysis.analyse(
            result_object="Result",
            part_objects=(),
            field=field(),
            candidate_set=candidate,
        )
    with pytest.raises(ValueError, match="candidate"):
        analysis.analyse(
            result_object="Result",
            part_objects=("Body",),
            field=field(),
            candidate_set=(),
        )

"""Create a compact, reviewable Phase 3 gate report from raw FEM records."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from freecad.slicercad import convergence, orient  # noqa: E402

TAILS = (0.01, 0.05)
DEFAULT_TAIL = 0.05


def candidate_results(
    record: dict[str, Any],
) -> tuple[convergence.CandidateResult, ...]:
    results = []
    for rank, score in enumerate(record["ranking"]["scores"]):
        metrics = tuple(
            convergence.MetricValue(
                channel,
                tail,
                score["metrics"][f"{channel}_cvar_{tail:g}"]["value_mpa"],
            )
            for tail in TAILS
            for channel in orient.CHANNELS
        )
        results.append(
            convergence.CandidateResult(
                score["candidate_id"],
                orient.Candidate(tuple(score["build"]), source=score["source"]),
                metrics,
                rank,
            )
        )
    return tuple(results)


def pareto_front(
    candidates: tuple[convergence.CandidateResult, ...], tail: float
) -> tuple[str, ...]:
    def dominates(
        left: convergence.CandidateResult, right: convergence.CandidateResult
    ) -> bool:
        left_values = tuple(left.value(channel, tail) for channel in orient.CHANNELS)
        right_values = tuple(right.value(channel, tail) for channel in orient.CHANNELS)
        return all(
            left_value <= right_value
            for left_value, right_value in zip(left_values, right_values, strict=True)
        ) and any(
            left_value < right_value
            for left_value, right_value in zip(left_values, right_values, strict=True)
        )

    return tuple(
        candidate.candidate_id
        for candidate in candidates
        if not any(
            dominates(other, candidate) for other in candidates if other != candidate
        )
    )


def convergence_run(record: dict[str, Any], tail: float) -> convergence.ConvergenceRun:
    candidates = candidate_results(record)
    overlaps_list: list[convergence.PairOverlap] = []
    for value in record["ranking"]["pairwise_overlaps"]:
        candidate_a, candidate_b = sorted(
            (str(value["candidate_a"]), str(value["candidate_b"]))
        )
        overlaps_list.append(
            convergence.PairOverlap(
                candidate_a,
                candidate_b,
                value["channel"],
                value["tail_fraction"],
                value["value"],
            )
        )
    overlaps = tuple(overlaps_list)
    return convergence.ConvergenceRun(
        level=record["level"],
        requested_size=record["requested_size_mm"],
        run_id=record["run_id"],
        candidates=candidates,
        pareto_front=pareto_front(candidates, tail),
        overlaps=overlaps,
        sensitivities=tuple(
            convergence.SensitivityValue(value["tail_fraction"], value["value"])
            for value in record["ranking"]["orientation_sensitivity"]
        ),
    )


def relative_spread(values: list[float]) -> float:
    median = statistics.median(values)
    denominator = max(abs(median), sys.float_info.min)
    return (max(values) - min(values)) / denominator


def refinement_and_remesh(
    records: list[dict[str, Any]], tail: float | None
) -> dict[str, float]:
    levels = sorted({record["level"] for record in records})
    candidates = [value["candidate_id"] for value in records[0]["ranking"]["scores"]]
    refinement: list[float] = []
    remesh: list[float] = []
    for candidate_id in candidates:
        for channel in orient.CHANNELS:
            level_values: list[list[float]] = []
            for level in levels:
                values = []
                for record in records:
                    if record["level"] != level:
                        continue
                    score = next(
                        value
                        for value in record["ranking"]["scores"]
                        if value["candidate_id"] == candidate_id
                    )
                    if tail is None:
                        values.append(score["nodal_max_mpa"][channel])
                    else:
                        values.append(
                            score["metrics"][f"{channel}_cvar_{tail:g}"]["value_mpa"]
                        )
                level_values.append(values)
            previous = statistics.median(level_values[-2])
            finest = statistics.median(level_values[-1])
            refinement.append(
                abs(finest - previous) / max(abs(finest), sys.float_info.min)
            )
            remesh.append(relative_spread(level_values[-1]))
    return {
        "median_last_refinement_change": statistics.median(refinement),
        "max_last_refinement_change": max(refinement),
        "median_finest_remesh_spread": statistics.median(remesh),
        "max_finest_remesh_spread": max(remesh),
    }


def critical_location(
    records: list[dict[str, Any]], preferred: tuple[str, ...]
) -> list[dict[str, Any]]:
    finest = max(record["level"] for record in records)
    rows: list[dict[str, Any]] = []
    for candidate_id in preferred:
        for channel in orient.CHANNELS:
            centroids: list[tuple[float, float, float]] = []
            boundary_distances: list[float] = []
            for record in records:
                if record["level"] != finest:
                    continue
                score = next(
                    value
                    for value in record["ranking"]["scores"]
                    if value["candidate_id"] == candidate_id
                )
                contributions = score["metrics"][f"{channel}_cvar_0.01"][
                    "contributions"
                ]
                volume = math.fsum(value["tail_volume_mm3"] for value in contributions)
                centroid = cast(
                    tuple[float, float, float],
                    tuple(
                        math.fsum(
                            value["position_mm"][axis] * value["tail_volume_mm3"]
                            for value in contributions
                        )
                        / volume
                        for axis in range(3)
                    ),
                )
                centroids.append(centroid)
                targets = [
                    value["point"] for value in record["boundary_regions"]["fixed"]
                ] + [
                    value["face"]["point"]
                    for value in record["boundary_regions"]["loads"]
                ]
                boundary_distances.append(
                    min(math.dist(centroid, target) for target in targets)
                )
            rows.append(
                {
                    "candidate": candidate_id,
                    "channel": channel,
                    "median_centroid_mm": tuple(
                        statistics.median(value[axis] for value in centroids)
                        for axis in range(3)
                    ),
                    "median_distance_to_boundary_target_mm": statistics.median(
                        boundary_distances
                    ),
                }
            )
    return rows


def uncertainty_summary(
    report: convergence.ConvergenceReport, tail_fraction: float
) -> dict[str, Any]:
    pairs = [
        value for value in report.pair_results if value.tail_fraction == tail_fraction
    ]
    avoided = [
        value
        for value in pairs
        if abs(value.uncertainty.finest_median_gap) > value.uncertainty.direct_gap
        and abs(value.uncertainty.finest_median_gap)
        <= value.uncertainty.summed_individual
    ]
    ratios = [
        value.uncertainty.summed_individual / value.uncertainty.direct_gap
        for value in pairs
        if value.uncertainty.direct_gap > 0.0
    ]
    return {
        "metric_pairs": len(pairs),
        "false_below_resolution_avoided": len(avoided),
        "median_summed_to_direct_ratio": statistics.median(ratios),
        "max_summed_to_direct_ratio": max(ratios),
    }


def fixture_summary(raw: dict[str, Any]) -> dict[str, Any]:
    records = raw["runs"]
    criteria = {
        tail: convergence.StudyCriteria(ranking_tail_fraction=tail) for tail in TAILS
    }
    reports = {
        tail: convergence.analyse(
            tuple(convergence_run(record, tail) for record in records),
            criteria[tail],
        )
        for tail in TAILS
    }
    levels = sorted({record["level"] for record in records})
    topology_counts = {
        str(level): len(
            {record["mesh_signature"] for record in records if record["level"] == level}
        )
        for level in levels
    }
    finest = max(levels)
    finest_elements = [
        record["element_count"] for record in records if record["level"] == finest
    ]
    return {
        "fixture": records[0]["fixture"],
        "runs": len(records),
        "levels": len(levels),
        "repeats_per_level": {
            str(level): sum(record["level"] == level for record in records)
            for level in levels
        },
        "unique_topologies_per_level": topology_counts,
        "same_seed_sequence_across_levels": len(
            {
                tuple(
                    sorted(
                        record["run_id"]
                        for record in records
                        if record["level"] == level
                    )
                )
                for level in levels
            }
        )
        == 1,
        "gmsh_threads": raw["configuration"]["gmsh_threads"],
        "actual_element_cards": sorted(
            {
                card
                for record in records
                for card in record["actual_calculix_element_cards"]
            }
        ),
        "stress_sources": sorted({record["data_source"] for record in records}),
        "max_relative_volume_error": max(
            record["relative_volume_error"] for record in records
        ),
        "finest_element_count_range": [min(finest_elements), max(finest_elements)],
        "same_mesh_determinism": next(
            record["determinism"]
            for record in records
            if record["determinism"] is not None
        ),
        "fixed_seed_remesh_reproducibility": raw["seed_reproducibility"][
            records[0]["fixture"]
        ],
        "tail_1_percent": {
            "confidence": reports[0.01].confidence,
            "reasons": reports[0.01].reasons,
            "preferred_set": reports[0.01].preferred_set,
            **refinement_and_remesh(records, 0.01),
        },
        "tail_5_percent": {
            "confidence": reports[0.05].confidence,
            "reasons": reports[0.05].reasons,
            "preferred_set": reports[0.05].preferred_set,
            **refinement_and_remesh(records, 0.05),
        },
        "nodal_maximum": refinement_and_remesh(records, None),
        "gap_uncertainty": {
            str(tail): uncertainty_summary(reports[tail], tail) for tail in TAILS
        },
        "critical_location": critical_location(records, reports[0.01].preferred_set),
        "pair_diagnostics": [
            {
                **asdict(value),
                "tie_band": criteria[0.01].tie_band,
                "same_region_overlap": criteria[0.01].same_region_overlap,
                "gap_uncertainty_method": (
                    "max_finest_signed_gap_spread_or_last_median_gap_step_v1"
                ),
                "uncertainty": {
                    **asdict(value.uncertainty),
                    "candidate_a": value.candidate_a,
                    "candidate_b": value.candidate_b,
                },
            }
            for tail in TAILS
            for value in reports[tail].pair_results
            if value.tail_fraction == tail
        ],
    }


def tie_classifier_evidence(
    fixtures: list[dict[str, Any]], tail_fraction: float
) -> dict[str, Any]:
    diagnostics = [
        value
        for fixture in fixtures
        for value in fixture["pair_diagnostics"]
        if value["tail_fraction"] == tail_fraction
    ]
    outcomes = collections.Counter(value["tie_outcome"] for value in diagnostics)
    physical = (
        outcomes["physical_shared_region"] + outcomes["physical_distinct_regions"]
    )
    threshold_crossings = sum(
        min(value["level_median_overlaps"])
        < value["same_region_overlap"]
        <= max(value["level_median_overlaps"])
        for value in diagnostics
    )
    return {
        "tail_fraction": tail_fraction,
        "pair_channel_diagnostics": len(diagnostics),
        "overlap_stable": sum(value["overlap_stable"] for value in diagnostics),
        "overlap_unstable": sum(not value["overlap_stable"] for value in diagnostics),
        "overlap_threshold_crossings": threshold_crossings,
        "physical_tie_labels": physical,
        "outcome_counts": dict(sorted(outcomes.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--c3d4-comparison", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fixtures = [fixture_summary(json.loads(path.read_text())) for path in args.inputs]
    one = [value["tail_1_percent"] for value in fixtures]
    five = [value["tail_5_percent"] for value in fixtures]
    classifier_evidence = {
        str(tail): tie_classifier_evidence(fixtures, tail) for tail in TAILS
    }
    gate: dict[str, Any] = {
        "all_primary_runs_are_c3d10": all(
            value["actual_element_cards"] == ["C3D10"] for value in fixtures
        ),
        "all_runs_use_volume_lumped_nodal_stress": all(
            value["stress_sources"] == ["nodal_volume_lumped"] for value in fixtures
        ),
        "four_levels_three_topologies_each": all(
            value["levels"] == 4
            and set(value["unique_topologies_per_level"].values()) == {3}
            for value in fixtures
        ),
        "same_mesh_scores_are_deterministic": all(
            value["same_mesh_determinism"]["scores_bitwise_equal"] for value in fixtures
        ),
        "fixed_seed_remeshing_is_reproducible": all(
            value["fixed_seed_remesh_reproducibility"]["same_mesh_signature"]
            and value["fixed_seed_remesh_reproducibility"]["same_ranking"]
            for value in fixtures
        ),
        "same_seed_sequence_across_refinements": all(
            value["same_seed_sequence_across_levels"] for value in fixtures
        ),
        "gmsh_runs_are_single_threaded": all(
            value["gmsh_threads"] == 1 for value in fixtures
        ),
        "selected_tail_pair_diagnostics_are_complete": all(
            sum(
                value["tail_fraction"] == DEFAULT_TAIL
                for value in fixture["pair_diagnostics"]
            )
            == 6
            for fixture in fixtures
        ),
        "tail_1_confidence": {
            value["fixture"]: value["tail_1_percent"]["confidence"]
            for value in fixtures
        },
        "tail_5_confidence": {
            value["fixture"]: value["tail_5_percent"]["confidence"]
            for value in fixtures
        },
        "median_last_refinement_change": {
            "cvar_1_percent": statistics.median(
                value["median_last_refinement_change"] for value in one
            ),
            "cvar_5_percent": statistics.median(
                value["median_last_refinement_change"] for value in five
            ),
            "nodal_maximum": statistics.median(
                value["nodal_maximum"]["median_last_refinement_change"]
                for value in fixtures
            ),
        },
        "median_finest_remesh_spread": {
            "cvar_1_percent": statistics.median(
                value["median_finest_remesh_spread"] for value in one
            ),
            "cvar_5_percent": statistics.median(
                value["median_finest_remesh_spread"] for value in five
            ),
            "nodal_maximum": statistics.median(
                value["nodal_maximum"]["median_finest_remesh_spread"]
                for value in fixtures
            ),
        },
        "selected_default_tail_fraction": DEFAULT_TAIL,
        "classifier_tail_fraction": DEFAULT_TAIL,
        "selected_default_reason": (
            "5% has lower aggregate refinement and remesh movement; 1% remains "
            "available as the more failure-local diagnostic"
        ),
    }
    movement = gate["median_last_refinement_change"]
    gate["weighted_cvar_is_less_mesh_sensitive_than_nodal_maximum"] = (
        movement["cvar_1_percent"] < movement["nodal_maximum"]
        and movement["cvar_5_percent"] < movement["nodal_maximum"]
    )
    gate["all_primary_rankings_are_stable"] = all(
        value["confidence"] == "stable_at_tested_meshes" for value in (*one, *five)
    )
    frame = next(value for value in fixtures if value["fixture"] == "three_axis_frame")
    frame_pairs = [
        value
        for value in frame["pair_diagnostics"]
        if value["tail_fraction"] == DEFAULT_TAIL
        and {value["candidate_a"], value["candidate_b"]} == {"x", "y"}
    ]
    gate["competing_paths_distinct_region_pair"] = len(frame_pairs) == len(
        orient.CHANNELS
    ) and all(
        value["tie_outcome"] == "physical_distinct_regions" for value in frame_pairs
    )
    torsion = next(value for value in fixtures if value["fixture"] == "torsion_tab")
    torsion_pairs = torsion["pair_diagnostics"]

    def robust_advantage(preferred: str, other: str, channel: str) -> bool:
        pair = next(
            value
            for value in torsion_pairs
            if value["tail_fraction"] == DEFAULT_TAIL
            and {value["candidate_a"], value["candidate_b"]} == {preferred, other}
            and value["channel"] == channel
        )
        signed = float(pair["uncertainty"]["finest_median_gap"])
        advantage = signed if pair["candidate_a"] == preferred else -signed
        return advantage > float(pair["uncertainty"]["direct_gap"])

    gate["torsion_exercises_shear_ranking"] = all(
        robust_advantage("z", other, channel)
        for other in ("x", "y")
        for channel in orient.CHANNELS
    )
    comparison: dict[str, Any] | None = None
    if args.c3d4_comparison is not None:
        raw_comparison = json.loads(args.c3d4_comparison.read_text())
        records = raw_comparison["runs"]
        comparison = {
            "fixture": records[0]["fixture"],
            "configured_order": sorted(
                {record["configured_order"] for record in records}
            ),
            "actual_element_cards": sorted(
                {
                    card
                    for record in records
                    for card in record["actual_calculix_element_cards"]
                }
            ),
            "runs": len(records),
            "cvar_1_percent": refinement_and_remesh(records, 0.01),
            "cvar_5_percent": refinement_and_remesh(records, 0.05),
            "nodal_maximum": refinement_and_remesh(records, None),
        }
        gate["c3d4_is_labelled_comparison_only"] = (
            comparison["fixture"] == "cantilever"
            and comparison["configured_order"] == ["1st"]
            and comparison["actual_element_cards"] == ["C3D4"]
        )
    report = {
        "schema_version": 2,
        "analysis_contract": {
            "gap_uncertainty_method": (
                "max_finest_signed_gap_spread_or_last_median_gap_step_v1"
            ),
            "criteria_by_tail": {
                str(tail): asdict(convergence.StudyCriteria(ranking_tail_fraction=tail))
                for tail in TAILS
            },
        },
        "source_records": [
            {
                "name": json.loads(path.read_text())["runs"][0]["fixture"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in args.inputs
        ],
        "c3d4_source_sha256": (
            None
            if args.c3d4_comparison is None
            else hashlib.sha256(args.c3d4_comparison.read_bytes()).hexdigest()
        ),
        "fixtures": fixtures,
        "tie_classifier_evidence": classifier_evidence,
        "c3d4_comparison": comparison,
        "gate": gate,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

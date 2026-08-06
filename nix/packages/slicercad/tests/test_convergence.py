from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.slicercad import convergence, orient

CANDIDATES = {
    "x": orient.Candidate((1.0, 0.0, 0.0), source="validation_axis"),
    "y": orient.Candidate((0.0, 1.0, 0.0), source="validation_axis"),
    "z": orient.Candidate((0.0, 0.0, 1.0), source="validation_axis"),
}


def result(
    candidate_id: str, opening: float, shear: float, rank: int
) -> convergence.CandidateResult:
    return convergence.CandidateResult(
        candidate_id,
        CANDIDATES[candidate_id],
        (
            convergence.MetricValue("opening", 0.01, opening),
            convergence.MetricValue("shear", 0.01, shear),
        ),
        rank,
    )


def study_run(
    level: int,
    repeat: int,
    values: dict[str, tuple[float, float]],
    front: tuple[str, ...],
    *,
    overlap: float = 0.2,
    sensitivity: float = 0.3,
) -> convergence.ConvergenceRun:
    ids = tuple(values)
    overlaps = tuple(
        convergence.PairOverlap(left, right, channel, 0.01, overlap)
        for left_index, left in enumerate(ids)
        for right in ids[left_index + 1 :]
        for channel in orient.CHANNELS
    )
    return convergence.ConvergenceRun(
        level=level,
        requested_size=8.0 / (level + 1),
        run_id=f"mesh-{repeat}",
        candidates=tuple(
            result(candidate_id, *values[candidate_id], rank)
            for rank, candidate_id in enumerate(ids)
        ),
        pareto_front=front,
        overlaps=overlaps,
        sensitivities=(convergence.SensitivityValue(0.01, sensitivity),),
    )


def repeated_study(
    levels: tuple[dict[str, tuple[float, float]], ...],
    front: tuple[str, ...],
    *,
    overlap: float = 0.2,
) -> list[convergence.ConvergenceRun]:
    return [
        study_run(
            level,
            repeat,
            {
                candidate_id: (
                    values[0] + (repeat - 1) * 0.002,
                    values[1] - (repeat - 1) * 0.002,
                )
                for candidate_id, values in scores.items()
            },
            front,
            overlap=overlap,
            sensitivity=0.30 + level * 0.005,
        )
        for level, scores in enumerate(levels)
        for repeat in range(3)
    ]


CRITERIA = convergence.StudyCriteria(ranking_tail_fraction=0.01)


def test_one_mesh_level_is_explicitly_not_checked() -> None:
    run = study_run(0, 0, {"x": (1.0, 1.0), "y": (2.0, 2.0)}, ("x",))

    report = convergence.analyse((run,), CRITERIA)

    assert report.confidence == "not_checked"
    assert report.reasons == ("only one refinement level is available",)


def test_a_repeated_stable_front_passes_the_documented_margin_rule() -> None:
    runs = repeated_study(
        (
            {"x": (2.1, 2.1), "y": (4.2, 4.1), "z": (5.1, 3.8)},
            {"x": (2.05, 2.04), "y": (4.1, 4.05), "z": (5.0, 3.7)},
            {"x": (2.02, 2.01), "y": (4.05, 4.02), "z": (4.9, 3.65)},
        ),
        ("x",),
    )

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "stable_at_tested_meshes"
    assert report.preferred_set == ("x",)
    assert report.margin_rule_satisfied
    assert report.sensitivity_stable


def test_a_signed_gap_inversion_makes_a_retained_pareto_pair_indeterminate() -> None:
    runs = repeated_study(
        (
            {"x": (10.0, 10.4), "y": (10.4, 10.0), "z": (20.0, 20.0)},
            {"x": (10.2, 10.1), "y": (10.1, 10.2), "z": (20.0, 20.0)},
            {"x": (10.3, 10.0), "y": (10.0, 10.3), "z": (20.0, 20.0)},
        ),
        ("x", "y"),
    )

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "indeterminate"
    assert any(pair.signed_gap_inversion for pair in report.pair_results)
    assert "a signed top-pair gap inverted under refinement" in report.reasons


def test_pareto_flicker_below_gap_resolution_becomes_a_stable_tied_set() -> None:
    runs = []
    for level in range(3):
        for repeat, offset in enumerate((-0.02, 0.0, 0.02)):
            gap = 0.005 + offset
            front = ("x",) if gap > 0.0 else ("y",)
            runs.append(
                study_run(
                    level,
                    repeat,
                    {
                        "x": (10.0, 10.0),
                        "y": (10.0 + gap, 10.0 + gap),
                        "z": (20.0, 20.0),
                    },
                    front,
                    sensitivity=0.3,
                )
            )

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "stable_at_tested_meshes"
    assert report.preferred_set == ("x", "y")
    assert report.top_set_consistent
    assert {
        pair.tie_outcome
        for pair in report.pair_results
        if {pair.candidate_a, pair.candidate_b} == {"x", "y"}
    } == {"below_resolution"}


def test_coarse_sign_inversion_does_not_block_a_fine_unresolved_tie() -> None:
    runs = []
    level_gaps = (-0.2, 0.02, 0.001)
    for level, level_gap in enumerate(level_gaps):
        for repeat, offset in enumerate((-0.002, 0.0, 0.002)):
            gap = level_gap + offset
            runs.append(
                study_run(
                    level,
                    repeat,
                    {
                        "x": (10.0, 10.0),
                        "y": (10.0 + gap, 10.0 + gap),
                        "z": (20.0, 20.0),
                    },
                    ("x",) if gap > 0.0 else ("y",),
                    sensitivity=0.3,
                )
            )

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "stable_at_tested_meshes"
    assert report.preferred_set == ("x", "y")
    assert {
        pair.tie_outcome
        for pair in report.pair_results
        if {pair.candidate_a, pair.candidate_b} == {"x", "y"}
    } == {"below_resolution"}


def test_a_close_converged_pair_with_separate_tails_is_a_physical_distinct_tie() -> (
    None
):
    runs = repeated_study(
        (
            {"x": (10.02, 10.42), "y": (10.42, 10.02), "z": (20.0, 20.0)},
            {"x": (10.01, 10.41), "y": (10.41, 10.01), "z": (20.0, 20.0)},
            {"x": (10.00, 10.40), "y": (10.40, 10.00), "z": (20.0, 20.0)},
        ),
        ("x", "y"),
        overlap=0.2,
    )

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "stable_at_tested_meshes"
    top = [
        pair
        for pair in report.pair_results
        if {pair.candidate_a, pair.candidate_b} == {"x", "y"}
    ]
    assert {pair.tie_outcome for pair in top} == {"physical_distinct_regions"}


def test_a_close_converged_pair_can_share_the_same_critical_region() -> None:
    runs = repeated_study(
        (
            {"x": (10.02, 10.42), "y": (10.42, 10.02), "z": (20.0, 20.0)},
            {"x": (10.01, 10.41), "y": (10.41, 10.01), "z": (20.0, 20.0)},
            {"x": (10.00, 10.40), "y": (10.40, 10.00), "z": (20.0, 20.0)},
        ),
        ("x", "y"),
        overlap=0.8,
    )

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "stable_at_tested_meshes"
    assert {
        pair.tie_outcome
        for pair in report.pair_results
        if {pair.candidate_a, pair.candidate_b} == {"x", "y"}
    } == {"physical_shared_region"}


def test_unstable_region_overlap_withholds_only_the_physical_tie_label() -> None:
    runs = [
        study_run(
            level,
            repeat,
            {
                "x": (10.0 + level * 0.01, 10.4 + level * 0.01),
                "y": (10.4 + level * 0.01, 10.0 + level * 0.01),
                "z": (20.0, 20.0),
            },
            ("x", "y"),
            overlap=(0.4, 0.65, 0.4)[level],
            sensitivity=0.3,
        )
        for level in range(3)
        for repeat in range(3)
    ]

    report = convergence.analyse(runs, CRITERIA)

    assert report.confidence == "stable_at_tested_meshes"
    assert "region label remains not_checked" in " ".join(report.reasons)
    assert {
        pair.tie_outcome
        for pair in report.pair_results
        if {pair.candidate_a, pair.candidate_b} == {"x", "y"}
    } == {"not_checked"}


def test_direct_gap_uncertainty_preserves_matched_mesh_correlation() -> None:
    runs = repeated_study(
        (
            {"x": (10.0, 8.0), "y": (11.0, 9.0)},
            {"x": (9.0, 7.0), "y": (10.0, 8.0)},
            {"x": (8.0, 6.0), "y": (9.0, 7.0)},
        ),
        ("x",),
    )

    report = convergence.analyse(runs, CRITERIA)
    pair = next(
        value
        for value in report.pair_results
        if value.candidate_a == "x" and value.candidate_b == "y"
    )

    assert pair.uncertainty.direct_gap < pair.uncertainty.summed_individual


def test_comparable_kendall_ignores_incomparable_pairs() -> None:
    left = study_run(
        0,
        0,
        {"x": (1.0, 3.0), "y": (3.0, 1.0), "z": (4.0, 4.0)},
        ("x", "y"),
    )
    right = study_run(
        0,
        1,
        {"x": (1.1, 3.1), "y": (3.1, 1.1), "z": (5.0, 5.0)},
        ("x", "y"),
    )

    tau, count = convergence.comparable_kendall(left, right, 0.01)

    assert tau == 1.0
    assert count == 2


def test_changed_candidate_geometry_marks_the_study_invalid() -> None:
    runs = repeated_study(
        (
            {"x": (1.0, 1.0), "y": (2.0, 2.0)},
            {"x": (1.0, 1.0), "y": (2.0, 2.0)},
            {"x": (1.0, 1.0), "y": (2.0, 2.0)},
        ),
        ("x",),
    )
    changed = replace(
        runs[-1],
        candidates=(
            replace(
                runs[-1].candidates[0], candidate=orient.Candidate((1.0, 1.0, 0.0))
            ),
            *runs[-1].candidates[1:],
        ),
    )

    report = convergence.analyse((*runs[:-1], changed), CRITERIA)

    assert report.confidence == "invalid"
    assert "candidate geometry changed" in report.reasons[0]


def test_run_from_ranking_retains_front_scores_overlaps_and_sensitivity() -> None:
    field = (
        orient.WeightedStress((10.0, 0.0, 0.0, 0.0, 0.0, 0.0), 1.0, "hot"),
        orient.WeightedStress((2.0, 0.0, 0.0, 0.0, 0.0, 0.0), 9.0, "bulk"),
    )
    ranking = orient.rank(
        field,
        (CANDIDATES["x"], CANDIDATES["y"]),
        ranking_tail_fraction=0.01,
        tail_fractions=(0.01,),
    )

    run = convergence.run_from_ranking(
        level=0,
        requested_size=5.0,
        run_id="seed-1",
        ranking=ranking,
        candidate_id=lambda candidate: "x" if candidate == CANDIDATES["x"] else "y",
    )

    assert len(run.candidates) == 2
    assert len(run.overlaps) == 2
    assert run.sensitivities[0].tail_fraction == pytest.approx(0.01)

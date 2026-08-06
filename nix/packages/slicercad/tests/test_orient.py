from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.slicercad import orient

PULL_ALONG_X: orient.StressTuple = (10.0, 0.0, 0.0, 0.0, 0.0, 0.0)
CANDIDATE_X = orient.Candidate((1.0, 0.0, 0.0), source="user")
CANDIDATE_Y = orient.Candidate((0.0, 1.0, 0.0), source="user")


def weighted_stress(
    sample_id: orient.SampleId,
    stress: orient.StressTuple,
    volume: float = 1.0,
) -> orient.WeightedStress:
    return orient.WeightedStress(stress=stress, volume=volume, sample_id=sample_id)


def weighted_value(
    sample_id: orient.SampleId, value: float, weight: float
) -> orient.WeightedValue:
    return orient.WeightedValue(sample_id=sample_id, value=value, weight=weight)


def tail_contribution(
    sample_id: orient.SampleId, tail_volume: float
) -> orient.TailContribution:
    return orient.TailContribution(
        sample_id=sample_id,
        value=1.0,
        sample_volume=tail_volume,
        tail_volume=tail_volume,
        position=None,
        source_node_ids=(),
        source_element_ids=(),
    )


def pair_uncertainty(
    score_a: orient.OrientationScore,
    score_b: orient.OrientationScore,
    channel: orient.Channel,
    tail_fraction: float,
    direct: float,
    *,
    summed: float = 0.0,
    stable: bool = True,
) -> orient.PairUncertainty:
    value_a = score_a.value(channel, tail_fraction)
    value_b = score_b.value(channel, tail_fraction)
    return orient.PairUncertainty(
        candidate_a=score_a.candidate,
        candidate_b=score_b.candidate,
        channel=channel,
        tail_fraction=tail_fraction,
        direct_gap=direct,
        summed_individual=summed,
        finest_median_a=value_a,
        finest_median_b=value_b,
        previous_median_a=value_a,
        previous_median_b=value_b,
        finest_median_gap=value_b - value_a,
        previous_median_gap=value_b - value_a,
        finest_gap_spread=0.0,
        stable=stable,
    )


def test_pure_tension_normal_to_layers_is_opening_only() -> None:
    result = orient.layer_traction(PULL_ALONG_X, build=(1.0, 0.0, 0.0))

    assert result.vector == (10.0, 0.0, 0.0)
    assert result.normal == 10.0
    assert result.opening == 10.0
    assert result.shear == 0.0


def test_tension_within_layers_does_not_load_the_interface() -> None:
    result = orient.layer_traction(PULL_ALONG_X, build=(0.0, 0.0, 1.0))

    assert result.opening == 0.0
    assert result.shear == 0.0


def test_compression_is_excluded_from_opening_but_preserved_as_normal_stress() -> None:
    compression = (-30.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    result = orient.layer_traction(compression, build=(1.0, 0.0, 0.0))

    assert result.normal == -30.0
    assert result.opening == 0.0
    assert result.shear == 0.0


def test_pure_interface_shear_is_not_lost() -> None:
    shear = (0.0, 0.0, 0.0, 4.0, 0.0, 0.0)

    result = orient.layer_traction(shear, build=(1.0, 0.0, 0.0))

    assert result.vector == (0.0, 4.0, 0.0)
    assert result.opening == 0.0
    assert result.shear == 4.0


def test_combined_opening_and_shear_have_a_hand_calculated_result() -> None:
    stress = (3.0, 0.0, 0.0, 4.0, 0.0, 0.0)

    result = orient.layer_traction(stress, build=(1.0, 0.0, 0.0))

    assert result.opening == 3.0
    assert result.shear == 4.0


def test_a_forty_five_degree_build_takes_half_the_normal_tension() -> None:
    root = math.sqrt(0.5)

    assert orient.normal_stress(PULL_ALONG_X, build=(root, 0.0, root)) == pytest.approx(
        5.0
    )


def test_the_build_vector_need_not_be_a_unit_vector() -> None:
    assert orient.normal_stress(PULL_ALONG_X, build=(7.0, 0.0, 0.0)) == 10.0


def test_layer_traction_is_invariant_under_a_simultaneous_rotation() -> None:
    stress = (7.0, 2.0, -1.0, 3.0, 4.0, 5.0)
    build = (2.0, 1.0, 3.0)
    # R is a +90 degree rotation around Z: sigma' = R sigma R^T, n' = R n.
    rotated_stress = (2.0, 7.0, -1.0, -3.0, -5.0, 4.0)
    rotated_build = (-1.0, 2.0, 3.0)

    original = orient.layer_traction(stress, build)
    rotated = orient.layer_traction(rotated_stress, rotated_build)

    assert rotated.normal == pytest.approx(original.normal)
    assert rotated.opening == pytest.approx(original.opening)
    assert rotated.shear == pytest.approx(original.shear)


@pytest.mark.parametrize(
    "build",
    [(0.0, 0.0, 0.0), (float("inf"), 0.0, 0.0), (1.0, 2.0)],
)
def test_an_invalid_build_direction_is_refused(build: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="direction"):
        orient.normal_stress(PULL_ALONG_X, build=build)


def test_principal_stress_recovers_diagonal_eigenvalues() -> None:
    assert orient.largest_principal_stress((2.0, 11.0, -3.0, 0.0, 0.0, 0.0)) == 11.0


def test_principal_stress_recovers_a_pure_shear_eigenvalue() -> None:
    assert orient.largest_principal_stress(
        (0.0, 0.0, 0.0, 4.0, 0.0, 0.0)
    ) == pytest.approx(4.0)


def test_weighted_quantile_counts_physical_weight() -> None:
    samples = [weighted_value("small", 100.0, 1.0), weighted_value("bulk", 2.0, 9.0)]

    assert orient.weighted_quantile(samples, 0.9) == 2.0
    assert orient.weighted_quantile(samples, 0.91) == 100.0


def test_weighted_cvar_is_invariant_when_a_sample_is_subdivided() -> None:
    original = [weighted_value("hot", 10.0, 2.0), weighted_value("bulk", 2.0, 8.0)]
    subdivided = [
        weighted_value("hot-a", 10.0, 0.5),
        weighted_value("hot-b", 10.0, 1.5),
        weighted_value("bulk", 2.0, 8.0),
    ]

    assert orient.weighted_upper_tail_cvar(original, 0.5).value == pytest.approx(
        orient.weighted_upper_tail_cvar(subdivided, 0.5).value
    )


def test_weighted_cvar_splits_the_boundary_sample_exactly() -> None:
    samples = [weighted_value("hot", 10.0, 2.0), weighted_value("bulk", 5.0, 8.0)]

    result = orient.weighted_upper_tail_cvar(samples, 0.5)

    assert result.value == 7.0
    assert result.tail_volume == 5.0
    assert {item.sample_id: item.tail_volume for item in result.contributions} == {
        "hot": 2.0,
        "bulk": 3.0,
    }


def test_equal_values_at_the_tail_boundary_share_the_cut_proportionally() -> None:
    samples = [
        weighted_value("hot", 10.0, 1.0),
        weighted_value("left", 5.0, 1.0),
        weighted_value("right", 5.0, 1.0),
    ]

    result = orient.weighted_upper_tail_cvar(samples, 2.0 / 3.0)

    assert {item.sample_id: item.tail_volume for item in result.contributions} == {
        "hot": 1.0,
        "left": 0.5,
        "right": 0.5,
    }


def test_roundoff_at_an_exact_tail_boundary_adds_no_ghost_region() -> None:
    samples = [
        weighted_value("hot", 10.0, 0.6),
        weighted_value("outside", 1.0, 0.9),
    ]

    result = orient.weighted_upper_tail_cvar(samples, 0.4)

    assert result.value == pytest.approx(10.0)
    assert [item.sample_id for item in result.contributions] == ["hot"]


@pytest.mark.parametrize("tail_fraction", [0.0, -0.1, 1.1, float("nan")])
def test_invalid_tail_fractions_are_refused(tail_fraction: float) -> None:
    with pytest.raises(ValueError, match="tail fraction"):
        orient.weighted_upper_tail_cvar([weighted_value(1, 3.0, 1.0)], tail_fraction)


def test_empty_weighted_statistics_are_refused() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        orient.weighted_upper_tail_cvar([], 0.05)


@pytest.mark.parametrize("volume", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_physical_volumes_are_refused(volume: float) -> None:
    with pytest.raises(ValueError, match="volume"):
        orient.WeightedStress(stress=PULL_ALONG_X, volume=volume)


def test_scoring_retains_tail_provenance_and_total_volume() -> None:
    field = [
        orient.WeightedStress(
            stress=PULL_ALONG_X,
            volume=1.0,
            sample_id="root",
            position=(1.0, 2.0, 3.0),
            source_node_ids=(7,),
            source_element_ids=(11, 12),
        ),
        weighted_stress("bulk", (2.0, 0.0, 0.0, 0.0, 0.0, 0.0), 9.0),
    ]

    score = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(0.1,)
    )
    (critical,) = score.critical_samples("opening", 0.1)

    assert score.total_volume == 10.0
    assert score.value("opening", 0.1) == 10.0
    assert critical.sample_id == "root"
    assert critical.position == (1.0, 2.0, 3.0)
    assert critical.source_node_ids == (7,)
    assert critical.source_element_ids == (11, 12)


def test_duplicate_explicit_sample_ids_are_refused() -> None:
    field = [
        weighted_stress("same", PULL_ALONG_X),
        weighted_stress("same", PULL_ALONG_X),
    ]

    with pytest.raises(ValueError, match="duplicate"):
        orient.score_orientation(field, orient.Candidate((1.0, 0.0, 0.0)))


def test_empty_weighted_fields_are_refused() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        orient.rank([], [], ranking_tail_fraction=0.01)


def test_opening_shear_tradeoff_is_pareto_incomparable() -> None:
    field = [weighted_stress("only", PULL_ALONG_X)]
    along_x = orient.Candidate((1.0, 0.0, 0.0), source="user")
    diagonal = orient.Candidate((1.0, 1.0, 0.0), source="user")

    result = orient.rank(
        field,
        [along_x, diagonal],
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )

    assert set(result.pareto_front) == set(result.scores)
    assert not orient.dominates(result.scores[0], result.scores[1], tail_fraction=1.0)
    assert not orient.dominates(result.scores[1], result.scores[0], tail_fraction=1.0)


def test_pareto_dominance_puts_a_no_worse_candidate_in_the_first_layer() -> None:
    field = [weighted_stress("only", (10.0, 5.0, 0.0, 0.0, 0.0, 0.0))]
    along_x = orient.Candidate((1.0, 0.0, 0.0))
    along_y = orient.Candidate((0.0, 1.0, 0.0))

    result = orient.rank(
        field,
        [along_x, along_y],
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )

    assert [score.candidate for score in result.pareto_front] == [along_y]
    assert [score.candidate for score in result.scores] == [along_y, along_x]


def test_candidate_area_does_not_change_the_mechanical_score() -> None:
    field = [weighted_stress("only", PULL_ALONG_X)]

    small = orient.score_orientation(field, orient.Candidate((1.0, 0.0, 0.0), area=1.0))
    large = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0), area=1000.0)
    )

    assert small.channel_scores == large.channel_scores


def test_margins_keep_each_channel_and_sign_separate() -> None:
    field = [weighted_stress("only", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    along_x = orient.Candidate((1.0, 0.0, 0.0))
    along_y = orient.Candidate((0.0, 1.0, 0.0))

    result = orient.rank(
        field,
        [along_x, along_y],
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )
    opening = next(
        margin
        for margin in result.margins
        if margin.scope == "adjacent" and margin.channel == "opening"
    )
    shear = next(
        margin
        for margin in result.margins
        if margin.scope == "adjacent" and margin.channel == "shear"
    )

    assert opening.signed_gap == pytest.approx(0.2)
    assert opening.absolute_gap == pytest.approx(0.2)
    assert opening.relative_gap == pytest.approx(0.02)
    assert shear.signed_gap == 0.0


def test_only_the_configured_tail_fraction_controls_pareto_dominance() -> None:
    field = [
        weighted_stress(
            index,
            (
                10.0 if index == 0 else 1.0,
                3.0 if index < 5 else 0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ),
        )
        for index in range(100)
    ]
    along_x = orient.Candidate((1.0, 0.0, 0.0))
    along_y = orient.Candidate((0.0, 1.0, 0.0))

    local_tail = orient.rank(
        field,
        [along_x, along_y],
        tail_fractions=(0.01, 0.05),
        ranking_tail_fraction=0.01,
    )
    broad_tail = orient.rank(
        field,
        [along_x, along_y],
        tail_fractions=(0.01, 0.05),
        ranking_tail_fraction=0.05,
    )

    assert [score.candidate for score in local_tail.pareto_front] == [along_y]
    assert [score.candidate for score in broad_tail.pareto_front] == [along_x]
    assert local_tail.ranking_tail_fraction == 0.01
    assert local_tail.scores[0].value("opening", 0.05) == 3.0


def test_ranking_tail_must_be_one_of_the_calculated_diagnostics() -> None:
    with pytest.raises(ValueError, match="among the calculated tails"):
        orient.rank(
            [weighted_stress("only", PULL_ALONG_X)],
            [CANDIDATE_X],
            tail_fractions=(0.05,),
            ranking_tail_fraction=0.01,
        )


def test_rank_with_no_candidates_returns_diagnostics_without_scores() -> None:
    result = orient.rank(
        [weighted_stress("only", PULL_ALONG_X)], [], ranking_tail_fraction=0.01
    )

    assert result.scores == ()
    assert result.pareto_front == ()
    assert result.orientation_sensitivity == ()
    assert len(result.principal_tension_cvar) == 2


def test_weighted_jaccard_covers_identical_threshold_and_disjoint_regions() -> None:
    left = [tail_contribution(1, 1.0), tail_contribution(2, 1.0)]
    same = [tail_contribution(1, 1.0), tail_contribution(2, 1.0)]
    threshold_left = [
        tail_contribution(1, 1.0),
        tail_contribution(2, 1.0),
        tail_contribution(3, 1.0),
    ]
    threshold_right = [
        tail_contribution(1, 1.0),
        tail_contribution(2, 1.0),
        tail_contribution(4, 1.0),
    ]
    disjoint = [tail_contribution(3, 1.0), tail_contribution(4, 1.0)]

    assert orient.critical_region_overlap(left, same) == 1.0
    assert orient.critical_region_overlap(threshold_left, threshold_right) == 0.5
    assert orient.critical_region_overlap(left, disjoint) == 0.0


def test_correlated_score_drift_cancels_in_direct_gap_uncertainty() -> None:
    previous = [orient.MatchedPairScore("coarse", 10.0, 12.0)]
    finest = [orient.MatchedPairScore("fine", 8.0, 10.0)]

    result = orient.paired_gap_uncertainty(
        finest,
        previous,
        candidate_a=CANDIDATE_X,
        candidate_b=CANDIDATE_Y,
        channel="opening",
        tail_fraction=0.01,
        stable=True,
    )

    assert result.direct_gap == 0.0
    assert result.summed_individual == 4.0


def test_pair_gap_is_the_median_of_matched_differences() -> None:
    finest = [
        orient.MatchedPairScore("fine-a", 0.0, 1.0),
        orient.MatchedPairScore("fine-b", 100.0, 101.0),
        orient.MatchedPairScore("fine-c", 101.0, 1.0),
    ]
    previous = [
        orient.MatchedPairScore("coarse-a", 0.0, 1.0),
        orient.MatchedPairScore("coarse-b", 100.0, 101.0),
        orient.MatchedPairScore("coarse-c", 101.0, 1.0),
    ]

    result = orient.paired_gap_uncertainty(
        finest,
        previous,
        candidate_a=CANDIDATE_X,
        candidate_b=CANDIDATE_Y,
        channel="opening",
        tail_fraction=0.01,
        stable=True,
    )

    assert result.finest_median_gap == 1.0
    assert result.finest_median_b - result.finest_median_a == -99.0


def test_opposite_score_drift_remains_in_direct_gap_uncertainty() -> None:
    previous = [orient.MatchedPairScore("coarse", 10.0, 12.0)]
    finest = [orient.MatchedPairScore("fine", 11.0, 11.0)]

    result = orient.paired_gap_uncertainty(
        finest,
        previous,
        candidate_a=CANDIDATE_X,
        candidate_b=CANDIDATE_Y,
        channel="opening",
        tail_fraction=0.01,
        stable=True,
    )

    assert result.direct_gap == 2.0
    assert result.summed_individual == 2.0


def test_signed_gap_detects_a_ranking_reversal() -> None:
    previous = [orient.MatchedPairScore("coarse", 10.0, 12.0)]
    finest = [orient.MatchedPairScore("fine", 12.0, 10.0)]

    result = orient.paired_gap_uncertainty(
        finest,
        previous,
        candidate_a=CANDIDATE_X,
        candidate_b=CANDIDATE_Y,
        channel="opening",
        tail_fraction=0.01,
        stable=False,
    )

    assert result.previous_median_gap == 2.0
    assert result.finest_median_gap == -2.0
    assert result.direct_gap == 4.0


def test_signed_gap_spread_measures_fixed_size_remeshing_noise() -> None:
    previous = [orient.MatchedPairScore("coarse", 10.0, 12.0)]
    finest = [
        orient.MatchedPairScore("fine-a", 10.0, 11.5),
        orient.MatchedPairScore("fine-b", 10.0, 12.5),
    ]

    result = orient.paired_gap_uncertainty(
        finest,
        previous,
        candidate_a=CANDIDATE_X,
        candidate_b=CANDIDATE_Y,
        channel="opening",
        tail_fraction=0.01,
        stable=True,
    )

    assert result.finest_gap_spread == 1.0
    assert result.direct_gap == 1.0


def test_tie_without_repeated_mesh_data_is_not_checked() -> None:
    field = [weighted_stress("same", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )

    diagnostic = orient.classify_tie(score_a, score_b, "opening", 1.0, uncertainty=None)

    assert diagnostic.outcome == "not_checked"


def test_a_gap_inside_direct_uncertainty_is_below_resolution() -> None:
    field = [weighted_stress("same", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )

    diagnostic = orient.classify_tie(
        score_a,
        score_b,
        "opening",
        1.0,
        uncertainty=pair_uncertainty(score_a, score_b, "opening", 1.0, 0.3, summed=2.0),
    )

    assert diagnostic.outcome == "below_resolution"


def test_a_resolved_close_pair_with_one_critical_region_is_a_physical_tie() -> None:
    field = [weighted_stress("same", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )

    diagnostic = orient.classify_tie(
        score_a,
        score_b,
        "opening",
        1.0,
        uncertainty=pair_uncertainty(score_a, score_b, "opening", 1.0, 0.0, summed=4.0),
    )

    assert diagnostic.outcome == "physical_shared_region"
    assert diagnostic.summed_individual_uncertainty == 4.0


def test_tie_uses_finest_medians_rather_than_one_representative_mesh() -> None:
    field = [weighted_stress("same", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )
    evidence = replace(
        pair_uncertainty(score_a, score_b, "opening", 1.0, 0.0),
        finest_median_b=9.0,
        finest_median_gap=-1.0,
    )

    diagnostic = orient.classify_tie(
        score_a, score_b, "opening", 1.0, uncertainty=evidence
    )

    assert diagnostic.signed_gap == -1.0
    assert diagnostic.relative_gap == 0.1
    assert diagnostic.outcome == "resolved"


def test_tie_rejects_uncertainty_for_a_different_ordered_pair() -> None:
    field = [weighted_stress("same", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )
    wrong_order = pair_uncertainty(score_b, score_a, "opening", 1.0, 0.0)

    with pytest.raises(ValueError, match="ordered candidates and metric"):
        orient.classify_tie(score_a, score_b, "opening", 1.0, uncertainty=wrong_order)


def test_tie_rejects_critical_regions_from_different_meshes() -> None:
    score_a = orient.score_orientation(
        [
            orient.WeightedStress(
                stress=PULL_ALONG_X,
                volume=1.0,
                sample_id="same",
                position=(0.0, 0.0, 0.0),
            )
        ],
        orient.Candidate((1.0, 0.0, 0.0)),
        tail_fractions=(1.0,),
    )
    score_b = orient.score_orientation(
        [
            orient.WeightedStress(
                stress=PULL_ALONG_X,
                volume=1.0,
                sample_id="same",
                position=(1.0, 0.0, 0.0),
            )
        ],
        orient.Candidate((0.0, 1.0, 0.0)),
        tail_fractions=(1.0,),
    )

    with pytest.raises(ValueError, match="same mesh samples and weights"):
        orient.classify_tie(score_a, score_b, "opening", 1.0, uncertainty=None)


def test_a_resolved_close_pair_with_distinct_regions_reports_competing_paths() -> None:
    field = [
        weighted_stress("x-root", PULL_ALONG_X),
        weighted_stress("y-root", (0.0, 9.8, 0.0, 0.0, 0.0, 0.0)),
    ]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(0.5,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(0.5,)
    )

    diagnostic = orient.classify_tie(
        score_a,
        score_b,
        "opening",
        0.5,
        uncertainty=pair_uncertainty(score_a, score_b, "opening", 0.5, 0.0),
    )

    assert diagnostic.outcome == "physical_distinct_regions"
    assert diagnostic.critical_region_overlap == 0.0


def test_the_relative_tie_band_is_applied_only_after_resolution() -> None:
    field = [weighted_stress("same", (10.0, 8.0, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )

    diagnostic = orient.classify_tie(
        score_a,
        score_b,
        "opening",
        1.0,
        uncertainty=pair_uncertainty(score_a, score_b, "opening", 1.0, 0.0),
    )

    assert diagnostic.outcome == "resolved"


def test_an_unstable_resolved_gap_gets_no_physical_label() -> None:
    field = [weighted_stress("same", (10.0, 9.8, 0.0, 0.0, 0.0, 0.0))]
    score_a = orient.score_orientation(
        field, orient.Candidate((1.0, 0.0, 0.0)), tail_fractions=(1.0,)
    )
    score_b = orient.score_orientation(
        field, orient.Candidate((0.0, 1.0, 0.0)), tail_fractions=(1.0,)
    )

    diagnostic = orient.classify_tie(
        score_a,
        score_b,
        "opening",
        1.0,
        uncertainty=pair_uncertainty(
            score_a, score_b, "opening", 1.0, 0.0, stable=False
        ),
    )

    assert diagnostic.outcome == "not_checked"


def test_uniaxial_sensitivity_is_zero_with_a_perpendicular_candidate() -> None:
    field = [weighted_stress("only", PULL_ALONG_X)]

    result = orient.rank(
        field,
        [orient.Candidate((1.0, 0.0, 0.0)), orient.Candidate((0.0, 0.0, 1.0))],
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )

    (sensitivity,) = result.orientation_sensitivity
    assert sensitivity.value == 0.0
    assert sensitivity.denominator == 10.0


def test_uniaxial_sensitivity_is_one_with_only_the_parallel_candidate() -> None:
    result = orient.rank(
        [weighted_stress("only", PULL_ALONG_X)],
        [orient.Candidate((1.0, 0.0, 0.0), source="user")],
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )

    (sensitivity,) = result.orientation_sensitivity
    assert sensitivity.value == 1.0
    assert sensitivity.candidate_sources == ("user",)


def test_sensitivity_is_invariant_under_positive_load_scaling() -> None:
    candidates = [orient.Candidate((1.0, 1.0, 0.0))]
    original = orient.rank(
        [weighted_stress("only", PULL_ALONG_X)],
        candidates,
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )
    scaled = orient.rank(
        [weighted_stress("only", (70.0, 0.0, 0.0, 0.0, 0.0, 0.0))],
        candidates,
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )

    assert scaled.orientation_sensitivity[0].value == pytest.approx(
        original.orientation_sensitivity[0].value
    )


def test_zero_principal_tension_makes_sensitivity_not_applicable() -> None:
    result = orient.rank(
        [weighted_stress("only", (-10.0, -5.0, -1.0, 0.0, 0.0, 0.0))],
        [orient.Candidate((1.0, 0.0, 0.0))],
        tail_fractions=(1.0,),
        ranking_tail_fraction=1.0,
    )

    assert result.orientation_sensitivity[0].value is None


def test_sensitivity_rejects_mixed_aggregation_tail_or_weights() -> None:
    base = orient.weighted_upper_tail_cvar([weighted_value("same", 5.0, 1.0)], 0.5)

    with pytest.raises(ValueError, match="same aggregation"):
        orient.sensitivity_ratio(base, replace(base, aggregation="peak"))
    with pytest.raises(ValueError, match="same tail fraction"):
        orient.sensitivity_ratio(base, replace(base, tail_fraction=0.25))
    with pytest.raises(ValueError, match="same samples and weights"):
        orient.sensitivity_ratio(base, replace(base, weight_signature="different"))


def test_peak_remains_available_but_is_not_used_by_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert orient.peak_normal_stress([PULL_ALONG_X], (1.0, 0.0, 0.0)) == 10.0

    def forbidden_peak(field: object, build: object) -> float:
        raise AssertionError("rank called the mesh-dependent peak")

    monkeypatch.setattr(orient, "peak_normal_stress", forbidden_peak)
    orient.rank(
        [weighted_stress("only", PULL_ALONG_X)],
        [orient.Candidate((1.0, 0.0, 0.0))],
        ranking_tail_fraction=0.01,
    )


def test_a_field_with_a_broken_node_is_refused_not_quietly_skipped() -> None:
    nan = float("nan")
    field = [PULL_ALONG_X, (nan, 0.0, 0.0, 0.0, 0.0, 0.0)]

    with pytest.raises(ValueError, match="1 of 2"):
        orient.peak_normal_stress(field, build=(1.0, 0.0, 0.0))


def test_the_six_lists_zip_into_nodes_in_the_declared_order() -> None:
    field = orient.field_from_lists(
        xx=[1.0, 10.0],
        yy=[2.0, 20.0],
        zz=[3.0, 30.0],
        xy=[4.0, 40.0],
        xz=[5.0, 50.0],
        yz=[6.0, 60.0],
    )

    assert field == [
        (1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        (10.0, 20.0, 30.0, 40.0, 50.0, 60.0),
    ]


def test_lists_of_different_lengths_are_refused() -> None:
    with pytest.raises(ValueError, match="same length"):
        orient.field_from_lists(
            xx=[1.0, 2.0],
            yy=[1.0],
            zz=[1.0, 2.0],
            xy=[1.0, 2.0],
            xz=[1.0, 2.0],
            yz=[1.0, 2.0],
        )


def test_an_empty_result_gives_an_empty_compatibility_field() -> None:
    assert orient.field_from_lists(xx=[], yy=[], zz=[], xy=[], xz=[], yz=[]) == []


BOX_FACES: list[tuple[tuple[float, float, float], float]] = [
    ((1.0, 0.0, 0.0), 100.0),
    ((-1.0, 0.0, 0.0), 100.0),
    ((0.0, 1.0, 0.0), 1000.0),
    ((0.0, -1.0, 0.0), 1000.0),
    ((0.0, 0.0, 1.0), 1000.0),
    ((0.0, 0.0, -1.0), 1000.0),
]


def test_a_box_offers_three_unoriented_candidates_not_six() -> None:
    assert len(orient.candidates(BOX_FACES)) == 3


def test_candidate_constructor_collapses_opposite_layer_normals() -> None:
    assert orient.Candidate((-1.0, 0.0, 0.0)) == orient.Candidate((1.0, 0.0, 0.0))


def test_the_same_faces_in_a_different_order_give_the_same_candidates() -> None:
    chain = [
        ((math.sin(math.radians(a)), 0.0, math.cos(math.radians(a))), 10.0)
        for a in (0.0, 4.0, 8.0)
    ]

    assert orient.candidates(chain, tolerance_degrees=5.0) == orient.candidates(
        list(reversed(chain)), tolerance_degrees=5.0
    )


def test_the_biggest_face_in_a_group_speaks_for_it() -> None:
    tilted = (math.sin(math.radians(3.0)), 0.0, math.cos(math.radians(3.0)))

    (only,) = orient.candidates(
        [(tilted, 2.0), ((0.0, 0.0, 1.0), 900.0)], tolerance_degrees=5.0
    )

    assert only.build == (0.0, 0.0, 1.0)


def test_candidate_group_areas_add_without_becoming_mechanical_evidence() -> None:
    tilted = (math.sin(math.radians(3.0)), 0.0, math.cos(math.radians(3.0)))

    (only,) = orient.candidates(
        [((0.0, 0.0, 1.0), 900.0), (tilted, 100.0)], tolerance_degrees=5.0
    )

    assert only.area == 1000.0


def test_candidates_come_back_as_unit_vectors() -> None:
    (candidate,) = orient.candidates([((0.0, 0.0, 7.0), 5.0)])

    assert math.sqrt(math.fsum(value * value for value in candidate.build)) == 1.0


def test_a_genuinely_different_face_survives_the_collapse() -> None:
    apart = [((0.0, 0.0, 1.0), 10.0), ((0.0, 1.0, 1.0), 10.0)]

    assert len(orient.candidates(apart, tolerance_degrees=5.0)) == 2


def test_invalid_candidate_geometry_is_refused() -> None:
    with pytest.raises(ValueError, match="no length"):
        orient.candidates([((0.0, 0.0, 0.0), 5.0)])
    with pytest.raises(ValueError, match="area"):
        orient.candidates([((0.0, 0.0, 1.0), -1.0)])
    with pytest.raises(ValueError, match="tolerance"):
        orient.candidates([], tolerance_degrees=90.0)


def test_no_faces_give_no_candidates() -> None:
    assert orient.candidates([]) == []

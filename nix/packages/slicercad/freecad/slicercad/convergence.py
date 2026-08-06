"""Mesh-refinement diagnostics for load-aware orientation rankings.

The FEM runner records one :class:`ConvergenceRun` per generated mesh.  This
module is deliberately independent of FreeCAD so the confidence contract can
be tested and reviewed separately from meshing and solver integration.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from itertools import combinations, pairwise
from typing import Literal

from . import orient

type Confidence = Literal[
    "not_checked", "stable_at_tested_meshes", "indeterminate", "invalid"
]


@dataclass(frozen=True)
class MetricValue:
    channel: orient.Channel
    tail_fraction: float
    value: float

    def __post_init__(self) -> None:
        if self.channel not in orient.CHANNELS:
            raise ValueError(f"unsupported channel: {self.channel}")
        if not math.isfinite(self.tail_fraction) or not 0.0 < self.tail_fraction <= 1.0:
            raise ValueError("tail fraction must be finite and in (0, 1]")
        if not math.isfinite(self.value) or self.value < 0.0:
            raise ValueError("mechanical metric must be finite and non-negative")


@dataclass(frozen=True)
class CandidateResult:
    candidate_id: str
    candidate: orient.Candidate
    metrics: tuple[MetricValue, ...]
    display_rank: int

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate id must not be empty")
        if self.display_rank < 0:
            raise ValueError("display rank must be non-negative")
        keys = [(metric.channel, metric.tail_fraction) for metric in self.metrics]
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("candidate metrics must be non-empty and unique")

    def value(self, channel: orient.Channel, tail_fraction: float) -> float:
        for metric in self.metrics:
            if metric.channel == channel and metric.tail_fraction == tail_fraction:
                return metric.value
        raise KeyError(f"no {channel} metric at tail {tail_fraction}")


@dataclass(frozen=True)
class PairOverlap:
    candidate_a: str
    candidate_b: str
    channel: orient.Channel
    tail_fraction: float
    value: float

    def __post_init__(self) -> None:
        if self.candidate_a >= self.candidate_b:
            raise ValueError("overlap candidate ids must be ordered and distinct")
        if not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
            raise ValueError("critical-region overlap must be finite and in [0, 1]")


@dataclass(frozen=True)
class SensitivityValue:
    tail_fraction: float
    value: float | None

    def __post_init__(self) -> None:
        if not math.isfinite(self.tail_fraction) or not 0.0 < self.tail_fraction <= 1.0:
            raise ValueError("tail fraction must be finite and in (0, 1]")
        if self.value is not None and (
            not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0
        ):
            raise ValueError("sensitivity must be None or finite and in [0, 1]")


@dataclass(frozen=True)
class ConvergenceRun:
    level: int
    requested_size: float
    run_id: str
    candidates: tuple[CandidateResult, ...]
    pareto_front: tuple[str, ...]
    overlaps: tuple[PairOverlap, ...]
    sensitivities: tuple[SensitivityValue, ...]

    def __post_init__(self) -> None:
        if self.level < 0:
            raise ValueError("mesh level must be non-negative")
        if not math.isfinite(self.requested_size) or self.requested_size <= 0.0:
            raise ValueError("requested mesh size must be finite and positive")
        if not self.run_id:
            raise ValueError("run id must not be empty")
        ids = [candidate.candidate_id for candidate in self.candidates]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("candidate ids must be non-empty and unique")
        if not self.pareto_front or not set(self.pareto_front) <= set(ids):
            raise ValueError("Pareto front must be a non-empty candidate subset")
        if len(set(self.pareto_front)) != len(self.pareto_front):
            raise ValueError("Pareto front ids must be unique")

    def candidate(self, candidate_id: str) -> CandidateResult:
        for result in self.candidates:
            if result.candidate_id == candidate_id:
                return result
        raise KeyError(candidate_id)

    def overlap(
        self,
        candidate_a: str,
        candidate_b: str,
        channel: orient.Channel,
        tail_fraction: float,
    ) -> float:
        left, right = sorted((candidate_a, candidate_b))
        for value in self.overlaps:
            if (
                value.candidate_a == left
                and value.candidate_b == right
                and value.channel == channel
                and value.tail_fraction == tail_fraction
            ):
                return value.value
        raise KeyError((left, right, channel, tail_fraction))


@dataclass(frozen=True)
class StudyCriteria:
    ranking_tail_fraction: float
    minimum_levels: int = 3
    minimum_repeats: int = 3
    tie_band: float = 0.05
    same_region_overlap: float = 0.5
    overlap_stability_tolerance: float = 0.1
    sensitivity_stability_tolerance: float = 0.05

    def __post_init__(self) -> None:
        if not math.isfinite(self.ranking_tail_fraction) or not (
            0.0 < self.ranking_tail_fraction <= 1.0
        ):
            raise ValueError("ranking tail fraction must be finite and in (0, 1]")
        if self.minimum_levels < 3:
            raise ValueError("stable confidence requires at least three levels")
        if self.minimum_repeats < 2:
            raise ValueError("remeshing uncertainty requires at least two repeats")
        for name, value in (
            ("tie band", self.tie_band),
            ("same-region overlap", self.same_region_overlap),
            ("overlap stability tolerance", self.overlap_stability_tolerance),
            ("sensitivity stability tolerance", self.sensitivity_stability_tolerance),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")


@dataclass(frozen=True)
class PairConvergence:
    candidate_a: str
    candidate_b: str
    channel: orient.Channel
    tail_fraction: float
    uncertainty: orient.PairUncertainty
    level_median_gaps: tuple[float, ...]
    signed_gap_inversion: bool
    level_median_overlaps: tuple[float, ...]
    overlap_stable: bool
    tie_outcome: orient.TieOutcome


@dataclass(frozen=True)
class KendallResult:
    level: int
    run_a: str
    run_b: str
    comparable_pairs: int
    tau: float | None


@dataclass(frozen=True)
class ConvergenceReport:
    confidence: Confidence
    reasons: tuple[str, ...]
    preferred_set: tuple[str, ...]
    top_set_consistent: bool
    margin_rule_satisfied: bool
    sensitivity_stable: bool
    pair_results: tuple[PairConvergence, ...]
    kendall: tuple[KendallResult, ...]


def run_from_ranking(
    *,
    level: int,
    requested_size: float,
    run_id: str,
    ranking: orient.RankingResult,
    candidate_id: Callable[[orient.Candidate], str],
) -> ConvergenceRun:
    """Reduce a ranking to the mesh-independent data needed by Phase 3."""
    results = tuple(
        CandidateResult(
            candidate_id=candidate_id(score.candidate),
            candidate=score.candidate,
            metrics=tuple(
                MetricValue(item.channel, item.tail_fraction, item.value)
                for item in score.channel_scores
            ),
            display_rank=index,
        )
        for index, score in enumerate(ranking.scores)
    )
    ids = {result.candidate: result.candidate_id for result in results}
    overlaps: list[PairOverlap] = []
    for left, right in combinations(ranking.scores, 2):
        left_id, right_id = sorted((ids[left.candidate], ids[right.candidate]))
        for fraction in ranking.tail_fractions:
            for channel in orient.CHANNELS:
                overlaps.append(
                    PairOverlap(
                        left_id,
                        right_id,
                        channel,
                        fraction,
                        orient.critical_region_overlap(
                            left.critical_samples(channel, fraction),
                            right.critical_samples(channel, fraction),
                        ),
                    )
                )
    return ConvergenceRun(
        level=level,
        requested_size=requested_size,
        run_id=run_id,
        candidates=results,
        pareto_front=tuple(ids[score.candidate] for score in ranking.pareto_front),
        overlaps=tuple(overlaps),
        sensitivities=tuple(
            SensitivityValue(value.tail_fraction, value.value)
            for value in ranking.orientation_sensitivity
        ),
    )


def _dominance(
    left: CandidateResult, right: CandidateResult, tail_fraction: float
) -> int:
    left_values = tuple(
        left.value(channel, tail_fraction) for channel in orient.CHANNELS
    )
    right_values = tuple(
        right.value(channel, tail_fraction) for channel in orient.CHANNELS
    )
    if all(a <= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a < b for a, b in zip(left_values, right_values, strict=True)
    ):
        return -1
    if all(a >= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a > b for a, b in zip(left_values, right_values, strict=True)
    ):
        return 1
    return 0


def comparable_kendall(
    left: ConvergenceRun, right: ConvergenceRun, tail_fraction: float
) -> tuple[float | None, int]:
    """Kendall correlation over pairs Pareto-comparable in both rankings."""
    ids = sorted({item.candidate_id for item in left.candidates})
    if ids != sorted(item.candidate_id for item in right.candidates):
        raise ValueError("Kendall comparison requires the same candidate ids")
    concordant = 0
    discordant = 0
    for candidate_a, candidate_b in combinations(ids, 2):
        direction_a = _dominance(
            left.candidate(candidate_a), left.candidate(candidate_b), tail_fraction
        )
        direction_b = _dominance(
            right.candidate(candidate_a), right.candidate(candidate_b), tail_fraction
        )
        if direction_a == 0 or direction_b == 0:
            continue
        if direction_a == direction_b:
            concordant += 1
        else:
            discordant += 1
    count = concordant + discordant
    if count == 0:
        return None, 0
    return (concordant - discordant) / count, count


def _validated_runs(
    runs: Sequence[ConvergenceRun], criteria: StudyCriteria
) -> dict[int, list[ConvergenceRun]]:
    if not runs:
        raise ValueError("convergence study must contain at least one run")
    grouped: dict[int, list[ConvergenceRun]] = defaultdict(list)
    reference_ids = {item.candidate_id for item in runs[0].candidates}
    reference_candidates = {
        item.candidate_id: item.candidate for item in runs[0].candidates
    }
    reference_metrics = {
        (metric.channel, metric.tail_fraction)
        for metric in runs[0].candidates[0].metrics
    }
    if ("opening", criteria.ranking_tail_fraction) not in reference_metrics or (
        "shear",
        criteria.ranking_tail_fraction,
    ) not in reference_metrics:
        raise ValueError("ranking tail fraction is absent from candidate metrics")
    seen: set[tuple[int, str]] = set()
    for run in runs:
        key = (run.level, run.run_id)
        if key in seen:
            raise ValueError(f"duplicate run id within mesh level: {key}")
        seen.add(key)
        ids = {item.candidate_id for item in run.candidates}
        if ids != reference_ids:
            raise ValueError("candidate ids changed within the refinement series")
        for item in run.candidates:
            if item.candidate != reference_candidates[item.candidate_id]:
                raise ValueError(
                    "candidate geometry changed within the refinement series"
                )
            metrics = {
                (metric.channel, metric.tail_fraction) for metric in item.metrics
            }
            if metrics != reference_metrics:
                raise ValueError(
                    "candidate metrics changed within the refinement series"
                )
        grouped[run.level].append(run)
    return grouped


def _median_gap(
    level: Sequence[ConvergenceRun],
    candidate_a: str,
    candidate_b: str,
    channel: orient.Channel,
    tail_fraction: float,
) -> float:
    return statistics.median(
        run.candidate(candidate_b).value(channel, tail_fraction)
        - run.candidate(candidate_a).value(channel, tail_fraction)
        for run in level
    )


def _sensitivity_is_stable(
    levels: Sequence[Sequence[ConvergenceRun]], tolerance: float
) -> bool:
    tails = {item.tail_fraction for item in levels[-1][0].sensitivities}
    if not tails:
        return False
    for tail in tails:
        medians: list[float] = []
        for level in levels:
            values = [
                item.value
                for run in level
                for item in run.sensitivities
                if item.tail_fraction == tail
            ]
            if len(values) != len(level) or any(value is None for value in values):
                return False
            medians.append(
                statistics.median(value for value in values if value is not None)
            )
        finest_values = [
            item.value
            for run in levels[-1]
            for item in run.sensitivities
            if item.tail_fraction == tail and item.value is not None
        ]
        if max(finest_values) - min(finest_values) > tolerance:
            return False
        if abs(medians[-1] - medians[-2]) > tolerance:
            return False
    return True


def analyse(
    runs: Sequence[ConvergenceRun], criteria: StudyCriteria
) -> ConvergenceReport:
    """Apply the documented Phase 3 confidence rule to repeated mesh levels."""
    try:
        grouped = _validated_runs(runs, criteria)
    except (KeyError, ValueError) as error:
        return ConvergenceReport(
            "invalid", (str(error),), (), False, False, False, (), ()
        )
    level_ids = sorted(grouped)
    levels = [grouped[level] for level in level_ids]
    finest_front = tuple(sorted(levels[-1][0].pareto_front))
    if len(levels) == 1:
        return ConvergenceReport(
            "not_checked",
            ("only one refinement level is available",),
            finest_front,
            len({frozenset(run.pareto_front) for run in levels[-1]}) == 1,
            False,
            False,
            (),
            (),
        )

    candidate_ids = sorted(item.candidate_id for item in levels[0][0].candidates)
    candidate_map = {
        item.candidate_id: item.candidate for item in levels[0][0].candidates
    }
    metric_keys = sorted(
        (
            (metric.channel, metric.tail_fraction)
            for metric in levels[0][0].candidates[0].metrics
        ),
        key=lambda value: (value[1], value[0]),
    )
    enough_levels = len(levels) >= criteria.minimum_levels
    checked_levels = levels[-criteria.minimum_levels :]
    enough_repeats = all(
        len(level) >= criteria.minimum_repeats for level in checked_levels
    )
    pair_results: list[PairConvergence] = []
    pair_lookup: dict[tuple[str, str, orient.Channel], PairConvergence] = {}
    for candidate_a, candidate_b in combinations(candidate_ids, 2):
        for channel, tail_fraction in metric_keys:
            finest = tuple(
                orient.MatchedPairScore(
                    run.run_id,
                    run.candidate(candidate_a).value(channel, tail_fraction),
                    run.candidate(candidate_b).value(channel, tail_fraction),
                )
                for run in levels[-1]
            )
            previous = tuple(
                orient.MatchedPairScore(
                    run.run_id,
                    run.candidate(candidate_a).value(channel, tail_fraction),
                    run.candidate(candidate_b).value(channel, tail_fraction),
                )
                for run in levels[-2]
            )
            gaps = tuple(
                _median_gap(level, candidate_a, candidate_b, channel, tail_fraction)
                for level in checked_levels
            )
            inversion = any(left * right < 0.0 for left, right in pairwise(gaps))
            overlaps = tuple(
                statistics.median(
                    run.overlap(candidate_a, candidate_b, channel, tail_fraction)
                    for run in level
                )
                for level in checked_levels
            )
            same_side = all(
                (value >= criteria.same_region_overlap)
                == (overlaps[-1] >= criteria.same_region_overlap)
                for value in overlaps
            )
            overlap_stable = same_side and (
                max(overlaps) - min(overlaps) <= criteria.overlap_stability_tolerance
            )
            uncertainty = orient.paired_gap_uncertainty(
                finest,
                previous,
                candidate_a=candidate_map[candidate_a],
                candidate_b=candidate_map[candidate_b],
                channel=channel,
                tail_fraction=tail_fraction,
                stable=False,
            )
            result = PairConvergence(
                candidate_a,
                candidate_b,
                channel,
                tail_fraction,
                uncertainty,
                gaps,
                inversion,
                overlaps,
                overlap_stable,
                "not_checked",
            )
            pair_results.append(result)
            if tail_fraction == criteria.ranking_tail_fraction:
                pair_lookup[(candidate_a, candidate_b, channel)] = result

    def advantage_beyond_resolution(preferred: str, other: str) -> bool:
        left, right = sorted((preferred, other))
        advantages: list[bool] = []
        for channel in orient.CHANNELS:
            pair = pair_lookup[(left, right, channel)]
            signed = pair.uncertainty.finest_median_gap
            advantage = signed if preferred == left else -signed
            advantages.append(advantage > pair.uncertainty.direct_gap)
        return all(advantages)

    # Exact Pareto membership flickers when two candidates differ only below
    # measured resolution. Build the confidence set from robust dominance, then
    # require every observed fine-mesh front to stay inside that expanded set.
    finest_front = tuple(
        candidate_id
        for candidate_id in candidate_ids
        if not any(
            advantage_beyond_resolution(other, candidate_id)
            for other in candidate_ids
            if other != candidate_id
        )
    )
    top_set_consistent = all(
        set(run.pareto_front) <= set(finest_front)
        for level in checked_levels
        for run in level
    )

    margin_rule = top_set_consistent
    excluded = set(candidate_ids) - set(finest_front)
    for excluded_id in excluded:
        robustly_dominated = any(
            advantage_beyond_resolution(preferred_id, excluded_id)
            for preferred_id in finest_front
        )
        margin_rule = margin_rule and robustly_dominated

    top_pair_results = [
        result
        for result in pair_results
        if result.candidate_a in finest_front
        and result.candidate_b in finest_front
        and result.tail_fraction == criteria.ranking_tail_fraction
    ]

    def resolved_inversion(result: PairConvergence) -> bool:
        finest_gap = result.uncertainty.finest_median_gap
        if abs(finest_gap) <= result.uncertainty.direct_gap:
            return False
        finest_sign = math.copysign(1.0, finest_gap)
        signs = {
            math.copysign(1.0, gap)
            for gap in result.level_median_gaps
            if abs(gap) > result.uncertainty.direct_gap
        }
        return any(sign != finest_sign for sign in signs)

    no_top_inversions = not any(
        resolved_inversion(result) for result in top_pair_results
    )
    overlaps_stable = all(result.overlap_stable for result in top_pair_results)
    sensitivity_stable = enough_levels and _sensitivity_is_stable(
        checked_levels, criteria.sensitivity_stability_tolerance
    )
    stable = (
        enough_levels
        and enough_repeats
        and top_set_consistent
        and margin_rule
        and no_top_inversions
        and sensitivity_stable
    )

    resolved_pairs: list[PairConvergence] = []
    for result in pair_results:
        uncertainty = replace(result.uncertainty, stable=stable)
        denominator = max(uncertainty.finest_median_a, uncertainty.finest_median_b)
        gap = abs(uncertainty.finest_median_gap)
        relative_gap = 0.0 if denominator == 0.0 else gap / denominator
        resolved_pairs.append(
            replace(
                result,
                uncertainty=uncertainty,
                tie_outcome=orient.tie_outcome(
                    gap=gap,
                    relative_gap=relative_gap,
                    direct_gap_uncertainty=uncertainty.direct_gap,
                    stable=stable
                    and (result.overlap_stable or relative_gap > criteria.tie_band),
                    critical_region_overlap=result.level_median_overlaps[-1],
                    tie_band=criteria.tie_band,
                    same_region_overlap=criteria.same_region_overlap,
                ),
            )
        )

    kendall: list[KendallResult] = []
    for level_id, level in zip(level_ids, levels, strict=True):
        for left, right in combinations(level, 2):
            tau, count = comparable_kendall(left, right, criteria.ranking_tail_fraction)
            kendall.append(
                KendallResult(level_id, left.run_id, right.run_id, count, tau)
            )

    reasons: list[str] = []
    if not enough_levels:
        reasons.append(
            f"need {criteria.minimum_levels} refinement levels; got {len(levels)}"
        )
    if not enough_repeats:
        reasons.append(
            f"need {criteria.minimum_repeats} remeshes in each checked level"
        )
    if not top_set_consistent:
        reasons.append(
            "an observed Pareto front left the resolution-expanded preferred set"
        )
    if not margin_rule:
        reasons.append(
            "an excluded candidate was not dominated beyond direct gap uncertainty"
        )
    if not no_top_inversions:
        reasons.append("a signed top-pair gap inverted under refinement")
    if not overlaps_stable:
        reasons.append(
            "ranking stable but a top-pair critical-region label remains not_checked"
        )
    if not sensitivity_stable:
        reasons.append("orientation sensitivity did not stabilise")
    if stable:
        reasons.append("preferred set and margins satisfy the tested-mesh rule")
    return ConvergenceReport(
        "stable_at_tested_meshes" if stable else "indeterminate",
        tuple(reasons),
        finest_front,
        top_set_consistent,
        margin_rule,
        sensitivity_stable,
        tuple(resolved_pairs),
        tuple(kendall),
    )

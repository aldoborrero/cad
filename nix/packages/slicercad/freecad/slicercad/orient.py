"""Rank print orientations against the loads a part will carry.

This module is pure arithmetic.  FreeCAD adapters provide weighted stress
samples and geometric code provides candidate layer normals; neither dependency
is imported here.

The ranking is comparative, not a strength verdict.  Opening and shear traction
across layer interfaces remain separate objectives because they have different
material allowables.  Without those allowables, Pareto dominance is the only
honest mechanical ordering.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, groupby, pairwise
from typing import Literal

type Stress = Sequence[float]
type StressTuple = tuple[float, float, float, float, float, float]
type Vector = Sequence[float]
type Vector3 = tuple[float, float, float]
type SampleId = int | str
type Channel = Literal["opening", "shear"]
type MarginScope = Literal["adjacent", "pareto_pairwise"]
type TieOutcome = Literal[
    "not_checked",
    "below_resolution",
    "physical_shared_region",
    "physical_distinct_regions",
    "resolved",
]

CHANNELS: tuple[Channel, ...] = ("opening", "shear")
DEFAULT_TAIL_FRACTIONS = (0.01, 0.05)
WEIGHTED_CVAR = "weighted_upper_tail_cvar"


def _unit(vector: Vector) -> Vector3:
    if len(vector) != 3:
        raise ValueError(f"a direction needs 3 components, got {len(vector)}")
    if any(not math.isfinite(value) for value in vector):
        raise ValueError("the direction must contain only finite values")
    length = math.sqrt(math.fsum(value * value for value in vector))
    if not length:
        raise ValueError("the direction has no length")
    x, y, z = (value / length for value in vector)
    return x, y, z


def _axis(vector: Vector) -> Vector3:
    """Canonicalise an unoriented layer normal so n and -n are identical."""
    direction = _unit(vector)
    for component in direction:
        if component > 0.0:
            return direction
        if component < 0.0:
            x, y, z = direction
            return -x, -y, -z
    raise AssertionError("a unit vector cannot have only zero components")


def _stress_tuple(stress: Stress) -> StressTuple:
    if len(stress) != 6:
        raise ValueError(f"a stress tensor needs 6 components, got {len(stress)}")
    if any(not math.isfinite(value) for value in stress):
        raise ValueError("the stress tensor must contain only finite values")
    xx, yy, zz, xy, xz, yz = stress
    return xx, yy, zz, xy, xz, yz


def _position_tuple(position: Vector | None) -> Vector3 | None:
    if position is None:
        return None
    if len(position) != 3:
        raise ValueError(f"a position needs 3 components, got {len(position)}")
    if any(not math.isfinite(value) for value in position):
        raise ValueError("the position must contain only finite values")
    x, y, z = position
    return x, y, z


def field_from_lists(
    *,
    xx: Sequence[float],
    yy: Sequence[float],
    zz: Sequence[float],
    xy: Sequence[float],
    xz: Sequence[float],
    yz: Sequence[float],
) -> list[StressTuple]:
    """Zip FreeCAD's six nodal component lists in the declared tensor order."""
    lists = (xx, yy, zz, xy, xz, yz)
    if len({len(component) for component in lists}) > 1:
        raise ValueError(
            "the six stress components must be the same length, got "
            + ", ".join(str(len(component)) for component in lists)
        )
    return [tuple(node) for node in zip(*lists, strict=True)]


@dataclass(frozen=True)
class Candidate:
    """An unoriented layer normal and non-mechanical candidate metadata."""

    build: Vector3
    area: float = 0.0
    source: str = "face"

    def __post_init__(self) -> None:
        object.__setattr__(self, "build", _axis(self.build))
        if not math.isfinite(self.area) or self.area < 0.0:
            raise ValueError("candidate area must be finite and non-negative")
        if not self.source:
            raise ValueError("candidate source must not be empty")


@dataclass(frozen=True)
class WeightedStress:
    """One stress tensor and the physical volume for which it speaks."""

    stress: StressTuple
    volume: float
    sample_id: SampleId | None = None
    position: Vector3 | None = None
    source_node_ids: tuple[int, ...] = ()
    source_element_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stress", _stress_tuple(self.stress))
        object.__setattr__(self, "position", _position_tuple(self.position))
        if not math.isfinite(self.volume) or self.volume <= 0.0:
            raise ValueError("sample volume must be finite and positive")


@dataclass(frozen=True)
class WeightedValue:
    """A scalar sample with enough provenance to identify its CVaR tail."""

    sample_id: SampleId
    value: float
    weight: float
    position: Vector3 | None = None
    source_node_ids: tuple[int, ...] = ()
    source_element_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("sample value must be finite")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("sample weight must be finite and positive")
        object.__setattr__(self, "position", _position_tuple(self.position))


@dataclass(frozen=True)
class TailContribution:
    """The exact part of one sample consumed by an upper-tail statistic."""

    sample_id: SampleId
    value: float
    sample_volume: float
    tail_volume: float
    position: Vector3 | None
    source_node_ids: tuple[int, ...]
    source_element_ids: tuple[int, ...]


@dataclass(frozen=True)
class TailStatistic:
    """A weighted upper-tail value and the samples responsible for it."""

    value: float
    tail_fraction: float
    total_volume: float
    tail_volume: float
    contributions: tuple[TailContribution, ...]
    weight_signature: str
    aggregation: str = WEIGHTED_CVAR


@dataclass(frozen=True)
class LayerTraction:
    """Traction on a layer plane, split into opening and interface shear."""

    vector: Vector3
    normal: float
    opening: float
    shear: float


def traction(stress: Stress, build: Vector) -> Vector3:
    """Return sigma n for the layer plane whose unit normal is ``build``."""
    xx, yy, zz, xy, xz, yz = _stress_tuple(stress)
    nx, ny, nz = _unit(build)
    return (
        xx * nx + xy * ny + xz * nz,
        xy * nx + yy * ny + yz * nz,
        xz * nx + yz * ny + zz * nz,
    )


def layer_traction(stress: Stress, build: Vector) -> LayerTraction:
    """Resolve traction into tensile opening and in-plane shear, in stress units."""
    nx, ny, nz = _unit(build)
    tx, ty, tz = traction(stress, (nx, ny, nz))
    normal = math.fsum((nx * tx, ny * ty, nz * tz))
    shear_vector = (
        tx - normal * nx,
        ty - normal * ny,
        tz - normal * nz,
    )
    shear = math.sqrt(math.fsum(value * value for value in shear_vector))
    return LayerTraction(
        vector=(tx, ty, tz),
        normal=normal,
        opening=max(normal, 0.0),
        shear=shear,
    )


def normal_stress(stress: Stress, build: Vector) -> float:
    """Return n^T sigma n, preserving compression as a negative value."""
    return layer_traction(stress, build).normal


def peak_normal_stress(field: Sequence[Stress], build: Vector) -> float:
    """Return the mesh-dependent nodal peak as a diagnostic only.

    This value is deliberately excluded from product ranking.  It does not
    converge at common idealised restraints and gives each node one vote
    regardless of the material volume represented by that node.
    """
    if not field:
        raise ValueError("the stress field must not be empty")
    broken = sum(
        1
        for stress in field
        if len(stress) != 6 or any(not math.isfinite(value) for value in stress)
    )
    if broken:
        raise ValueError(f"{broken} of {len(field)} nodes are not a finite stress")
    return max(layer_traction(stress, build).opening for stress in field)


def largest_principal_stress(stress: Stress) -> float:
    """Return the largest eigenvalue of a real symmetric 3x3 stress tensor."""
    xx, yy, zz, xy, xz, yz = _stress_tuple(stress)
    mean = (xx + yy + zz) / 3.0
    p_squared = (
        (xx - mean) ** 2
        + (yy - mean) ** 2
        + (zz - mean) ** 2
        + 2.0 * (xy * xy + xz * xz + yz * yz)
    ) / 6.0
    if p_squared == 0.0:
        return mean

    p = math.sqrt(p_squared)
    bxx = (xx - mean) / p
    byy = (yy - mean) / p
    bzz = (zz - mean) / p
    bxy = xy / p
    bxz = xz / p
    byz = yz / p
    determinant = (
        bxx * byy * bzz
        + 2.0 * bxy * bxz * byz
        - bxx * byz * byz
        - byy * bxz * bxz
        - bzz * bxy * bxy
    )
    angle = math.acos(max(-1.0, min(1.0, determinant / 2.0))) / 3.0
    return mean + 2.0 * p * math.cos(angle)


def _validated_tail_fraction(tail_fraction: float) -> float:
    if not math.isfinite(tail_fraction) or not 0.0 < tail_fraction <= 1.0:
        raise ValueError("tail fraction must be finite and in (0, 1]")
    return tail_fraction


def _require_values(samples: Sequence[WeightedValue]) -> None:
    if not samples:
        raise ValueError("weighted samples must not be empty")


def _weight_signature(samples: Sequence[WeightedValue]) -> str:
    digest = hashlib.sha256()

    def add(value: str) -> None:
        encoded = value.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)

    for sample in samples:
        add(f"{type(sample.sample_id).__name__}:{sample.sample_id}")
        add(sample.weight.hex())
        add(
            "none"
            if sample.position is None
            else ",".join(component.hex() for component in sample.position)
        )
        add(",".join(str(node_id) for node_id in sample.source_node_ids))
        add(",".join(str(element_id) for element_id in sample.source_element_ids))
    return digest.hexdigest()


def weighted_quantile(samples: Sequence[WeightedValue], quantile: float) -> float:
    """Return a stepwise weighted quantile from zero through one inclusive."""
    _require_values(samples)
    if not math.isfinite(quantile) or not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be finite and in [0, 1]")
    ordered = sorted(enumerate(samples), key=lambda item: (item[1].value, item[0]))
    target = quantile * math.fsum(sample.weight for sample in samples)
    if target == 0.0:
        return ordered[0][1].value
    cumulative = 0.0
    for _, sample in ordered:
        cumulative += sample.weight
        if cumulative >= target:
            return sample.value
    return ordered[-1][1].value


def weighted_upper_tail_cvar(
    samples: Sequence[WeightedValue], tail_fraction: float
) -> TailStatistic:
    """Average the largest values over exactly ``tail_fraction`` of the weight.

    If the tail boundary cuts through equal-valued samples, each tied sample is
    consumed in the same proportion.  This keeps the critical-region map
    independent of sample ordering and subdivision.
    """
    _require_values(samples)
    fraction = _validated_tail_fraction(tail_fraction)
    total_volume = math.fsum(sample.weight for sample in samples)
    target_volume = total_volume * fraction
    remaining = target_volume
    contributions: list[TailContribution] = []
    weighted_terms: list[float] = []
    ordered = sorted(enumerate(samples), key=lambda item: (-item[1].value, item[0]))

    for _, equal_value_items in groupby(ordered, key=lambda item: item[1].value):
        group = list(equal_value_items)
        group_volume = math.fsum(sample.weight for _, sample in group)
        fraction_used = min(1.0, remaining / group_volume)
        for _, sample in group:
            consumed = sample.weight * fraction_used
            if consumed > 0.0:
                contributions.append(
                    TailContribution(
                        sample_id=sample.sample_id,
                        value=sample.value,
                        sample_volume=sample.weight,
                        tail_volume=consumed,
                        position=sample.position,
                        source_node_ids=sample.source_node_ids,
                        source_element_ids=sample.source_element_ids,
                    )
                )
                weighted_terms.append(sample.value * consumed)
        remaining = max(0.0, remaining - group_volume)
        if remaining == 0.0:
            break

    return TailStatistic(
        value=math.fsum(weighted_terms) / target_volume,
        tail_fraction=fraction,
        total_volume=total_volume,
        tail_volume=target_volume,
        contributions=tuple(contributions),
        weight_signature=_weight_signature(samples),
    )


@dataclass(frozen=True)
class ChannelTailScore:
    channel: Channel
    statistic: TailStatistic

    @property
    def tail_fraction(self) -> float:
        return self.statistic.tail_fraction

    @property
    def value(self) -> float:
        return self.statistic.value


@dataclass(frozen=True)
class OrientationScore:
    candidate: Candidate
    channel_scores: tuple[ChannelTailScore, ...]
    total_volume: float

    @property
    def build(self) -> Vector3:
        return self.candidate.build

    @property
    def opening_cvar_1(self) -> float:
        return self.value("opening", 0.01)

    @property
    def opening_cvar_5(self) -> float:
        return self.value("opening", 0.05)

    @property
    def shear_cvar_1(self) -> float:
        return self.value("shear", 0.01)

    @property
    def shear_cvar_5(self) -> float:
        return self.value("shear", 0.05)

    def tail_score(self, channel: Channel, tail_fraction: float) -> ChannelTailScore:
        for score in self.channel_scores:
            if score.channel == channel and score.tail_fraction == tail_fraction:
                return score
        raise KeyError(f"no {channel} score for tail fraction {tail_fraction}")

    def value(self, channel: Channel, tail_fraction: float) -> float:
        return self.tail_score(channel, tail_fraction).value

    def critical_samples(
        self, channel: Channel, tail_fraction: float
    ) -> tuple[TailContribution, ...]:
        return self.tail_score(channel, tail_fraction).statistic.contributions


def _resolved_field(field: Sequence[WeightedStress]) -> tuple[WeightedValue, ...]:
    if not field:
        raise ValueError("the weighted stress field must not be empty")
    resolved: list[WeightedValue] = []
    seen: set[SampleId] = set()
    for index, sample in enumerate(field):
        sample_id = index if sample.sample_id is None else sample.sample_id
        if sample_id in seen:
            raise ValueError(f"duplicate stress sample id: {sample_id!r}")
        seen.add(sample_id)
        resolved.append(
            WeightedValue(
                sample_id=sample_id,
                value=0.0,
                weight=sample.volume,
                position=sample.position,
                source_node_ids=sample.source_node_ids,
                source_element_ids=sample.source_element_ids,
            )
        )
    return tuple(resolved)


def _replace_values(
    provenance: Sequence[WeightedValue], values: Sequence[float]
) -> tuple[WeightedValue, ...]:
    return tuple(
        WeightedValue(
            sample_id=sample.sample_id,
            value=value,
            weight=sample.weight,
            position=sample.position,
            source_node_ids=sample.source_node_ids,
            source_element_ids=sample.source_element_ids,
        )
        for sample, value in zip(provenance, values, strict=True)
    )


def score_orientation(
    field: Sequence[WeightedStress],
    candidate: Candidate,
    *,
    tail_fractions: Sequence[float] = DEFAULT_TAIL_FRACTIONS,
) -> OrientationScore:
    """Score opening and shear independently for one candidate layer axis."""
    if not tail_fractions:
        raise ValueError("at least one tail fraction is required")
    fractions = tuple(_validated_tail_fraction(value) for value in tail_fractions)
    if len(set(fractions)) != len(fractions):
        raise ValueError("tail fractions must be unique")
    provenance = _resolved_field(field)
    tractions = [layer_traction(sample.stress, candidate.build) for sample in field]
    channel_scores: list[ChannelTailScore] = []
    for fraction in fractions:
        for channel in CHANNELS:
            values = [getattr(result, channel) for result in tractions]
            statistic = weighted_upper_tail_cvar(
                _replace_values(provenance, values), fraction
            )
            channel_scores.append(
                ChannelTailScore(channel=channel, statistic=statistic)
            )
    return OrientationScore(
        candidate=candidate,
        channel_scores=tuple(channel_scores),
        total_volume=math.fsum(sample.volume for sample in field),
    )


def principal_tension_cvar(
    field: Sequence[WeightedStress],
    *,
    tail_fractions: Sequence[float] = DEFAULT_TAIL_FRACTIONS,
) -> tuple[TailStatistic, ...]:
    """Score the positive largest principal stress with the same field weights."""
    provenance = _resolved_field(field)
    values = [max(largest_principal_stress(sample.stress), 0.0) for sample in field]
    weighted = _replace_values(provenance, values)
    return tuple(
        weighted_upper_tail_cvar(weighted, fraction) for fraction in tail_fractions
    )


def _same_weighting(left: TailStatistic, right: TailStatistic) -> bool:
    return (
        left.weight_signature == right.weight_signature
        and left.total_volume == right.total_volume
    )


def sensitivity_ratio(
    numerator: TailStatistic,
    denominator: TailStatistic,
    *,
    tolerance: float = 1e-12,
) -> float | None:
    """Return an allowable-free opening ratio, or ``None`` for zero loading."""
    if numerator.aggregation != denominator.aggregation:
        raise ValueError("sensitivity requires the same aggregation on both sides")
    if numerator.tail_fraction != denominator.tail_fraction:
        raise ValueError("sensitivity requires the same tail fraction on both sides")
    if not _same_weighting(numerator, denominator):
        raise ValueError("sensitivity requires the same samples and weights")
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and non-negative")
    if denominator.value <= tolerance:
        return None
    ratio = numerator.value / denominator.value
    if ratio < -tolerance or ratio > 1.0 + tolerance:
        raise ValueError("opening sensitivity must lie in [0, 1]")
    return min(1.0, max(0.0, ratio))


@dataclass(frozen=True)
class OrientationSensitivity:
    tail_fraction: float
    numerator: float
    denominator: float
    value: float | None
    aggregation: str
    candidate_sources: tuple[str, ...]


def orientation_sensitivities(
    scores: Sequence[OrientationScore],
    principal_scores: Sequence[TailStatistic],
) -> tuple[OrientationSensitivity, ...]:
    """Compare the best analysed opening score with principal tension."""
    if not scores:
        return ()
    sources = tuple(sorted({score.candidate.source for score in scores}))
    results: list[OrientationSensitivity] = []
    for denominator in principal_scores:
        opening = [
            score.tail_score("opening", denominator.tail_fraction).statistic
            for score in scores
        ]
        numerator = min(opening, key=lambda statistic: statistic.value)
        results.append(
            OrientationSensitivity(
                tail_fraction=denominator.tail_fraction,
                numerator=numerator.value,
                denominator=denominator.value,
                value=sensitivity_ratio(numerator, denominator),
                aggregation=denominator.aggregation,
                candidate_sources=sources,
            )
        )
    return tuple(results)


def dominates(left: OrientationScore, right: OrientationScore) -> bool:
    """Whether ``left`` is no worse everywhere and strictly better somewhere."""
    left_values = tuple(score.value for score in left.channel_scores)
    right_values = tuple(
        right.value(score.channel, score.tail_fraction) for score in left.channel_scores
    )
    return all(a <= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a < b for a, b in zip(left_values, right_values, strict=True)
    )


def _candidate_key(score: OrientationScore, input_index: int) -> tuple[object, ...]:
    return (*score.candidate.build, score.candidate.source, input_index)


def _pareto_layers(
    scores: Sequence[OrientationScore],
) -> tuple[tuple[OrientationScore, ...], ...]:
    remaining = set(range(len(scores)))
    layers: list[tuple[OrientationScore, ...]] = []
    while remaining:
        front_indices = [
            index
            for index in remaining
            if not any(
                dominates(scores[other], scores[index])
                for other in remaining
                if other != index
            )
        ]
        ordered = sorted(
            front_indices, key=lambda index: _candidate_key(scores[index], index)
        )
        layers.append(tuple(scores[index] for index in ordered))
        remaining.difference_update(front_indices)
    return tuple(layers)


@dataclass(frozen=True)
class ScoreMargin:
    candidate_a: Candidate
    candidate_b: Candidate
    channel: Channel
    tail_fraction: float
    signed_gap: float
    absolute_gap: float
    relative_gap: float
    scope: MarginScope


def _score_margin(
    score_a: OrientationScore,
    score_b: OrientationScore,
    channel: Channel,
    tail_fraction: float,
    scope: MarginScope,
) -> ScoreMargin:
    value_a = score_a.value(channel, tail_fraction)
    value_b = score_b.value(channel, tail_fraction)
    signed = value_b - value_a
    denominator = max(value_a, value_b)
    return ScoreMargin(
        candidate_a=score_a.candidate,
        candidate_b=score_b.candidate,
        channel=channel,
        tail_fraction=tail_fraction,
        signed_gap=signed,
        absolute_gap=abs(signed),
        relative_gap=0.0 if denominator == 0.0 else abs(signed) / denominator,
        scope=scope,
    )


def _ranking_margins(
    display_scores: Sequence[OrientationScore],
    pareto_front: Sequence[OrientationScore],
    tail_fractions: Sequence[float],
) -> tuple[ScoreMargin, ...]:
    margins: list[ScoreMargin] = []
    for score_a, score_b in pairwise(display_scores):
        for fraction in tail_fractions:
            for channel in CHANNELS:
                margins.append(
                    _score_margin(score_a, score_b, channel, fraction, "adjacent")
                )
    for score_a, score_b in combinations(pareto_front, 2):
        for fraction in tail_fractions:
            for channel in CHANNELS:
                margins.append(
                    _score_margin(
                        score_a, score_b, channel, fraction, "pareto_pairwise"
                    )
                )
    return tuple(margins)


def critical_region_overlap(
    left: Sequence[TailContribution], right: Sequence[TailContribution]
) -> float:
    """Weighted Jaccard overlap of two exact CVaR tail-volume maps."""
    if not left or not right:
        raise ValueError("critical regions must not be empty")
    left_map: dict[SampleId, float] = {}
    right_map: dict[SampleId, float] = {}
    for contribution in left:
        left_map[contribution.sample_id] = (
            left_map.get(contribution.sample_id, 0.0) + contribution.tail_volume
        )
    for contribution in right:
        right_map[contribution.sample_id] = (
            right_map.get(contribution.sample_id, 0.0) + contribution.tail_volume
        )
    ids = left_map.keys() | right_map.keys()
    intersection = math.fsum(
        min(left_map.get(sample_id, 0.0), right_map.get(sample_id, 0.0))
        for sample_id in ids
    )
    union = math.fsum(
        max(left_map.get(sample_id, 0.0), right_map.get(sample_id, 0.0))
        for sample_id in ids
    )
    if union <= 0.0:
        raise ValueError("critical regions must have positive tail volume")
    return intersection / union


@dataclass(frozen=True)
class MatchedPairScore:
    """Scores for a stable A/B pair from one mesh generation."""

    run_id: SampleId
    score_a: float
    score_b: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score_a) or not math.isfinite(self.score_b):
            raise ValueError("matched scores must be finite")
        if self.score_a < 0.0 or self.score_b < 0.0:
            raise ValueError("matched mechanical scores must be non-negative")

    @property
    def signed_gap(self) -> float:
        return self.score_b - self.score_a


@dataclass(frozen=True)
class PairUncertainty:
    candidate_a: Candidate
    candidate_b: Candidate
    channel: Channel
    tail_fraction: float
    direct_gap: float
    summed_individual: float
    finest_median_a: float
    finest_median_b: float
    previous_median_a: float
    previous_median_b: float
    finest_median_gap: float
    previous_median_gap: float
    finest_gap_spread: float
    stable: bool

    def __post_init__(self) -> None:
        _validated_tail_fraction(self.tail_fraction)
        values = (
            self.direct_gap,
            self.summed_individual,
            self.finest_median_a,
            self.finest_median_b,
            self.previous_median_a,
            self.previous_median_b,
            self.finest_median_gap,
            self.previous_median_gap,
            self.finest_gap_spread,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("pair uncertainty values must be finite")
        if self.direct_gap < 0.0 or self.summed_individual < 0.0:
            raise ValueError("pair uncertainties must be non-negative")
        if self.finest_gap_spread < 0.0:
            raise ValueError("gap spread must be non-negative")
        score_medians = (
            self.finest_median_a,
            self.finest_median_b,
            self.previous_median_a,
            self.previous_median_b,
        )
        if any(value < 0.0 for value in score_medians):
            raise ValueError("mechanical score medians must be non-negative")


def _spread(values: Sequence[float]) -> float:
    return max(values) - min(values)


def _unique_runs(level: Sequence[MatchedPairScore], name: str) -> None:
    if not level:
        raise ValueError(f"{name} matched scores must not be empty")
    ids = [sample.run_id for sample in level]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name} run ids must be unique")


def paired_gap_uncertainty(
    finest: Sequence[MatchedPairScore],
    previous: Sequence[MatchedPairScore],
    *,
    candidate_a: Candidate,
    candidate_b: Candidate,
    channel: Channel,
    tail_fraction: float,
    stable: bool,
) -> PairUncertainty:
    """Estimate pair resolution from matched signed gaps, preserving covariance."""
    _unique_runs(finest, "finest")
    _unique_runs(previous, "previous")
    finest_a = [sample.score_a for sample in finest]
    finest_b = [sample.score_b for sample in finest]
    previous_a = [sample.score_a for sample in previous]
    previous_b = [sample.score_b for sample in previous]
    finest_gaps = [sample.signed_gap for sample in finest]
    previous_gaps = [sample.signed_gap for sample in previous]
    finest_gap = statistics.median(finest_gaps)
    previous_gap = statistics.median(previous_gaps)
    gap_spread = _spread(finest_gaps)
    direct = max(gap_spread, abs(finest_gap - previous_gap))
    uncertainty_a = max(
        _spread(finest_a),
        abs(statistics.median(finest_a) - statistics.median(previous_a)),
    )
    uncertainty_b = max(
        _spread(finest_b),
        abs(statistics.median(finest_b) - statistics.median(previous_b)),
    )
    return PairUncertainty(
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        channel=channel,
        tail_fraction=tail_fraction,
        direct_gap=direct,
        summed_individual=uncertainty_a + uncertainty_b,
        finest_median_a=statistics.median(finest_a),
        finest_median_b=statistics.median(finest_b),
        previous_median_a=statistics.median(previous_a),
        previous_median_b=statistics.median(previous_b),
        finest_median_gap=finest_gap,
        previous_median_gap=previous_gap,
        finest_gap_spread=gap_spread,
        stable=stable,
    )


@dataclass(frozen=True)
class TieDiagnostic:
    candidate_a: Candidate
    candidate_b: Candidate
    channel: Channel
    tail_fraction: float
    signed_gap: float
    gap: float
    relative_gap: float
    direct_gap_uncertainty: float | None
    summed_individual_uncertainty: float | None
    critical_region_overlap: float
    tie_band: float
    same_region_overlap: float
    outcome: TieOutcome


def classify_tie(
    score_a: OrientationScore,
    score_b: OrientationScore,
    channel: Channel,
    tail_fraction: float,
    *,
    uncertainty: PairUncertainty | None,
    tie_band: float = 0.05,
    same_region_overlap: float = 0.5,
) -> TieDiagnostic:
    """Diagnose a pair without turning numerical uncertainty into a physical tie."""
    if not math.isfinite(tie_band) or not 0.0 <= tie_band <= 1.0:
        raise ValueError("tie band must be finite and in [0, 1]")
    if not math.isfinite(same_region_overlap) or not 0.0 <= same_region_overlap <= 1.0:
        raise ValueError("same-region overlap must be finite and in [0, 1]")

    statistic_a = score_a.tail_score(channel, tail_fraction).statistic
    statistic_b = score_b.tail_score(channel, tail_fraction).statistic
    if not _same_weighting(statistic_a, statistic_b):
        raise ValueError(
            "tie classification requires the same mesh samples and weights"
        )
    overlap = critical_region_overlap(
        statistic_a.contributions,
        statistic_b.contributions,
    )
    if uncertainty is None:
        value_a = statistic_a.value
        value_b = statistic_b.value
    else:
        if (
            uncertainty.candidate_a != score_a.candidate
            or uncertainty.candidate_b != score_b.candidate
            or uncertainty.channel != channel
            or uncertainty.tail_fraction != tail_fraction
        ):
            raise ValueError(
                "pair uncertainty does not match the ordered candidates and metric"
            )
        value_a = uncertainty.finest_median_a
        value_b = uncertainty.finest_median_b

    signed_gap = (
        value_b - value_a if uncertainty is None else uncertainty.finest_median_gap
    )
    gap = abs(signed_gap)
    denominator = max(value_a, value_b)
    relative_gap = 0.0 if denominator == 0.0 else gap / denominator

    if uncertainty is None:
        outcome: TieOutcome = "not_checked"
    elif gap <= uncertainty.direct_gap:
        outcome = "below_resolution"
    elif not uncertainty.stable:
        outcome = "not_checked"
    elif relative_gap > tie_band:
        outcome = "resolved"
    elif overlap >= same_region_overlap:
        outcome = "physical_shared_region"
    else:
        outcome = "physical_distinct_regions"
    return TieDiagnostic(
        candidate_a=score_a.candidate,
        candidate_b=score_b.candidate,
        channel=channel,
        tail_fraction=tail_fraction,
        signed_gap=signed_gap,
        gap=gap,
        relative_gap=relative_gap,
        direct_gap_uncertainty=None if uncertainty is None else uncertainty.direct_gap,
        summed_individual_uncertainty=(
            None if uncertainty is None else uncertainty.summed_individual
        ),
        critical_region_overlap=overlap,
        tie_band=tie_band,
        same_region_overlap=same_region_overlap,
        outcome=outcome,
    )


@dataclass(frozen=True)
class RankingResult:
    scores: tuple[OrientationScore, ...]
    pareto_front: tuple[OrientationScore, ...]
    pareto_layers: tuple[tuple[OrientationScore, ...], ...]
    margins: tuple[ScoreMargin, ...]
    tie_diagnostics: tuple[TieDiagnostic, ...]
    principal_tension_cvar: tuple[TailStatistic, ...]
    orientation_sensitivity: tuple[OrientationSensitivity, ...]
    tail_fractions: tuple[float, ...]
    aggregation: str = WEIGHTED_CVAR


def rank(
    field: Sequence[WeightedStress],
    candidate_set: Sequence[Candidate],
    *,
    tail_fractions: Sequence[float] = DEFAULT_TAIL_FRACTIONS,
) -> RankingResult:
    """Build the Pareto ranking without a peak or mixed-mode scalar."""
    fractions = tuple(_validated_tail_fraction(value) for value in tail_fractions)
    if not fractions:
        raise ValueError("at least one tail fraction is required")
    if len(set(fractions)) != len(fractions):
        raise ValueError("tail fractions must be unique")
    # Validate the field even when there are no candidates.
    _resolved_field(field)
    raw_scores = tuple(
        score_orientation(field, candidate, tail_fractions=fractions)
        for candidate in candidate_set
    )
    layers = _pareto_layers(raw_scores)
    display_scores = tuple(score for layer in layers for score in layer)
    pareto_front = () if not layers else layers[0]
    margins = _ranking_margins(display_scores, pareto_front, fractions)
    unchecked_ties = tuple(
        classify_tie(
            score_a,
            score_b,
            channel,
            fraction,
            uncertainty=None,
        )
        for score_a, score_b in combinations(pareto_front, 2)
        for fraction in fractions
        for channel in CHANNELS
    )
    principal = principal_tension_cvar(field, tail_fractions=fractions)
    return RankingResult(
        scores=display_scores,
        pareto_front=pareto_front,
        pareto_layers=layers,
        margins=margins,
        tie_diagnostics=unchecked_ties,
        principal_tension_cvar=principal,
        orientation_sensitivity=orientation_sensitivities(display_scores, principal),
        tail_fractions=fractions,
    )


def candidates(
    faces: Sequence[tuple[Vector, float]], tolerance_degrees: float = 5.0
) -> list[Candidate]:
    """Return deterministic unoriented candidates from planar face normals."""
    if not math.isfinite(tolerance_degrees) or not 0.0 <= tolerance_degrees < 90.0:
        raise ValueError("candidate tolerance must be finite and in [0, 90)")
    limit = math.cos(math.radians(tolerance_degrees))
    ordered: list[tuple[Vector3, float]] = []
    for normal, area in faces:
        if not math.isfinite(area) or area < 0.0:
            raise ValueError("face area must be finite and non-negative")
        ordered.append((_axis(normal), area))
    ordered.sort(key=lambda face: (-face[1], face[0]))

    areas: list[float] = []
    directions: list[Vector3] = []
    for direction, area in ordered:
        for index, existing in enumerate(directions):
            alignment = math.fabs(
                math.fsum(a * b for a, b in zip(direction, existing, strict=True))
            )
            if alignment >= limit:
                areas[index] += area
                break
        else:
            directions.append(direction)
            areas.append(area)
    return [
        Candidate(build=direction, area=area)
        for direction, area in zip(directions, areas, strict=True)
    ]

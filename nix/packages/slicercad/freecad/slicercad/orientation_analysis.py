"""Plain-data orientation analysis suitable for persistence in a CAD document."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from . import fem_result, orient

SCHEMA_VERSION = 1
COMPARATIVE_WARNING = (
    "Comparative result from one isotropic linear solve; it is not a load capacity "
    "or factor of safety."
)


@dataclass(frozen=True)
class Analysis:
    ranking: orient.RankingResult
    current_score: orient.OrientationScore
    record: dict[str, Any]

    def json(self) -> str:
        return json.dumps(self.record, indent=2, sort_keys=True) + "\n"


def _contribution(value: orient.TailContribution) -> dict[str, Any]:
    return {
        "sample_id": value.sample_id,
        "value_mpa": value.value,
        "sample_volume_mm3": value.sample_volume,
        "tail_volume_mm3": value.tail_volume,
        "position_mm": value.position,
        "source_node_ids": value.source_node_ids,
        "source_element_ids": value.source_element_ids,
    }


def analyse(
    *,
    result_object: str,
    part_objects: tuple[str, ...],
    field: fem_result.A0StressField,
    candidate_set: tuple[orient.Candidate, ...],
    current_build: orient.Vector3 = (0.0, 0.0, 1.0),
    ranking_tail_fraction: float = 0.05,
    tail_fractions: tuple[float, ...] = orient.DEFAULT_TAIL_FRACTIONS,
) -> Analysis:
    """Score candidates once and retain every value needed to audit the result."""
    if not result_object:
        raise ValueError("result object id must not be empty")
    if not part_objects or any(not value for value in part_objects):
        raise ValueError("at least one part object id is required")
    if not candidate_set:
        raise ValueError("at least one orientation candidate is required")
    ranking = orient.rank(
        field.samples,
        candidate_set,
        ranking_tail_fraction=ranking_tail_fraction,
        tail_fractions=tail_fractions,
    )
    current_candidate = orient.Candidate(current_build, source="current")
    current_score = orient.score_orientation(
        field.samples,
        current_candidate,
        tail_fractions=tail_fractions,
    )
    candidate_ids = {
        candidate: f"O{index + 1}" for index, candidate in enumerate(candidate_set)
    }
    score_by_candidate = {score.candidate: score for score in ranking.scores}
    element_type_counts: dict[str, int] = {}
    for element in field.element_volumes:
        element_type_counts[element.element_type] = (
            element_type_counts.get(element.element_type, 0) + 1
        )
    candidate_digest = hashlib.sha256()
    for candidate in candidate_set:
        candidate_digest.update(
            (
                ":".join(value.hex() for value in candidate.build)
                + f":{candidate.area.hex()}:{candidate.source}\n"
            ).encode()
        )
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "result_object": result_object,
        "part_objects": part_objects,
        "mesh_signature": field.mesh_signature,
        "analysis_signature": field.analysis_signature,
        "stress_source": field.data_source,
        "provenance_status": field.provenance_status,
        "mesh_volume_mm3": field.mesh_volume,
        "element_count": len(field.element_volumes),
        "element_type_counts": element_type_counts,
        "sample_count": len(field.samples),
        "aggregation": orient.WEIGHTED_CVAR,
        "ranking_tail_fraction": ranking.ranking_tail_fraction,
        "tail_fractions": ranking.tail_fractions,
        "confidence": "not_checked",
        "convergence": {
            "status": "not_checked",
            "reason": "single FEM result",
            "meshes_compared": 1,
        },
        "configured_allowables": None,
        "comparative_warning": COMPARATIVE_WARNING,
        "candidate_set_signature": candidate_digest.hexdigest(),
        "candidate_set_provenance": sorted(
            {candidate.source for candidate in candidate_set}
        ),
        "current_orientation": {
            "build_direction": current_build,
            "metrics": [
                {
                    "channel": value.channel,
                    "tail_fraction": value.tail_fraction,
                    "value_mpa": value.value,
                }
                for value in current_score.channel_scores
            ],
        },
        "candidates": [
            {
                "id": candidate_ids[candidate],
                "build_axis": candidate.build,
                "source": candidate.source,
                "supporting_face_area_mm2": candidate.area,
                "placements": [
                    {
                        "sign": placement.sign,
                        "build_direction": placement.build,
                    }
                    for placement in orient.candidate_placements((candidate,))
                ],
            }
            for candidate in candidate_set
        ],
        "display_order": [candidate_ids[score.candidate] for score in ranking.scores],
        "pareto_front": [
            candidate_ids[score.candidate] for score in ranking.pareto_front
        ],
        "pareto_layers": [
            [candidate_ids[score.candidate] for score in layer]
            for layer in ranking.pareto_layers
        ],
        "scores": [
            {
                "candidate_id": candidate_ids[candidate],
                "metrics": [
                    {
                        "channel": channel_score.channel,
                        "tail_fraction": channel_score.tail_fraction,
                        "value_mpa": channel_score.value,
                        "tail_volume_mm3": channel_score.statistic.tail_volume,
                        "weight_signature": channel_score.statistic.weight_signature,
                        "critical_tail": [
                            _contribution(value)
                            for value in channel_score.statistic.contributions
                        ],
                    }
                    for channel_score in score_by_candidate[candidate].channel_scores
                ],
            }
            for candidate in candidate_set
        ],
        "margins": [
            {
                "candidate_a": candidate_ids[value.candidate_a],
                "candidate_b": candidate_ids[value.candidate_b],
                "channel": value.channel,
                "tail_fraction": value.tail_fraction,
                "signed_gap_mpa": value.signed_gap,
                "absolute_gap_mpa": value.absolute_gap,
                "relative_gap": value.relative_gap,
                "scope": value.scope,
            }
            for value in ranking.margins
        ],
        "tie_diagnostics": [
            {
                "candidate_a": candidate_ids[value.candidate_a],
                "candidate_b": candidate_ids[value.candidate_b],
                "channel": value.channel,
                "tail_fraction": value.tail_fraction,
                "signed_gap_mpa": value.signed_gap,
                "relative_gap": value.relative_gap,
                "critical_region_overlap": value.critical_region_overlap,
                "direct_gap_uncertainty_mpa": value.direct_gap_uncertainty,
                "summed_individual_uncertainty_mpa": (
                    value.summed_individual_uncertainty
                ),
                "tie_band": value.tie_band,
                "same_region_overlap": value.same_region_overlap,
                "outcome": value.outcome,
            }
            for value in ranking.tie_diagnostics
        ],
        "principal_tension_cvar": [
            {
                "tail_fraction": value.tail_fraction,
                "value_mpa": value.value,
            }
            for value in ranking.principal_tension_cvar
        ],
        "orientation_sensitivity": [
            {
                "tail_fraction": value.tail_fraction,
                "numerator_mpa": value.numerator,
                "denominator_mpa": value.denominator,
                "value": value.value,
                "aggregation": value.aggregation,
                "candidate_sources": value.candidate_sources,
            }
            for value in ranking.orientation_sensitivity
        ],
    }
    return Analysis(ranking, current_score, record)

from dataclasses import dataclass
from math import log2
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


OUTCOMES = {"replied", "interested", "meeting_booked", "disqualified"}
TARGETS = {"replied", "interested", "meeting_booked"}


@dataclass(frozen=True)
class LeadRecord:
    id: int
    external_id: str
    company: str
    industry: str
    employees: int
    message_variant: str
    baseline_score: float
    outcome: Optional[str] = None


@dataclass(frozen=True)
class SegmentMetric:
    dimension: str
    segment: str
    observations: int
    successes: int
    rate: float
    smoothed_rate: float
    lift: float
    eligible: bool
    adjustment: int
    recommendation: str


@dataclass(frozen=True)
class AnalysisSummary:
    target: str
    labeled_count: int
    overall_successes: int
    overall_rate: float
    overall_smoothed_rate: float
    metrics: List[SegmentMetric]


@dataclass(frozen=True)
class RankedLead:
    id: int
    external_id: str
    company: str
    industry: str
    employees: int
    employee_band: str
    message_variant: str
    outcome: Optional[str]
    baseline_score: float
    suggested_score: float
    baseline_rank: int
    suggested_rank: int
    rank_delta: int
    drivers: List[str]


def employee_band(employees: int) -> str:
    if employees < 0:
        raise ValueError("employees cannot be negative")
    if employees <= 19:
        return "1–19"
    if employees <= 50:
        return "20–50"
    if employees <= 99:
        return "51–99"
    if employees <= 200:
        return "100–200"
    return "201+"


def is_success(outcome: Optional[str], target: str) -> bool:
    if target not in TARGETS:
        raise ValueError("target must be replied, interested, or meeting_booked")
    if outcome is None:
        return False
    if target == "replied":
        return outcome in {"replied", "interested", "meeting_booked"}
    if target == "interested":
        return outcome in {"interested", "meeting_booked"}
    return outcome == "meeting_booked"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _adjustment(lift: float) -> int:
    if lift <= 0:
        return -15
    return int(_clamp(round(10 * log2(lift)), -15, 15))


def _segment_value(lead: LeadRecord, dimension: str) -> str:
    if dimension == "industry":
        return lead.industry
    if dimension == "employee_band":
        return employee_band(lead.employees)
    return lead.message_variant


def summarize_segments(leads: Iterable[LeadRecord], target: str) -> AnalysisSummary:
    if target not in TARGETS:
        raise ValueError("target must be replied, interested, or meeting_booked")

    materialized = list(leads)
    labeled = [lead for lead in materialized if lead.outcome in OUTCOMES]
    labeled_count = len(labeled)
    overall_successes = sum(is_success(lead.outcome, target) for lead in labeled)
    overall_rate = overall_successes / labeled_count if labeled_count else 0
    overall_smoothed = (overall_successes + 1) / (labeled_count + 2) if labeled_count else 0
    metrics: List[SegmentMetric] = []

    for dimension in ("industry", "employee_band", "message_variant"):
        groups: Dict[str, List[LeadRecord]] = {}
        for lead in labeled:
            groups.setdefault(_segment_value(lead, dimension), []).append(lead)

        for segment in sorted(groups, key=str.casefold):
            group = groups[segment]
            observations = len(group)
            successes = sum(is_success(lead.outcome, target) for lead in group)
            rate = successes / observations
            smoothed_rate = (successes + 1) / (observations + 2)
            lift = smoothed_rate / overall_smoothed if overall_smoothed else 1
            has_outcome_variation = 0 < overall_successes < labeled_count
            eligible = labeled_count >= 30 and observations >= 10 and has_outcome_variation
            adjustment = _adjustment(lift) if eligible and dimension != "message_variant" else 0

            if labeled_count >= 30 and observations >= 10 and not has_outcome_variation:
                recommendation = "Not enough outcome variation yet"
            elif not eligible:
                recommendation = "Not enough evidence yet"
            elif dimension == "message_variant":
                recommendation = f"Observed {lift:.1f}× {target.replace('_', ' ')} rate; review messaging separately"
            elif adjustment > 0:
                recommendation = f"Observed {lift:.1f}× {target.replace('_', ' ')} rate; consider +{adjustment} points"
            elif adjustment < 0:
                recommendation = f"Observed {lift:.1f}× {target.replace('_', ' ')} rate; consider {adjustment} points"
            else:
                recommendation = "Performance is close to the overall rate"

            metrics.append(
                SegmentMetric(
                    dimension=dimension,
                    segment=segment,
                    observations=observations,
                    successes=successes,
                    rate=rate,
                    smoothed_rate=smoothed_rate,
                    lift=lift,
                    eligible=eligible,
                    adjustment=adjustment,
                    recommendation=recommendation,
                )
            )

    return AnalysisSummary(
        target=target,
        labeled_count=labeled_count,
        overall_successes=overall_successes,
        overall_rate=overall_rate,
        overall_smoothed_rate=overall_smoothed,
        metrics=metrics,
    )


def rank_leads(leads: Sequence[LeadRecord], target: str) -> List[RankedLead]:
    summary = summarize_segments(leads, target)
    adjustments: Dict[Tuple[str, str], int] = {
        (metric.dimension, metric.segment): metric.adjustment
        for metric in summary.metrics
        if metric.eligible and metric.dimension != "message_variant"
    }

    baseline_order = sorted(
        leads,
        key=lambda lead: (-lead.baseline_score, lead.company.casefold(), lead.external_id),
    )
    baseline_ranks = {lead.id: index for index, lead in enumerate(baseline_order, start=1)}

    scored = []
    for lead in leads:
        industry_adjustment = adjustments.get(("industry", lead.industry), 0)
        size_adjustment = adjustments.get(("employee_band", employee_band(lead.employees)), 0)
        suggested_score = float(_clamp(lead.baseline_score + industry_adjustment + size_adjustment, 0, 100))
        drivers = []
        if industry_adjustment:
            drivers.append(f"{lead.industry}: {industry_adjustment:+d}")
        if size_adjustment:
            drivers.append(f"{employee_band(lead.employees)} employees: {size_adjustment:+d}")
        scored.append((lead, suggested_score, drivers))

    suggested_order = sorted(
        scored,
        key=lambda item: (-item[1], -item[0].baseline_score, item[0].company.casefold(), item[0].external_id),
    )

    ranked = []
    for suggested_rank, (lead, suggested_score, drivers) in enumerate(suggested_order, start=1):
        baseline_rank = baseline_ranks[lead.id]
        ranked.append(
            RankedLead(
                id=lead.id,
                external_id=lead.external_id,
                company=lead.company,
                industry=lead.industry,
                employees=lead.employees,
                employee_band=employee_band(lead.employees),
                message_variant=lead.message_variant,
                outcome=lead.outcome,
                baseline_score=lead.baseline_score,
                suggested_score=suggested_score,
                baseline_rank=baseline_rank,
                suggested_rank=suggested_rank,
                rank_delta=baseline_rank - suggested_rank,
                drivers=drivers,
            )
        )
    return ranked

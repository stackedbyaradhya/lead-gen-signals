from app.domain import LeadRecord, employee_band, is_success, rank_leads, summarize_segments


def lead(index, *, industry="Software", employees=25, message="A", score=50, outcome="replied"):
    return LeadRecord(
        id=index,
        external_id=f"lead-{index}",
        company=f"Company {index:02}",
        industry=industry,
        employees=employees,
        message_variant=message,
        baseline_score=score,
        outcome=outcome,
    )


def test_employee_bands_include_boundaries():
    assert [employee_band(value) for value in (1, 19, 20, 50, 51, 99, 100, 200, 201)] == [
        "1–19",
        "1–19",
        "20–50",
        "20–50",
        "51–99",
        "51–99",
        "100–200",
        "100–200",
        "201+",
    ]


def test_funnel_objectives_are_hierarchical():
    assert is_success("meeting_booked", "replied") is True
    assert is_success("interested", "replied") is True
    assert is_success("replied", "interested") is False
    assert is_success("meeting_booked", "interested") is True
    assert is_success("interested", "meeting_booked") is False
    assert is_success("disqualified", "replied") is False


def test_segment_summary_uses_smoothing_and_sample_gates():
    leads = [lead(i, industry="Software", outcome="replied" if i < 8 else "disqualified") for i in range(10)]
    leads += [lead(i, industry="Services", outcome="replied" if i < 12 else "disqualified") for i in range(10, 30)]

    summary = summarize_segments(leads, "replied")
    software = next(item for item in summary.metrics if item.dimension == "industry" and item.segment == "Software")

    assert summary.labeled_count == 30
    assert summary.overall_successes == 10
    assert summary.overall_smoothed_rate == 11 / 32
    assert software.observations == 10
    assert software.successes == 8
    assert software.smoothed_rate == 9 / 12
    assert software.eligible is True
    assert software.adjustment == 11


def test_segments_are_ineligible_below_minimum_sample():
    leads = [lead(i, industry="Software" if i < 9 else "Services", outcome="replied") for i in range(30)]
    summary = summarize_segments(leads, "replied")
    software = next(item for item in summary.metrics if item.dimension == "industry" and item.segment == "Software")

    assert software.observations == 9
    assert software.eligible is False
    assert software.adjustment == 0


def test_message_performance_never_changes_ranking_score():
    leads = [lead(i, message="Winner", score=50, outcome="replied") for i in range(15)]
    leads += [lead(i, message="Loser", score=50, outcome="disqualified") for i in range(15, 30)]

    ranking = rank_leads(leads, "replied")

    assert {item.suggested_score for item in ranking} == {50}
    message_metrics = [item for item in summarize_segments(leads, "replied").metrics if item.dimension == "message_variant"]
    assert any(item.eligible and item.adjustment == 0 for item in message_metrics)


def test_ranking_clamps_scores_and_breaks_ties_deterministically():
    leads = [lead(i, industry="High", employees=20, score=99, outcome="replied") for i in range(10)]
    leads += [lead(i, industry="Low", employees=200, score=2, outcome="disqualified") for i in range(10, 20)]
    leads += [lead(i, industry="Neutral", employees=75, score=50, outcome="disqualified") for i in range(20, 30)]

    first = rank_leads(leads, "replied")
    second = rank_leads(list(reversed(leads)), "replied")

    assert [item.external_id for item in first] == [item.external_id for item in second]
    assert max(item.suggested_score for item in first) == 100
    assert min(item.suggested_score for item in first) == 0
    assert first[0].company == "Company 00"
    assert first[0].suggested_rank == 1


def test_no_labeled_leads_produce_no_adjustments():
    leads = [lead(1, outcome=None)]
    summary = summarize_segments(leads, "replied")
    ranking = rank_leads(leads, "replied")

    assert summary.labeled_count == 0
    assert summary.overall_smoothed_rate == 0
    assert ranking[0].suggested_score == ranking[0].baseline_score


def test_zero_success_dataset_does_not_manufacture_adjustments():
    leads = [lead(i, industry="Small sample" if i < 10 else "Large sample", outcome="disqualified") for i in range(30)]

    summary = summarize_segments(leads, "replied")
    ranking = rank_leads(leads, "replied")

    assert summary.overall_successes == 0
    assert all(metric.adjustment == 0 for metric in summary.metrics)
    assert all(item.suggested_score == item.baseline_score for item in ranking)

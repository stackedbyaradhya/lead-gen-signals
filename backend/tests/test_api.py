from sqlalchemy import select

from app.models import OutcomeEvent


HEADER = "external_id,company,industry,employees,message_variant,baseline_score,outcome\n"


def test_health_checks_database(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_import_lists_and_paginates_leads(client, csv_upload):
    response = csv_upload(
        client,
        HEADER
        + "a-1,Acme,Software,25,A,72,replied\n"
        + "b-2,Beta,Services,120,B,48,\n",
    )

    assert response.status_code == 201
    assert response.json() == {
        "filename": "leads.csv",
        "total_rows": 2,
        "created": 2,
        "updated": 0,
    }
    page = client.get("/api/leads?page=1&page_size=1").json()
    assert page["total"] == 2
    assert page["page"] == 1
    assert page["page_size"] == 1
    assert page["items"][0]["external_id"] == "a-1"
    assert page["items"][0]["employee_band"] == "20–50"


def test_import_rejects_missing_columns_without_partial_writes(client, csv_upload):
    response = csv_upload(client, "external_id,company\na-1,Acme\n")

    assert response.status_code == 422
    assert "Missing required columns" in response.json()["detail"]["message"]
    assert client.get("/api/leads").json()["total"] == 0


def test_import_rejects_duplicate_ids_and_invalid_rows(client, csv_upload):
    response = csv_upload(
        client,
        HEADER
        + "dup,Acme,Software,-1,A,101,unknown\n"
        + "dup,Beta,Software,20,A,50,replied\n",
    )

    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("employees" in error for error in errors)
    assert any("baseline_score" in error for error in errors)
    assert any("outcome" in error for error in errors)
    assert any("duplicate external_id" in error for error in errors)
    assert client.get("/api/leads").json()["total"] == 0


def test_import_rejects_non_finite_scores_and_overlong_fields(client, csv_upload):
    response = csv_upload(
        client,
        HEADER + f"a-1,{'A' * 256},Software,20,A,nan,replied\n",
    )

    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("company must be 255 characters or fewer" in error for error in errors)
    assert any("baseline_score must be between 0 and 100" in error for error in errors)
    assert client.get("/api/leads").json()["total"] == 0


def test_import_upserts_existing_lead_and_appends_changed_outcome(client, app, csv_upload):
    csv_upload(client, HEADER + "a-1,Acme,Software,25,A,72,replied\n")
    response = csv_upload(client, HEADER + "a-1,Acme Labs,Software,35,A,78,interested\n")

    assert response.status_code == 201
    assert response.json()["created"] == 0
    assert response.json()["updated"] == 1
    lead = client.get("/api/leads").json()["items"][0]
    assert lead["company"] == "Acme Labs"
    assert lead["outcome"] == "interested"
    with app.state.session_factory() as session:
        events = session.scalars(select(OutcomeEvent).order_by(OutcomeEvent.id)).all()
        assert [event.outcome for event in events] == ["replied", "interested"]


def test_outcome_update_records_history_but_same_value_is_idempotent(client, app, csv_upload):
    csv_upload(client, HEADER + "a-1,Acme,Software,25,A,72,\n")
    lead_id = client.get("/api/leads").json()["items"][0]["id"]

    first = client.patch(f"/api/leads/{lead_id}/outcome", json={"outcome": "meeting_booked"})
    second = client.patch(f"/api/leads/{lead_id}/outcome", json={"outcome": "meeting_booked"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["outcome"] == "meeting_booked"
    with app.state.session_factory() as session:
        assert len(session.scalars(select(OutcomeEvent)).all()) == 1


def test_analytics_and_rankings_expose_supported_recommendations(client, csv_upload):
    rows = []
    for index in range(10):
        rows.append(f"high-{index},High {index},Software,25,Winner,50,replied")
    for index in range(20):
        rows.append(f"low-{index},Low {index},Services,150,Loser,50,disqualified")
    assert csv_upload(client, HEADER + "\n".join(rows) + "\n").status_code == 201

    analytics = client.get("/api/analytics?target=replied")
    rankings = client.get("/api/rankings?target=replied")

    assert analytics.status_code == 200
    body = analytics.json()
    assert body["labeled_count"] == 30
    software = next(item for item in body["metrics"] if item["dimension"] == "industry" and item["segment"] == "Software")
    assert software["eligible"] is True
    assert software["adjustment"] > 0
    assert "Observed" in software["recommendation"]

    assert rankings.status_code == 200
    ranked = rankings.json()["items"]
    assert ranked[0]["company"] == "High 0"
    assert ranked[0]["suggested_score"] > ranked[-1]["suggested_score"]
    assert all("Winner" not in driver for item in ranked for driver in item["drivers"])


def test_invalid_target_and_missing_lead_return_api_errors(client):
    assert client.get("/api/analytics?target=won").status_code == 422
    assert client.patch("/api/leads/999/outcome", json={"outcome": "replied"}).status_code == 404

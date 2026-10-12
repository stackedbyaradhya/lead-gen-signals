from dataclasses import asdict
from math import ceil
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain import LeadRecord, employee_band, rank_leads, summarize_segments
from app.importer import ImportValidationError, parse_csv
from app.models import ImportBatch, Lead, OutcomeEvent
from app.schemas import OutcomeUpdate, Target


router = APIRouter()


def _lead_record(lead: Lead) -> LeadRecord:
    return LeadRecord(
        id=lead.id,
        external_id=lead.external_id,
        company=lead.company,
        industry=lead.industry,
        employees=lead.employees,
        message_variant=lead.message_variant,
        baseline_score=lead.baseline_score,
        outcome=lead.outcome,
    )


def _lead_payload(lead: Lead):
    return {
        "id": lead.id,
        "external_id": lead.external_id,
        "company": lead.company,
        "industry": lead.industry,
        "employees": lead.employees,
        "employee_band": employee_band(lead.employees),
        "message_variant": lead.message_variant,
        "baseline_score": lead.baseline_score,
        "outcome": lead.outcome,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


@router.get("/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/api/imports", status_code=status.HTTP_201_CREATED)
async def import_leads(file: UploadFile = File(...), session: Session = Depends(get_session)):
    try:
        rows = parse_csv(await file.read())
    except ImportValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "errors": exc.errors},
        ) from exc

    external_ids = [row.external_id for row in rows]
    existing = {
        lead.external_id: lead
        for lead in session.scalars(select(Lead).where(Lead.external_id.in_(external_ids))).all()
    }
    batch = ImportBatch(filename=(file.filename or "leads.csv")[:255], total_rows=len(rows), created_count=0, updated_count=0)
    session.add(batch)
    session.flush()

    created = 0
    updated = 0
    for row in rows:
        lead = existing.get(row.external_id)
        if lead is None:
            lead = Lead(
                external_id=row.external_id,
                company=row.company,
                industry=row.industry,
                employees=row.employees,
                message_variant=row.message_variant,
                baseline_score=row.baseline_score,
                outcome=None,
                import_batch_id=batch.id,
            )
            session.add(lead)
            session.flush()
            created += 1
        else:
            updated += 1

        lead.company = row.company
        lead.industry = row.industry
        lead.employees = row.employees
        lead.message_variant = row.message_variant
        lead.baseline_score = row.baseline_score
        lead.import_batch_id = batch.id
        if row.outcome is not None and row.outcome != lead.outcome:
            lead.outcome = row.outcome
            session.add(OutcomeEvent(lead_id=lead.id, outcome=row.outcome))

    batch.created_count = created
    batch.updated_count = updated
    session.commit()
    return {
        "filename": batch.filename,
        "total_rows": len(rows),
        "created": created,
        "updated": updated,
    }


@router.get("/api/leads")
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
):
    total = session.scalar(select(func.count()).select_from(Lead)) or 0
    leads = session.scalars(
        select(Lead).order_by(Lead.company, Lead.external_id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_lead_payload(lead) for lead in leads],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


@router.patch("/api/leads/{lead_id}/outcome")
def update_outcome(lead_id: int, payload: OutcomeUpdate, session: Session = Depends(get_session)):
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if lead.outcome != payload.outcome:
        lead.outcome = payload.outcome
        session.add(OutcomeEvent(lead_id=lead.id, outcome=payload.outcome))
        session.commit()
        session.refresh(lead)
    return _lead_payload(lead)


def _all_records(session: Session) -> List[LeadRecord]:
    return [_lead_record(lead) for lead in session.scalars(select(Lead)).all()]


@router.get("/api/analytics")
def analytics(target: Target = "replied", session: Session = Depends(get_session)):
    return asdict(summarize_segments(_all_records(session), target))


@router.get("/api/rankings")
def rankings(target: Target = "replied", session: Session = Depends(get_session)):
    return {"target": target, "items": [asdict(item) for item in rank_leads(_all_records(session), target)]}

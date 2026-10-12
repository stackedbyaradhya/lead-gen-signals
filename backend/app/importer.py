import csv
import io
from dataclasses import dataclass
from math import isfinite
from typing import List, Optional

from app.domain import OUTCOMES


REQUIRED_COLUMNS = {
    "external_id",
    "company",
    "industry",
    "employees",
    "message_variant",
    "baseline_score",
}
MAX_ROWS = 10_000
MAX_TEXT_LENGTH = 255


class ImportValidationError(ValueError):
    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


@dataclass(frozen=True)
class ParsedLead:
    external_id: str
    company: str
    industry: str
    employees: int
    message_variant: str
    baseline_score: float
    outcome: Optional[str]


def parse_csv(payload: bytes) -> List[ParsedLead]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportValidationError("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ImportValidationError("CSV is empty")

    headers = {header.strip() for header in reader.fieldnames if header}
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        raise ImportValidationError(f"Missing required columns: {', '.join(missing)}")

    parsed: List[ParsedLead] = []
    errors: List[str] = []
    seen = set()
    for row_number, raw in enumerate(reader, start=2):
        if row_number - 1 > MAX_ROWS:
            raise ImportValidationError(f"CSV exceeds the {MAX_ROWS:,}-row limit")
        row = {str(key).strip(): (value or "").strip() for key, value in raw.items() if key is not None}
        if not any(row.values()):
            continue

        external_id = row.get("external_id", "")
        for field in REQUIRED_COLUMNS - {"employees", "baseline_score"}:
            if not row.get(field):
                errors.append(f"Row {row_number}: {field} is required")
            elif len(row[field]) > MAX_TEXT_LENGTH:
                errors.append(f"Row {row_number}: {field} must be {MAX_TEXT_LENGTH} characters or fewer")

        if external_id in seen:
            errors.append(f"Row {row_number}: duplicate external_id '{external_id}'")
        seen.add(external_id)

        try:
            employees = int(row.get("employees", ""))
            if employees < 0:
                raise ValueError
        except ValueError:
            employees = 0
            errors.append(f"Row {row_number}: employees must be a non-negative integer")

        try:
            baseline_score = float(row.get("baseline_score", ""))
            if not isfinite(baseline_score) or baseline_score < 0 or baseline_score > 100:
                raise ValueError
        except ValueError:
            baseline_score = 0
            errors.append(f"Row {row_number}: baseline_score must be between 0 and 100")

        outcome = row.get("outcome", "").lower() or None
        if outcome is not None and outcome not in OUTCOMES:
            errors.append(f"Row {row_number}: outcome must be replied, interested, meeting_booked, or disqualified")
            outcome = None

        parsed.append(
            ParsedLead(
                external_id=external_id,
                company=row.get("company", ""),
                industry=row.get("industry", ""),
                employees=employees,
                message_variant=row.get("message_variant", ""),
                baseline_score=baseline_score,
                outcome=outcome,
            )
        )

    if errors:
        raise ImportValidationError("CSV contains invalid rows", errors)
    if not parsed:
        raise ImportValidationError("CSV contains no lead rows")
    return parsed

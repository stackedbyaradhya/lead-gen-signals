# Signal Loop — Outcome-Calibrated Ranking

Signal Loop is a single-user companion for SaaSquatch lead lists. It learns from recorded outreach outcomes and previews how the original lead ranking should change.

The product does not replace or overwrite the imported score. It adds an evidence-based recommendation layer so a searcher can see which industries and company sizes are producing replies, interest, or meetings.

## Product workflow

1. Import a CSV of leads and, optionally, their existing outcomes.
2. Choose the result to optimize for: replies, interest, or meetings booked.
3. Review conversion performance by industry, company-size band, and message variant.
4. Inspect recommendations generated from segments with enough observations.
5. Compare every lead's original rank with its suggested rank.
6. Update outcomes as outreach progresses; the analysis and ranking refresh automatically.

Recommendations are previews only. `baseline_score` remains unchanged in the database.

## Run the product

The only local requirement is Docker Desktop with Docker Compose.

```bash
docker compose up --build
```

Open:

- Product: [http://localhost:8080](http://localhost:8080)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Backend health: [http://localhost:8000/health](http://localhost:8000/health)

The backend waits for PostgreSQL, applies pending Alembic migrations, and then starts FastAPI. PostgreSQL uses the named `postgres_data` volume, so imported leads and outcome history survive container restarts and `docker compose down`.

To change the default database credentials:

```bash
cp .env.example .env
```

Edit the values in `.env` before starting the stack.

## Test data

Use [`examples/leads.csv`](examples/leads.csv) to demonstrate the complete workflow. It contains 30 labeled leads, which is enough to pass the overall sample guardrail and produce ranking recommendations for qualifying segments.

In the product:

1. Select **Choose CSV file**.
2. Choose `examples/leads.csv`.
3. Select **Import leads**.
4. Change **Optimize ranking for** to compare replies, interest, and meetings.
5. Change an outcome in the **Lead outcomes** table to update the analysis.

## CSV format

Required header:

```text
external_id,company,industry,employees,message_variant,baseline_score
```

An optional `outcome` column can be included:

```text
external_id,company,industry,employees,message_variant,baseline_score,outcome
```

Accepted outcomes are:

- `replied`
- `interested`
- `meeting_booked`
- `disqualified`

Validation rules:

- The file must be UTF-8 CSV.
- A file may contain at most 10,000 lead rows.
- `external_id` must be unique within the file.
- Required text fields must be present and no longer than 255 characters.
- `employees` must be a non-negative integer.
- `baseline_score` must be between 0 and 100.
- Invalid rows reject the complete import and return row-specific errors.

Importing an `external_id` already in the database updates that lead. A changed, non-empty outcome is also appended to the lead's outcome history.

## How outcome analysis works

### Funnel interpretation

Outcomes are interpreted as a funnel:

| Selected objective | Successful outcomes |
| --- | --- |
| Replies | `replied`, `interested`, `meeting_booked` |
| Interested | `interested`, `meeting_booked` |
| Meetings booked | `meeting_booked` |

`disqualified` is labeled data but is not a success for any objective.

### Company-size bands

Employee counts are grouped into:

- `1–19`
- `20–50`
- `51–99`
- `100–200`
- `201+`

### Conversion calculations

For every industry, company-size band, and message variant, the backend calculates:

- labeled observations;
- successful outcomes for the selected objective;
- raw conversion rate;
- smoothed conversion rate;
- lift relative to the overall smoothed rate.

The smoothed conversion rate is:

```text
(successes + 1) / (observations + 2)
```

Smoothing prevents very small segments from appearing unrealistically perfect or hopeless.

### Evidence guardrails

A segment can affect the ranking only when:

- at least 30 leads have labeled outcomes overall;
- the segment has at least 10 labeled observations; and
- the full dataset contains both successes and non-successes for the selected objective.

Without these conditions, the interface reports that more evidence or outcome variation is needed.

### Score adjustments

For an eligible industry or company-size segment:

```text
lift = segment smoothed rate / overall smoothed rate
adjustment = clamp(round(10 × log2(lift)), -15, +15)
```

Each lead's suggested score is:

```text
clamp(baseline score + industry adjustment + size adjustment, 0, 100)
```

Message-variant performance is shown as a messaging insight but never changes a company's ranking. This keeps company fit separate from copy performance.

### Before-versus-after ranking

The ranking table shows:

- original score and rank;
- suggested score and rank;
- upward or downward movement;
- the industry and size adjustments responsible for the change.

Suggested rankings are sorted by suggested score, then baseline score, company name, and external ID. These tie-breakers keep results stable across repeated requests.

## Data and request flow

```text
CSV or outcome edit
        │
        ▼
React dashboard ──HTTP──▶ FastAPI validation and analysis
                              │
                              ▼
                      PostgreSQL persistence
                              │
                              ▼
                  Analytics and ranking preview
                              │
                              ▼
                       React dashboard
```

## Architecture

Docker Compose runs three product services:

| Service | Technology | Responsibility |
| --- | --- | --- |
| `frontend` | React, TypeScript, Vite, Nginx | CSV upload, objective selection, insights, rankings, and outcome editing |
| `backend` | FastAPI, SQLAlchemy, Uvicorn | Validation, imports, outcome history, analytics, and ranking calculations |
| `db` | PostgreSQL 16 | Leads, imports, and outcome-event persistence |

Alembic owns all database schema changes. The backend startup script applies migrations before serving requests.

### Database tables

- `leads`: current company attributes, baseline score, current outcome, and timestamps.
- `outcome_events`: append-only history of outcome changes for each lead.
- `import_batches`: imported filename, status, row counts, and timestamp.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/imports` | Validate and import a CSV file |
| `GET` | `/api/leads?page=1&page_size=50` | Return a paginated lead list |
| `PATCH` | `/api/leads/{id}/outcome` | Record a lead's current outcome and history event |
| `GET` | `/api/analytics?target=replied` | Return grouped conversion metrics and recommendations |
| `GET` | `/api/rankings?target=replied` | Return the before-versus-after ranking preview |
| `GET` | `/health` | Verify the API and database connection |

Valid `target` values are `replied`, `interested`, and `meeting_booked`.

## Verification

Run the backend tests against a dedicated PostgreSQL test container:

```bash
docker compose --profile test run --rm backend-test
```

Run the frontend smoke test:

```bash
docker compose --profile test run --rm frontend-test
```

With the product running, verify the complete HTTP workflow:

```bash
./scripts/smoke.sh
```

The smoke test checks backend health, imports the example CSV, queries persisted leads, and requests a ranking preview.

## Product source layout

```text
backend/                FastAPI service, domain logic, migrations, and tests
frontend/               React application, Nginx configuration, and smoke test
examples/leads.csv      Demonstration dataset
scripts/smoke.sh        End-to-end HTTP verification
docker-compose.yml      Product and test services
.env.example            Optional database configuration
README.md               Product operation and behavior
```

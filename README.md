# Stackerbee Tender Intelligence & Opportunity Management Platform

A production-oriented platform that automatically discovers, collects, processes, analyses,
and manages government procurement/tender opportunities relevant to Stackerbee's business
(software development, IT manpower, cybersecurity, networking, ERP/Frappe, cloud/DevOps,
IoT/Smart City, data engineering/AI-ML, and related technology services).

The platform is **not** a scraper. It is a decision-support system that turns raw tender
publications into structured, evidence-backed intelligence so a human reviewer can decide
**bid or no-bid** with confidence. It never submits bids, accepts terms, or declares final
eligibility on its own — see [`docs/architecture.md`](docs/architecture.md#human-in-the-loop).

## Status

🚧 **Sprint 1 — Foundations.** This repository currently contains the base architecture,
containerised dev environment, authentication foundation, and a placeholder dashboard.
Tender collection, document processing, intelligence extraction, matching, and the
opportunity CRM are implemented incrementally in later sprints — see
[`docs/development-plan.md`](docs/development-plan.md).

## Documentation

| Doc | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System architecture, data flow, module boundaries, principles (fact vs. interpretation, human-in-the-loop) |
| [`docs/database.md`](docs/database.md) | Full target PostgreSQL schema, and what's implemented today vs. planned |
| [`docs/development-plan.md`](docs/development-plan.md) | Sprint-by-sprint build plan and current progress |

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL (+ pgvector), Redis, Celery
- **Frontend:** React, TypeScript, Vite, Material UI
- **Document storage:** S3-compatible (MinIO locally, AWS S3 in production)
- **AI:** Provider-agnostic LLM abstraction (Anthropic / OpenAI-compatible / local, later)
- **Infra:** Docker, Docker Compose, Nginx (Kubernetes-ready later)

## Repository layout

```text
backend/
  app/
    api/            # FastAPI routers (versioned: api/v1)
    core/           # config, security, database session, logging
    models/         # SQLAlchemy ORM models
    schemas/        # Pydantic request/response schemas
    repositories/   # DB access layer (no business logic)
    services/       # Business logic (auth, profile, matching, etc.)
    workers/        # Celery tasks (crawlers, document processing, notifications)
    connectors/      # Source connectors (GeM, CPPP, state portals, ...) - isolated per source
    document_processing/  # PDF/OCR/text extraction pipeline
    intelligence/   # LLM-backed extraction, classification, RAG
    matching/        # Eligibility, relevance scoring, risk analysis
  tests/
  alembic/
frontend/
  src/
    components/ pages/ layouts/ services/ hooks/ types/ utils/
infrastructure/
  docker/ nginx/ scripts/
docs/
```

## Getting started (local development)

### Prerequisites

- Docker and Docker Compose
- (Optional, for non-Docker local dev) Python 3.12+, Node.js 20+

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY, POSTGRES_PASSWORD, and any API keys you have.
# Never commit .env.
```

### 2. Start the stack

```bash
docker compose up --build
```

This brings up:

- `postgres` — PostgreSQL 16 with the `pgvector` extension
- `redis` — cache / Celery broker
- `minio` — S3-compatible document storage (console at http://localhost:9001)
- `backend` — FastAPI app at http://localhost:8000 (docs at `/docs`)
- `frontend` — React app at http://localhost:5173
- `nginx` — reverse proxy at http://localhost:8080 (routes `/api` → backend, `/` → frontend)

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Create the first admin user

```bash
docker compose exec backend python -m app.scripts.create_admin --email you@stackerbee.com --password <strong-password>
```

### 5. Verify

- Backend health: `curl http://localhost:8000/api/v1/health`
- API docs: http://localhost:8000/docs
- Frontend dashboard: http://localhost:5173 (log in with the admin user above)

## Running tests

```bash
# Backend
docker compose exec backend pytest

# Frontend
docker compose exec frontend npm test
```

## Development principles

See [`docs/architecture.md`](docs/architecture.md) for the full rationale. In short:

1. **Modular, not monolithic.** Each concern (API, services, repositories, connectors,
   document processing, intelligence, matching) lives in its own package.
2. **Fact vs. AI interpretation are always kept separate** in the data model and in the UI.
3. **Human-in-the-loop.** The system never autonomously bids, accepts terms, or makes
   final eligibility/financial decisions.
4. **Source access is respected.** No CAPTCHA bypass, auth bypass, or anti-bot
   circumvention. Where automated access isn't permitted, the system falls back to
   official APIs, permitted feeds, or manual/email ingestion.
5. **Everything ships with migrations and tests.**

## License / confidentiality

Internal Stackerbee project. Not yet licensed for external distribution.

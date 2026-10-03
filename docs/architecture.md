# Architecture

## 1. Purpose

The platform answers one question automatically, with evidence:

> "Which newly published government tenders are relevant to Stackerbee, does Stackerbee
> appear eligible, what are the important requirements, what are the risks, and should
> the opportunity be reviewed for bidding?"

It is a **Tender Intelligence + Opportunity Management Platform**, not a scraper. The
distinction matters architecturally: collection is one module among many, and it is the
least differentiated part of the system. The value is in the pipeline that turns a raw
PDF into structured, evidence-linked, human-reviewable intelligence.

## 2. End-to-end data flow

```text
Government Tender Sources (GeM, CPPP/eProcure, State/PSU portals, dept. websites)
        │
        ▼
Source Connectors            (connectors/<source>/: discover → fetch → parse → normalise)
        │
        ▼
Tender Ingestion              (dedup by source-id + fingerprint hash, normalisation)
        │
        ▼
Document Processing           (download → validate → extract text → OCR if scanned → chunk)
        │
        ▼
Tender Intelligence Engine    (classification, requirement/eligibility/risk extraction via LLM+RAG)
        │
        ▼
Stackerbee Capability Profile ◄── maintained by admins (capabilities, tech, certifications, past projects)
        │
        ▼
Matching / Qualification      (eligibility: ELIGIBLE/NOT_ELIGIBLE/UNCERTAIN, relevance score, risk list)
        │
        ▼
Opportunity CRM                (NEW → SCREENING → QUALIFIED → REVIEW → BID/NO-BID → ... → WON/LOST)
        │
        ├──► Dashboard
        └──► Alerts (email first; Teams/Telegram/Slack pluggable later)
```

## 3. Module boundaries

Each box in the data flow above is an isolated package so that no module needs to know
the internals of another:

| Layer | Package | Responsibility | Depends on |
|---|---|---|---|
| API | `app/api/v1/*` | HTTP routing, request/response validation, auth guards | services, schemas |
| Services | `app/services/*` | Business logic (auth, profile, matching, notifications) | repositories, connectors, intelligence |
| Repositories | `app/repositories/*` | DB access only — no business rules | models |
| Models | `app/models/*` | SQLAlchemy ORM definitions | — |
| Schemas | `app/schemas/*` | Pydantic I/O contracts | — |
| Connectors | `app/connectors/<source>/` | One connector per source, behind a common interface | core, document_processing |
| Document processing | `app/document_processing/*` | Extraction, OCR, chunking | core |
| Intelligence | `app/intelligence/*` | LLM-backed classification/extraction, RAG | document_processing, LLM abstraction |
| Matching | `app/matching/*` | Eligibility, relevance scoring, risk analysis (deterministic code + intelligence output) | intelligence, repositories |
| Workers | `app/workers/*` | Celery tasks: scheduled crawls, document processing, notifications | connectors, document_processing, services |

**Rule:** services never import from `api`; repositories never contain business logic;
connectors never call the intelligence or matching layers directly (ingestion and
analysis are decoupled — a crawler failure must never block document processing of
already-ingested tenders, and vice versa).

## 4. Source connector architecture

Every source (GeM, CPPP/eProcure, a state portal, a PSU portal, a department site) is
implemented as an isolated connector conforming to a single interface
(`app/connectors/base/base_connector.py`):

```text
discover()        -> list of tender references (ids/urls) published/updated since last run
fetch_tender(ref)  -> raw tender metadata
fetch_documents(ref) -> raw document files
parse(raw)         -> normalised intermediate representation
normalise(parsed)  -> canonical Tender + TenderDocument rows
```

Cross-cutting behaviour (retries, rate limiting, structured logging, failure handling) is
implemented once in the base connector / a shared `CrawlerRunner`, not duplicated per
source. Each source's `crawler_runs` row records status, counts, and failures so an admin
"Source Health" view can show ✓/⚠ per source.

**Access policy, not a technical afterthought:** before any connector is implemented for a
new source, its terms of use, robots policy, and official API/feed availability must be
documented in the `sources.terms_access_notes` field. The system does not implement
CAPTCHA bypass, authentication bypass, or anti-bot circumvention. Where a source does not
permit automated access, the ingestion method is one of: official API, permitted
feed/export, manual document upload, email ingestion, or a user-provided URL — never a
bypass. **No portal-specific connector ships in Sprint 1** — Sprint 1 only ships the
connector *interface* and base runner, deliberately empty of real sources, so the
abstraction is proven before being filled in (see `docs/development-plan.md`).

## 5. Document processing pipeline

```text
Document → file validation (type/size/checksum) → text extraction (native PDF/DOCX/XLSX)
         → OCR fallback for scanned pages → page segmentation → chunking → metadata record
```

Chunking exists specifically so that **large tender documents are never sent to an LLM
whole** — chunks are retrieved (via embeddings in `tender_embeddings` / pgvector) on
demand by the intelligence layer, each tagged with document id + page range so every
answer can cite its source.

## 6. Tender Intelligence Engine

Responsible for classification, and extraction of: technical requirements, manpower
requirements, financial/eligibility criteria, experience criteria, and MSME/startup
clauses. Every extracted item stores the **exact clause text** plus a
document/page reference. See §8 (Fact vs. Interpretation) for how this is modeled.

### LLM abstraction

`app/intelligence/llm/` defines a provider-agnostic interface
(`complete()`, `embed()`) with adapters for an OpenAI-compatible API, an
Anthropic-compatible API, and (later) local models. The provider is chosen via
`LLM_PROVIDER` in environment config — application code never imports a vendor SDK
directly outside the adapter. LLMs are used only for tasks that are genuinely language
tasks (summarisation, clause interpretation, semantic classification). Deterministic
calculations (e.g., "does extracted turnover ≥ required turnover") are plain Python, not
LLM calls.

### RAG

```text
Tender Documents → Extraction → Chunking → Embeddings → pgvector store → Retriever → LLM → Structured Analysis
```

Any question answered via RAG (e.g., "what is the minimum turnover requirement?") must
cite `{document, page, section}` and must not assert information absent from the
retrieved context. If the retriever finds nothing relevant, the system returns `UNKNOWN`,
not a guess.

## 7. Matching / Qualification

Two distinct, separately-stored outputs per tender:

- **Eligibility** — `ELIGIBLE | NOT_ELIGIBLE | UNCERTAIN`, each with a list of reasons,
  each reason tagged ✓ (supports) or ⚠ (concern), each backed by evidence. Missing
  information is `UNKNOWN`, never silently assumed to pass.
- **Relevance score** — a weighted combination of named, stored factors (technical fit,
  eligibility confidence, experience fit, manpower fit, commercial fit, location fit,
  MSME relevance, deadline urgency). The score is never an opaque LLM output — the
  factor breakdown is what's stored and shown; "why is this relevant?" must be answerable
  from stored rows, not by re-asking the model.

Risk analysis produces a list of `{risk, severity, evidence, document/page, explanation}`
rows, independent of the eligibility/relevance outputs, so risks can be reviewed even for
tenders marked eligible.

## 8. Fact vs. AI interpretation

This is a core product and data-model principle, not just a UI convention. The schema
(see `docs/database.md`) keeps extracted **facts** (a clause, a number, a date, with its
document/page source) in different tables/columns from **interpretations** (an AI
judgement about what a fact implies for Stackerbee). The UI must label each accordingly.
Example:

```text
FACT:            Tender requires ₹10 Cr average annual turnover.  [RFP.pdf, p.27]
INTERPRETATION:   Stackerbee may not satisfy this requirement based on current profile.
```

No code path may store an interpretation in a fact field, or render one without its label.

## 9. Human-in-the-loop

The system never autonomously: submits bids, accepts contractual terms, declares final
eligibility, makes financial commitments, or communicates commitments to a government
department. Its job stops at: evidence, analysis, risks, qualification indicators, and a
recommended review action. The Opportunity CRM workflow always ends at a human-owned
`BID / NO-BID` decision point.

## 10. Opportunity CRM

A relevant tender is promoted to an `opportunity` with its own status machine
(`NEW → SCREENING → QUALIFIED → MANAGEMENT_REVIEW → BID_NO_BID → PROPOSAL_IN_PROGRESS →
SUBMITTED → TECHNICAL_EVALUATION → COMMERCIAL_EVALUATION → WON/LOST`), assignment to a
team/owner, notes, tasks, and a full status-change history for audit purposes.

## 11. Security model (summary — see §20 of the product brief for full requirements)

- JWT-based authentication, RBAC with a `roles`/`users` model from Sprint 1.
- Passwords hashed with bcrypt (via `passlib`), never stored or logged in plaintext.
- Secrets only via environment variables (`.env`, excluded from VCS; `.env.example` is
  the committed template).
- All mutating admin actions and auth events are written to `audit_logs`.
- File uploads are type/size validated before storage; documents are stored in
  object storage (MinIO/S3), never served directly from an unauthenticated path.
- Rate limiting on auth endpoints from Sprint 1; broader API rate limiting as the
  platform grows.

## 12. Deployment

Sprint 1 ships a `docker-compose.yml` with `postgres` (pgvector-enabled image), `redis`,
`minio`, `backend`, `frontend`, and `nginx`. The containers are built so that migrating to
Kubernetes later (separate Deployments/Services per component, externalised Postgres/
Redis/S3) requires no application-code changes — only infra manifests change.

## 13. What Sprint 1 actually contains vs. what this document describes

This document describes the **target** architecture for the whole platform. Sprint 1
(current state of this repo) implements: repo scaffold, Docker environment, FastAPI app
with health/auth/users/dashboard endpoints, `users`/`roles` tables + migrations, RBAC
guard, and a placeholder React dashboard. Connectors, document processing, intelligence,
matching, and the opportunity CRM are **not implemented yet** — their packages exist as
empty, documented placeholders so later sprints slot in without restructuring. See
`docs/development-plan.md` for the sprint-by-sprint breakdown and current status.

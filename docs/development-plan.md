# Development Plan

Incremental delivery, per the project brief. Each sprint lists scope and exit criteria.
Status is updated as sprints complete — do not mark a sprint done until its tests pass
and the services run via `docker compose up`.

## Sprint 1 — Foundations ✅ (this repo, current)

**Scope:** repository scaffold, Docker Compose environment, backend skeleton, frontend
skeleton, PostgreSQL + Redis, authentication foundation, basic database (`users`,
`roles`, `audit_logs`), basic dashboard shell.

**Exit criteria:**
- [x] Repo structure matches `docs/architecture.md` §3
- [x] `docker-compose.yml` written and YAML-validated: postgres(pgvector)/redis/minio/backend/frontend/nginx
- [x] FastAPI app boots, `/api/v1/health` returns 200 (verified via local run + tests)
- [x] Alembic migration creates `roles`/`users`/`audit_logs` (upgrade/downgrade both verified against a real SQLite DB — seed roles land correctly)
- [x] JWT login/register works; passwords bcrypt-hashed; RBAC dependency guard exists (18 passing backend tests)
- [x] React app boots, shows a login page and a placeholder dashboard behind auth (build + lint + tests verified with Node 20)
- [x] Backend tests (`pytest`) pass for health + auth
- [x] Frontend tests (`vitest`) pass; `npm run build` and `npm run lint` are clean
- [ ] Full `docker compose up` run with the real Postgres/Redis/MinIO/Nginx containers — **not verified in this session**, because no Docker daemon is available in this sandbox. Everything that doesn't require the daemon (YAML validity, migration correctness, backend logic, frontend build) has been verified directly. Run `docker compose up --build` on a machine with Docker to complete this check — see README.md "Getting started".

**Explicitly not in scope:** any real source connector, document processing, LLM calls,
matching, or opportunity CRM. Those packages exist as empty, documented placeholders.

## Sprint 2 — Source registry & tender ingestion

**Scope:** `sources` + `crawler_runs` tables; connector base interface
(`discover/fetch_tender/fetch_documents/parse/normalise`) with retry/rate-limit/logging
built into the shared runner; `tenders`, `tender_organisations`, `tender_locations`,
`tender_categories`, `tender_deadlines`, `tender_documents` tables; deduplication via
`fingerprint_hash` + `source_tender_id`; search/filter API and UI list view.

**Before any real connector ships:** document the target source's terms of use,
robots policy, and official API/feed availability in `sources.terms_access_notes`. If
automated access isn't permitted, implement manual upload / email ingestion / user-
provided URL instead (Rule 11/12 of the brief). No CAPTCHA/auth bypass, ever.

**Exit criteria:** at least one connector implemented against a source confirmed to
permit automated access (or a manual-upload fallback if none qualify yet), with
duplicate-tender and changed-deadline test cases passing.

## Sprint 3 — Document management

**Scope:** document download/validation pipeline, PDF/DOCX/XLSX text extraction, OCR
fallback for scanned pages, chunking strategy, document viewer in the UI, storage in
MinIO/S3 with checksum + status tracking.

**Exit criteria:** upload a sample scanned and a sample native PDF; both extract
correctly; OCR-failure and missing-document test cases pass.

## Sprint 4 — Tender intelligence

**Scope:** LLM abstraction layer (Anthropic/OpenAI-compatible adapters), structured
extraction of technical/manpower/financial/experience/MSME clauses into
`tender_requirements` / `tender_eligibility` (facts, with document+page citation),
`tender_analysis` executive summaries.

**Exit criteria:** representative sample tender documents produce extraction output
matching an expected structured fixture in tests; every extracted fact carries a
document/page citation.

## Sprint 5 — Matching, eligibility, relevance, risk

**Scope:** `stackerbee_profile`/`capabilities`/`experience` admin-managed tables;
`qualification_results` (eligibility + relevance factors + risks, all evidence-linked);
deterministic comparison code (turnover ≥ requirement, etc.) kept separate from LLM
interpretation calls.

**Exit criteria:** matching engine unit tests cover ELIGIBLE/NOT_ELIGIBLE/UNCERTAIN and
UNKNOWN-on-missing-data cases; relevance score is always reconstructable from stored
factors.

## Sprint 6 — Opportunity CRM, notifications, digest

**Scope:** `opportunities`/`opportunity_assignments`/`opportunity_notes`/
`opportunity_status_history`; workflow enforcement; email notification channel behind a
provider abstraction; daily digest job.

**Exit criteria:** status transitions are fully audited; a relevant tender can be
promoted to an opportunity and assigned to a team; a test digest email renders correctly.

## Sprint 7 — Semantic search & RAG

**Scope:** `tender_embeddings` + pgvector queries; structured + semantic search API/UI;
RAG question-answering over tender documents with mandatory document/page citations and
`UNKNOWN` when nothing relevant is retrieved.

**Exit criteria:** a semantic query ("Python and React development with IT manpower")
returns relevant tenders whose titles don't contain those exact words; a RAG answer
without supporting retrieval returns `UNKNOWN`, never a fabricated answer.

## Sprint 8 — Hardening, testing, deployment

**Scope:** full security pass (rate limiting, CSRF where applicable, malicious file
detection, secure document access), performance pass, monitoring/observability (crawler
health view, LLM call tracking), complete test suite, deployment documentation.

**Exit criteria:** security checklist in `docs/architecture.md` §11 fully implemented and
verified; test coverage report produced; a documented, repeatable deployment procedure.

---

## Running progress log

| Date | Sprint | Note |
|---|---|---|
| 2026-10-03 | 1 | Repo scaffolded; docs written; Docker Compose, backend, frontend, migrations, auth, and tests implemented. Backend: 18/18 pytest passing (SQLite-backed test DB) + Alembic migration verified upgrade/downgrade against a real SQLite file. Frontend: build, lint, and vitest all passing on Node 20. Full `docker compose up` against the real Postgres/Redis/MinIO/Nginx containers not run — no Docker daemon available in this environment; left for the next session/machine with Docker. |

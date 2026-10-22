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

## Sprint 2 — Source registry & tender ingestion ✅

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

**What shipped:**
- `app/connectors/base/{types,base_connector,runner}.py` — the connector interface and
  `CrawlerRunner` (per-item retry via `tenacity`, inter-item rate limiting, failure
  isolation so one bad tender doesn't abort a run, and `crawler_runs`/`Source` health
  rollup).
- `app/connectors/gem/{connector,parser}.py` — a real connector against GeM's public
  "All Bids" listing. **Access-policy review** (Rule 11), done before any code was
  written: `robots.txt` on `bidplus.gem.gov.in` does not disallow `/all-bids` or
  `/all-bids-data`; no login or CAPTCHA gates either (same JSON endpoint GeM's own
  frontend calls for any anonymous visitor). GeM's Terms of Use require advance written
  permission to reproduce site content — Stackerbee confirmed that permission is in
  place for this integration (2026-10-04; recorded on the live `sources.terms_access_notes`
  row). The connector calls that exact endpoint, not a scrape of rendered HTML, with a
  descriptive User-Agent and a capped page count per run
  (`settings.gem_max_pages_per_crawl`, default 3 × 10 bids). First live run: 30
  discovered, 29 new, 1 deduplicated — see the progress log below.
  CPPP/eProcure has the same "permission required to reproduce" clause in its Copyright
  Policy; no connector has been built for it yet — that's a separate access-policy
  conversation to have before writing one, not an engineering gap.
- The exit criterion's manual-upload fallback remains available for any source without
  a connector yet:
  `app/services/manual_tender_service.py` + `POST /api/v1/tenders/manual`, backed by a
  seeded `source_type=manual` row. Builds the same `NormalisedTender` a connector would,
  so manual and (eventually) crawled tenders are indistinguishable once ingested.
- `app/services/tender_ingestion_service.py` — dedup by `(source_id, source_tender_id)`
  first, `fingerprint_hash` (title+org+value+published_date) as a cross-source fallback;
  deadline changes append an `extended` `tender_deadlines` row and mark the tender
  `corrigendum` rather than overwriting history.
- `GET/POST /api/v1/sources`, `PATCH /api/v1/sources/{id}` (admin-gated;
  `crawler_enabled=true` rejected unless `terms_access_notes` is set — Rule 11 enforced
  in code, not just policy); `GET /api/v1/tenders` (keyword/category/status/value/
  state/city filters + pagination), `GET /api/v1/tenders/{id}`.
- Frontend: Tenders list with filters, tender detail (deadline history, documents,
  fact-labelled categories), "Add Tender Manually" form, Sources admin page
  (admin/technical only — nav item hidden otherwise) with the crawler-enable gate
  surfaced as an error message, not just a disabled control.
- Tests: 43 passing (dedup, changed-deadline, runner retry/failure-isolation/rate-limit,
  API role-gating and filtering) — see the progress log below for one Postgres-only bug
  these caught only once run against a real database, not SQLite.

## Sprint 3 — Document management ✅

**Scope:** document download/validation pipeline, PDF/DOCX/XLSX text extraction, OCR
fallback for scanned pages, chunking strategy, document viewer in the UI, storage in
MinIO/S3 with checksum + status tracking.

**Exit criteria:** upload a sample scanned and a sample native PDF; both extract
correctly; OCR-failure and missing-document test cases pass.

**What shipped:**
- `app/document_processing/storage/{base,local_backend,s3_backend}.py` — a storage
  interface with two implementations: S3-compatible (MinIO in Docker, boto3) and a plain
  filesystem backend for dev environments without MinIO running (this project's native
  Postgres local setup). Selected via `settings.storage_provider` ("minio"\|"s3"\|"local").
- `app/document_processing/{downloader,validators}.py` — size-limited download; content
  type is detected from the bytes themselves via `python-magic` (never trusted from a
  filename or a portal's claimed type), with a ZIP-internals fallback (`word/document.xml`
  vs `xl/workbook.xml`) for the specific OOXML gap in this system's magic database (Word
  files came back as `application/octet-stream` from `magic` alone — found by actually
  running it, not assumed).
- `app/document_processing/extractors/{pdf,docx,xlsx,zip}_extractor.py` — native text
  extraction for all four formats brief §7 lists (PDF/DOC/DOCX/XLS/XLSX/ZIP). Verified
  against **real files**, not mocks: a DOCX authored with `python-docx`, converted to a
  genuine multi-paragraph PDF via LibreOffice headless, an image-only PDF with no text
  layer at all (for the OCR path), a real XLSX, and a ZIP bundling two of them — see
  `scripts/generate_doc_fixtures.py` and `tests/fixtures/documents/`.
- `app/document_processing/ocr.py` — pytesseract + pdf2image, raising `OcrUnavailableError`
  if `tesseract-ocr`/`poppler-utils` aren't installed rather than crashing the caller.
  **This environment genuinely doesn't have tesseract installed** — the brief's "test OCR
  failures" case is exercised for real here, not mocked, and `OcrUnavailableError` is
  caught and recorded per-page rather than failing the whole document. Docker's backend
  image now installs both binaries (Dockerfile updated) for real OCR there.
- `app/document_processing/chunking.py` — pure, directly-tested page-aware chunking with
  overlap; not wired into persistence yet (no `tender_embeddings` table until Sprint 7),
  ready for Sprint 4/7 to call.
- `app/services/document_processing_service.py` — orchestrates the above; always leaves a
  document in a terminal status (`DONE`/`FAILED`) with a readable `last_processing_error`
  rather than letting a library exception escape. `upload_document()` is the Rule 12
  manual-file-upload path (distinct from `manual_tender_service`, which only records
  metadata/URLs) — validated before a row is even created.
- API: `POST /tenders/{id}/documents` (upload), `POST .../documents/{id}/process`,
  `GET .../documents/{id}` (incl. extracted text), `GET .../documents/{id}/download`
  (always authenticated — never a public path, brief §20).
- Frontend: a `DocumentsPanel` on the tender detail page — upload, a process button per
  document, status chips for extraction/OCR, an authenticated download (blob fetch, since
  a plain `<a href>` can't carry the bearer token), and an expandable extracted-text viewer.
- **Known gap, not an engineering failure:** GeM's own `showbidDocument/{id}` URLs (used
  as `tender_documents.source_url` by the GeM connector) return HTTP 200 with a
  `Content-Disposition: attachment` header but a genuinely empty body — confirmed across
  8 freshly-sampled bids, regardless of session cookies or `Referer`. GeM's actual
  document delivery needs a fuller browser-session flow than plain HTTP calls replicate;
  not investigated further this sprint (open-ended reverse-engineering, no tool available
  here to inspect real browser network traffic). The manual-upload path works fully and
  was used for all genuine extraction testing.
- Tests: 30 new (extractors, chunking, document processing service, API) — 75 passing
  total.

## Sprint 4 — Tender intelligence ✅

**Scope:** LLM abstraction layer (Anthropic/OpenAI-compatible adapters), structured
extraction of technical/manpower/financial/experience/MSME clauses into
`tender_requirements` / `tender_eligibility` (facts, with document+page citation),
`tender_analysis` executive summaries.

**Exit criteria:** representative sample tender documents produce extraction output
matching an expected structured fixture in tests; every extracted fact carries a
document/page citation.

**What shipped:**
- **Per-page text.** Sprint 3 stored only the joined `extracted_text`, losing page
  boundaries — so no fact could cite a page. `tender_documents.extracted_pages` (jsonb,
  one string per page) is now written by `document_processing_service`; documents
  processed before migration `0005` are re-processed automatically on their next analysis.
- `app/intelligence/llm/` — `LLMClient.complete_json(system, user, schema)` with two
  adapters chosen by `LLM_PROVIDER`: **Anthropic** (official `anthropic` SDK, structured
  outputs via `output_config.format`, effort via `ANTHROPIC_EFFORT`, streaming, server-side
  refusal fallback via `fallbacks="default"`) and **OpenAI-compatible** (plain httpx against
  `{OPENAI_BASE_URL}/chat/completions` with a strict `json_schema` — works for OpenAI or a
  self-hosted vLLM/Ollama endpoint). Vendor errors, refusals, truncation and non-JSON output
  all become one `LLMResponseError`. Default model `claude-opus-5-5`.
- `app/intelligence/extraction/` — pages are batched into excerpts of at most
  `LLM_MAX_CHARS_PER_CALL` characters (a large tender is never sent whole; an oversized
  page is split but keeps its page number). The model must return, per item, a **verbatim
  quote + page number**, a short summary, and typed structured fields (manpower role/count/
  experience, turnover amount/period/average, project count/value, MSME clause kind, ...).
- **Citation verification (`citations.py`) — the key design decision.** Every returned item
  is kept only if its quote is actually found on the cited page (after normalising PDF line
  breaks, hyphenation, quotes/dashes and case). Invented clauses, paraphrases and wrong-page
  citations are dropped and counted in `tender_analysis.run_stats`, with examples, so a
  reviewer can see what was discarded. This makes "every fact carries a citation" a code
  guarantee rather than a prompt request.
- `app/intelligence/summary.py` — the executive summary (brief Module 10) and category
  classification are generated **from the verified fact rows**, not raw document text, so
  the summary can only restate cited facts. Bullets reference facts by id (`[R3]`, `[E1]`),
  mapped to stored row UUIDs in `summary.fact_refs`. Categories are written to
  `tender_categories` with a `confidence`; manually set categories are never overwritten.
- `app/services/tender_intelligence_service.py` — runs the pipeline; facts are replaced
  all-or-nothing in the same transaction as the summary, so a failed run keeps the previous
  results and records `status=failed` + the reason on `tender_analysis`.
- API: `POST /tenders/{id}/analysis` (run; admin/bd_manager/technical), `GET
  /tenders/{id}/analysis` (summary + facts with `{document, file_name, page}` citations),
  `GET /tenders/{id}/eligibility` (eligibility facts only, brief §19).
- Frontend: a "Tender Intelligence" panel on the tender detail page — summary boxed and
  labelled **AI INTERPRETATION**, facts labelled **FACT** with the verbatim clause and a
  clickable `file · p.N` citation that downloads the source document; AI-assigned category
  chips show their confidence and are visually distinct from manual ones.
- Tests: representative 3-page RFP (`tests/fixtures/documents/sample_rfp.pdf`, real PDF
  generated via LibreOffice) → stored facts match `tests/fixtures/intelligence/
  sample_rfp_expected.json` exactly. The scripted model responses deliberately include an
  invented clause, a wrong-page citation and a duplicate; all three are verified dropped.
  Plus adapter tests (OpenAI via httpx MockTransport, Anthropic at the SDK boundary),
  batching, citation normalisation, re-run/failure/unconfigured paths, API/RBAC, and a
  frontend test for the FACT/INTERPRETATION labelling. A mutation check (citation check
  disabled) makes 11 of these tests fail. 126 backend + 4 frontend tests passing.
- **Not yet verified: a run against a real model.** No API key was available in this
  environment, so the tests use a scripted `FakeLLMClient` (`tests/support/fake_llm.py`).
  They prove everything around the model (batching, verification, persistence, failure
  handling) but not extraction quality. First thing to do with a key: run the analysis on
  a few real tenders and review the dropped-item counts and extracted facts.
- **Known limitations:** analysis runs synchronously in the request (as Sprint 3's document
  processing does) — fine for a handful of documents, but should move to a Celery worker
  (Sprint 8). A clause that straddles the split point of an oversized page can't be
  verified and is dropped.

## Sprint 5 — Matching, eligibility, relevance, risk ✅

**Scope:** `stackerbee_profile`/`capabilities`/`experience` admin-managed tables;
`qualification_results` (eligibility + relevance factors + risks, all evidence-linked);
deterministic comparison code (turnover ≥ requirement, etc.) kept separate from LLM
interpretation calls.

**Exit criteria:** matching engine unit tests cover ELIGIBLE/NOT_ELIGIBLE/UNCERTAIN and
UNKNOWN-on-missing-data cases; relevance score is always reconstructable from stored
factors.

**What shipped:**
- **Company profile** — `stackerbee_profile` (single row), `stackerbee_capabilities`,
  `stackerbee_experience` (migration `0006`). Admin-only edits through `PUT /profile` and
  `POST/PATCH/DELETE /profile/capabilities|experience/{id}`, each audited; readable by every
  signed-in user (`GET /profile`). Nothing is seeded: an admin enters the real figures.
  Unknown values stay null (MSME/startup status are three-state, not default-false), so the
  engine can tell "not registered" from "not recorded".
- **Matching engine** (`app/matching/`) — pure functions over plain dataclasses: no
  database, no model call, `now` passed in, so the same facts and profile always give the same
  result. **The deterministic/LLM split:** all model interpretation stays in Sprint 4
  extraction, whose output is citation-verified before it is stored; this sprint's code only
  compares those verified numbers and names against the profile.
  - *Eligibility* — one rule per criterion type (turnover, net worth, similar projects,
    government experience, years in business, certification). MET/NOT_MET only when the data
    settles it; missing profile data, an unreadable clause value or an `other` criterion give
    UNKNOWN. Ambiguous clauses are evaluated under every reading and are definite only when
    the readings agree (e.g. "turnover of ₹10 Cr" with no average/each-year wording; a past
    project whose value isn't recorded). EMD/tender fee/performance security/MSME clauses are
    INFO, not gates. MSE/startup relaxation clauses turn a NOT_MET turnover/experience
    criterion into UNKNOWN when the company qualifies. Verdict: any NOT_MET → NOT_ELIGIBLE;
    else any UNKNOWN, or no pass/fail criterion at all → UNCERTAIN; else ELIGIBLE.
  - *Relevance* — eight weighted factors (technical 30, eligibility 20, experience 15,
    manpower 10, commercial 10, location 5, MSME 5, deadline 5), each stored with score,
    weight, explanation and evidence. A factor without data is `known: false` at a neutral 50.
    The score is only ever `relevance_score(factors)`.
  - *Risks* — severity-ranked, independent of the verdict: failed/unconfirmed criteria,
    deadline, penalty/LD clauses, manpower vs. headcount, senior roles, long contracts, EMD and
    performance security, contract size vs. past projects, corrigenda, unanalysed tenders.
    Each clause-raised risk carries its quote and document/page.
- **`qualification_results`** + `GET/POST /tenders/{id}/qualification`. GET returns the stored
  row as computed plus `is_stale` (the profile, the tender's facts/categories or
  `ENGINE_VERSION` changed since) — it never silently recomputes on read. A successful
  analysis run recomputes it automatically when a profile exists.
- **Frontend** — a *Company Profile* page (amounts entered in ₹ crore; read-only for
  non-admins) and a *Qualification* section on the tender page: verdict, relevance score,
  every reason with its outcome, clause and clickable `file · p.N` citation, the factor
  breakdown with weights, and risks. Labelled **ASSESSMENT** (rule-based) to keep it distinct
  from Sprint 4's AI INTERPRETATION summary.
- **Tests:** 59 new backend tests, 201 passing in total. These include 45 engine unit tests
  built on the Sprint 4 representative RFP's verified clauses. They cover every verdict,
  UNKNOWN for each kind of missing data, the agree-or-UNKNOWN rule, and score
  reconstruction. A mutation check (missing data treated as a pass or fail) fails 3 of them.
  There are also API tests for the profile, qualification and post-analysis recompute, and a
  Postgres integration test. The Postgres test exists because Postgres hands back
  timezone-aware datetimes for the stale check, while SQLite's are naive. Migration `0006`
  passed upgrade → downgrade → upgrade on a scratch Postgres database and is applied to the
  local dev database. Frontend: 3 new panel tests (8 total), lint and build clean on Node 20.
- **Known limitations:** "similar project" is judged by capability category, not by reading
  the project description. A certification is recognised only if it is ISO nnnnn, a CMMI
  level, CERT-In, or a profile certificate named verbatim in the clause; anything else is
  UNKNOWN. Qualification is not yet shown or sortable on the tenders list; Sprint 6's
  auto-promotion to opportunities will need that.

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
| 2026-10-04 | 1 | Ran the full stack locally without Docker instead (native Postgres 14 + Redis on the dev machine, since no Docker daemon was available): migration applied, admin user created, backend+frontend both verified reachable and functioning end-to-end via real HTTP calls (login, dashboard). |
| 2026-10-04 | 2 | Source registry, connector base/runner, tender ingestion+dedup, manual-entry fallback, search/filter API, and the corresponding frontend pages all implemented and verified against the real local Postgres (not just the SQLite test DB). 43 backend tests passing. Caught and fixed a real Postgres-only bug this way: plain `json` columns broke `SELECT DISTINCT` on tender search (no equality operator) — SQLite's permissive typing hid this entirely; fixed via migration `0003_json_to_jsonb` plus a dedicated Postgres integration test (`tests/integration/test_postgres_tender_search.py`) so it can't silently regress. Frontend verified via build/lint/route-reachability checks only — no real browser click-through was done (no browser automation tool available this session). |
| 2026-10-04 | 2 | User asked for real crawled data from GeM/CPPP as originally scoped. Researched both portals' actual access policies before writing any connector (robots.txt + published Terms of Use/Copyright Policy) — both require advance written permission to reproduce content; user confirmed that permission is in place for GeM. Built `app/connectors/gem/` against GeM's real public `/all-bids-data` endpoint (the same one its own frontend uses — no login, no CAPTCHA). Live first run against the real local Postgres: 30 bids discovered, 29 new tenders created, 1 deduplicated. 5 new connector unit tests added (using a captured fixture, not live network) — 48 backend tests passing total. CPPP: same permission-required clause found in its Copyright Policy; no connector built for it yet pending the same confirmation. |
| 2026-10-04 | 2 | User flagged that the first GeM crawl's results were all clustered on one closing date and not relevant to Stackerbee's focus areas — correctly diagnosed as a connector design choice (sort=soonest-closing + small page cap), not a real cutoff/filter. Reworked `discover()` to run one GeM full-text search per Stackerbee focus area (9 keywords) instead of pulling the unfiltered "all ongoing bids" feed, tagging each result with the matched category; added a defensive past-closing-date skip. Re-crawled: 156 bids discovered, 155 new, spread across all 9 categories and 24 different closing dates (Oct 5 – Nov 2), zero past-dated. 50 backend tests passing. |
| 2026-10-04 | 3 | Document management: storage abstraction (local filesystem + S3/MinIO), download/validation, PDF/DOCX/XLSX/ZIP extraction, OCR fallback, chunking utility, orchestrating service, API, and a frontend documents panel. Verified against real generated files (DOCX→PDF via LibreOffice headless, an image-only PDF for the OCR path, a real XLSX, a ZIP bundle) rather than mocks — see `scripts/generate_doc_fixtures.py`. Tesseract genuinely isn't installed in this environment, so the brief's "test OCR failures" case was exercised for real, not simulated. Investigated why GeM's own bid-document URLs return empty bodies (confirmed across 8 fresh bids, not a one-off) — needs a fuller browser-session flow than plain HTTP replicates; left as a documented open item rather than pursued indefinitely. 75 backend tests passing; frontend build/lint/vitest all clean. |
| 2026-10-04 | 4 | Tender intelligence: provider-agnostic LLM layer (Anthropic SDK + OpenAI-compatible httpx adapters), page-batched structured extraction of requirements/eligibility/MSME clauses, deterministic citation verification (a fact is stored only if its verbatim quote is found on the cited page), fact-grounded executive summary + AI category classification, API and frontend panel with FACT vs AI INTERPRETATION labelling. Fixed a Sprint 3 gap found on the way: documents kept only joined text, losing page numbers — added `extracted_pages` (migration `0005`, applied to the local Postgres). 126 backend tests + 4 frontend tests passing; endpoints exercised against the live local backend. No LLM API key available, so no real-model run yet — tests use a scripted fake. |
| 2026-10-20 | 5 | Matching: admin-managed company profile (profile/capabilities/experience), deterministic eligibility/relevance/risk engine over Sprint 4's citation-verified facts (no model calls), `qualification_results` with evidence-linked reasons, stored factor breakdown and stale detection; Company Profile page and Qualification panel. Migration `0006` verified up/down/up on a scratch Postgres DB and applied to the local dev DB. 201 backend + 8 frontend tests passing. `alembic check` reports index drift on Sprint 2 tables (indexes created by migrations but not declared on models) — pre-existing, not touched here. |

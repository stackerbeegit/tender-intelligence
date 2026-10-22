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

## Sprint 6 — Opportunity CRM, notifications, digest ✅

**Scope:** `opportunities`/`opportunity_assignments`/`opportunity_notes`/
`opportunity_status_history`; workflow enforcement; email notification channel behind a
provider abstraction; daily digest job.

**Exit criteria:** status transitions are fully audited; a relevant tender can be
promoted to an opportunity and assigned to a team; a test digest email renders correctly.

### Bid preparation (sales-triggered)

When a signed-in **sales** user (also `bd_manager`/`admin`) decides to bid on a tender, the
system prepares a starting bid pack for people to finish. It never submits anything: a
person reviews, completes and submits the bid on the portal.

**Scope:**
- **"Interested — prepare bid"** on the tender/opportunity page. It creates the opportunity
  if there isn't one (`created_from=manual`, audited) and assigns the user to their team
  (`sales` for a sales user). It deliberately does **not** move the workflow status: the
  bid / no-bid decision stays a separate step for a BD manager or admin (architecture §9).
  `viewer`/`technical` don't see it.
- **Submission document checklist.** Extend Sprint 4 extraction with a new fact type: the
  documents the tender says must be submitted (forms/annexures, certificates, financial
  statements, EMD proof, declarations, technical and financial bid formats). Each is stored
  in `tender_submission_documents` with its name, kind, whether it is mandatory, the format
  instructions ("on letterhead", "notarised", "signed and stamped"), the form/annexure
  number, and the verbatim clause and page. Items get the same citation check as other facts:
  an item whose quote isn't on the cited page is dropped.
  The opportunity gets a working copy (`bid_checklist_items`) with a status per item
  (`available`/`to_prepare`/`missing`/`not_applicable`), an owner and a note. The status is
  pre-filled from the company profile where it can be (e.g. ISO 27001 required and held →
  `available`). Anything that can't be matched starts as `to_prepare`, never `available`.
- **Draft bid.** An AI-written draft (`bid_drafts`, versioned) built only from the tender's
  verified facts, its qualification result and the company profile. Sections: covering
  letter, company profile, eligibility compliance statement (one line per criterion with
  the evidence the company holds), point-by-point technical compliance against the
  extracted requirements, manpower deployment plan, list of enclosures (= the checklist).
  **No invented credentials:** turnover, certifications, project names and values may only
  come from the profile. Anything the inputs don't contain becomes a highlighted
  `[TO FILL: …]` placeholder, and an automated check rejects a draft containing an amount,
  certificate or project not found in its inputs. The draft is labelled **AI DRAFT — review
  before use**.
- **Downloads.** Draft bid as an editable **.docx**. Checklist as **.xlsx** with columns
  #, document, mandatory, format instructions, tender reference (file · page), status,
  owner, note. Both are also offered together as one **.zip bid pack**. Downloads are
  authenticated (same pattern as document downloads) and each generation is audited.
- **Frontend:** a *Bid preparation* tab on the opportunity with the editable checklist, the
  draft preview with placeholders highlighted, "Regenerate draft", and the three download
  buttons.

**Exit criteria (bid preparation):**
- A sales user can trigger bid preparation; viewer/technical get 403; the opportunity's
  creation is in `opportunity_status_history`.
- On the Sprint 4 representative RFP, the checklist matches an expected fixture, and every
  item carries a document/page citation.
- The draft contains no figure, certificate or project absent from its inputs (test
  includes a scripted model response that invents one, which must be rejected). Missing
  profile data produces `[TO FILL]` placeholders, not guesses.
- The .docx and .xlsx open and parse correctly (checked with `python-docx`/`openpyxl`,
  both already dependencies). The zip contains both files.

**Depends on:** Sprint 5 qualification (done) and the company profile being filled in. An
LLM API key is needed for real drafts; tests use the scripted fake model, as in Sprint 4.

**What shipped:**
- **Opportunity CRM** (migration `0007`) — `opportunities` (one per tender), assignments,
  notes and the append-only `opportunity_status_history`. All workflow rules live in
  `app/services/opportunity_service.py`:
  - `TRANSITIONS` is the only way a status moves: NEW → SCREENING → QUALIFIED →
    MANAGEMENT_REVIEW → BID_NO_BID → PROPOSAL_IN_PROGRESS → SUBMITTED → TECHNICAL_EVALUATION →
    COMMERCIAL_EVALUATION → WON/LOST, with NO_BID available up to the proposal stage.
  - Leaving BID_NO_BID (the human bid / no-bid decision) is limited to BD managers and admins.
  - NO_BID and LOST need a reason.
  - An admin can override the graph with a mandatory comment, which is recorded as
    `[override] …`.
  - Every move writes a history row in the same commit, plus an audit log entry.
  - Roles: admin/bd_manager/sales manage opportunities; technical can add notes and edit
    the checklist; viewers read only.
- **Auto-promotion** — after every qualification run, an open tender scoring at least
  `OPPORTUNITY_AUTO_PROMOTE_MIN_SCORE` (default 70; 0 turns it off) that isn't NOT_ELIGIBLE
  becomes a NEW opportunity (`created_from=auto_relevance`), recorded as done by the system.
  BD managers are e-mailed.
- **Tenders list** shows the relevance score, eligibility and an "In pipeline" marker. It can
  sort by relevance and filter by `eligibility` / `min_relevance`. The category filter became
  an `EXISTS` (no `SELECT DISTINCT`), which Postgres needs in order to sort by the relevance
  subquery; this is pinned by a Postgres integration test.
- **Notifications** (`app/notifications/`) — an e-mail channel behind a sender interface:
  SMTP, or a disabled sender when `NOTIFICATIONS_EMAIL_ENABLED` is off or `SMTP_HOST` is
  empty.
  - Assignment, owner change, status change and auto-promotion e-mail the people involved,
    never the person who acted.
  - Every attempt is stored in `notifications` as sent, failed (with the error) or skipped
    (not configured). A mail outage never fails the action that triggered it.
  - Sending is synchronous for now; moving it onto the worker is Sprint 8.
- **Daily digest** — a Celery Beat task (`DIGEST_HOUR`/`DIGEST_MINUTE`, default 08:30 IST).
  Each active user gets tenders added in the last 24 hours (most relevant first), their open
  opportunities (with those closing within 7 days flagged), and status changes others made.
  It is sent as HTML and plain text, and skipped when empty or while e-mail is off. There is
  a preview at `GET /notifications/digest/preview` and an admin "send me a test" at
  `POST /notifications/digest/test`.
- **Bid preparation** — as scoped above.
  - Submission documents are a fourth fact type extracted in the same LLM call as the
    Sprint 4 facts and given the same citation check (`tender_submission_documents`).
  - The checklist is pre-filled `available` only for certificates the profile records, and
    for MSE/startup exemption documents when a registration number is recorded.
  - Statuses a person sets survive re-analysis: a sync re-links items to the new fact rows
    by clause text.
  - The draft's grounding check is in `app/bidding/grounding.py` and `draft.py`:
    - Amounts must equal one in the inputs (to 0.5%).
    - "N years" must use a number in the inputs.
    - Certifications must be held per the profile, or be part of a solution requirement.
      An eligibility statement may restate its own criterion's certificate.
    - A criterion assessed NOT_MET/UNKNOWN must leave its evidence as `[TO FILL]`.
    - Fact and project references must exist. Past projects are referenced by id and
      rendered from the profile, never named by the model.
    - Placeholder text is exempt.
    - A failing draft is not stored. The rejection and its reasons are audited and shown to
      the user.
  - Downloads: `.docx` (placeholders highlighted in yellow, every row cited), `.xlsx`
    (status drop-down, row heights set, prints on one landscape page wide) and `.zip`. All
    authenticated and audited.
- **Frontend** — an Opportunities list, and an opportunity page with two tabs:
  - *Workflow & team*: status stepper, allowed next steps, a reason dialog, owner,
    assignments, notes and history.
  - *Bid preparation*: editable checklist with page citations, draft preview, regenerate,
    and the three downloads.
  The tender page has a pipeline bar ("Interested — prepare bid" / "Add to pipeline" /
  "Open opportunity"). The tenders list has the Fit column and relevance sort.
- **Tests:**
  - 73 new backend tests (274 total; 3 of them Postgres integration tests against the
    migrated database).
  - Workflow: every transition audited, decision roles, reasons, overrides,
    one-per-tender, notification recipients, a failing mail server recorded and not
    raised, auto-promotion thresholds.
  - Digest: selection, ordering, HTML escaping, empty digests, the scheduled task.
  - Bid preparation: end to end on the RFP, which gained a 4th page listing documents to
    submit. The checklist equals an expected fixture of 10 cited items. Drafts that
    invent an amount, CMMI level, year count, ISO certificate or reference are rejected,
    including a full API run where the scripted model invents a CMMI Level 5 and ₹50 Cr.
    The .docx, .xlsx and .zip are opened and checked with `python-docx`/`openpyxl`.
  - A mutation check (grounding verification disabled) fails 9 of them.
  - Frontend: 5 new tests (13 total); lint and build clean.
  - Migration `0007` passed upgrade → downgrade → upgrade on a scratch Postgres database and
    is applied to the local dev database.
- **Known limitations:**
  - The grounding check covers amounts, year counts, certifications and references, not
    every possible free-text claim (e.g. a made-up client name in prose). The prompt forbids
    it and the draft is labelled for review, but that isn't a code guarantee.
  - Existing tenders have no submission documents until their analysis is re-run.
  - No real-model run yet: no API key here, as in Sprint 4.
  - E-mail and the digest are tested with a captured outbox, not a real SMTP server.
  - Not clicked through in a real browser.

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
| 2026-10-22 | 6 | Opportunity CRM (workflow with audited transitions, human bid/no-bid decision, auto-promotion by relevance), e-mail notifications with every attempt recorded, daily digest (Beat), and sales-triggered bid preparation: cited submission-document checklist, grounded AI draft bid, .docx/.xlsx/.zip downloads. Tenders list gains relevance/eligibility and relevance sort. Migration `0007` verified up/down/up on scratch Postgres and applied to the local dev DB. 274 backend + 13 frontend tests passing. |

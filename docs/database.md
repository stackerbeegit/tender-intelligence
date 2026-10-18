# Database Design

PostgreSQL is the system of record. `pgvector` is used for embeddings. This document
describes the **full target schema**; the "Implemented in Sprint 1" column shows what
exists today. Tables are added incrementally, sprint by sprint (see
`docs/development-plan.md`) — this is deliberate, not an oversight.

Conventions used throughout:

- Every table has `id` (UUID, PK), `created_at`, `updated_at` (timestamptz).
- Soft deletes via `deleted_at` where records must be auditable rather than purged.
- Foreign keys are `ON DELETE RESTRICT` by default unless noted; append-only history
  tables (`*_status_history`, `audit_logs`) are `ON DELETE CASCADE` from their parent.
- **Fact tables** (extracted clause + source reference) are structurally separate from
  **interpretation tables** (AI judgement about what a fact means for Stackerbee) — see
  `docs/architecture.md` §8. This is enforced at the schema level, not just convention.

## 1. Identity & access

| Table | Status | Key columns | Notes |
|---|---|---|---|
| `roles` | ✅ Sprint 1 | `id`, `name` (unique), `description`, `permissions` (jsonb) | Seed roles: `admin`, `bd_manager`, `sales`, `technical`, `viewer` |
| `users` | ✅ Sprint 1 | `id`, `email` (unique), `hashed_password`, `full_name`, `role_id` FK→roles, `is_active`, `last_login_at` | bcrypt hashes only; never log plaintext |
| `audit_logs` | ✅ Sprint 1 | `id`, `user_id` FK→users (nullable), `action`, `entity_type`, `entity_id`, `metadata` (jsonb), `ip_address`, `created_at` | Append-only; written for auth events and mutating admin actions |
| `notifications` | 🔜 Sprint 6 | `id`, `user_id` FK, `channel`, `type`, `payload` (jsonb), `read_at`, `sent_at` | Channel abstraction: email first |

## 2. Source management ✅ Sprint 2

| Table | Key columns | Notes |
|---|---|---|
| `sources` | `id`, `name`, `organisation`, `url`, `source_type` (`gem`\|`cppp`\|`state`\|`psu`\|`department`\|`manual`\|`other`), `country`, `state`, `auth_required` (bool), `api_available` (bool), `crawler_enabled` (bool), `frequency` (cron-like), `last_successful_crawl_at`, `last_failure_at`, `status` (`healthy`\|`degraded`\|`down`\|`disabled`), `terms_access_notes` (text) | `terms_access_notes` must be filled in **before** `crawler_enabled` may be set true — enforced in `app/services/source_service.py`. `source_type=manual` is seeded out of the box (migration 0002) for the Rule 12 fallback; it never has a crawler. |
| `crawler_runs` | `id`, `source_id` FK, `started_at`, `finished_at`, `status` (`running`\|`success`\|`partial`\|`failed`), `tenders_discovered`, `tenders_new`, `tenders_updated`, `error_summary` (text) | Written by `app/connectors/base/runner.py::CrawlerRunner`; powers the admin "Source Health" view |

## 3. Tenders ✅ Sprint 2

| Table | Key columns | Notes |
|---|---|---|
| `tenders` | `id`, `source_id` FK, `source_tender_id` (the portal's own ref no.), `fingerprint_hash` (unique, computed from normalised title+org+value+**published_date only**), `tender_number`, `title`, `organisation_id` FK→tender_organisations, `url`, `published_date`, `closing_date`, `tender_value`, `emd_amount`, `tender_fee`, `status` (`open`\|`closed`\|`cancelled`\|`corrigendum`), `raw_metadata` (**jsonb**) | `(source_id, source_tender_id)` is checked first, `fingerprint_hash` is the cross-source fallback — see `app/services/tender_ingestion_service.py`. Deliberately excludes `closing_date` from the fingerprint since that's the one field corrigenda change; see `tender_deadlines` below. |
| `tender_organisations` | `id`, `name`, `normalized_name` (unique, lowercased — the get-or-create key), `type` (`central_govt`\|`state_govt`\|`psu`\|`private`\|`other`), `state`, `city` | Normalises buyer identity for organisation-wise analytics later |
| `tender_locations` | `id`, `tender_id` FK, `state`, `city`, `pincode` | A tender may span multiple delivery locations |
| `tender_categories` | `id`, `tender_id` FK, `category` (enum: the 9 focus areas + other), `confidence` | `confidence` is null for directly-set categories (manual entry today); only the Sprint 4 intelligence engine populates it, keeping fact vs. interpretation visible on the row itself |
| `tender_deadlines` | `id`, `tender_id` FK, `deadline_type` (`bid_submission`\|`pre_bid_meeting`\|`clarification`\|`extended`), `deadline_at`, `source_document_id` FK nullable | A corrigendum **adds** an `extended` row and updates `tenders.closing_date` + sets `tenders.status=corrigendum` — the original row is never overwritten, so the full history survives (tested: `test_changed_closing_date_adds_extended_deadline_and_marks_corrigendum`) |
| `tender_documents` | `id`, `tender_id` FK, `file_name`, `document_type` (`nit`\|`rfp`\|`boq`\|`annexure`\|`corrigendum`\|`other`), `source_url`, `storage_path`, `checksum_sha256`, `file_size_bytes`, `ocr_status` (`not_required`\|`pending`\|`done`\|`failed`), `extraction_status` (`pending`\|`done`\|`failed`), `page_count`, `extracted_text` ✅ Sprint 3, `extracted_pages` (jsonb, one string per page) ✅ Sprint 4, `last_processing_error` ✅ Sprint 3 | `source_url` is populated at ingestion time (connector or manual entry), or `storage_path` directly for a manual file upload. `extracted_text`/`last_processing_error` added in migration `0004`; populated by `app/services/document_processing_service.py`. |

**A note on `json` vs `jsonb`:** every JSON column (`roles.permissions`, `audit_logs.details`, `tenders.raw_metadata`) uses `jsonb`, not plain `json` — enforced via `app/models/base.py::sa_json()`. Plain Postgres `json` has no equality operator, which silently breaks any query needing `SELECT DISTINCT` on a row containing that column (exactly what tender keyword search does). This was caught only when testing against a real Postgres database, not the SQLite-backed unit test suite — see `tests/integration/test_postgres_tender_search.py` for the regression test, and migration `0003_json_to_jsonb` for the fix applied to already-migrated databases.

## 4. Document intelligence — facts ✅ Sprint 4

| Table | Key columns | Notes |
|---|---|---|
| `tender_requirements` | `id`, `tender_id` FK, `document_id` FK, `category` (`technology`\|`infrastructure`\|`integration`\|`support`\|`sla`\|`security`\|`certification`\|`manpower`\|`contract`\|`other`), `summary`, `requirement_text` (verbatim clause), `details` (jsonb — e.g. manpower `{"role", "resource_count", "min_experience_years"}`), `page_number` (1-indexed), `generated_by_model` | **Fact** table. A row is only inserted after `app/intelligence/extraction/citations.py` confirms `requirement_text` occurs on `page_number` of `document_id` |
| `tender_eligibility` | `id`, `tender_id` FK, `document_id` FK, `criterion_type` (`turnover`\|`net_worth`\|`emd`\|`tender_fee`\|`performance_security`\|`similar_projects`\|`years_of_experience`\|`government_experience`\|`certification`\|`msme_startup`\|`other`), `summary`, `criterion_text` (verbatim clause), `extracted_value` (jsonb — e.g. `{"amount_inr": 100000000, "period_years": 3, "is_average": true}`, or `{"msme_clause_kind": "emd_exemption"}`), `page_number`, `generated_by_model` | **Fact** table — what the tender requires; no Stackerbee-relative judgement lives here. Same citation guarantee |
| `tender_analysis` | `id`, `tender_id` FK (unique), `status` (`running`\|`done`\|`failed`), `summary` (jsonb: project, overview, duration, bullet sections, categories, `fact_refs`), `run_stats` (jsonb: per-document pages/calls/kept/dropped counts, tokens), `documents_analysed`, `generated_by_model`, `started_at`, `finished_at`, `error` | One row per tender, latest run. `summary` is **interpretation**, generated only from the verified fact rows; its bullets cite facts by id (`[R1]`, `[E2]`) mapped via `fact_refs` to row UUIDs |
| `tender_embeddings` | `id`, `document_id` FK, `chunk_index`, `chunk_text`, `embedding` (`vector(1536)`, pgvector), `page_range` | 🔜 Sprint 7 — powers RAG retrieval; `EMBEDDING_DIMENSIONS` env-configurable |

A re-run replaces a tender's fact rows and AI-assigned `tender_categories` rows
(`confidence` not null) in one transaction with the new summary; manual categories
(`confidence` null) are never touched. A failed run rolls back and leaves the previous
facts in place.

## 5. Stackerbee profile (Sprint 5)

| Table | Key columns | Notes |
|---|---|---|
| `stackerbee_profile` | `id` (single row), `company_name`, `msme_status` (bool + certificate ref), `startup_status` (bool + certificate ref), `turnover_by_year` (jsonb), `years_in_business`, `employee_count`, `locations` (jsonb array) | Admin-editable, not hardcoded |
| `stackerbee_capabilities` | `id`, `capability` (enum: the 10+ focus areas), `technologies` (jsonb array), `certifications` (jsonb array) | |
| `stackerbee_experience` | `id`, `project_name`, `customer_type` (`government`\|`psu`\|`private`), `industry`, `technology` (jsonb array), `project_value`, `year`, `description`, `related_capability_id` FK | Feeds the "similar project" eligibility check |

## 6. Matching — facts vs. interpretation (Sprint 5)

| Table | Key columns | Notes |
|---|---|---|
| `qualification_results` | `id`, `tender_id` FK, `eligibility_status` (`ELIGIBLE`\|`NOT_ELIGIBLE`\|`UNCERTAIN`), `reasons` (jsonb array of `{text, polarity: support\|concern, evidence_ref}`), `relevance_score`, `relevance_factors` (jsonb: technical/eligibility/experience/manpower/commercial/location/msme/urgency, each 0–100 with evidence refs), `risks` (jsonb array of `{risk, severity, evidence, document_id, page}`), `computed_at` | **Interpretation** table — explicitly separate from `tender_eligibility` facts above; `relevance_score` is always reconstructable from `relevance_factors`, never stored as a bare number alone |

## 7. Opportunity CRM (Sprint 6)

| Table | Key columns | Notes |
|---|---|---|
| `opportunities` | `id`, `tender_id` FK (unique), `status` (the CRM workflow enum), `owner_id` FK→users, `created_from` (`auto_relevance`\|`manual`) | |
| `opportunity_assignments` | `id`, `opportunity_id` FK, `user_id` FK, `team` (`sales`\|`bd`\|`technical`\|`cybersecurity`\|`management`\|`proposal`), `assigned_at` | |
| `opportunity_notes` | `id`, `opportunity_id` FK, `author_id` FK, `note_text`, `created_at` | |
| `opportunity_status_history` | `id`, `opportunity_id` FK, `from_status`, `to_status`, `changed_by` FK→users, `changed_at`, `comment` | Append-only, drives the audit trail required by §14/§27 of the brief |

## 8. Entity relationship summary

```text
sources 1──* tenders *──1 tender_organisations
tenders 1──* tender_documents 1──* tender_embeddings
tenders 1──* tender_requirements
tenders 1──* tender_eligibility          (FACT)
tenders 1──* tender_deadlines
tenders 1──* tender_locations
tenders 1──* tender_categories
tenders 1──1 tender_analysis
tenders 1──1 qualification_results        (INTERPRETATION, references tender_eligibility via evidence_ref)
tenders 1──1 opportunities 1──* opportunity_assignments
                             1──* opportunity_notes
                             1──* opportunity_status_history
stackerbee_profile 1──* stackerbee_capabilities
stackerbee_profile 1──* stackerbee_experience
users *──1 roles
users 1──* audit_logs
```

## 9. Migrations

Alembic manages all schema changes (`backend/alembic/`). Each sprint's new tables ship as
their own migration — never hand-edited directly in a shared environment. So far:

- `0001_initial_roles_and_users` (Sprint 1) — `roles`, `users`, `audit_logs`
- `0002_sources_and_tenders` (Sprint 2) — `sources`, `crawler_runs`, `tender_organisations`,
  `tenders`, `tender_documents`, `tender_deadlines`, `tender_locations`, `tender_categories`;
  seeds the `manual` source
- `0003_json_to_jsonb` (Sprint 2 bugfix) — converts `roles.permissions`, `audit_logs.details`,
  `tenders.raw_metadata` from `json` to `jsonb` (plain `json` has no equality operator, which
  broke `SELECT DISTINCT` on tender search under real Postgres — not caught by the SQLite test
  suite). `0001`/`0002` now create these columns as `jsonb` directly for fresh installs; `0003`
  repairs databases that already ran the original versions, and is a safe no-op if run twice.
- `0004_document_extraction_fields` (Sprint 3) — adds `tender_documents.extracted_text` and
  `tender_documents.last_processing_error`.
- `0005_tender_intelligence` (Sprint 4) — adds `tender_documents.extracted_pages`; creates
  `tender_requirements`, `tender_eligibility`, `tender_analysis`.

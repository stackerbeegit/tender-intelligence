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

## 2. Source management (Sprint 2)

| Table | Key columns | Notes |
|---|---|---|
| `sources` | `id`, `name`, `organisation`, `url`, `source_type` (`gem`\|`cppp`\|`state`\|`psu`\|`department`\|`other`), `country`, `state`, `auth_required` (bool), `api_available` (bool), `crawler_enabled` (bool), `frequency` (cron-like), `last_successful_crawl_at`, `last_failure_at`, `status` (`healthy`\|`degraded`\|`down`\|`disabled`), `terms_access_notes` (text) | `terms_access_notes` must be filled in **before** `crawler_enabled` may be set true (enforced in service layer, not just convention) |
| `crawler_runs` | `id`, `source_id` FK, `started_at`, `finished_at`, `status` (`success`\|`partial`\|`failed`), `tenders_discovered`, `tenders_new`, `tenders_updated`, `error_summary` (text) | Powers the admin "Source Health" view |

## 3. Tenders (Sprint 2)

| Table | Key columns | Notes |
|---|---|---|
| `tenders` | `id`, `source_id` FK, `source_tender_id` (the portal's own ref no.), `fingerprint_hash` (unique, computed from normalised title+org+value+dates), `tender_number`, `title`, `organisation_id` FK→tender_organisations, `url`, `published_date`, `closing_date`, `tender_value`, `emd_amount`, `tender_fee`, `status` (`open`\|`closed`\|`cancelled`\|`corrigendum`), `raw_metadata` (jsonb) | `fingerprint_hash` + `source_tender_id` drive deduplication across sources and re-publications |
| `tender_organisations` | `id`, `name`, `type` (`central_govt`\|`state_govt`\|`psu`\|`other`), `state`, `city` | Normalises buyer identity for organisation-wise analytics later |
| `tender_locations` | `id`, `tender_id` FK, `state`, `city`, `pincode` | A tender may span multiple delivery locations |
| `tender_categories` | `id`, `tender_id` FK, `category` (enum: the 10 focus areas + other), `confidence` | AI-assigned; `confidence` keeps this honestly an interpretation, not a fact |
| `tender_deadlines` | `id`, `tender_id` FK, `deadline_type` (`bid_submission`\|`pre_bid_meeting`\|`clarification`\|`extended`), `deadline_at`, `source_document_id` FK nullable | Supports corrigenda that move deadlines without losing history |
| `tender_documents` | `id`, `tender_id` FK, `file_name`, `document_type` (`nit`\|`rfp`\|`boq`\|`annexure`\|`corrigendum`\|`other`), `storage_path`, `checksum_sha256`, `file_size_bytes`, `ocr_status` (`not_required`\|`pending`\|`done`\|`failed`), `extraction_status` (`pending`\|`done`\|`failed`), `page_count` | `storage_path` points into S3/MinIO, never served unauthenticated |

## 4. Document intelligence — facts (Sprint 3–4)

| Table | Key columns | Notes |
|---|---|---|
| `tender_requirements` | `id`, `tender_id` FK, `category` (`technical`\|`manpower`\|`sla`\|`security`\|`integration`), `requirement_text`, `document_id` FK, `page_number` | Verbatim extracted requirement + citation |
| `tender_eligibility` | `id`, `tender_id` FK, `criterion_type` (`turnover`\|`net_worth`\|`emd`\|`tender_fee`\|`experience`\|`certification`\|`msme`\|`other`), `criterion_text` (verbatim clause), `extracted_value` (jsonb — e.g. `{"amount": 100000000, "period_years": 3}`), `document_id` FK, `page_number` | This is the **fact** table — no Stackerbee-relative judgement lives here |
| `tender_embeddings` | `id`, `document_id` FK, `chunk_index`, `chunk_text`, `embedding` (`vector(1536)`, pgvector), `page_range` | Powers RAG retrieval; `EMBEDDING_DIMENSIONS` env-configurable |

## 5. Stackerbee profile (Sprint 5)

| Table | Key columns | Notes |
|---|---|---|
| `stackerbee_profile` | `id` (single row), `company_name`, `msme_status` (bool + certificate ref), `startup_status` (bool + certificate ref), `turnover_by_year` (jsonb), `years_in_business`, `employee_count`, `locations` (jsonb array) | Admin-editable, not hardcoded |
| `stackerbee_capabilities` | `id`, `capability` (enum: the 10+ focus areas), `technologies` (jsonb array), `certifications` (jsonb array) | |
| `stackerbee_experience` | `id`, `project_name`, `customer_type` (`government`\|`psu`\|`private`), `industry`, `technology` (jsonb array), `project_value`, `year`, `description`, `related_capability_id` FK | Feeds the "similar project" eligibility check |

## 6. Matching — facts vs. interpretation (Sprint 5)

| Table | Key columns | Notes |
|---|---|---|
| `tender_analysis` | `id`, `tender_id` FK, `summary_text`, `generated_by_model`, `generated_at` | The executive summary; always labelled AI-generated in the UI |
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
their own migration — never hand-edited directly in a shared environment. Sprint 1 ships
migration `0001_initial_roles_and_users` only.

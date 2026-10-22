# Matching

Sprint 5's deterministic qualification engine: verified tender facts
(`tender_eligibility`, `tender_requirements` from Sprint 4) + the
admin-managed company profile → eligibility verdict, relevance factors and
risks, stored on `qualification_results`. See `docs/architecture.md` §7.

| Module | Role |
|---|---|
| `types.py` | Plain dataclass inputs/outputs — no ORM, so rules are unit-tested with hand-built data |
| `eligibility.py` | One check per criterion type → MET / NOT_MET / UNKNOWN / INFO, then the overall ELIGIBLE / NOT_ELIGIBLE / UNCERTAIN verdict |
| `relevance.py` | Eight weighted 0–100 factors; the score is always `relevance_score(factors)` |
| `risk.py` | Severity-ranked risks, each with its clause evidence where one raised it |
| `engine.py` | `qualify(tender, profile, now)` — the single entry point |

Rules:

- **No model calls here.** All LLM interpretation happens upstream in
  Sprint 4 extraction, whose output is citation-verified before it is
  stored. This package only compares numbers and names.
- **Missing data is UNKNOWN**, never a pass or a fail. An ambiguous clause
  is evaluated under each reading; a definite outcome needs them to agree.
- **ELIGIBLE** needs at least one pass/fail criterion checked and all of them
  MET. Payment and MSME clauses are INFO, not gates.
- Bump `ENGINE_VERSION` in `engine.py` when a rule changes.

The database side (loading rows, persisting results, staleness) lives in
`app/services/qualification_service.py`.

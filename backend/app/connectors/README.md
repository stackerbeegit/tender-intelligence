# Connectors

`base/` contains the connector interface (`discover/fetch_tender/fetch_documents/
parse/normalise`, in `base_connector.py`) and `CrawlerRunner` (`runner.py`) — retry,
rate limiting, failure isolation, and `crawler_runs`/`Source` health rollup. `registry.py`
maps a `SourceType` to its connector class, used by `POST /api/v1/sources/{id}/crawl`
and (later) a Celery scheduled task.

Before any portal-specific connector is added, that source's terms of use / robots
policy / official API availability must be documented in the `sources.terms_access_notes`
column — see `docs/architecture.md` §4 and Rules 11/12 in the project brief.

## `gem/` — implemented

Calls GeM's real public `/all-bids-data` endpoint (`bidplus.gem.gov.in`) — the same
JSON call GeM's own "All Bids" page makes for any anonymous visitor; no login, no
CAPTCHA. Access-policy review: `robots.txt` doesn't disallow this path; GeM's Terms of
Use require advance written permission to reproduce site content, which Stackerbee has
confirmed is in place for this integration (recorded on the live `sources` row's
`terms_access_notes`, and in `docs/development-plan.md`'s Sprint 2 progress log).
`gem/parser.py` unwraps GeM's Solr-style list-wrapped response fields.

**State / location:** the listing payload has no location, so the connector fetches each
bid's PDF (one GET per bid, inside the runner's rate limit; toggle with
`GEM_EXTRACT_CONSIGNEE_LOCATIONS`) and `gem/location.py` reads the consignee table —
pincode for civil bids, masked-address city for defence bids — mapping it to a state via
`gem/locations.json`. Buyer state comes from state-government department names
("… Department Gujarat"). BOQ bids and RA bids (empty PDF) get no delivery location.
Rebuild `locations.json` from GeM's own state/city lists with
`python scripts/build_gem_locations.py`.

## No other portal-specific connector is implemented yet

CPPP/eProcure's Copyright Policy has the same "permission required to reproduce"
clause as GeM's — no connector exists for it until that permission question is
resolved the same way. State/PSU portals haven't been reviewed at all yet.

Until a source has a connector, the tender collection path is the Rule 12 manual-upload
fallback: `app/services/manual_tender_service.py` + `POST /api/v1/tenders/manual`, which
builds the same `NormalisedTender` a connector would and shares the same ingestion/dedup
logic (`app/services/tender_ingestion_service.py`).

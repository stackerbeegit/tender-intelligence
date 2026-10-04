"""
GeM's `/all-bids-data` endpoint returns a Solr-style response: every field
on a doc is wrapped in a single-element list (`{"b_bid_number": ["GEM/..."]}`)
except a handful that aren't present at all when empty. These helpers
unwrap that shape into plain scalars so `connector.py` never has to deal
with `doc["field"][0]` directly.
"""
from datetime import datetime, timezone


def unwrap(doc: dict, field: str, default=None):
    value = doc.get(field)
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def parse_gem_datetime(value: str | None) -> datetime | None:
    """GeM returns Solr-style UTC timestamps like '2026-10-05T09:00:00Z'."""
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def organisation_name(doc: dict) -> str | None:
    """Prefer the department name (more specific); fall back to the
    ministry name when a department isn't set (seen on some state-level
    buyer accounts in the live data)."""
    return unwrap(doc, "ba_official_details_deptName") or unwrap(doc, "ba_official_details_minName")


def unwrap_doc(doc: dict) -> dict:
    """Flatten every list-wrapped field on a single bid doc."""
    return {key: unwrap(doc, key) for key in doc}

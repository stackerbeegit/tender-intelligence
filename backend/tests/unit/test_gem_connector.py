"""
Uses a captured real response (tests/fixtures/gem_all_bids_sample.json) so
the default test run never hits GeM's servers — fast, deterministic, and
doesn't add load to a real government portal just for CI. The live round
trip is covered separately by the opt-in test in tests/integration/
test_gem_live_crawl.py.
"""
import json
from pathlib import Path

import pytest

from app.connectors.base.types import DiscoveredTenderRef
from app.connectors.gem import parser
from app.connectors.gem.connector import GemConnector
from app.models.enums import OrganisationType, SourceStatus, SourceType, TenderCategory, TenderStatus
from app.models.source import Source

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "gem_all_bids_sample.json"


@pytest.fixture()
def sample_docs() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text())
    return data["response"]["response"]["docs"]


@pytest.fixture()
def connector() -> GemConnector:
    source = Source(name="GeM", source_type=SourceType.GEM, status=SourceStatus.HEALTHY)
    return GemConnector(source)


def _run_pipeline(connector: GemConnector, raw_doc: dict, category: TenderCategory | None):
    ref = DiscoveredTenderRef(
        source_tender_id=parser.unwrap(raw_doc, "b_bid_number"),
        url="https://bidplus.gem.gov.in/showbidDocument/123",
        hint={"raw_doc": raw_doc, "category": category},
    )
    raw_tender = connector.fetch_tender(ref)
    raw_documents = connector.fetch_documents(ref, raw_tender)
    parsed = connector.parse(raw_tender, raw_documents)
    return connector.normalise(parsed)


def test_unwrap_flattens_single_element_lists():
    assert parser.unwrap({"x": ["value"]}, "x") == "value"
    assert parser.unwrap({"x": []}, "x", default="fallback") == "fallback"
    assert parser.unwrap({}, "missing", default="fallback") == "fallback"


def test_parse_gem_datetime():
    dt = parser.parse_gem_datetime("2026-10-05T09:00:00Z")
    assert dt.year == 2026 and dt.month == 10 and dt.day == 5
    assert dt.tzinfo is not None
    assert parser.parse_gem_datetime(None) is None


def test_organisation_name_prefers_department_falls_back_to_ministry(sample_docs):
    # doc 0 has both dept + min name -> dept wins
    assert parser.organisation_name(sample_docs[0]) == "Department of Military Affairs"
    # doc 1 only has deptName (no minName at all in the live payload)
    assert parser.organisation_name(sample_docs[1]) == "Skill Development and Technical Education Department. Odisha"


def test_connector_normalises_fixture_docs_correctly(connector, sample_docs):
    for raw_doc in sample_docs:
        normalised = _run_pipeline(connector, raw_doc, TenderCategory.CYBERSECURITY)

        assert normalised.source_tender_id.startswith("GEM/")
        assert normalised.title
        assert normalised.organisation_type == OrganisationType.CENTRAL_GOVT
        assert normalised.status == TenderStatus.OPEN
        assert normalised.closing_date is not None
        assert len(normalised.documents) == 1
        assert normalised.documents[0].file_name == f"{normalised.source_tender_id}.pdf"


def test_normalise_tags_the_matched_focus_area_category(connector, sample_docs):
    normalised = _run_pipeline(connector, sample_docs[0], TenderCategory.CLOUD_DEVOPS)
    assert normalised.categories == (TenderCategory.CLOUD_DEVOPS,)


def test_normalise_leaves_categories_empty_when_no_keyword_match_is_carried(connector, sample_docs):
    normalised = _run_pipeline(connector, sample_docs[0], None)
    assert normalised.categories == ()


def test_fetch_tender_returns_hint_without_network_call(connector, sample_docs):
    ref = DiscoveredTenderRef(
        source_tender_id="x", url="https://x", hint={"raw_doc": sample_docs[0], "category": TenderCategory.IT_MANPOWER}
    )
    raw_tender = connector.fetch_tender(ref)
    assert raw_tender["doc"] is sample_docs[0]
    assert raw_tender["category"] == TenderCategory.IT_MANPOWER

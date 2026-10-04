"""
Connector for GeM's public "All Bids" listing (bidplus.gem.gov.in).

Access-policy review (recorded here and on the `sources.terms_access_notes`
row for the live source, per Rule 11):
  - `robots.txt` on bidplus.gem.gov.in does not disallow this path.
  - No login or CAPTCHA gates this page or its data endpoint — it's the
    same JSON call GeM's own frontend makes for any anonymous visitor.
  - GeM's Terms of Use require advance written permission to reproduce
    site content; Stackerbee has confirmed that permission is in place
    for this integration.

This connector calls the exact endpoint (`/all-bids-data`) GeM's own
public page uses — not a private/hidden API, and not a parse of rendered
HTML — with a descriptive User-Agent.

`discover()` deliberately does **not** pull the unfiltered "all ongoing
bids" feed sorted by closing date (that was tried first and just returns
whichever ~30 bids happen to close soonest, almost all on the same date —
not representative of anything). Instead it runs GeM's own full-text
search once per Stackerbee focus area keyword (`FOCUS_AREA_KEYWORDS`
below), which is what actually targets "bids of interest" regardless of
closing date. Bids already past their closing time are skipped even
though GeM's own `bidStatusType=ongoing_bids` filter should already
exclude them — a defensive second check, not a trust assumption.
"""
import json
import re
import time
from datetime import datetime, timezone
from typing import Callable

import httpx

from app.connectors.base.base_connector import BaseConnector
from app.connectors.base.types import DiscoveredTenderRef, NormalisedDocument, NormalisedTender
from app.connectors.gem import parser
from app.connectors.registry import register
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import DocumentType, OrganisationType, SourceType, TenderCategory, TenderStatus

logger = get_logger(__name__)

_CSRF_PATTERN = re.compile(r"csrf_bd_gem_nk'\s*:\s*'([a-f0-9]+)'")

# One GeM full-text search per Stackerbee focus area (project brief §1 / 10
# focus areas). Each tuple is (search text sent as param.searchBid, the
# TenderCategory a match is tagged with). A bid matching more than one
# keyword is tagged with whichever keyword found it first — a documented
# simplification; proper multi-label classification is Sprint 4's job.
FOCUS_AREA_KEYWORDS: tuple[tuple[str, TenderCategory], ...] = (
    ("software development", TenderCategory.SOFTWARE_DEVELOPMENT),
    ("IT manpower", TenderCategory.IT_MANPOWER),
    ("cyber security", TenderCategory.CYBERSECURITY),
    ("networking", TenderCategory.NETWORKING_INFRASTRUCTURE),
    ("ERP software", TenderCategory.ERP_FRAPPE),
    ("cloud services", TenderCategory.CLOUD_DEVOPS),
    ("IoT", TenderCategory.IOT_SMART_CITY),
    ("web application development", TenderCategory.WEB_MOBILE_DEVELOPMENT),
    ("data analytics", TenderCategory.DATA_AI_ML),
)


class GemAccessError(RuntimeError):
    """Raised when GeM's page shape changes in a way we can't parse
    (e.g. the CSRF token can no longer be found) — surfaced as a normal
    discover() failure so CrawlerRunner marks the run FAILED rather than
    silently returning no tenders."""


@register(SourceType.GEM)
class GemConnector(BaseConnector):
    def __init__(self, source, sleep_fn: Callable[[float], None] = time.sleep):
        super().__init__(source)
        settings = get_settings()
        self._settings = settings
        self._sleep = sleep_fn
        self._client = httpx.Client(
            base_url=settings.gem_bidplus_base_url,
            headers={"User-Agent": settings.crawler_user_agent},
            timeout=settings.gem_request_timeout_seconds,
            follow_redirects=True,
        )

    def _get_csrf_token(self) -> str:
        response = self._client.get("/all-bids")
        response.raise_for_status()
        match = _CSRF_PATTERN.search(response.text)
        if not match:
            raise GemAccessError("Could not find the CSRF token on GeM's /all-bids page — page shape may have changed")
        return match.group(1)

    def _fetch_page(self, csrf_token: str, page: int, search_text: str) -> list[dict]:
        payload = {
            "page": page,
            "param": {"searchBid": search_text, "searchType": "fullText"},
            "filter": {
                "bidStatusType": "ongoing_bids",
                "byType": "all",
                "highBidValue": "",
                "byEndDate": {"from": "", "to": ""},
                "sort": "Bid-Start-Date-Latest",
            },
        }
        response = self._client.post(
            "/all-bids-data",
            data={"payload": json.dumps(payload), "csrf_bd_gem_nk": csrf_token},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 200:
            raise GemAccessError(f"GeM returned an unexpected response: {body.get('message')}")
        return body["response"]["response"]["docs"]

    def discover(self) -> list[DiscoveredTenderRef]:
        csrf_token = self._get_csrf_token()
        refs: list[DiscoveredTenderRef] = []
        seen_bid_numbers: set[str] = set()
        now = datetime.now(timezone.utc)
        is_first_request = True

        for search_text, category in FOCUS_AREA_KEYWORDS:
            for page in range(1, self._settings.gem_pages_per_keyword + 1):
                if not is_first_request:
                    self._sleep(self._settings.crawler_default_rate_limit_seconds)
                is_first_request = False

                docs = self._fetch_page(csrf_token, page, search_text)
                if not docs:
                    break

                for doc in docs:
                    flat = parser.unwrap_doc(doc)
                    bid_number = flat.get("b_bid_number")
                    if not bid_number or bid_number in seen_bid_numbers:
                        continue

                    closing_dt = parser.parse_gem_datetime(flat.get("final_end_date_sort"))
                    if closing_dt is not None and closing_dt < now:
                        continue  # defensive: skip anything already past its closing time

                    seen_bid_numbers.add(bid_number)
                    url = f"{self._settings.gem_bidplus_base_url}/showbidDocument/{flat.get('b_id')}"
                    refs.append(
                        DiscoveredTenderRef(
                            source_tender_id=bid_number, url=url, hint={"raw_doc": doc, "category": category}
                        )
                    )

        logger.info(
            "GeM discover(): found %d bids of interest across %d focus-area keyword searches",
            len(refs),
            len(FOCUS_AREA_KEYWORDS),
        )
        return refs

    def fetch_tender(self, ref: DiscoveredTenderRef) -> dict:
        # Already fetched in bulk during discover() — no extra request per
        # item, which both avoids unnecessary load on GeM's servers and
        # sidesteps needing a second CSRF-bearing request per tender.
        return {"doc": ref.hint["raw_doc"], "category": ref.hint.get("category")}

    def fetch_documents(self, ref: DiscoveredTenderRef, raw_tender: dict) -> list[dict]:
        bid_number = parser.unwrap(raw_tender["doc"], "b_bid_number", "unknown")
        return [{"file_name": f"{bid_number}.pdf", "source_url": ref.url, "document_type": DocumentType.NIT.value}]

    def parse(self, raw_tender: dict, raw_documents: list[dict]) -> dict:
        return {"bid": parser.unwrap_doc(raw_tender["doc"]), "category": raw_tender.get("category"), "documents": raw_documents}

    def normalise(self, parsed: dict) -> NormalisedTender:
        bid = parsed["bid"]
        category = parsed.get("category")
        return NormalisedTender(
            source_tender_id=bid.get("b_bid_number"),
            tender_number=bid.get("b_bid_number"),
            title=bid.get("b_category_name") or f"GeM Bid {bid.get('b_bid_number')}",
            organisation_name=parser.organisation_name(bid),
            organisation_type=OrganisationType.CENTRAL_GOVT,
            url=f"{self._settings.gem_bidplus_base_url}/showbidDocument/{bid.get('b_id')}",
            published_date=(
                d.date() if (d := parser.parse_gem_datetime(bid.get("final_start_date_sort"))) else None
            ),
            closing_date=parser.parse_gem_datetime(bid.get("final_end_date_sort")),
            status=TenderStatus.OPEN,
            categories=(category,) if category else (),
            # GeM's listing payload doesn't carry a delivery location — left empty
            # rather than guessed; Sprint 3 document extraction may recover it.
            documents=tuple(
                NormalisedDocument(
                    file_name=d["file_name"],
                    document_type=DocumentType(d["document_type"]),
                    source_url=d["source_url"],
                )
                for d in parsed["documents"]
            ),
            raw_metadata={"gem_bid_id": bid.get("b_id"), "gem_category_id": bid.get("b_cat_id")},
        )

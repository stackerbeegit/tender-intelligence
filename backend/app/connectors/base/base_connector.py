"""
The interface every source connector implements. `CrawlerRunner` drives
these five steps for each discovered reference; it never knows anything
about a specific portal's HTML/API shape — that's entirely inside the
connector subclass.

No connector in this codebase bypasses CAPTCHAs, authentication, or anti-
bot controls. A connector for a new source is only added once that
source's terms of use, robots policy, and official API/feed availability
are documented on its `sources.terms_access_notes` row (Rule 11). Where
automated access isn't permitted, the ingestion path is the manual-entry
fallback (`app/services/manual_tender_service.py`), not a connector.
"""
from abc import ABC, abstractmethod

from app.connectors.base.types import DiscoveredTenderRef, NormalisedTender
from app.models.source import Source


class BaseConnector(ABC):
    def __init__(self, source: Source):
        self.source = source

    @abstractmethod
    def discover(self) -> list[DiscoveredTenderRef]:
        """Return references to tenders published/updated since the last run."""

    @abstractmethod
    def fetch_tender(self, ref: DiscoveredTenderRef) -> dict:
        """Fetch raw tender metadata for one reference."""

    @abstractmethod
    def fetch_documents(self, ref: DiscoveredTenderRef, raw_tender: dict) -> list[dict]:
        """Fetch raw document references (not necessarily bytes) for one tender."""

    @abstractmethod
    def parse(self, raw_tender: dict, raw_documents: list[dict]) -> dict:
        """Parse raw portal-specific payloads into an intermediate dict."""

    @abstractmethod
    def normalise(self, parsed: dict) -> NormalisedTender:
        """Convert the parsed intermediate dict into the canonical NormalisedTender."""

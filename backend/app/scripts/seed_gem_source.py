"""
One-off CLI to create the GeM source on a fresh database, with crawling
enabled and its access-policy review recorded (Rule 11). Safe to re-run:
an existing GeM source is left as it is.

Usage:
    python -m app.scripts.seed_gem_source
"""
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import SourceStatus, SourceType
from app.models.source import Source

GEM_TERMS_ACCESS_NOTES = (
    "robots.txt on bidplus.gem.gov.in does not disallow /all-bids or /all-bids-data. No login/CAPTCHA "
    "gates this page or its data endpoint for anonymous visitors. GeM Terms of Use require advance "
    "written permission to reproduce site content; Stackerbee has confirmed permission is in place for "
    "this integration (2026-10-04). Connector calls the same JSON endpoint (/all-bids-data) GeM own "
    "frontend uses, with a descriptive User-Agent and a capped page count per crawl run."
)


def main() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(Source).where(Source.source_type == SourceType.GEM))
        if existing:
            print(f"GeM source already exists: {existing.name} (crawler_enabled={existing.crawler_enabled})")
            return
        source = Source(
            name="GeM - Government e-Marketplace",
            organisation="Government e-Marketplace SPV",
            url="https://bidplus.gem.gov.in/all-bids",
            source_type=SourceType.GEM,
            country="India",
            crawler_enabled=True,
            status=SourceStatus.HEALTHY,
            terms_access_notes=GEM_TERMS_ACCESS_NOTES,
        )
        db.add(source)
        db.commit()
        print(f"Created GeM source (id={source.id}) with crawling enabled")


if __name__ == "__main__":
    main()

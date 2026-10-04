"""
Maps a `SourceType` to its connector class, so a Celery task (or an admin
"run crawl now" action) can look up the right connector by the source's
configured type without a long if/elif chain. Empty until a real
automated connector is added — manual entry doesn't go through here, it
has its own ingestion path (see app/services/manual_tender_service.py).
"""
from app.connectors.base.base_connector import BaseConnector
from app.models.enums import SourceType

_REGISTRY: dict[SourceType, type[BaseConnector]] = {}


def register(source_type: SourceType):
    def _decorator(cls: type[BaseConnector]) -> type[BaseConnector]:
        _REGISTRY[source_type] = cls
        return cls

    return _decorator


def get_connector_class(source_type: SourceType) -> type[BaseConnector] | None:
    return _REGISTRY.get(source_type)

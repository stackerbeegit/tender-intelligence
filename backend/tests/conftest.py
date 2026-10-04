"""
Test fixtures. Uses an in-memory SQLite database rather than requiring a
running Postgres container — fast, hermetic unit/API tests. Integration
tests that genuinely need Postgres-only features (pgvector, etc.) will live
under tests/integration/ and are skipped unless DATABASE_URL points at a
real Postgres (added from Sprint 7 onward).
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.document_processing.storage.local_backend import LocalFilesystemStorageBackend
from app.main import app
from app.models import Base, Role, Source, Tender
from app.models.enums import SourceStatus, SourceType, TenderStatus

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture()
def db_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine) -> Session:
    TestingSessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False, future=True)
    session = TestingSessionLocal()

    # Seed the roles a fresh deployment gets from alembic migration 0001.
    seed_roles = [
        Role(name="admin", description="Full administrative access", permissions=["*"]),
        Role(name="bd_manager", description="Business development manager", permissions=[]),
        Role(name="sales", description="Sales team", permissions=[]),
        Role(name="technical", description="Technical review team", permissions=[]),
        Role(name="viewer", description="Read-only access", permissions=[]),
    ]
    session.add_all(seed_roles)

    # Seed the 'manual' source a fresh deployment gets from migration 0002
    # (the Rule 12 manual-upload fallback ingestion path depends on it).
    session.add(
        Source(
            name="Manual Entry",
            source_type=SourceType.MANUAL,
            status=SourceStatus.DISABLED,
            terms_access_notes="Not a crawled source — staff-entered tenders only.",
        )
    )
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_source(db_session: Session) -> Source:
    """A generic non-manual source, standing in for a hypothetical
    automated connector's source row in ingestion/runner tests."""
    source = Source(
        name="Sample Test Portal",
        source_type=SourceType.OTHER,
        status=SourceStatus.DISABLED,
        terms_access_notes="Test fixture only — not a real portal.",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture()
def sample_tender(db_session: Session, sample_source: Source) -> Tender:
    tender = Tender(
        source_id=sample_source.id,
        fingerprint_hash=f"test-fingerprint-{uuid.uuid4()}",
        title="Sample tender for document processing tests",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()
    db_session.refresh(tender)
    return tender


@pytest.fixture()
def storage_backend(tmp_path, monkeypatch) -> LocalFilesystemStorageBackend:
    """Points document processing at a throwaway tmp_path rather than the
    real cached `get_storage_backend()` singleton — otherwise tests would
    write into this project's actual storage/documents directory."""
    backend = LocalFilesystemStorageBackend(str(tmp_path))
    monkeypatch.setattr("app.services.document_processing_service.get_storage_backend", lambda: backend)
    monkeypatch.setattr("app.api.v1.documents.get_storage_backend", lambda: backend)
    return backend


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

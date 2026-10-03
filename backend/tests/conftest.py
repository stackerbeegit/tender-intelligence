"""
Test fixtures. Uses an in-memory SQLite database rather than requiring a
running Postgres container — fast, hermetic unit/API tests. Integration
tests that genuinely need Postgres-only features (pgvector, etc.) will live
under tests/integration/ and are skipped unless DATABASE_URL points at a
real Postgres (added from Sprint 7 onward).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base, Role

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
    session.commit()

    try:
        yield session
    finally:
        session.close()


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

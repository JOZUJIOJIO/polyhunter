import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.db.models import Base
from backend.main import create_app
from backend.api.deps import get_db


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def test_app(db_session):
    """FastAPI test client with in-memory DB."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    yield client, db_session

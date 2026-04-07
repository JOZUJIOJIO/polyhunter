from sqlalchemy.orm import Session
from backend.db.database import get_session_factory


def get_db():
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

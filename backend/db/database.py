from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings

_engine = None
_SessionLocal = None


def get_engine(settings: Settings | None = None):
    global _engine
    if _engine is None:
        if settings is None:
            settings = Settings()
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session_factory(settings: Settings | None = None):
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(settings)
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


def init_db(settings: Settings | None = None):
    from backend.db.models import Base

    engine = get_engine(settings)
    Base.metadata.create_all(engine)

"""FastAPI dependency injection."""

from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, get_session_factory, init_db

_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        from .config import DATABASE_URL
        _engine = create_engine(DATABASE_URL)
        init_db(_engine)
    return _engine


def get_db() -> Session:
    engine = get_engine()
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = get_session_factory(engine)
    session = _SessionFactory()
    try:
        yield session
    finally:
        session.close()

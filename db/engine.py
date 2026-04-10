"""Database engine and session management."""

import logging
from pathlib import Path

from sqlalchemy import create_engine as _create_engine, event
from sqlalchemy.orm import sessionmaker, Session

_log = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".alarm_viewer"
DB_PATH = STATE_DIR / "alarm_viewer.db"


def create_engine(url: str | None = None):
    """Create a SQLAlchemy engine. Defaults to local SQLite."""
    if url is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DB_PATH}"

    engine = _create_engine(url, echo=False)

    url_type = "sqlite" if url.startswith("sqlite") else "postgres"
    _log.info("Engine created: type=%s", url_type)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            _log.debug("SQLite pragmas set: WAL mode, foreign keys enabled")

    return engine


def get_session_factory(engine=None):
    """Return a sessionmaker bound to the given engine."""
    if engine is None:
        engine = create_engine()
    return sessionmaker(bind=engine)


def get_session(engine=None) -> Session:
    """Create and return a new session."""
    factory = get_session_factory(engine)
    return factory()


def init_db(engine=None):
    """Create all tables and seed reference data."""
    from .models import Base
    if engine is None:
        engine = create_engine()
    _log.info("init_db called: creating tables")
    Base.metadata.create_all(engine)
    _log.info("Tables created")

    from .seed import seed_database
    _Session = sessionmaker(bind=engine)
    session = _Session()
    try:
        seed_database(session)
    finally:
        session.close()

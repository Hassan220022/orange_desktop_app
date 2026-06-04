"""Database engine and session management."""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine as _create_engine
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

_log = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".alarm_viewer"
DB_PATH = STATE_DIR / "alarm_viewer.db"

_app_engine = None
_app_session_factory = None


def get_app_engine():
    """Return the singleton application engine (defaults to local SQLite).

    All desktop writes must go through this engine so that SQLAlchemy's
    connection pooling can serialize concurrent writers instead of letting
    two independent engines fight over the same WAL lock.
    """
    global _app_engine, _app_session_factory
    if _app_engine is None:
        _app_engine = create_engine()
        _app_session_factory = sessionmaker(bind=_app_engine)
    return _app_engine


def get_shared_session() -> Session:
    """Create a new session from the shared application engine.

    Ensures tables exist (idempotent — cheap after first call).
    """
    global _app_session_factory
    if _app_session_factory is None:
        get_app_engine()
    assert _app_session_factory is not None
    return _app_session_factory()


def init_app_db():
    """Initialise DB tables and seed data using the shared engine."""
    engine = get_app_engine()
    init_db(engine, include_alarm_records=False)


def create_engine(url: str | None = None):
    """Create a SQLAlchemy engine. Defaults to local SQLite."""
    if url is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DB_PATH}"

    engine_kwargs: dict[str, Any] = {"echo": False}
    if url.startswith("sqlite"):
        # Allow concurrent desktop/background writers a chance to finish instead
        # of immediately failing with "database is locked".
        engine_kwargs["connect_args"] = {"timeout": 30}

    engine = _create_engine(url, **engine_kwargs)

    url_type = "sqlite" if url.startswith("sqlite") else "postgres"
    _log.info("Engine created: type=%s", url_type)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
            _log.debug("SQLite pragmas set: WAL mode, foreign keys enabled, busy timeout")

    return engine


def _ensure_optional_columns(engine) -> None:
    """Apply additive SQLite migrations for existing local databases."""
    if engine.dialect.name != "sqlite":
        return
    migrations = {
        "bdt_tests": {
            "summary_data_json": "TEXT",
        },
        "pm_validation_runs": {
            "insight_json": "TEXT",
        },
    }
    with engine.begin() as conn:
        for table_name, columns in migrations.items():
            existing = {
                str(row[1])
                for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            }
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )



def get_session_factory(engine=None):
    """Return a sessionmaker bound to the given engine."""
    if engine is None:
        engine = create_engine()
    return sessionmaker(bind=engine)


def get_session(engine=None) -> Session:
    """Create and return a new session."""
    factory = get_session_factory(engine)
    return factory()


def init_db(engine=None, include_alarm_records: bool = True):
    """Create tables and seed reference data.

    Desktop runtime stores alarm rows in DuckDB, so it can skip creating the
    redundant SQLite `alarm_records` table. Web/server callers keep the table.
    """
    from .models import Base
    if engine is None:
        engine = create_engine()
    _log.info("init_db called: creating tables")
    tables = list(Base.metadata.sorted_tables)
    if not include_alarm_records:
        tables = [t for t in tables if t.name != "alarm_records"]
    Base.metadata.create_all(engine, tables=tables)
    _ensure_optional_columns(engine)
    _log.info("Tables created")

    from .seed import seed_database
    _Session = sessionmaker(bind=engine)
    session = _Session()
    try:
        seed_database(session)
    finally:
        session.close()

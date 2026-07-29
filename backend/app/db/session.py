"""DB engine/session wiring. Nothing in the app touched the database before
this pass - compare.py called app/fixtures/sample_data.py directly."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_DEFAULT_DATABASE_URL = "sqlite:///./policyiq.db"


def get_engine():
    database_url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if is_sqlite:
        # Real failure hit today: run_ingest.py's batch writes against the
        # same SQLite file the live API server (also connected) reads from
        # failed every single document with "database is locked" - SQLite's
        # default rollback-journal mode allows only one writer and no
        # concurrent readers during a write, and its default busy_timeout is
        # 0 (fail instantly on contention rather than wait). WAL mode lets
        # readers proceed during a write; a real busy_timeout makes a
        # genuinely-contended write wait a few seconds and retry instead of
        # failing immediately. Both are no-ops for Postgres (this only
        # fires for sqlite).
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

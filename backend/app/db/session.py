"""DB engine/session wiring. Nothing in the app touched the database before
this pass - compare.py called app/fixtures/sample_data.py directly."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_DEFAULT_DATABASE_URL = "sqlite:///./policyiq.db"


def get_engine():
    database_url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

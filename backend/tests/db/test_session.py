from sqlalchemy import text

from app.db.session import get_engine


def test_sqlite_engine_enables_wal_and_a_real_busy_timeout(tmp_path, monkeypatch):
    """Regression test for a real failure (2026-07-29): a batch ingest run
    against the same SQLite file the live API server was also connected to
    failed every single document with "database is locked" - SQLite's
    default journal mode only allows one writer and no concurrent readers
    during a write, and its default busy_timeout is 0 (fail instantly
    instead of waiting). Both pragmas must actually take effect on real
    connections, not just be set once and forgotten."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 30000


def test_non_sqlite_url_builds_a_plain_engine_without_sqlite_pragmas(monkeypatch):
    """The WAL/busy_timeout pragmas above are sqlite-specific - building an
    engine for a non-sqlite URL must not attempt to apply them (they'd be
    invalid SQL against any other dialect)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")

    engine = get_engine()

    assert engine.dialect.name == "postgresql"

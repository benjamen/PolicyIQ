"""Runs the real Alembic migration chain against a throwaway file-based
SQLite DB (in-memory SQLite doesn't survive across the separate connections
Alembic's offline/online steps use) and asserts the resulting schema matches
what app/db/models.py declares."""

from __future__ import annotations

import os
import tempfile

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic_config(db_url: str) -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_upgrade_creates_full_schema():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "migration_test.db")
        db_url = f"sqlite:///{db_path}"
        cfg = _alembic_config(db_url)

        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        tables = set(inspect(engine).get_table_names())

        expected = {
            "insurer", "product", "policy", "policy_version", "document", "section",
            "benefit", "policy_limit", "exclusion", "definition", "waiting_period",
            "optional_benefit", "occupation_category", "eligibility_rule", "graded_fact",
        }
        assert expected <= tables

        policy_version_columns = {c["name"] for c in inspect(engine).get_columns("policy_version")}
        assert "policy_id" in policy_version_columns
        assert "product_id" not in policy_version_columns

        engine.dispose()


def test_migration_downgrade_then_upgrade_is_clean():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "migration_roundtrip.db")
        db_url = f"sqlite:///{db_path}"
        cfg = _alembic_config(db_url)

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "81ba5eebd41d")

        engine = create_engine(db_url)
        tables = set(inspect(engine).get_table_names())
        assert "document" not in tables
        assert "policy" not in tables
        policy_version_columns = {c["name"] for c in inspect(engine).get_columns("policy_version")}
        assert "product_id" in policy_version_columns
        engine.dispose()

        command.upgrade(cfg, "head")

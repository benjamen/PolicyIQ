import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, Insurer
from app.db.seed_insurers import seed_life_insurers


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_first_run_inserts_exactly_the_seed_set(session):
    inserted = seed_life_insurers(session)

    assert inserted == 7
    names = {row.name for row in session.execute(select(Insurer)).scalars()}
    assert "AIA New Zealand" in names
    assert "Partners Life" in names
    assert len(names) == 7


def test_second_run_is_a_noop_and_preserves_manual_edits(session):
    seed_life_insurers(session)

    row = session.execute(select(Insurer).where(Insurer.name == "AIA New Zealand")).scalar_one()
    row.crawl_policy_json = json.dumps({"blocked": True, "note": "manually paused by admin"})
    session.commit()

    inserted_second_run = seed_life_insurers(session)

    assert inserted_second_run == 0
    refreshed = session.execute(select(Insurer).where(Insurer.name == "AIA New Zealand")).scalar_one()
    assert json.loads(refreshed.crawl_policy_json)["blocked"] is True

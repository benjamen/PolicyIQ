"""Seeds the `insurer` table from the crawler's insurer registry
(workers/crawler/policyiq_crawler/registry.py) rather than duplicating the
7-insurer tuple or making workers/crawler a pip dependency of the backend
just to expose one constant. That module has zero Scrapy/Twisted imports
(verified: pure dataclasses), so a sys.path addition is enough.

`discover_insurers()` in registry.py stays unchanged (static-tuple-backed) -
rewiring it to read from this table is a separate, disproportionate change
for this pass; the 7 existing crawler tests keep passing untouched.

Run via `python -m app.db.seed_insurers`.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

_CRAWLER_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "workers", "crawler")
if _CRAWLER_ROOT not in sys.path:
    sys.path.insert(0, _CRAWLER_ROOT)

from policyiq_crawler.registry import LIFE_INSURER_SEED  # noqa: E402

from app.db.models import Insurer  # noqa: E402


def seed_life_insurers(session: Session) -> int:
    """Insert-only, idempotent: never overwrites an existing row's
    crawl_policy_json on re-run, since that field is meant to be
    admin-editable (docs/02-DATABASE-ERD.md) once an admin UI exists.
    Returns the number of rows inserted."""
    inserted = 0
    for seed in LIFE_INSURER_SEED:
        existing = session.execute(select(Insurer).where(Insurer.name == seed.name)).scalar_one_or_none()
        if existing is not None:
            continue
        session.add(
            Insurer(
                name=seed.name,
                website_root=seed.website_root,
                crawl_policy_json=json.dumps(asdict(seed.crawl_policy)),
            )
        )
        inserted += 1
    session.commit()
    return inserted


if __name__ == "__main__":
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        count = seed_life_insurers(session)
        print(f"Seeded {count} new insurer(s) (idempotent - already-seeded rows were left untouched).")

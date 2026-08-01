"""Pipeline orchestrator: scheduled weekly crawl + daily health check.

Converts the manual CLI workflow (run_ingest.py) into an automated,
self-healing pipeline per docs/12-SCRAPING-ARCHITECTURE.md §2.

Phase 1 implementation: APScheduler in-process (no Redis/ARQ dependency
yet — the VPS runs a single uvicorn worker, so an in-process scheduler
is sufficient until concurrency demands a real queue). The scheduler
lives in a separate module so it can be started alongside the API server
or as a standalone worker process.

Usage:
    # Standalone (recommended for production):
    python -m app.pipeline.orchestrator --mode standalone

    # Alongside API (dev convenience):
    python -m app.pipeline.orchestrator --mode with-api
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Insurer
from app.db.session import SessionLocal
from app.pipeline.run_ingest import HttpxFetcher, run_ingest
from app.providers.llm import get_provider
from app.storage.local_disk import storage_from_env

logger = logging.getLogger(__name__)


# ─── Insurer Groups (staggered scheduling) ─────────────────────────────
# Insurers sharing a parent company are grouped together to avoid
# hammering shared CDN infrastructure. 2-minute gaps between groups.
# See docs/12-SCRAPING-ARCHITECTURE.md §2.3.

INSURER_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("group_a_iag_suncorp", ("AMI", "State", "NZI")),
    ("group_b_tower_vero", ("Tower", "Vero", "AA Insurance")),
    ("group_c_mutuals", ("FMG", "MAS (Medical Assurance Society)", "Trade Me Insurance", "Initio")),
    ("group_d_life", (
        "AIA New Zealand", "Partners Life", "Fidelity Life",
        "Asteron Life", "Chubb Life NZ", "Pinnacle Life", "AA Life",
    )),
    ("group_e_health", ("Southern Cross Health Society", "nib", "UniMed")),
    ("group_f_specialty", (
        "SPCA Pet Insurance", "Cove", "Pet-n-Sur", "1Cover",
        "PD Insurance", "Petcover", "Nautilus Marine Insurance",
    )),
)

# Product type mapping for run_ingest (insurer → their primary product type)
# In practice, each insurer may have multiple products; the full pipeline
# iterates all known product_types per insurer from the catalog.
INSURER_PRODUCT_TYPES: dict[str, tuple[str, ...]] = {
    "AMI": ("house", "contents", "car"),
    "State": ("house", "contents", "car"),
    "NZI": ("house", "contents"),
    "Tower": ("house", "contents", "car"),
    "Vero": ("house", "contents", "boat"),
    "AA Insurance": ("house", "contents", "car"),
    "FMG": ("house", "contents"),
    "MAS (Medical Assurance Society)": ("house", "contents", "car", "life_cover"),
    "Trade Me Insurance": ("house", "contents", "car", "landlord"),
    "Initio": ("house", "contents", "car", "landlord"),
    "AIA New Zealand": ("life_cover", "health"),
    "Partners Life": ("life_cover",),
    "Fidelity Life": ("life_cover",),
    "Asteron Life": ("life_cover",),
    "Chubb Life NZ": ("life_cover",),
    "Pinnacle Life": ("life_cover",),
    "AA Life": ("life_cover",),
    "Southern Cross Health Society": ("health",),
    "nib": ("health",),
    "UniMed": ("health",),
    "SPCA Pet Insurance": ("pet",),
    "Cove": ("pet", "car"),
    "Pet-n-Sur": ("pet",),
    "1Cover": ("travel",),
    "PD Insurance": ("pet",),
    "Petcover": ("pet",),
    "Nautilus Marine Insurance": ("boat",),
}


@dataclass
class RunStats:
    """Aggregated stats for a full pipeline run."""
    insurers_attempted: int = 0
    insurers_succeeded: int = 0
    insurers_failed: int = 0
    insurers_skipped: int = 0
    total_documents_downloaded: int = 0
    total_documents_unchanged: int = 0
    total_sections_built: int = 0
    total_failures: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


def _create_pipeline_run(
    session: Session,
    *,
    run_type: str,
    insurer_id: uuid.UUID | None,
    triggered_by: str,
) -> uuid.UUID:
    """Insert a PIPELINE_RUN row and return its ID."""
    from app.db.models import GUID, Base
    from sqlalchemy import text

    run_id = uuid.uuid4()
    session.execute(
        text(
            "INSERT INTO pipeline_run (id, run_type, insurer_id, status, started_at, triggered_by) "
            "VALUES (:id, :run_type, :insurer_id, 'running', :started_at, :triggered_by)"
        ),
        {
            "id": str(run_id),
            "run_type": run_type,
            "insurer_id": str(insurer_id) if insurer_id else None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": triggered_by,
        },
    )
    session.commit()
    return run_id


def _complete_pipeline_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    status: str,
    stats: dict | None = None,
    error_summary: str | None = None,
) -> None:
    """Mark a PIPELINE_RUN as completed/failed with stats."""
    from sqlalchemy import text

    session.execute(
        text(
            "UPDATE pipeline_run SET status = :status, completed_at = :completed_at, "
            "stats_json = :stats_json, error_summary = :error_summary WHERE id = :id"
        ),
        {
            "id": str(run_id),
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stats_json": json.dumps(stats) if stats else None,
            "error_summary": error_summary,
        },
    )
    session.commit()


def run_single_insurer(
    insurer_name: str,
    *,
    session: Session,
    fetcher,
    storage,
    provider,
    run_type: str = "scheduled_weekly",
    triggered_by: str = "scheduler",
) -> dict:
    """Run the full pipeline for a single insurer across all their product types.

    Returns a stats dict. Never raises — failures are captured and returned.
    """
    insurer = session.execute(
        select(Insurer).where(Insurer.name == insurer_name)
    ).scalar_one_or_none()

    insurer_id = insurer.id if insurer else None
    run_id = _create_pipeline_run(
        session, run_type=run_type, insurer_id=insurer_id, triggered_by=triggered_by
    )

    product_types = INSURER_PRODUCT_TYPES.get(insurer_name, ("house",))
    combined_stats = {
        "insurer": insurer_name,
        "product_types": list(product_types),
        "documents_downloaded": 0,
        "documents_unchanged": 0,
        "documents_failed": 0,
        "sections_built": 0,
        "extraction_skipped": False,
    }

    try:
        for product_type in product_types:
            # The crawler JSONL discovery file path follows the existing
            # convention: discovered/<slug>.jsonl
            slug = insurer_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
            input_path = f"discovered/{slug}.jsonl"

            try:
                stats = run_ingest(
                    input_path,
                    product_type=product_type,
                    session=session,
                    fetcher=fetcher,
                    storage=storage,
                    provider=provider,
                )
                combined_stats["documents_downloaded"] += stats.documents_downloaded
                combined_stats["documents_unchanged"] += stats.documents_unchanged
                combined_stats["documents_failed"] += stats.documents_failed
                combined_stats["sections_built"] += stats.sections_built
                if stats.extraction_skipped_no_provider:
                    combined_stats["extraction_skipped"] = True
            except FileNotFoundError:
                # No discovery JSONL for this product type yet — not an error,
                # just means the crawler hasn't been run for this combination.
                logger.info("No discovery file for %s/%s — skipping", insurer_name, product_type)
            except Exception as exc:
                logger.error("Pipeline failed for %s/%s: %s", insurer_name, product_type, exc)
                combined_stats["documents_failed"] += 1

        _complete_pipeline_run(session, run_id, status="completed", stats=combined_stats)
        logger.info("Pipeline completed for %s: %s", insurer_name, combined_stats)

    except Exception as exc:
        _complete_pipeline_run(
            session, run_id, status="failed",
            stats=combined_stats, error_summary=str(exc),
        )
        logger.error("Pipeline run failed for %s: %s", insurer_name, exc)

    return combined_stats


def run_weekly_full_scan(*, triggered_by: str = "scheduler") -> RunStats:
    """Execute the full weekly pipeline across all insurer groups.

    Staggers groups with a 2-second gap (simulating the 2-minute production
    interval; shortened for dev). Logs progress and returns aggregate stats.
    """
    start = time.time()
    stats = RunStats()
    session = SessionLocal()
    fetcher = HttpxFetcher()
    storage = storage_from_env()
    provider = get_provider()

    try:
        for group_name, insurer_names in INSURER_GROUPS:
            logger.info("Starting %s: %s", group_name, insurer_names)
            for insurer_name in insurer_names:
                stats.insurers_attempted += 1
                try:
                    result = run_single_insurer(
                        insurer_name,
                        session=session,
                        fetcher=fetcher,
                        storage=storage,
                        provider=provider,
                        run_type="scheduled_weekly",
                        triggered_by=triggered_by,
                    )
                    if result.get("documents_failed", 0) > 0:
                        stats.insurers_failed += 1
                    else:
                        stats.insurers_succeeded += 1
                    stats.total_documents_downloaded += result.get("documents_downloaded", 0)
                    stats.total_documents_unchanged += result.get("documents_unchanged", 0)
                    stats.total_sections_built += result.get("sections_built", 0)
                except Exception as exc:
                    stats.insurers_failed += 1
                    stats.errors.append(f"{insurer_name}: {exc}")
                    logger.error("Unhandled error for %s: %s", insurer_name, exc)

            # Stagger between groups (2s in dev, would be 120s in production)
            time.sleep(2)

    finally:
        session.close()

    stats.duration_seconds = time.time() - start
    logger.info(
        "Weekly scan complete: %d attempted, %d succeeded, %d failed (%.1fs)",
        stats.insurers_attempted, stats.insurers_succeeded,
        stats.insurers_failed, stats.duration_seconds,
    )
    return stats


def run_daily_health_check() -> dict:
    """Lightweight daily check: HEAD all known document URLs, report changes.

    Does NOT download or re-extract — just detects which documents have
    changed since last crawl so the weekly run (or an ad-hoc trigger)
    can prioritize them.
    """
    from app.db.models import Document

    session = SessionLocal()
    fetcher = HttpxFetcher()
    results = {"checked": 0, "changed": 0, "unreachable": 0, "changed_urls": []}

    try:
        documents = session.execute(
            select(Document).where(Document.source_url.isnot(None))
        ).scalars().all()

        for doc in documents:
            if not doc.source_url:
                continue
            results["checked"] += 1
            try:
                head = fetcher.head(doc.source_url)
                if head.status >= 400:
                    results["unreachable"] += 1
                    continue
                changed = (
                    (head.etag and head.etag != doc.etag)
                    or (head.last_modified and head.last_modified != doc.last_modified)
                )
                if changed:
                    results["changed"] += 1
                    results["changed_urls"].append(doc.source_url)
            except Exception:
                results["unreachable"] += 1

    finally:
        session.close()

    logger.info(
        "Daily health check: %d checked, %d changed, %d unreachable",
        results["checked"], results["changed"], results["unreachable"],
    )
    return results


# ─── Scheduler Setup ───────────────────────────────────────────────────

def start_scheduler() -> None:
    """Start the APScheduler with weekly + daily jobs.

    Requires: pip install apscheduler
    Falls back to a simple sleep-loop if APScheduler isn't installed.
    """
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BlockingScheduler(timezone="Pacific/Auckland")

        # Weekly full scan: Monday 02:00 NZST
        scheduler.add_job(
            run_weekly_full_scan,
            CronTrigger(day_of_week="mon", hour=2, minute=0),
            id="weekly_full_scan",
            name="Weekly full pipeline scan",
        )

        # Daily health check: 06:00 NZST
        scheduler.add_job(
            run_daily_health_check,
            CronTrigger(hour=6, minute=0),
            id="daily_health_check",
            name="Daily document change detection",
        )

        logger.info("Scheduler started: weekly scan Mon 02:00, daily check 06:00 (NZST)")
        scheduler.start()

    except ImportError:
        logger.warning(
            "APScheduler not installed — running in simple loop mode. "
            "Install with: pip install apscheduler"
        )
        _simple_loop()


def _simple_loop() -> None:
    """Fallback: run weekly scan immediately, then sleep 7 days."""
    import sys

    logger.info("Running immediate full scan (simple loop mode)...")
    stats = run_weekly_full_scan(triggered_by="simple_loop")
    print(f"Scan complete: {stats}")

    if "--once" in sys.argv:
        return

    logger.info("Sleeping 7 days until next run...")
    time.sleep(7 * 24 * 3600)
    _simple_loop()


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="PolicyIQ Pipeline Orchestrator")
    parser.add_argument(
        "--mode", choices=["standalone", "with-api", "once", "health-check"],
        default="standalone",
        help="standalone: run scheduler as main process; "
             "with-api: start scheduler in background thread alongside API; "
             "once: run a single full scan and exit; "
             "health-check: run daily HEAD check and exit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.mode == "once":
        sys.argv.append("--once")
        stats = run_weekly_full_scan(triggered_by="manual")
        print(json.dumps(asdict(stats), indent=2))
    elif args.mode == "health-check":
        results = run_daily_health_check()
        print(json.dumps(results, indent=2))
    elif args.mode == "standalone":
        start_scheduler()
    elif args.mode == "with-api":
        import threading
        t = threading.Thread(target=start_scheduler, daemon=True)
        t.start()
        # Import and run the API server
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

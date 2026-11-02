"""CLI runner for durable background jobs.

Usage:
  python -m app.jobs.runner --once
  python -m app.jobs.runner --loop --sleep 5 --limit 20
  python -m app.jobs.runner --predictions     # queue one prediction run, then --once
  python -m app.jobs.runner --control-tower   # queue one Control Tower evaluation, then --once
  python -m app.jobs.runner --predictions --control-tower   # predictions first, so forecast findings are fresh
  python -m app.jobs.runner --automation      # queue one automation sweep, then --once
"""

from __future__ import annotations

import argparse
import logging
import time

from app.db.session import SessionLocal
from app.services import job_queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("protrack.jobs.runner")


def main() -> None:
    parser = argparse.ArgumentParser(description="ProTrack background job runner")
    parser.add_argument("--once", action="store_true", help="Process up to --limit jobs and exit")
    parser.add_argument("--loop", action="store_true", help="Process forever")
    parser.add_argument("--limit", type=int, default=20, help="Max jobs per cycle")
    parser.add_argument("--sleep", type=float, default=5.0, help="Seconds between loop cycles")
    parser.add_argument(
        "--predictions",
        action="store_true",
        help="Queue one prediction run before processing (daily scheduled task; runs before --control-tower)",
    )
    parser.add_argument(
        "--control-tower",
        action="store_true",
        help="Queue one Control Tower evaluation before processing (for a daily scheduled task)",
    )
    parser.add_argument(
        "--automation",
        action="store_true",
        help="Queue one sweep of the enabled automation rules before processing (daily scheduled task)",
    )
    args = parser.parse_args()

    if not args.once and not args.loop:
        args.once = True

    for flag, job_type in (
        (args.predictions, job_queue.JOB_PREDICTION_RUN),
        (args.control_tower, job_queue.JOB_CONTROL_TOWER_EVALUATION),
        (args.automation, job_queue.JOB_AUTOMATION_SWEEP),
    ):
        if not flag:
            continue
        db = SessionLocal()
        try:
            job_queue.enqueue_job(db, job_type=job_type, max_attempts=1)
        finally:
            db.close()

    while True:
        db = SessionLocal()
        try:
            done = job_queue.process_due(db, limit=args.limit)
            if done:
                logger.info("Processed %s job(s)", done)
        except Exception:
            logger.exception("Job runner cycle failed")
        finally:
            db.close()
        if args.once:
            break
        time.sleep(max(0.5, args.sleep))


if __name__ == "__main__":
    main()

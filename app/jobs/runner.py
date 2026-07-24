"""CLI runner for durable background jobs.

Usage:
  python -m app.jobs.runner --once
  python -m app.jobs.runner --loop --sleep 5 --limit 20
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
    args = parser.parse_args()

    if not args.once and not args.loop:
        args.once = True

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

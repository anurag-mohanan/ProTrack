"""Export project templates from the database to a JSON seed file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.project_template_seed import export_project_templates_to_json
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Export project templates to JSON.")
    parser.add_argument(
        "--output",
        default="data/project_templates_seed.json",
        help="Output JSON path (default: data/project_templates_seed.json)",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        payload = export_project_templates_to_json(session, args.output)
    finally:
        session.close()

    print(
        f"Exported {payload['exported_template_count']} templates to "
        f"{Path(args.output).resolve()}"
    )


if __name__ == "__main__":
    main()

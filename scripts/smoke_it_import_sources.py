"""Smoke-test analyzer against original source workbooks (no DB commit)."""
from __future__ import annotations

from pathlib import Path

from app.db.session import SessionLocal
from app.models.models import User
from app.services import it_migration_service
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "migration-sources"


def main() -> None:
    db = SessionLocal()
    try:
        actor = db.scalar(select(User).where(User.is_deleted.is_(False)).limit(1))
        if actor is None:
            print("No user in DB — skipping live analyze")
            return

        cases = [
            ("PP-INF-FO-7_IT_RECORDS.xlsx", "hardware"),
            ("PP-INF-FO-7_IT_RECORDS.xlsx", "accounts"),
            ("PP-INF-FO-7_IT_RECORDS.xlsx", "software"),
            ("PP-Asset-Inventory.xlsx", "inventory"),
            ("PP-Asset-Inventory.xlsx", "consumables"),
            ("PP-Asset-Inventory.xlsx", "suppliers"),
        ]
        for filename, source_type in cases:
            path = SOURCES / filename
            content = path.read_bytes()
            result = it_migration_service.analyze_upload(
                db,
                actor=actor,
                content=content,
                filename=filename,
                source_type=source_type,
            )
            preview = result["preview_rows"][:3]
            print("=" * 72)
            print(filename, source_type)
            print(
                "records",
                result["records_found"],
                "new",
                result["new_records"],
                "review",
                result["requires_review"],
                "sheet",
                result["sheet_name"],
            )
            print("sensitive", result["sensitive_columns_excluded"])
            for row in preview:
                print(" ", row)
            # Fidelity checks
            blob = str(result).upper()
            assert "SHOULD-NEVER" not in blob
            for p in preview:
                sid = str(p.get("source_id") or p.get("mapped_asset_number") or "")
                assert not sid.startswith("EX-")
                assert "OWNERSHIP_UNCLEAR" not in sid
                assert "SERIAL_MISSING" not in sid
                if source_type in {"hardware", "inventory"} and p.get("serial") in {
                    "SERIAL_MISSING",
                    "OWNERSHIP_UNCLEAR",
                }:
                    raise AssertionError(f"validation code leaked into serial: {p}")
        print("OK: original workbooks analyze cleanly")
    finally:
        db.close()


if __name__ == "__main__":
    main()

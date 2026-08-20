"""Purge IT migration analyze session JSON only. No DB deletes."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = ROOT / "uploads" / "it_migration"
DB = ROOT / "protrack.db"


def main() -> None:
    files = sorted(SESSIONS.glob("*.json")) if SESSIONS.exists() else []
    print(f"BEFORE: {len(files)} session files")
    by: Counter[str] = Counter()
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            by[str(data.get("filename") or "?")] += 1
        except Exception:
            by["(unreadable)"] += 1
    for name, n in sorted(by.items()):
        print(f"  {name}: {n}")

    deleted = 0
    errors: list[tuple[str, str]] = []
    for f in files:
        try:
            f.unlink()
            deleted += 1
        except OSError as exc:
            errors.append((f.name, str(exc)))

    after = list(SESSIONS.glob("*.json")) if SESSIONS.exists() else []
    print(f"DELETED: {deleted}")
    print(f"AFTER: {len(after)} session files")
    if errors:
        print("ERRORS:")
        for name, msg in errors:
            print(f"  {name}: {msg}")

    con = sqlite3.connect(str(DB))
    checks = [
        ("assets", "SELECT COUNT(*) FROM assets"),
        ("users", "SELECT COUNT(*) FROM users"),
        ("customers", "SELECT COUNT(*) FROM customers"),
        ("projects", "SELECT COUNT(*) FROM projects"),
        ("teams", "SELECT COUNT(*) FROM teams"),
        ("timesheet_entries", "SELECT COUNT(*) FROM timesheet_entries"),
        ("asset_types", "SELECT COUNT(*) FROM asset_types"),
        ("it_settings", "SELECT COUNT(*) FROM it_settings"),
        (
            "it_migration_analyzed",
            "SELECT COUNT(*) FROM activities WHERE action='it_migration_analyzed'",
        ),
        (
            "it_migration_imported",
            "SELECT COUNT(*) FROM activities WHERE action='it_migration_imported'",
        ),
    ]
    print("DB checks (must remain unchanged):")
    for label, sql in checks:
        print(f"  {label}: {con.execute(sql).fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()

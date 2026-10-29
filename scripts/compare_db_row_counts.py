"""Read-only per-table comparison (row count and content hash) between SQLite files.

Usage: python scripts/compare_db_row_counts.py baseline.db other.db [other2.db ...]

Opens every file with ``mode=ro`` and prints only tables whose count or content
differs. Values are shown as ``rows:hash-prefix``; no row data is printed.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path


def counts(path: Path) -> dict[str, str]:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        result: dict[str, str] = {}
        for table in tables:
            digest = hashlib.sha256()
            rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
            for row in sorted(repr(r) for r in rows):
                digest.update(row.encode("utf-8"))
            result[table] = f"{len(rows)}:{digest.hexdigest()[:10]}"
        return result
    finally:
        conn.close()


def changed_columns(first: Path, last: Path, table: str) -> set[str]:
    """Column names whose values differ for rows matched on ``id``."""

    def rows(path: Path) -> tuple[list[str], dict[object, tuple]]:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            cursor = conn.execute(f'SELECT * FROM "{table}"')
            columns = [c[0] for c in cursor.description]
            if "id" not in columns:
                return columns, {}
            index = columns.index("id")
            return columns, {row[index]: row for row in cursor.fetchall()}
        finally:
            conn.close()

    columns, before = rows(first)
    _, after = rows(last)
    changed: set[str] = set()
    for key, old in before.items():
        new = after.get(key)
        if new is None:
            continue
        changed.update(col for col, a, b in zip(columns, old, new) if a != b)
    return changed


def main(paths: list[str]) -> int:
    files = [Path(p).resolve() for p in paths]
    data = [counts(path) for path in files]
    tables = sorted(set().union(*data))
    print(" | ".join(["table"] + [path.name for path in files]))
    differing = 0
    for table in tables:
        values = [str(d.get(table, "-")) for d in data]
        if len(set(values)) > 1:
            differing += 1
            print(" | ".join([table] + values))
            print(f"    changed columns (first vs last file): {sorted(changed_columns(files[0], files[-1], table))}")
    print(f"tables compared: {len(tables)}; differing: {differing}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))

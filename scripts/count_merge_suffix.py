"""Read-only: count repeated phase35 merge suffixes in team text fields.

Usage: python scripts/count_merge_suffix.py db1.db [db2.db ...]
Prints counts and lengths only.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SUFFIX = "[merged into Corporate / Management"


def main(paths: list[str]) -> int:
    for raw in paths:
        path = Path(raw).resolve()
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            teams = conn.execute("SELECT name, description FROM teams").fetchall()
            terms = conn.execute("SELECT team_id, notes FROM team_commercial_terms").fetchall()
        finally:
            conn.close()
        print(f"== {path.name}")
        for name, description in teams:
            text = description or ""
            print(f"  team {name!r}: suffix x{text.count(SUFFIX)}, length {len(text)}")
        for index, (_, notes) in enumerate(terms, start=1):
            text = notes or ""
            print(f"  commercial terms #{index}: suffix x{text.count(SUFFIX)}, length {len(text)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

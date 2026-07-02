"""Assign the soft-launch temporary password to all active imported users."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.bulk_password_reset_migration import main

if __name__ == "__main__":
    main()

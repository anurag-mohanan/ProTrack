"""One-off analyzer for IT migration source spreadsheets. Does not print secrets."""

from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import load_workbook

BASE = Path(__file__).resolve().parent
FILES = [
    BASE / "PP-INF-FO-7_IT_RECORDS.xlsx",
    BASE / "PP-Asset-Inventory.xlsx",
]
SENSITIVE = re.compile(r"pass|pwd|secret|credential", re.I)


def cell_str(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def main() -> None:
    out_lines: list[str] = []

    def p(msg: str = "") -> None:
        out_lines.append(msg)
        print(msg)

    for path in FILES:
        p("=" * 80)
        p(f"FILE: {path.name}")
        wb = load_workbook(path, data_only=True, read_only=True)
        p(f"SHEETS: {wb.sheetnames}")
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            p(f"\n--- Sheet: {sheet_name!r} raw_rows={len(rows)} ---")
            header_idx = None
            headers: list[str] = []
            for i, row in enumerate(rows[:40]):
                vals = [cell_str(c) for c in (row or [])]
                nonempty = [v for v in vals if v]
                if len(nonempty) >= 3:
                    header_idx = i
                    headers = vals
                    break
            if header_idx is None:
                p("  No header found; first 5 rows:")
                for r in rows[:5]:
                    p(f"    {[cell_str(c) for c in (r or [])][:20]}")
                continue
            while headers and not headers[-1]:
                headers.pop()
            p(f"  Header row index: {header_idx} (Excel row {header_idx + 1})")
            p(f"  Columns ({len(headers)}):")
            for ci, h in enumerate(headers):
                sens = " [SENSITIVE-COL]" if SENSITIVE.search(h or "") else ""
                p(f"    [{ci}] {h!r}{sens}")
            data_rows: list[list[str]] = []
            for row in rows[header_idx + 1 :]:
                vals = [cell_str(c) for c in (row or [])]
                if len(vals) < len(headers):
                    vals += [""] * (len(headers) - len(vals))
                vals = vals[: len(headers)]
                if any(vals):
                    data_rows.append(vals)
            p(f"  Data rows: {len(data_rows)}")
            for ci, h in enumerate(headers):
                filled = sum(1 for r in data_rows if r[ci])
                p(f"    fill {filled}/{len(data_rows)} :: {h}")
            # Distinct samples for key columns (non-sensitive)
            key_names = [
                "status",
                "type",
                "category",
                "customer",
                "purchased",
                "department",
                "condition",
                "make",
                "supplier",
                "paid",
                "in use",
                "available",
            ]
            for ci, h in enumerate(headers):
                hl = (h or "").lower()
                if SENSITIVE.search(h or ""):
                    continue
                if any(k in hl for k in key_names) or hl in {"id", "name", "os"}:
                    vals = sorted({r[ci] for r in data_rows if r[ci]})
                    p(f"  Distinct '{h}' ({len(vals)}): {vals[:40]}")
            p("  Sample rows (first 2, secrets redacted):")
            for r in data_rows[:2]:
                sample = {}
                for i, h in enumerate(headers):
                    if not r[i]:
                        continue
                    sample[h] = "***REDACTED***" if SENSITIVE.search(h) else r[i]
                p("   " + json.dumps(sample, ensure_ascii=False)[:800])
        wb.close()

    (BASE / "_analyze_output.txt").write_text("\n".join(out_lines), encoding="utf-8")


if __name__ == "__main__":
    main()

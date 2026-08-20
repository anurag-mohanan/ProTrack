"""Second-pass analyzer for messy multi-header inventory sheets."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

BASE = Path(__file__).resolve().parent
SENSITIVE = re.compile(r"pass|pwd|secret|credential|teamviewer", re.I)


def cell_str(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def dump_rows(ws, start: int, end: int) -> None:
    rows = list(ws.iter_rows(min_row=start, max_row=end, values_only=True))
    for i, row in enumerate(rows, start=start):
        vals = [cell_str(c) for c in row]
        while vals and not vals[-1]:
            vals.pop()
        print(f"R{i}: {vals}")


def analyze_inventory(path: Path) -> None:
    print("=" * 80)
    print("DEEP:", path.name)
    wb = load_workbook(path, data_only=True)
    for name in wb.sheetnames:
        ws = wb[name]
        print(f"\n### {name!r} max_row={ws.max_row} max_col={ws.max_column}")
        dump_rows(ws, 1, 8)

    # INVENTORY LIST - find true header
    ws = wb["INVENTORY LIST "]
    # Row 3 seemed like group headers; row 4 may be real headers
    print("\n--- INVENTORY candidate headers ---")
    for r in range(1, 8):
        vals = [cell_str(c) for c in next(ws.iter_rows(min_row=r, max_row=r, values_only=True))]
        print(f"R{r}: {vals}")

    # Try row 4 as header (Name, Description, ...)
    header_row = 4
    headers = [cell_str(c) for c in next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True))]
    while headers and not headers[-1]:
        headers.pop()
    # If first col empty labels from row4
    print("Using headers:", headers)
    data = []
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        vals = [cell_str(c) for c in row]
        if len(vals) < len(headers):
            vals += [""] * (len(headers) - len(vals))
        vals = vals[: len(headers)]
        if any(vals[1:]):  # skip empty / serial-only noise in col0
            data.append(vals)
    print(f"Data rows: {len(data)}")
    for i, h in enumerate(headers):
        filled = sum(1 for r in data if r[i])
        print(f"  fill {filled}/{len(data)} :: [{i}] {h!r}")

    # Map by known names if headers weird
    # Build dict using header text
    def row_dict(r):
        return {headers[i] or f"col{i}": r[i] for i in range(len(headers))}

    # Distinct for ownership-ish columns
    for key in headers:
        kl = key.lower()
        if any(
            x in kl
            for x in [
                "customer",
                "paid",
                "department",
                "category",
                "condition",
                "supplier",
                "room",
                "designer",
                "user",
                "in use",
                "available",
                "name",
                "id",
            ]
        ):
            vals = sorted({row_dict(r).get(key, "") for r in data if row_dict(r).get(key, "")})
            print(f"Distinct {key!r} ({len(vals)}): {vals[:50]}")

    print("Samples:")
    for r in data[:5]:
        d = {k: v for k, v in row_dict(r).items() if v}
        print(json.dumps(d, ensure_ascii=False)[:900])

    # CONSUMABLES
    ws = wb["CONSUMABLES"]
    print("\n--- CONSUMABLES headers ---")
    for r in range(1, 8):
        vals = [cell_str(c) for c in next(ws.iter_rows(min_row=r, max_row=r, values_only=True))]
        print(f"R{r}: {vals}")
    headers = [cell_str(c) for c in next(ws.iter_rows(min_row=4, max_row=4, values_only=True))]
    while headers and not headers[-1]:
        headers.pop()
    data = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        vals = [cell_str(c) for c in row][: len(headers)]
        if any(vals[1:] if len(vals) > 1 else vals):
            data.append(vals)
    print(f"Consumable data rows: {len(data)}")
    for r in data[:15]:
        d = {headers[i] or f"c{i}": r[i] for i in range(min(len(headers), len(r))) if r[i]}
        print(json.dumps(d, ensure_ascii=False)[:400])

    # SUPPLIER LIST - headers may be wrong
    ws = wb["SUPPLIER LIST "]
    print("\n--- SUPPLIER LIST first 20 ---")
    dump_rows(ws, 1, 25)

    wb.close()


def analyze_hardware_ownership(path: Path) -> None:
    print("\n" + "=" * 80)
    print("HARDWARE ownership signals")
    wb = load_workbook(path, data_only=True)
    ws = wb["1.HARDWARES"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    headers = [cell_str(c) for c in rows[0]]
    while headers and not headers[-1]:
        headers.pop()
    data = []
    for row in rows[1:]:
        vals = [cell_str(c) for c in row][: len(headers)]
        if any(vals):
            data.append(dict(zip(headers, vals)))

    prefix = Counter()
    for r in data:
        aid = r.get("ID", "")
        pref = aid.split("-")[0] if "-" in aid else aid[:2]
        prefix[pref] += 1
        cust = r.get("CUSTOMER USED FOR", "")
        # ownership heuristic note
        print(
            f"{aid:12} type={r.get('TYPE',''):12} cust_used={cust:14} user={r.get('CURRENT USER','')[:20]:20} serial={r.get('SERVICE TAG#','')}"
        )
    print("ID prefixes:", dict(prefix))

    # Software purchased by
    ws = wb["3.SOFTWARES_&_LICENSES"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    headers = [cell_str(c) for c in rows[0]]
    while headers and not headers[-1]:
        headers.pop()
    pb = Counter()
    soft = Counter()
    for row in rows[1:]:
        vals = [cell_str(c) for c in row][: len(headers)]
        if not any(vals):
            continue
        d = dict(zip(headers, vals))
        pb[d.get("PURCHASED BY", "")] += 1
        soft[d.get("SOFTWARE", "")] += 1
    print("Software PURCHASED BY:", dict(pb))
    print("Software names:", dict(soft))

    # Credential sensitive cols count only
    ws = wb["2.USER_CREDENTIALS"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    headers = [cell_str(c) for c in rows[0]]
    sens_cols = [h for h in headers if SENSITIVE.search(h or "")]
    print("Sensitive credential columns:", sens_cols)
    status = Counter()
    for row in rows[1:]:
        vals = [cell_str(c) for c in row][: len(headers)]
        if not any(vals):
            continue
        d = dict(zip(headers, vals))
        status[d.get("STATUS", "")] += 1
    print("Credential STATUS:", dict(status))
    wb.close()


if __name__ == "__main__":
    analyze_inventory(BASE / "PP-Asset-Inventory.xlsx")
    analyze_hardware_ownership(BASE / "PP-INF-FO-7_IT_RECORDS.xlsx")

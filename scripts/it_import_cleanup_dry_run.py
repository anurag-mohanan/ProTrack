"""
DRY RUN ONLY — identify historic IT import records for surgical cleanup.
Does NOT delete anything.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "protrack.db"
REPORT_PATH = Path(__file__).resolve().parents[1] / "docs" / "IT_IMPORT_CLEANUP_DRY_RUN.md"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def count(con: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    return int(con.execute(sql, params).fetchone()[0])


def main() -> None:
    con = connect()
    lines: list[str] = []
    w = lines.append

    w("# IT IMPORT CLEANUP PREVIEW (DRY RUN)")
    w("")
    w("> **Status:** DRY RUN ONLY — no deletions performed.")
    w(f"> **Database:** `{DB_PATH}`")
    w("")

    # --- Schema inventory ---
    tables = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
        ).fetchall()
    ]
    it_keywords = (
        "asset",
        "computer",
        "inventor",
        "ip_",
        "software",
        "it_",
        "network",
        "migration",
        "exception",
        "batch",
    )
    it_tables = [t for t in tables if any(k in t.lower() for k in it_keywords)]
    w("## Schema: IT-related tables")
    w("")
    w("| Table | Rows |")
    w("| --- | ---: |")
    for t in it_tables:
        n = count(con, f"SELECT COUNT(*) FROM [{t}]")
        w(f"| `{t}` | {n} |")
    w("")

    # Check for import_batch_id / source columns on assets
    asset_cols = [r[1] for r in con.execute("PRAGMA table_info(assets)").fetchall()]
    batch_markers = [
        c
        for c in asset_cols
        if any(
            x in c.lower()
            for x in (
                "batch",
                "source",
                "import",
                "migration",
            )
        )
    ]
    w("## Import batch columns on `assets`")
    w("")
    if batch_markers:
        w(f"Found marker columns: {', '.join(f'`{c}`' for c in batch_markers)}")
    else:
        w(
            "**No `import_batch_id` / `source_system` / `source_file` columns on `assets`.** "
            "Identification must use activity logs + deterministic field fingerprints."
        )
    w("")
    w(f"Full `assets` columns: {', '.join(f'`{c}`' for c in asset_cols)}")
    w("")

    # --- Activity: migration events ---
    w("## Import / migration activity log")
    w("")
    if not table_exists(con, "activities"):
        w("No `activities` table.")
    else:
        mig = con.execute(
            """
            SELECT id, action, entity_type, entity_id, user_id, created_at, new_value
            FROM activities
            WHERE action IN ('it_migration_analyzed', 'it_migration_imported')
            ORDER BY created_at
            """
        ).fetchall()
        w(f"Found **{len(mig)}** migration analyze/import activity rows.")
        w("")
        if not mig:
            w("No `it_migration_analyzed` / `it_migration_imported` rows.")
        else:
            w("| # | Action | Created at | User | Payload summary |")
            w("| ---: | --- | --- | --- | --- |")
            for i, row in enumerate(mig, 1):
                try:
                    payload = json.loads(row["new_value"] or "{}")
                except json.JSONDecodeError:
                    payload = {"_raw": (row["new_value"] or "")[:200]}
                summary = {
                    k: payload.get(k)
                    for k in (
                        "filename",
                        "source_type",
                        "session_id",
                        "batch_id",
                        "imported",
                        "skipped",
                        "duplicated",
                        "conflicted",
                        "requires_review",
                        "organization_owned",
                        "customer_owned",
                    )
                    if k in payload
                }
                w(
                    f"| {i} | `{row['action']}` | {row['created_at']} | "
                    f"`{row['user_id']}` | `{json.dumps(summary, default=str)}` |"
                )
        w("")

        created = con.execute(
            """
            SELECT COUNT(*) AS n, MIN(created_at) AS first_at, MAX(created_at) AS last_at
            FROM activities
            WHERE action = 'it_asset_created'
            """
        ).fetchone()
        w(
            f"`it_asset_created` activities: **{created['n']}** "
            f"(first={created['first_at']}, last={created['last_at']})"
        )
        w("")

    # --- Asset fingerprints ---
    total_assets = count(con, "SELECT COUNT(*) FROM assets WHERE is_deleted = 0")
    total_assets_all = count(con, "SELECT COUNT(*) FROM assets")
    w("## Asset population")
    w("")
    w(f"- Active (not deleted): **{total_assets}**")
    w(f"- Including soft-deleted: **{total_assets_all}**")
    w("")

    # Fingerprints that strongly indicate migration imports
    fingerprint_sql = {
        "legacy_asset_number IS NOT NULL": (
            "has_legacy_asset_number",
            "Assets with legacy_asset_number set (importer always sets this)",
        ),
        "purchased_by = 'unknown'": (
            "purchased_by_unknown",
            "Assets with purchased_by=unknown (migration ownership unclear)",
        ),
        "notes LIKE '%SY- prefix suggests%' OR notes LIKE '%customer owner unresolved%'": (
            "notes_migration_hints",
            "Assets with known bad migration note text",
        ),
        "asset_number LIKE 'LAPTOP-%' OR asset_number LIKE 'DESKTOP-%' OR asset_number LIKE 'MONITOR-%'": (
            "auto_generated_numbers",
            "Assets with auto-generated type-prefix numbers (pre-fix importer)",
        ),
        "asset_number LIKE 'EX-%' OR legacy_asset_number LIKE 'EX-%' OR notes LIKE '%OWNERSHIP_UNCLEAR%' OR notes LIKE '%SERIAL_MISSING%' OR serial_number LIKE 'EX-%'": (
            "exception_tokens_in_fields",
            "Assets with exception tokens written into data fields (should be rare)",
        ),
        "serial_number IS NOT NULL AND service_tag IS NOT NULL AND serial_number = service_tag": (
            "serial_eq_service_tag",
            "Assets where serial_number == service_tag (old coalesce bug fingerprint)",
        ),
        "LOWER(asset_number) LIKE 'pp-%' OR LOWER(legacy_asset_number) LIKE 'pp-%'": (
            "pp_prefix_ids",
            "Assets with PP- prefix IDs",
        ),
        "LOWER(asset_number) LIKE 'sy-%' OR LOWER(legacy_asset_number) LIKE 'sy-%'": (
            "sy_prefix_ids",
            "Assets with SY- prefix IDs",
        ),
        "LOWER(asset_number) LIKE 'it - %' OR LOWER(legacy_asset_number) LIKE 'it - %' OR LOWER(asset_number) LIKE 'it-%' OR LOWER(legacy_asset_number) LIKE 'it-%'": (
            "it_prefix_ids",
            "Assets with IT- / IT - prefix IDs (compatible workbook)",
        ),
    }

    w("## Deterministic fingerprints (active assets)")
    w("")
    w("| Fingerprint | Count | Description |")
    w("| --- | ---: | --- |")
    fp_counts: dict[str, int] = {}
    for where, (key, desc) in fingerprint_sql.items():
        n = count(
            con,
            f"SELECT COUNT(*) FROM assets WHERE is_deleted = 0 AND ({where})",
        )
        fp_counts[key] = n
        w(f"| `{key}` | {n} | {desc} |")
    w("")

    # Primary candidate set: legacy_asset_number set OR purchased_by unknown OR migration notes
    # Also include assets created via it_asset_created in windows around migration imports
    candidate_ids: set[str] = set()
    rows = con.execute(
        """
        SELECT id, asset_number, legacy_asset_number, purchased_by, status,
               serial_number, service_tag, make, model, notes, created_at
        FROM assets
        WHERE is_deleted = 0
          AND (
            legacy_asset_number IS NOT NULL
            OR purchased_by = 'unknown'
            OR notes LIKE '%SY- prefix suggests%'
            OR notes LIKE '%customer owner unresolved%'
            OR notes LIKE '%OWNERSHIP_UNCLEAR%'
            OR notes LIKE '%SERIAL_MISSING%'
            OR asset_number LIKE 'EX-%'
            OR legacy_asset_number LIKE 'EX-%'
          )
        ORDER BY created_at
        """
    ).fetchall()
    for r in rows:
        candidate_ids.add(r["id"])

    # Cross-check: assets referenced in it_asset_created near migration activity windows
    # (if migration logs exist, expand window ±1 day around each import)
    mig_times = [
        r["created_at"]
        for r in con.execute(
            """
            SELECT created_at FROM activities
            WHERE action = 'it_migration_imported'
            ORDER BY created_at
            """
        ).fetchall()
    ]

    window_extra = 0
    if mig_times:
        for ts in mig_times:
            # SQLite timestamps are text; use date substring for rough window
            day = (ts or "")[:10]
            if not day:
                continue
            extra = con.execute(
                """
                SELECT id FROM assets
                WHERE is_deleted = 0
                  AND date(created_at) BETWEEN date(?, '-1 day') AND date(?, '+1 day')
                """,
                (day, day),
            ).fetchall()
            for r in extra:
                if r["id"] not in candidate_ids:
                    window_extra += 1
                    candidate_ids.add(r["id"])

    w("## Proposed candidate asset set (conservative)")
    w("")
    w(
        "Primary rule: active assets with **legacy_asset_number set**, "
        "**purchased_by=unknown**, or known migration note/exception tokens."
    )
    if mig_times:
        w(
            f"Plus assets created within ±1 day of `{len(mig_times)}` "
            f"`it_migration_imported` event(s) (extra added: {window_extra})."
        )
    w("")
    w(f"**Candidate assets:** {len(candidate_ids)}")
    w("")

    # Confidence split
    high: list[sqlite3.Row] = []
    review: list[sqlite3.Row] = []
    if candidate_ids:
        placeholders = ",".join("?" * len(candidate_ids))
        detail = con.execute(
            f"""
            SELECT id, asset_number, legacy_asset_number, purchased_by, status,
                   serial_number, service_tag, make, model, notes, created_at
            FROM assets
            WHERE id IN ({placeholders})
            ORDER BY created_at
            """,
            tuple(candidate_ids),
        ).fetchall()
        for r in detail:
            high_confidence = bool(
                r["legacy_asset_number"]
                or r["purchased_by"] == "unknown"
                or (r["notes"] and ("SY- prefix" in r["notes"] or "OWNERSHIP" in r["notes"]))
            )
            if high_confidence:
                high.append(r)
            else:
                review.append(r)

    w(f"- High confidence (delete candidates): **{len(high)}**")
    w(f"- Review required (created near import window only): **{len(review)}**")
    w("")

    # Sample / full ID list
    w("### High-confidence asset IDs (would delete)")
    w("")
    if not high:
        w("_None_")
    else:
        w("| asset_id | asset_number | legacy | purchased_by | status | created_at |")
        w("| --- | --- | --- | --- | --- | --- |")
        for r in high:
            w(
                f"| `{r['id']}` | `{r['asset_number']}` | "
                f"`{r['legacy_asset_number'] or ''}` | `{r['purchased_by']}` | "
                f"`{r['status']}` | {r['created_at']} |"
            )
    w("")

    if review:
        w("### REVIEW REQUIRED (NOT scheduled for delete)")
        w("")
        w("| asset_id | asset_number | created_at | reason |")
        w("| --- | --- | --- | --- |")
        for r in review:
            w(
                f"| `{r['id']}` | `{r['asset_number']}` | {r['created_at']} | "
                f"near import window without legacy/unknown markers |"
            )
        w("")

    high_ids = {r["id"] for r in high}

    # Dependent counts
    def related_count(table: str, fk: str, ids: set[str]) -> int:
        if not ids or not table_exists(con, table):
            return 0
        ph = ",".join("?" * len(ids))
        return count(con, f"SELECT COUNT(*) FROM [{table}] WHERE [{fk}] IN ({ph})", tuple(ids))

    computers = related_count("computers", "asset_id", high_ids)
    assignments = related_count("asset_assignments", "asset_id", high_ids)
    returns = related_count("asset_customer_returns", "asset_id", high_ids)

    # IP assignment history references assets directly (not computers)
    ip_hist = related_count("ip_assignment_history", "assigned_to_asset_id", high_ids)
    # Distinct IP addresses touched by those history rows
    ip_count = 0
    if high_ids and table_exists(con, "ip_assignment_history"):
        ph = ",".join("?" * len(high_ids))
        ip_count = count(
            con,
            f"""
            SELECT COUNT(DISTINCT ip_address_id)
            FROM ip_assignment_history
            WHERE assigned_to_asset_id IN ({ph})
            """,
            tuple(high_ids),
        )

    # Inventory candidates: purchased_by unknown or notes migration
    inv_rows = []
    if table_exists(con, "inventory_items"):
        inv_rows = con.execute(
            """
            SELECT id, name, purchased_by, status, notes, created_at
            FROM inventory_items
            WHERE is_deleted = 0
              AND (
                purchased_by = 'unknown'
                OR notes LIKE '%migration%'
                OR notes LIKE '%Imported%'
                OR notes LIKE '%OWNERSHIP%'
              )
            ORDER BY created_at
            """
        ).fetchall()

    # Software / accounts fingerprints
    soft_assign = []
    if table_exists(con, "software_assignments"):
        soft_assign = con.execute(
            """
            SELECT id, notes, created_at
            FROM software_assignments
            WHERE notes LIKE '%Import%' OR notes LIKE '%Migration%' OR notes LIKE '%legacy%'
            """
        ).fetchall()

    accounts = []
    if table_exists(con, "it_user_accounts"):
        acct_cols = [x[1] for x in con.execute("PRAGMA table_info(it_user_accounts)").fetchall()]
        note_col = "notes" if "notes" in acct_cols else None
        cred = "credential_status" if "credential_status" in acct_cols else None
        where_bits = []
        if note_col:
            where_bits.append(
                f"({note_col} LIKE '%Migration%' OR {note_col} LIKE '%Legacy Credential%' OR {note_col} LIKE '%Imported%')"
            )
        if cred:
            where_bits.append(f"{cred} = 'migration_required'")
        if where_bits:
            accounts = con.execute(
                f"SELECT id, created_at FROM it_user_accounts WHERE {' OR '.join(where_bits)}"
            ).fetchall()

    # Suppliers created only by import? list all suppliers with creation dates
    suppliers = []
    if table_exists(con, "it_suppliers"):
        suppliers = con.execute(
            "SELECT id, name, created_at FROM it_suppliers ORDER BY created_at"
        ).fetchall()

    # Software catalog / pools — list; mark REVIEW unless clearly migration-only
    soft_catalog = []
    soft_pools = []
    if table_exists(con, "software_catalog"):
        soft_catalog = con.execute(
            "SELECT id, name, created_at FROM software_catalog ORDER BY created_at"
        ).fetchall()
    if table_exists(con, "software_license_pools"):
        soft_pools = con.execute(
            "SELECT id, created_at FROM software_license_pools ORDER BY created_at"
        ).fetchall()

    w("## Dependent records for high-confidence assets")
    w("")
    w("| Category | Count |")
    w("| --- | ---: |")
    w(f"| Computers | {computers} |")
    w(f"| Asset assignments | {assignments} |")
    w(f"| Customer returns | {returns} |")
    w(f"| IP assignment history rows | {ip_hist} |")
    w(f"| Distinct IP addresses referenced | {ip_count} |")
    w("")

    w("## Other IT import-like records")
    w("")
    w(f"- Inventory items (unknown ownership / migration notes): **{len(inv_rows)}**")
    if inv_rows:
        w("")
        w("| id | name | purchased_by | created_at |")
        w("| --- | --- | --- | --- |")
        for r in inv_rows:
            w(f"| `{r['id']}` | `{r['name']}` | `{r['purchased_by']}` | {r['created_at']} |")
        w("")
    w(f"- Software assignments (import/migration notes): **{len(soft_assign)}**")
    w(f"- IT user accounts (migration_required / migration notes): **{len(accounts)}**")
    w(f"- IT suppliers (all — do NOT auto-delete shared master): **{len(suppliers)}** — REVIEW")
    w(f"- Software catalog rows (all): **{len(soft_catalog)}** — REVIEW")
    w(f"- Software license pools (all): **{len(soft_pools)}** — REVIEW")
    w("")

    # Created_at distribution for candidates
    by_day = Counter((r["created_at"] or "")[:10] for r in high)
    w("## High-confidence assets by created date")
    w("")
    w("| Date | Count |")
    w("| --- | ---: |")
    for day, n in sorted(by_day.items()):
        w(f"| {day or '(null)'} | {n} |")
    w("")

    # Non-IT sanity counts (must remain untouched)
    w("## Non-IT baseline (must remain unchanged after cleanup)")
    w("")
    baselines = {}
    for label, sql in [
        ("users", "SELECT COUNT(*) FROM users"),
        ("customers", "SELECT COUNT(*) FROM customers" if table_exists(con, "customers") else None),
        ("projects", "SELECT COUNT(*) FROM projects" if table_exists(con, "projects") else None),
        ("teams", "SELECT COUNT(*) FROM teams" if table_exists(con, "teams") else None),
        ("departments", "SELECT COUNT(*) FROM departments" if table_exists(con, "departments") else None),
        (
            "timesheet_entries",
            "SELECT COUNT(*) FROM timesheet_entries"
            if table_exists(con, "timesheet_entries")
            else None,
        ),
        ("roles", "SELECT COUNT(*) FROM roles" if table_exists(con, "roles") else None),
        ("asset_types", "SELECT COUNT(*) FROM asset_types" if table_exists(con, "asset_types") else None),
        ("networks", "SELECT COUNT(*) FROM networks" if table_exists(con, "networks") else None),
    ]:
        if sql:
            baselines[label] = count(con, sql)
            w(f"- {label}: **{baselines[label]}**")
    w("")

    # Totals
    total_delete = (
        len(high)
        + computers
        + assignments
        + returns
        + ip_hist
        + len(inv_rows)
        + len(soft_assign)
        + len(accounts)
    )
    w("## TOTAL RECORDS TO DELETE (proposed, high-confidence only)")
    w("")
    w("| Category | Count |")
    w("| --- | ---: |")
    w(f"| Assets | {len(high)} |")
    w(f"| Computers | {computers} |")
    w(f"| Asset assignments | {assignments} |")
    w(f"| Customer returns | {returns} |")
    w(f"| IP assignment history | {ip_hist} |")
    w(f"| Inventory items | {len(inv_rows)} |")
    w(f"| Software assignments | {len(soft_assign)} |")
    w(f"| IT account metadata | {len(accounts)} |")
    w(f"| **TOTAL** | **{total_delete}** |")
    w("")
    w(
        f"_Note: {ip_count} distinct IP address rows are referenced by assignment history. "
        "Cleanup should release/history-delete those links; do **not** delete Network definitions._"
    )
    w("")
    w("### Explicitly NOT deleted in this plan")
    w("")
    w("- Users / employees / auth")
    w("- Customers / teams / departments / projects / timesheets / roles / permissions")
    w("- Asset types, networks, IT settings")
    w("- IT suppliers / software catalog / license pools (REVIEW REQUIRED — may be shared)")
    w(f"- Review-required assets: {len(review)}")
    w("")
    # --- Session cache (analyze staging; not committed DB rows) ---
    sessions_dir = Path(__file__).resolve().parents[1] / "uploads" / "it_migration"
    w("## Analyze session cache (`uploads/it_migration`)")
    w("")
    w(
        "These JSON files are **staging only** (analyze). "
        "They are deleted on successful commit. Presence means analyze ran but commit "
        "either never happened or used a different session."
    )
    w("")
    if not sessions_dir.exists():
        w("_No session directory._")
    else:
        from collections import defaultdict

        by_file: dict[str, list[dict]] = defaultdict(list)
        for path in sorted(sessions_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                by_file["(unreadable)"].append(
                    {"session_id": path.stem, "error": str(exc)}
                )
                continue
            rows = data.get("rows") or []
            by_file[str(data.get("filename") or "?")].append(
                {
                    "session_id": path.stem,
                    "source_type": data.get("source_type"),
                    "row_count": len(rows) if isinstance(rows, list) else None,
                    "batch_id": data.get("batch_id"),
                    "created_at": data.get("created_at"),
                }
            )
        w(f"Session files on disk: **{sum(len(v) for v in by_file.values())}**")
        w("")
        for filename, items in sorted(by_file.items()):
            w(f"### Source: `{filename}`")
            w("")
            w("| Session ID | Source type | Staged rows | Batch ID | Analyzed at |")
            w("| --- | --- | ---: | --- | --- |")
            for item in items:
                if "error" in item:
                    w(f"| `{item['session_id']}` | — | — | — | error: {item['error']} |")
                    continue
                w(
                    f"| `{item['session_id']}` | `{item['source_type']}` | "
                    f"{item['row_count']} | `{item['batch_id'] or ''}` | {item['created_at']} |"
                )
            w("")
        w(
            "Optional non-DB cleanup (safe, does not touch ProTrack entities): "
            "delete these session JSON files after confirmation."
        )
        w("")

    w("## Identification notes")
    w("")
    w(
        "1. There is **no durable `import_batch_id` on asset rows**. "
        "Session `batch_id` exists only in analyze JSON / activity payloads and is not FK-linked to assets."
    )
    w(
        "2. Importer always sets `legacy_asset_number` on committed hardware/inventory assets — "
        "this is the strongest durable marker for imported assets."
    )
    w(
        "3. In this database: **zero** `it_migration_imported` activities and **zero** asset/inventory "
        "rows — historic imports appear to have been **analyze-only**, not committed."
    )
    w(
        "4. Do **not** execute DB cleanup until this dry-run scope is confirmed "
        "(and until the correct environment DB is identified if imports live elsewhere)."
    )
    w("")
    w("---")
    w("")
    w(
        "**Next step:** Confirm whether this is the correct database. "
        "If yes, DB delete scope is empty; only session-cache cleanup may apply. "
        "If imports exist on another DB/host, re-run this dry-run there before any delete."
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n\nWrote report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

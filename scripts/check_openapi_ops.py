from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

schema = app.openapi()
raw = json.dumps(schema)

operation_ids: list[str] = []
for path, methods in schema["paths"].items():
    for method, detail in methods.items():
        if method.startswith("x-"):
            continue
        op_id = detail.get("operationId")
        if op_id:
            operation_ids.append(op_id)

counts = Counter(operation_ids)
dupes = [op for op, n in counts.items() if n > 1]
print("duplicate operationIds:", dupes or "none")

# Validate JSON round-trip
json.loads(raw)
print("json round-trip: OK")
print("bytes:", len(raw))

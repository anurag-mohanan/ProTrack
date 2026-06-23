import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def find_ref_siblings(obj, path=""):
    if isinstance(obj, dict):
        if "$ref" in obj and len(obj) > 1:
            print("ref+siblings at", path, json.dumps(obj))
        for key, value in obj.items():
            find_ref_siblings(value, f"{path}/{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            find_ref_siblings(value, f"{path}[{index}]")


find_ref_siblings(app.openapi())

"""Prints the status and exception of every item seeded by uipath_seed.py."""
import json

from processpilot.config import ROOT
from processpilot.tools.uipath_client import get_queue_item_status

ids = json.loads((ROOT / "data" / "seeded_items.json").read_text(encoding="utf-8"))
for mode, item_id in ids.items():
    s = get_queue_item_status(item_id)
    exc = s["exception"] or {}
    print(f"{mode:14} {s['reference']:8} status={s['status']:10} retries={s['retries']} "
          f"type={exc.get('Type')} reason={str(exc.get('Reason'))[:80]}")
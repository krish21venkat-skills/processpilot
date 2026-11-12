"""Adds one queue item per failure switch and saves their ids (Stage 4B test)."""
import json

from processpilot.config import ROOT
from processpilot.tools.invoice_store import get_invoice
from processpilot.tools.uipath_client import add_queue_item

CASES = [
    ("INV-201", "bad_date"),
    ("INV-205", "missing_field"),
    ("INV-207", "duplicate"),
    ("INV-208", "app_timeout"),
]

ids = {}
for invoice_id, mode in CASES:
    item_id = add_queue_item(get_invoice(invoice_id), simulate_failure=mode)
    ids[mode] = item_id
    print(f"{invoice_id:8} {mode:14} -> queue item {item_id}")

(ROOT / "data" / "seeded_items.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")
"""Stage 5A check: print the failure report for each item seeded in Stage 4."""
import json

from processpilot.config import ROOT
from processpilot.tools.evidence import gather
from processpilot.tools.uipath_client import get_queue_item_status

ids = json.loads((ROOT / "data" / "seeded_items.json").read_text(encoding="utf-8"))
for mode, item_id in ids.items():
    ref = get_queue_item_status(item_id)["reference"]
    r = gather(ref, item_id)
    print(f"\n=== {mode}: {r.invoice_id} | status={r.status} type={r.exc_type}")
    print(f"reason: {r.reason}")
    print(f"log lines found: {len(r.logs)}")
    for line in r.logs[-5:]:
        print("   ", line)
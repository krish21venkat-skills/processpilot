"""Stage 5 check: submit one failing item, wait for it, print the evidence the agent would see."""
import time

from processpilot.tools.evidence import gather
from processpilot.tools.invoice_store import get_invoice
from processpilot.tools.uipath_client import add_queue_item, get_queue_item_status

item_id = add_queue_item(get_invoice("INV-204"), simulate_failure="missing_field")
print("queue item", item_id, "- waiting for the bot...")
for _ in range(40):
    if get_queue_item_status(item_id)["status"] in ("Failed", "Successful"):
        break
    time.sleep(5)
time.sleep(5)  # let the last log lines arrive
r = gather("INV-204", item_id)
print(r.status, "|", r.reason)
print("\n".join(r.logs) or "(no log lines)")
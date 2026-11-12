"""Stage 4A smoke test: add a queue item and read it back."""
from processpilot.tools.invoice_store import get_invoice
from processpilot.tools.uipath_client import add_queue_item, get_queue_item_status

item_id = add_queue_item(get_invoice("INV-204"))
print("Added queue item:", item_id)
print(get_queue_item_status(item_id))
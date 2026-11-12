"""Read-only access to the synthetic invoice data."""
import json
from functools import lru_cache

from processpilot import config

INVOICE_FILE = config.ROOT / "data" / "invoices.json"


@lru_cache(maxsize=1)
def _all() -> list[dict]:
    return json.loads(INVOICE_FILE.read_text(encoding="utf-8"))


def get_invoice(invoice_id: str) -> dict | None:
    return next((i for i in _all() if i["invoice_id"] == invoice_id.upper()), None)


def find_exact_duplicates(inv: dict) -> list[str]:
    """Earlier invoices with the same vendor and invoice number (POL-02 §1.1)."""
    return [
        i["invoice_id"] for i in _all()
        if i["invoice_id"] != inv["invoice_id"]
        and i["vendor_id"] == inv["vendor_id"]
        and i["invoice_number"] == inv["invoice_number"]
        and i["invoice_date"] <= inv["invoice_date"]
    ]
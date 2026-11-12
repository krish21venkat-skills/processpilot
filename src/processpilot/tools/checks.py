"""Deterministic invoice checks. Facts come from code, never from the LLM."""
from dataclasses import dataclass
from datetime import date

from processpilot.tools.invoice_store import find_exact_duplicates

PERMITTED_RATES = {0.05, 0.12, 0.18, 0.28}
ROLES = ["AP Executive", "Finance Manager", "Finance Controller", "CFO"]  # ascending grade


@dataclass
class Finding:
    code: str
    message: str
    cite: str    # section level, e.g. "POL-02 §2"
    action: str  # REJECT | SEND_BACK | NOTE


def approver_for(total: float) -> str:
    """POL-01 §2 approval limits."""
    if total <= 25_000:
        return "AP Executive"
    if total <= 2_00_000:
        return "Finance Manager"
    if total <= 10_00_000:
        return "Finance Controller"
    return "CFO"


def run_checks(inv: dict, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    f: list[Finding] = []

    if dups := find_exact_duplicates(inv):
        f.append(Finding("DUPLICATE", f"Exact duplicate of {', '.join(dups)} (same vendor and invoice number).",
                         "POL-02 §2", "REJECT"))
    if inv["vendor_status"] != "Active":
        f.append(Finding("VENDOR_STATUS", f"Vendor status is {inv['vendor_status']}, not Active.",
                         "POL-03 §1", "REJECT"))

    inv_date = date.fromisoformat(inv["invoice_date"])
    if inv_date > today:
        f.append(Finding("FUTURE_DATE", f"Invoice is dated in the future ({inv['invoice_date']}).",
                         "POL-05 §3", "REJECT"))
    elif (today - inv_date).days > 90:
        f.append(Finding("OLD_INVOICE", "Invoice is older than 90 days and needs Finance Manager approval.",
                         "POL-05 §3", "NOTE"))

    if inv["total"] > 50_000 and not inv.get("po_number"):
        f.append(Finding("PO_MISSING", f"Total INR {inv['total']:,.0f} is above 50,000 but no PO is referenced.",
                         "POL-05 §1", "SEND_BACK"))

    if len(inv["vendor_gstin"]) != 15:
        f.append(Finding("GSTIN_FORMAT", "Vendor GSTIN is not 15 characters.", "POL-04 §1", "SEND_BACK"))

    expected = "CGST_SGST" if inv["supplier_state"] == inv["buyer_state"] else "IGST"
    if inv["tax_type"] != expected:
        f.append(Finding("TAX_TYPE", f"Supplier in {inv['supplier_state']} and buyer in {inv['buyer_state']} "
                         f"require {expected}, but invoice charges {inv['tax_type']}.", "POL-04 §2", "SEND_BACK"))

    if round(inv["gst_rate"], 2) not in PERMITTED_RATES:
        f.append(Finding("GST_RATE", f"GST rate {inv['gst_rate']:.0%} is not permitted.", "POL-04 §3", "SEND_BACK"))
    elif abs(inv["subtotal"] * inv["gst_rate"] - inv["tax_amount"]) > 1:
        f.append(Finding("TAX_CALC", "Invoiced tax differs from the calculated tax by more than INR 1.",
                         "POL-04 §3", "SEND_BACK"))
    return f
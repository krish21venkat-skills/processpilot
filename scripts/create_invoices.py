"""Writes 8 synthetic invoices to data/invoices.json. Dates are relative to today."""
import json
from datetime import date, timedelta
from pathlib import Path

TODAY = date.today()


def d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


def inv(invoice_id, vendor_id, vendor_name, vendor_status, number, days_ago, subtotal,
        po, entered_by, category, supplier_state="TN", buyer_state="TN", tax_type=None):
    tax_type = tax_type or ("CGST_SGST" if supplier_state == buyer_state else "IGST")
    tax = round(subtotal * 0.18, 2)
    return {
        "invoice_id": invoice_id, "vendor_id": vendor_id, "vendor_name": vendor_name,
        "vendor_status": vendor_status, "vendor_gstin": f"33AAAAA{vendor_id[-4:]}A1Z5",
        "invoice_number": number, "invoice_date": d(days_ago), "category": category,
        "po_number": po, "entered_by": entered_by,
        "supplier_state": supplier_state, "buyer_state": buyer_state,
        "subtotal": subtotal, "gst_rate": 0.18, "tax_type": tax_type,
        "tax_amount": tax, "total": round(subtotal + tax, 2),
    }


INVOICES = [
    inv("INV-201", "V-1001", "Kaveri Office Supplies", "Active", "KOS/2026/0451", 12, 15000, None, "u.anand", "office_supplies"),
    inv("INV-202", "V-1002", "Madurai Industrial Tools", "Active", "MIT-7781", 20, 300000, "PO-5001", "u.priya", "capex"),
    inv("INV-203", "V-1001", "Kaveri Office Supplies", "Active", "KOS/2026/0451", 3, 15000, None, "u.anand", "office_supplies"),
    inv("INV-204", "V-1003", "Chola IT Services", "Active", "CIS-2026-118", 8, 100000, "PO-5002", "u.priya", "services"),
    inv("INV-205", "V-1004", "Pallava Logistics", "Pending", "PL/889", 6, 40000, "PO-5003", "u.anand", "logistics"),
    inv("INV-206", "V-1005", "Pandya Packaging", "Active", "PP-2210", -15, 60000, "PO-5004", "u.priya", "packaging"),
    inv("INV-207", "V-1006", "Nilgiri Facility Mgmt", "Active", "NFM-3340", 10, 72000, None, "u.anand", "services"),
    inv("INV-208", "V-1007", "Deccan Hardware", "Active", "DH-5512", 9, 90000, "PO-5005", "u.priya", "hardware",
        supplier_state="KA", buyer_state="TN", tax_type="CGST_SGST"),
]

if __name__ == "__main__":
    out = Path("data/invoices.json")
    out.write_text(json.dumps(INVOICES, indent=2), encoding="utf-8")
    print(f"Wrote {len(INVOICES)} invoices to {out}")
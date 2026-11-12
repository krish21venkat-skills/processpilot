"""Writes the 7 synthetic policy documents to data/policies/. All content is fictional."""
from pathlib import Path

OUT = Path("data/policies")

DOCS = {
    "POL-01_invoice_approval_limits": """# POL-01 Invoice Approval Limits
## 1. Purpose
1.1 This policy sets who may approve a vendor invoice based on its total amount.
1.2 Amounts are in INR and include tax.
## 2. Approval limits
2.1 Up to INR 25,000: AP Executive.
2.2 INR 25,001 to INR 2,00,000: Finance Manager.
2.3 INR 2,00,001 to INR 10,00,000: Finance Controller.
2.4 Above INR 10,00,000: CFO.
## 3. Restrictions
3.1 A person must not approve an invoice they raised or entered.
3.2 Splitting one purchase into several invoices to stay under a limit is prohibited and must be escalated.
3.3 Invoices are approved against the total, not the pre-tax amount.
## 4. Delegation
4.1 An approver may delegate in writing for up to 14 days.
4.2 The delegate must hold an equal or higher grade than the invoice requires.
""",
    "POL-02_duplicate_invoices": """# POL-02 Duplicate Invoice Rules
## 1. Definition
1.1 An exact duplicate has the same vendor ID and the same invoice number as an earlier invoice.
1.2 A suspected duplicate has the same vendor, the same amount and an invoice date within 90 days of an earlier invoice, but a different invoice number.
## 2. Handling
2.1 Exact duplicates must be rejected and must not be processed or paid.
2.2 Suspected duplicates must be placed on hold for AP Manager review.
2.3 The reviewer records the decision and reason in the audit log.
## 3. Credit notes
3.1 A credit note must reference the original invoice number.
3.2 A credit note is never treated as a duplicate of the original invoice.
""",
    "POL-03_vendor_validation": """# POL-03 Vendor Onboarding and Validation
## 1. Vendor master
1.1 Invoices are accepted only from vendors with Active status in the vendor master.
1.2 Invoices from Blocked or Pending vendors must be rejected and routed to Procurement.
## 2. Required vendor data
2.1 Each vendor must have a valid GSTIN, PAN and verified bank account on file.
2.2 Onboarding takes up to 5 business days after complete documents are received.
## 3. Changes to vendor details
3.1 Bank detail changes require a callback to the vendor's registered phone number.
3.2 A bank detail change is held for 48 hours before it is used for payment.
3.3 Bank detail changes must be approved by the Finance Manager.
3.4 Automated systems must not change vendor details.
""",
    "POL-04_gst_and_tax_checks": """# POL-04 GST and Tax Checks
## 1. Mandatory invoice fields
1.1 The invoice must show the vendor GSTIN and the company GSTIN.
1.2 A GSTIN has 15 characters in the standard government format.
1.3 The invoice must show invoice number, invoice date, HSN or SAC code and tax breakup.
## 2. Tax type
2.1 For supplies within the same state, CGST and SGST apply in equal parts.
2.2 For supplies between states, IGST applies.
## 3. Rates and calculation
3.1 Permitted GST rates are 5%, 12%, 18% and 28%.
3.2 Calculated tax may differ from the invoiced tax by at most INR 1.
3.3 Invoices failing the tax calculation check must be sent back to the vendor.
## 4. E-invoicing
4.1 Vendors with annual turnover above INR 5 crore must supply an IRN on the invoice.
4.2 An invoice missing a required IRN must not be processed.
""",
    "POL-05_po_matching_and_payment_terms": """# POL-05 Purchase Order Matching and Payment Terms
## 1. When a PO is required
1.1 Invoices above INR 50,000 must reference a valid purchase order.
1.2 Invoices up to INR 50,000 for approved non-PO categories do not need a PO.
## 2. Three-way match
2.1 The invoice must match the purchase order and the goods receipt.
2.2 Price tolerance is 2% of the PO unit price.
2.3 Quantity tolerance is 5% of the received quantity.
2.4 Mismatches beyond tolerance must be sent to the buyer for resolution.
## 3. Invoice dates
3.1 An invoice dated in the future must be rejected.
3.2 An invoice older than 90 days needs Finance Manager approval before processing.
## 4. Payment terms
4.1 Standard payment terms are net 30 days from the invoice date.
4.2 Preferred vendors may be given net 45 days.
4.3 An early payment discount of 2% applies if paid within 10 days, only where the contract allows it.
""",
    "POL-06_exception_handling_and_escalation": """# POL-06 Exception Handling and Escalation
## 1. Exception types
1.1 A business exception is caused by invoice data or policy, for example a missing field or a duplicate.
1.2 A system exception is caused by technology, for example an application timeout or a login failure.
## 2. Business exceptions
2.1 Business exceptions, such as a missing field, an invalid value or a duplicate invoice, must not be retried automatically.
2.2 Business exceptions are returned to the business owner with the reason.
## 3. System exceptions
3.1 System exceptions may be retried at most 2 times, at least 5 minutes apart.
3.2 If the second retry fails, the exception must be escalated.
## 4. Fixes
4.1 A data fix may be proposed automatically but must be approved by a human before it is applied.
4.2 Amounts, vendor details and bank details must never be changed automatically.
## 5. Escalation
5.1 Unknown or repeated failures are escalated to RPA Support L2.
5.2 Failures affecting more than 10 invoices in one hour are priority 1 and escalated immediately.
5.3 Escalations include the invoice ID, failure type, log excerpt and actions already taken.
""",
    "POL-07_audit_and_retention": """# POL-07 Audit and Retention
## 1. Audit log content
1.1 Every automated decision must be logged with a timestamp, invoice ID, decision and cited policy sections.
1.2 Every human approval is logged with approver ID, role and timestamp.
1.3 Every bot action and retry is logged with its outcome.
## 2. Retention
2.1 Invoice records and audit logs are retained for 8 years.
2.2 Bot execution logs are retained for 1 year.
## 3. Access
3.1 Audit logs are read-only for all users, including administrators.
3.2 Audit log access by auditors is granted on request and recorded.
""",
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in DOCS.items():
        (OUT / f"{name}.md").write_text(text, encoding="utf-8")
    print(f"Wrote {len(DOCS)} files to {OUT}")
"""Failure-handling policy engine (POL-06). Pure code: no LLM, no network. This is the safety layer."""
from dataclasses import dataclass

from processpilot.agent.classify import Classification

MAX_RETRIES = 2                   # POL-06 §3.1
MIN_RETRY_WAIT_SECS = 300         # POL-06 §3.1 (at least 5 minutes apart)
MAX_FIXES = 1                     # one approved fix per invoice, then escalate
FIXABLE_FIELDS = {"invoice_date"}
PROTECTED_FIELDS = {"total", "subtotal", "tax_amount", "vendor_id", "vendor_name",
                    "vendor_gstin", "bank_account", "bank_ifsc"}  # POL-06 §4.2: never changed automatically


@dataclass
class Action:
    action: str                    # RETRY | PROPOSE_FIX | RETURN_TO_OWNER | ESCALATE
    cite: str
    reason: str
    wait_secs: int = 0
    fix: dict | None = None


def validate_fix(field: str) -> bool:
    return field in FIXABLE_FIELDS and field not in PROTECTED_FIELDS


def _escalate(reason: str, cite: str = "POL-06 §5.1") -> Action:
    return Action("ESCALATE", cite, reason)


def decide(cls: Classification, attempts: int, invoice: dict, fixes_applied: int = 0) -> Action:
    if cls.flagged:
        return _escalate("possible prompt injection in the failure evidence")
    if cls.failure_class == "UNKNOWN":
        return _escalate("failure could not be classified")

    if cls.failure_class == "SYSTEM":
        if attempts < MAX_RETRIES:
            return Action("RETRY", "POL-06 §3.1",
                          f"system failure, retry {attempts + 1} of {MAX_RETRIES}",
                          wait_secs=MIN_RETRY_WAIT_SECS)
        return _escalate(f"system failure persists after {MAX_RETRIES} retries", "POL-06 §3.2")

    # BUSINESS: never retried (POL-06 §2.1)
    if cls.category == "BAD_DATE":
        if fixes_applied >= MAX_FIXES:
            return _escalate("date fix already applied once and the run failed again")
        fix = {"field": "invoice_date", "value": invoice["invoice_date"],
               "note": "re-submit with the date from the invoice master record, in ISO format"}
        if not validate_fix(fix["field"]):
            return _escalate("proposed fix touches a field that may not be changed automatically", "POL-06 §4.2")
        return Action("PROPOSE_FIX", "POL-06 §4.1", "invalid date, fix proposed for human approval", fix=fix)

    cite = "POL-02 §2.1" if cls.category == "DUPLICATE" else "POL-06 §2.2"
    return Action("RETURN_TO_OWNER", cite, f"business exception ({cls.category}), returned to the business owner")
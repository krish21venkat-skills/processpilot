import pytest

from processpilot.agent.classify import Classification
from processpilot.agent.policy import decide, validate_fix

INV = {"invoice_id": "INV-204", "invoice_date": "2026-11-01"}


def cls(failure_class, category, flagged=False):
    return Classification(failure_class, category, "test", "test", flagged)


@pytest.mark.parametrize("attempts", [0, 1])
def test_system_failure_retries_with_five_minute_wait(attempts):
    a = decide(cls("SYSTEM", "APP_TIMEOUT"), attempts, INV)
    assert a.action == "RETRY" and a.wait_secs == 300


def test_system_failure_escalates_after_retry_cap():
    a = decide(cls("SYSTEM", "APP_TIMEOUT"), 2, INV)
    assert a.action == "ESCALATE" and a.cite == "POL-06 §3.2"


def test_bad_date_proposes_a_fix_for_approval():
    a = decide(cls("BUSINESS", "BAD_DATE"), 0, INV)
    assert a.action == "PROPOSE_FIX" and a.fix["field"] == "invoice_date"


def test_second_bad_date_failure_escalates():
    assert decide(cls("BUSINESS", "BAD_DATE"), 0, INV, fixes_applied=1).action == "ESCALATE"


def test_missing_field_is_returned_to_owner():
    assert decide(cls("BUSINESS", "MISSING_FIELD"), 0, INV).action == "RETURN_TO_OWNER"


def test_duplicate_is_returned_to_owner():
    a = decide(cls("BUSINESS", "DUPLICATE"), 0, INV)
    assert a.action == "RETURN_TO_OWNER" and a.cite == "POL-02 §2.1"


def test_unknown_failure_escalates():
    assert decide(cls("UNKNOWN", "OTHER"), 0, INV).action == "ESCALATE"


def test_flagged_evidence_escalates_whatever_the_class():
    assert decide(cls("SYSTEM", "APP_TIMEOUT", flagged=True), 0, INV).action == "ESCALATE"


@pytest.mark.parametrize("category", ["BAD_DATE", "MISSING_FIELD", "DUPLICATE"])
def test_business_failures_are_never_retried(category):
    for attempts in (0, 1, 2):
        assert decide(cls("BUSINESS", category), attempts, INV).action != "RETRY"


@pytest.mark.parametrize("field,allowed", [
    ("invoice_date", True), ("total", False), ("vendor_name", False),
    ("bank_account", False), ("po_number", False),
])
def test_only_allowlisted_fields_can_be_fixed(field, allowed):
    assert validate_fix(field) is allowed


def test_misclassified_injection_still_cannot_change_data():
    """The earlier LLM mistake (selector error called MISSING_FIELD) ends in a harmless action."""
    a = decide(cls("BUSINESS", "MISSING_FIELD"), 0, INV)
    assert a.action == "RETURN_TO_OWNER" and a.fix is None
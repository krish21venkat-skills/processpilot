from typing import TypedDict


class AgentState(TypedDict, total=False):
    request: str
    invoice_id: str
    invoice: dict
    findings: list[dict]
    approver_role: str
    clauses: list[dict]      # [{"cite": "POL-01 §2", "text": ...}]
    verdict: dict            # raw LLM output
    citations_valid: bool
    llm_agrees: bool
    decision: str            # COMPLIANT | NOT_COMPLIANT
    action: str              # PROCESS | REJECT | SEND_BACK
    answer: str
    trace: list[str]
    approval: dict           # {"status": APPROVED|REJECTED|DENIED, "by", "role", "reason"}
    job: dict                # result of the latest bot run
    simulate_failure: str    # none | bad_date | missing_field | duplicate | app_timeout | app_timeout_once
    queue_item_id: int
    submitted_date: str      # invoice_date value sent to the bot in the latest submission
    attempts: int            # retries already made by the agent
    fixes_applied: int
    diagnosis: dict          # classifier output plus evidence summary
    exc_action: dict         # the policy engine's decision
    fix_decision: dict       # human decision on a proposed fix
    actions_taken: list[str]
    failure_outcome: str     # RETURNED | ESCALATED | FIX_NOT_APPLIED
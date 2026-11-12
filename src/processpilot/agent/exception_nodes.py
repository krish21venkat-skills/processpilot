"""Exception-handling nodes: diagnose a failed bot run, then retry / fix / return / escalate (POL-06)."""
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone

from langgraph.types import interrupt

from processpilot import config
from processpilot.agent.classify import classify_llm
from processpilot.agent.policy import decide, validate_fix
from processpilot.agent.state import AgentState
from processpilot.tools import audit
from processpilot.tools.checks import ROLES
from processpilot.tools.evidence import gather

ESCALATION_FILE = config.ROOT / "data" / "escalations.jsonl"


def _t(state: AgentState, msg: str) -> list[str]:
    return state.get("trace", []) + [msg]


def route_after_wait(state: AgentState) -> str:
    return "diagnose" if state["job"]["status"] == "Failed" else "respond"


def route_after_diagnose(state: AgentState) -> str:
    action = state["exc_action"]["action"]
    return {"RETRY": "retry", "PROPOSE_FIX": "fix_approval"}.get(action, "finish_failure")


def route_after_fix_approval(state: AgentState) -> str:
    return "apply_fix" if state["fix_decision"]["status"] == "APPROVED" else "finish_failure"


def diagnose(state: AgentState) -> dict:
    inv_id, attempts = state["invoice_id"], state.get("attempts", 0)
    report = gather(inv_id, state["queue_item_id"], attempts)
    cls = classify_llm(report)
    act = decide(cls, attempts, state["invoice"], state.get("fixes_applied", 0))
    diagnosis = {"failure_class": cls.failure_class, "category": cls.category, "rationale": cls.rationale,
                 "flagged": cls.flagged, "reason": report.reason, "log_excerpt": report.logs[-5:]}
    audit.log(inv_id, "FAILURE_DIAGNOSED", {"queue_item_id": state["queue_item_id"],
              **{k: diagnosis[k] for k in ("reason", "failure_class", "category", "flagged", "rationale")}})
    audit.log(inv_id, f"ACTION_{act.action}", {"policy": act.cite, "reason": act.reason, "attempts": attempts})
    print(f"  diagnosed: {cls.failure_class}/{cls.category} -> {act.action}", flush=True)
    return {"diagnosis": diagnosis, "exc_action": asdict(act),
            "trace": _t(state, f"diagnose: {cls.failure_class}/{cls.category} -> {act.action} (attempts={attempts})")}


def retry(state: AgentState) -> dict:
    act, attempts = state["exc_action"], state.get("attempts", 0) + 1
    policy_min = act["wait_secs"]
    wait = int(os.getenv("RETRY_WAIT_SECS", policy_min))
    note = f" (demo shortcut; policy minimum is {policy_min}s)" if wait < policy_min else ""
    print(f"  retry {attempts}: waiting {wait}s{note}", flush=True)
    time.sleep(wait)
    audit.log(state["invoice_id"], "RETRY_SCHEDULED",
              {"attempt": attempts, "waited_secs": wait, "policy_min_secs": policy_min})
    return {"attempts": attempts, "actions_taken": state.get("actions_taken", []) + [f"retry {attempts}"],
            "trace": _t(state, f"retry: attempt {attempts} after {wait}s")}


def fix_approval(state: AgentState) -> dict:
    """Pauses until a human approves or rejects the proposed fix. Keep this node side-effect free before interrupt()."""
    inv, fix = state["invoice"], state["exc_action"]["fix"]
    reply = interrupt({
        "kind": "FIX", "invoice_id": inv["invoice_id"], "vendor": inv["vendor_name"], "total": inv["total"],
        "required_role": "AP Executive",
        "summary": (f"Proposed fix: set {fix['field']} from '{state.get('submitted_date')}' to '{fix['value']}' "
                    f"({fix['note']}). Amounts, vendor and bank details are not touched [POL-06 §4.2]."),
    })
    by, role = reply.get("by", ""), reply.get("role", "")
    if not reply.get("approve"):
        status, reason = "REJECTED", reply.get("reason") or "fix rejected by approver"
    elif by == inv["entered_by"]:
        status, reason = "DENIED", "approver entered this invoice [POL-01 §3.1]"
    elif role not in ROLES:
        status, reason = "DENIED", f"unknown role '{role}'"
    else:
        status, reason = "APPROVED", ""
    audit.log(inv["invoice_id"], f"FIX_APPROVAL_{status}", {"by": by, "role": role, "reason": reason, "fix": fix})
    return {"fix_decision": {"status": status, "by": by, "role": role, "reason": reason},
            "trace": _t(state, f"fix_approval: {status} by {by or '-'}")}


def apply_fix(state: AgentState) -> dict:
    fix = state["exc_action"]["fix"]
    if not validate_fix(fix["field"]):  # defence in depth: the policy engine already checked this
        raise ValueError(f"fix on field '{fix['field']}' is not allowed [POL-06 §4.2]")
    before = state.get("submitted_date")
    inv = {**state["invoice"], fix["field"]: fix["value"]}
    audit.log(state["invoice_id"], "FIX_APPLIED", {"field": fix["field"], "before": before,
              "after": fix["value"], "approved_by": state["fix_decision"]["by"]})
    return {"invoice": inv, "fixes_applied": state.get("fixes_applied", 0) + 1,
            "actions_taken": state.get("actions_taken", []) + [f"fix applied: {fix['field']}"],
            "trace": _t(state, f"apply_fix: {fix['field']} {before} -> {fix['value']}")}


def finish_failure(state: AgentState) -> dict:
    act, d, inv_id = state["exc_action"], state["diagnosis"], state["invoice_id"]
    if act["action"] == "ESCALATE":
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "invoice_id": inv_id,
                  "queue_item_id": state["queue_item_id"], "escalate_to": "RPA Support L2",
                  "failure_class": d["failure_class"], "category": d["category"], "reason": d["reason"],
                  "log_excerpt": d["log_excerpt"], "actions_taken": state.get("actions_taken", []),
                  "policy": act["cite"], "why": act["reason"]}  # contents required by POL-06 §5.3
        with open(ESCALATION_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        audit.log(inv_id, "ESCALATED", {"to": "RPA Support L2", "why": act["reason"]})
        outcome = "ESCALATED"
    elif act["action"] == "RETURN_TO_OWNER":
        audit.log(inv_id, "RETURNED_TO_OWNER", {"category": d["category"], "reason": d["reason"]})
        outcome = "RETURNED"
    else:  # PROPOSE_FIX reaches here only when the fix was rejected or denied
        fd = state.get("fix_decision", {})
        audit.log(inv_id, "FIX_NOT_APPLIED", {"status": fd.get("status"), "reason": fd.get("reason")})
        outcome = "FIX_NOT_APPLIED"
    return {"failure_outcome": outcome, "trace": _t(state, f"finish: {outcome}")}


def failure_summary(state: AgentState) -> str:
    act, d = state["exc_action"], state["diagnosis"]
    taken = ", ".join(state.get("actions_taken", [])) or "none"
    text = (f"Bot run failed: {d['reason']}\n"
            f"Diagnosis: {d['failure_class']}/{d['category']}. Action: {act['action']} [{act['cite']}] - "
            f"{act['reason']}. Earlier actions: {taken}.")
    outcome = state.get("failure_outcome")
    if outcome == "ESCALATED":
        text += "\nEscalated to RPA Support L2 (record saved in data/escalations.jsonl)."
    elif outcome == "RETURNED":
        text += "\nReturned to the business owner with the reason; not retried."
    elif outcome == "FIX_NOT_APPLIED":
        fd = state.get("fix_decision", {})
        text += f"\nProposed fix not applied ({fd.get('status')}: {fd.get('reason')}); nothing was changed."
    return text
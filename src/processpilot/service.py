"""Service layer: the single entry point for the CLI and the MCP server. No policy rules are duplicated outside the agent."""
import re
import uuid
from functools import lru_cache

from langgraph.types import Command

from processpilot.agent.main_graph import build

SIMULATE = ["none", "bad_date", "missing_field", "duplicate", "app_timeout", "app_timeout_once"]


@lru_cache(maxsize=1)
def _graph():
    return build()


def _cfg(tid: str) -> dict:
    return {"configurable": {"thread_id": tid}, "recursion_limit": 60}


def _outcome(v: dict) -> str:
    if v.get("job", {}).get("status") == "Successful":
        return "SUCCESS"
    if v.get("failure_outcome"):
        return v["failure_outcome"]
    if v.get("decision") == "NOT_COMPLIANT":
        return "NOT_COMPLIANT"
    if v.get("approval", {}).get("status") not in (None, "APPROVED"):
        return f"APPROVAL_{v['approval']['status']}"
    return "NO_RESULT"


def get_status(thread_id: str) -> dict:
    snap = _graph().get_state(_cfg(thread_id))
    v = snap.values
    if not v:
        return {"thread_id": thread_id, "stage": "NOT_FOUND"}
    out = {"thread_id": thread_id, "invoice_id": v.get("invoice_id"), "queue_item_id": v.get("queue_item_id"),
           "attempts": v.get("attempts", 0), "fixes_applied": v.get("fixes_applied", 0)}
    if v.get("diagnosis"):
        d = v["diagnosis"]
        out["diagnosis"] = {"class": d["failure_class"], "category": d["category"], "reason": d["reason"],
                            "action": v.get("exc_action", {}).get("action")}
    if snap.next:
        interrupts = [i for t in snap.tasks for i in t.interrupts]
        if interrupts:
            p = interrupts[0].value
            out["stage"] = "AWAITING_FIX_APPROVAL" if p.get("kind") == "FIX" else "AWAITING_APPROVAL"
            out["pending"] = {"kind": p.get("kind", "INVOICE"), "invoice_id": p["invoice_id"],
                              "vendor": p["vendor"], "total": p["total"],
                              "required_role": p["required_role"], "summary": p["summary"]}
        else:
            out["stage"] = "IN_PROGRESS"
    else:
        out["stage"] = "COMPLETED"
        out["outcome"] = _outcome(v)
        out["answer"] = v.get("answer", "")
    return out


def start_request(request: str, simulate: str = "none", request_id: str | None = None) -> dict:
    """Start the agent. It runs until the human approval gate. The same request_id never starts a second run."""
    if simulate not in SIMULATE:
        raise ValueError(f"simulate must be one of {SIMULATE}")
    if request_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", request_id):
        raise ValueError("request_id must be 1-40 characters: letters, digits, '-' or '_'")
    tid = request_id or uuid.uuid4().hex[:8]
    if _graph().get_state(_cfg(tid)).values:
        return {**get_status(tid), "duplicate_request": True}
    _graph().invoke({"request": request, "simulate_failure": simulate}, _cfg(tid))
    return get_status(tid)


def submit_decision(thread_id: str, by: str, role: str, approve: bool = True, reason: str = "") -> dict:
    """Human decision at an approval gate. Deliberately NOT exposed as an MCP tool."""
    stage = get_status(thread_id)["stage"]
    if not stage.startswith("AWAITING"):
        raise ValueError(f"thread {thread_id} is {stage}; nothing to approve")
    _graph().invoke(Command(resume={"approve": approve, "by": by, "role": role, "reason": reason}),
                    _cfg(thread_id))
    return get_status(thread_id)
import json
import re
import sqlite3
import time
from dataclasses import asdict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from processpilot import bedrock, config
from processpilot.agent.state import AgentState
from processpilot.rag.answer import CITE_RE
from processpilot.rag.retrieve import get_section, retrieve
from processpilot.tools import audit
from processpilot.tools.checks import ROLES, approver_for, run_checks
from processpilot.tools.invoice_store import get_invoice
from processpilot.tools.uipath_client import add_queue_item, get_queue_item_status
from processpilot.agent.exception_nodes import (apply_fix, diagnose, failure_summary, finish_failure,
                                                fix_approval, retry, route_after_diagnose,
                                                route_after_fix_approval, route_after_wait)

SYSTEM = (
    "You are an invoice compliance reviewer. Use ONLY the facts and policy text provided. "
    "The findings are authoritative: do not recompute or dispute them. "
    'Return JSON only: {"decision": "COMPLIANT" or "NOT_COMPLIANT", "summary": "..."}. '
    "The decision is NOT_COMPLIANT if any finding has action REJECT or SEND_BACK. "
    "The summary has at most 3 sentences and cites every policy statement like [POL-01 §2.3]. "
    "If COMPLIANT, name the required approver role and cite the approval limit clause."
)


def _t(state: AgentState, msg: str) -> list[str]:
    return state.get("trace", []) + [msg]


def parse(state: AgentState) -> dict:
    m = re.search(r"INV-\d+", state["request"], re.I)
    if not m:
        return {"answer": "I could not find an invoice ID (like INV-204) in your request.",
                "trace": _t(state, "parse: no invoice id")}
    return {"invoice_id": m.group(0).upper(), "trace": _t(state, f"parse: {m.group(0).upper()}")}


def load(state: AgentState) -> dict:
    inv = get_invoice(state["invoice_id"])
    if not inv:
        return {"answer": f"{state['invoice_id']} was not found.", "trace": _t(state, "load: not found")}
    return {"invoice": inv, "trace": _t(state, f"load: {inv['vendor_name']}, total {inv['total']:,.0f}")}


def check(state: AgentState) -> dict:
    inv = state["invoice"]
    findings = [asdict(f) for f in run_checks(inv)]
    role = approver_for(inv["total"])
    return {"findings": findings, "approver_role": role,
            "trace": _t(state, f"check: {[f['code'] for f in findings]}, approver={role}")}


def retrieve_policy(state: AgentState) -> dict:
    cites = {f["cite"] for f in state["findings"]} | {"POL-01 §2"}
    clauses = {}
    for cite in sorted(cites):
        doc, sec = cite.split(" §")
        if hit := get_section(doc, sec):
            clauses[hit.citation] = hit.text
    for hit in retrieve(state["request"], 2):  # semantic top-2 on the request
        clauses.setdefault(hit.citation, hit.text)
    return {"clauses": [{"cite": c, "text": t} for c, t in clauses.items()],
            "trace": _t(state, f"retrieve: {list(clauses)}")}


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return {"decision": "UNKNOWN", "summary": text}


def verdict(state: AgentState) -> dict:
    inv = state["invoice"]
    facts = {k: inv[k] for k in ("invoice_id", "vendor_name", "vendor_status", "invoice_number",
                                 "invoice_date", "total", "po_number")}
    policy = "\n\n".join(f"[{c['cite']}]\n{c['text']}" for c in state["clauses"])
    user = (f"Invoice facts: {json.dumps(facts)}\nRequired approver: {state['approver_role']}\n"
            f"Findings: {json.dumps(state['findings'])}\n\nPolicy text:\n{policy}")
    v = _parse_json(bedrock.chat(SYSTEM, user, max_tokens=300))

    cites = CITE_RE.findall(v.get("summary", ""))
    allowed = {c["cite"] for c in state["clauses"]}
    valid = bool(cites) and all((c.rsplit(".", 1)[0] if "." in c else c) in allowed for c in cites)
    return {"verdict": v, "citations_valid": valid,
            "trace": _t(state, f"verdict: llm={v.get('decision')}, citations_valid={valid}")}


def decide(state: AgentState) -> dict:
    """Final decision comes from code findings; the LLM verdict is cross-checked."""
    blocking = [f for f in state["findings"] if f["action"] in ("REJECT", "SEND_BACK")]
    if blocking:
        decision = "NOT_COMPLIANT"
        action = "REJECT" if any(f["action"] == "REJECT" for f in blocking) else "SEND_BACK"
    else:
        decision, action = "COMPLIANT", "PROCESS"
    agrees = state["verdict"].get("decision") == decision
    audit.log(state["invoice_id"], "DECISION", {"decision": decision, "action": action,
              "findings": [f["code"] for f in state["findings"]], "llm_agrees": agrees})
    return {"decision": decision, "action": action, "llm_agrees": agrees,
            "trace": _t(state, f"decide: {decision}/{action}, llm_agrees={agrees}")}

def approval(state: AgentState) -> dict:
    """Pauses the graph until a human replies. Code before interrupt() re-runs on resume, so keep it side-effect free."""
    inv = state["invoice"]
    reply = interrupt({
        "invoice_id": inv["invoice_id"], "vendor": inv["vendor_name"], "total": inv["total"],
        "required_role": state["approver_role"], "summary": state["verdict"].get("summary", ""),
    })
    by, role = reply.get("by", ""), reply.get("role", "")
    if not reply.get("approve"):
        status, reason = "REJECTED", reply.get("reason") or "rejected by approver"
    elif by == inv["entered_by"]:
        status, reason = "DENIED", "approver entered this invoice [POL-01 §3.1]"
    elif role not in ROLES or ROLES.index(role) < ROLES.index(state["approver_role"]):
        status, reason = "DENIED", f"role '{role}' is below required '{state['approver_role']}' [POL-01 §2]"
    else:
        status, reason = "APPROVED", ""
    audit.log(inv["invoice_id"], f"APPROVAL_{status}", {"by": by, "role": role, "reason": reason})
    return {"approval": {"status": status, "by": by, "role": role, "reason": reason},
            "trace": _t(state, f"approval: {status} by {by or '-'}")}

TERMINAL = {"Successful", "Failed", "Abandoned", "Deleted"}
POLL_SECS = 5
TIMEOUT_SECS = 240
BAD_DATE_VALUE = "31/13/2026"  # the invalid date injected by the bad_date simulation

def submit(state: AgentState) -> dict:
    """Push the invoice to the UiPath queue. The id is checkpointed so a retry of this node cannot double-submit."""
    mode = state.get("simulate_failure", "none")
    if mode == "app_timeout_once":  # test harness: fail the first attempt, succeed on retries
        mode = "app_timeout" if state.get("attempts", 0) == 0 else "none"
    inv = state["invoice"]
    if mode == "bad_date":
        if state.get("fixes_applied", 0) > 0:
            mode = "none"  # the approved fix cures the simulated bad date
        else:
            inv = {**inv, "invoice_date": BAD_DATE_VALUE}
    item_id = add_queue_item(inv, simulate_failure=mode)
    audit.log(state["invoice_id"], "PROCESS_SUBMITTED",
              {"queue_item_id": item_id, "simulate": mode, "attempt": state.get("attempts", 0),
               "invoice_date": inv["invoice_date"]})
    print(f"  queue item {item_id} submitted, waiting for the bot...", flush=True)
    return {"queue_item_id": item_id, "submitted_date": inv["invoice_date"],
            "trace": _t(state, f"submit: queue item {item_id}, simulate={mode}")}


def wait_for_bot(state: AgentState) -> dict:
    """Poll the queue item until it reaches a final status or the timeout passes."""
    item_id = state["queue_item_id"]
    deadline = time.time() + TIMEOUT_SECS
    while True:
        s = get_queue_item_status(item_id)
        if s["status"] in TERMINAL or time.time() > deadline:
            break
        time.sleep(POLL_SECS)
    exc = s.get("exception") or {}
    job = {"status": s["status"] if s["status"] in TERMINAL else "TIMEOUT",
           "queue_item_id": item_id, "exc_type": exc.get("Type"), "reason": exc.get("Reason")}
    audit.log(state["invoice_id"], "PROCESS_RESULT", job)
    return {"job": job, "trace": _t(state, f"wait: {job['status']} {job['reason'] or ''}".strip())}

def respond(state: AgentState) -> dict:
    if state.get("answer"):
        return {}
    if state["citations_valid"]:
        why = state["verdict"]["summary"]
    else:  # fall back to rule-based wording if the model's citations can't be trusted
        why = " ".join(f"{f['message']} [{f['cite']}]" for f in state["findings"]) or \
              f"No blocking issues. Required approver: {state['approver_role']} [POL-01 §2]."
    head = f"{state['invoice_id']}: {state['decision']} ({state['action']})"
    tail = ""
    if state["decision"] == "COMPLIANT":
        ap, job = state["approval"], state.get("job", {})
        if ap["status"] != "APPROVED":
            tail = f"\nNOT PROCESSED - approval {ap['status']}: {ap['reason']}."
        else:
            who = f"Approved by {ap['by']} ({ap['role']}). "
            status, retries = job.get("status"), state.get("attempts", 0)
            if status == "Successful":
                bits = ([f"{retries} retry(ies)"] if retries else []) + \
                       (["an approved fix"] if state.get("fixes_applied") else [])
                after = f" after {' and '.join(bits)}" if bits else ""
                tail = f"\n{who}Processed by UiPath (queue item {job['queue_item_id']}): Successful{after}."
            elif status == "Failed":
                tail = f"\n{who}{failure_summary(state)}"
            elif status == "TIMEOUT":
                tail = f"\n{who}Bot has not finished after {TIMEOUT_SECS}s (queue item {job['queue_item_id']}); check Orchestrator."
            else:
                tail = f"\n{who}Bot run {status}: {job.get('reason')}"
    return {"answer": f"{head}\n{why}{tail}"}

def build():
    conn = sqlite3.connect(config.ROOT / "data" / "checkpoints.sqlite", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    g = StateGraph(AgentState)
    for name, fn in [("parse", parse), ("load", load), ("check", check), ("retrieve", retrieve_policy),
                     ("verdict", verdict), ("decide", decide), ("approval", approval),
                     ("submit", submit), ("wait", wait_for_bot), ("diagnose", diagnose),
                     ("fix_approval", fix_approval), ("apply_fix", apply_fix),("retry", retry), ("finish_failure", finish_failure), ("respond", respond)]:
        g.add_node(name, fn)
    g.add_edge(START, "parse")
    g.add_conditional_edges("parse", lambda s: "load" if s.get("invoice_id") else "respond")
    g.add_conditional_edges("load", lambda s: "check" if s.get("invoice") else "respond")
    g.add_edge("check", "retrieve")
    g.add_edge("retrieve", "verdict")
    g.add_edge("verdict", "decide")
    g.add_conditional_edges("decide", lambda s: "approval" if s["decision"] == "COMPLIANT" else "respond")
    g.add_conditional_edges("approval", lambda s: "submit" if s["approval"]["status"] == "APPROVED" else "respond")
    g.add_edge("submit", "wait")
    g.add_conditional_edges("wait", route_after_wait)
    g.add_conditional_edges("diagnose", route_after_diagnose)
    g.add_conditional_edges("fix_approval", route_after_fix_approval)
    g.add_edge("apply_fix", "submit")
    g.add_edge("retry", "submit")
    g.add_edge("finish_failure", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=SqliteSaver(conn))
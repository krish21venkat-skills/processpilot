"""Stage 6B: drive the full agent live through UiPath for each failure scenario, with approvals automated."""
import json
import os
import time
import uuid
from pathlib import Path

from langgraph.types import Command

from processpilot import bedrock
from processpilot.agent.main_graph import build

os.environ.setdefault("RETRY_WAIT_SECS", "20")  # demo shortcut; the policy minimum is 300s
REQUEST = "Is invoice INV-204 compliant? If yes, process it."

SCENARIOS = [  # (name, simulate, approve the fix?, expected outcome, expected bot runs)
    ("success", "none", True, "SUCCESS", 1),
    ("transient timeout", "app_timeout_once", True, "SUCCESS", 2),
    ("persistent timeout", "app_timeout", True, "ESCALATED", 3),
    ("bad date, fix approved", "bad_date", True, "SUCCESS", 2),
    ("bad date, fix rejected", "bad_date", False, "FIX_NOT_APPLIED", 1),
    ("missing field", "missing_field", True, "RETURNED", 1),
    ("duplicate", "duplicate", True, "RETURNED", 1),
]


def run(graph, simulate: str, fix_approve: bool) -> dict:
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex[:8]}, "recursion_limit": 60}
    graph.invoke({"request": REQUEST, "simulate_failure": simulate}, cfg)
    while (snap := graph.get_state(cfg)).next:
        p = snap.tasks[0].interrupts[0].value
        if p.get("kind") == "FIX":
            reply = {"approve": fix_approve, "by": "r.kumar", "role": "AP Executive",
                     "reason": "live eval: fix rejected"}
        else:
            reply = {"approve": True, "by": "r.kumar", "role": "Finance Manager"}
        graph.invoke(Command(resume=reply), cfg)
    return graph.get_state(cfg).values


def outcome(v: dict) -> str:
    return "SUCCESS" if v.get("job", {}).get("status") == "Successful" else v.get("failure_outcome", "UNKNOWN")


def main() -> None:
    graph, rows = build(), []
    for name, simulate, fix_ok, exp_out, exp_runs in SCENARIOS:
        print(f"\n>>> {name}", flush=True)
        t0, tok0 = time.time(), (bedrock.USAGE["in"], bedrock.USAGE["out"])
        v = run(graph, simulate, fix_ok)
        runs = 1 + v.get("attempts", 0) + v.get("fixes_applied", 0)
        row = {"scenario": name, "outcome": outcome(v), "expected": exp_out, "bot_runs": runs,
               "expected_runs": exp_runs, "secs": round(time.time() - t0),
               "tokens": (bedrock.USAGE["in"] - tok0[0], bedrock.USAGE["out"] - tok0[1])}
        row["pass"] = row["outcome"] == exp_out and runs == exp_runs
        rows.append(row)

    print("\n--- Live results ---")
    for r in rows:
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['scenario']:24} outcome={r['outcome']:16} "
              f"bot runs={r['bot_runs']} (exp {r['expected_runs']})  {r['secs']}s  tokens={r['tokens']}")
    print(f"\n{sum(r['pass'] for r in rows)}/{len(rows)} scenarios as expected")
    Path(__file__).with_name("live_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
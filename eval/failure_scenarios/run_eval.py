"""Stage 6A: compare three failure handlers on 15 failure cases (no UiPath calls, only the classifier)."""
import json
import time
from pathlib import Path

from processpilot import bedrock
from processpilot.agent.classify import classify_llm, classify_rules
from processpilot.agent.policy import MAX_RETRIES, decide
from processpilot.tools.evidence import FailureReport
from processpilot.tools.invoice_store import get_invoice

HERE = Path(__file__).parent
INV = get_invoice("INV-204")
IN_PER_M, OUT_PER_M = 0.80, 3.20  # USD per million tokens: ASSUMED Nova Pro list prices, confirm on the Bedrock pricing page


def naive(attempts: int) -> str:
    return "RETRY" if attempts < MAX_RETRIES else "ESCALATE"


def unsafe(action: str, c: dict) -> bool:
    return ((action == "RETRY" and c["exp_class"] != "SYSTEM")
            or (action == "RETRY" and c["attempts"] >= MAX_RETRIES)
            or (action == "PROPOSE_FIX" and c["exp_category"] != "BAD_DATE"))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def main() -> None:
    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows, lat = [], []
    for c in cases:
        rep = FailureReport("INV-204", 0, "Failed", "Application", c["reason"], c["attempts"], c["logs"])
        t0 = time.time()
        llm = classify_llm(rep)
        lat.append(time.time() - t0)
        rb = classify_rules(rep)
        acts = {
            "naive": naive(c["attempts"]),
            "rules": decide(rb, c["attempts"], INV, c["fixes"]).action,
            "llm": decide(llm, c["attempts"], INV, c["fixes"]).action,
        }
        rows.append({"id": c["id"], "tag": c["tag"], "seen": c["seen"], "exp": c["ok_actions"],
                     "rules_class": f"{rb.failure_class}/{rb.category}", "llm_class": f"{llm.failure_class}/{llm.category}",
                     "flagged": llm.flagged, "actions": acts,
                     "ok": {k: v in c["ok_actions"] for k, v in acts.items()},
                     "unsafe": {k: unsafe(v, c) for k, v in acts.items()},
                     "class_ok": {"rules": rb.failure_class == c["exp_class"], "llm": llm.failure_class == c["exp_class"]}})
        print(f"{c['id']} {c['tag']:9} exp={'/'.join(c['ok_actions']):22} naive={acts['naive']:16} "
              f"rules={acts['rules']:16} llm={acts['llm']:16} {'[FLAGGED]' if llm.flagged else ''}")

    def block(label: str, subset: list[dict]) -> None:
        n = len(subset)
        print(f"\n--- {label} ({n} cases) ---")
        print(f"{'':14}{'correct action':18}{'unsafe actions':16}{'class accuracy'}")
        for k in ("naive", "rules", "llm"):
            ca = f"{pct(sum(r['class_ok'][k] for r in subset), n)}" if k != "naive" else "-"
            print(f"{k:14}{pct(sum(r['ok'][k] for r in subset), n):18}{sum(r['unsafe'][k] for r in subset):<16}{ca}")

    block("ALL", rows)
    block("HELD-OUT (not used to tune the prompt)", [r for r in rows if not r["seen"]])
    n = len(cases)
    cost = (bedrock.USAGE["in"] * IN_PER_M + bedrock.USAGE["out"] * OUT_PER_M) / 1_000_000
    print(f"\ntokens in/out = {bedrock.USAGE['in']}/{bedrock.USAGE['out']}   "
          f"per diagnosis ~ {bedrock.USAGE['in'] // n}/{bedrock.USAGE['out'] // n}   "
          f"est. cost/diagnosis = ${cost / n:.4f}   avg latency = {sum(lat) / n:.1f}s")
    (HERE / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
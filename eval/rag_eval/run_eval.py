"""Stage 2: score the RAG pipeline on questions.jsonl."""
import json
import time
from pathlib import Path

from processpilot.rag.answer import answer
from processpilot.rag.retrieve import retrieve

HERE = Path(__file__).parent


def load() -> list[dict]:
    lines = (HERE / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def keywords_ok(text: str, must: list[str]) -> bool:
    t = text.lower()
    return all(any(alt.strip().lower() in t for alt in m.split("|")) for m in must)


def pct(rows: list[dict], key: str) -> str:
    vals = [r[key] for r in rows if key in r]
    return f"{sum(vals)}/{len(vals)} ({100 * sum(vals) / len(vals):.0f}%)"


def main() -> None:
    rows = []
    for q in load():
        t0 = time.time()
        a = answer(q["question"])
        row = {
            "id": q["id"],
            "question": q["question"],
            "answer": a.text,
            "refusal_ok": a.covered == q["covered"],
            "secs": round(time.time() - t0, 1),
        }
        if q["covered"]:
            expected = set(q["expected"])
            retrieved = {h.citation for h in retrieve(q["question"], 3)}
            cited = {c.rsplit(".", 1)[0] for c in a.citations}
            row["retrieval_hit"] = bool(expected & retrieved)
            row["citation_correct"] = bool(expected & cited)
            row["citation_valid"] = a.citations_valid
            row["keywords_ok"] = keywords_ok(a.text, q["must_include"])
        row["pass"] = all(v for k, v in row.items() if k in
                          {"refusal_ok", "retrieval_hit", "citation_correct", "citation_valid", "keywords_ok"})
        rows.append(row)
        print(f"{row['id']}  {'PASS' if row['pass'] else 'FAIL'}  {row['secs']}s")

    covered = [r for r in rows if "retrieval_hit" in r]
    print("\n--- Summary ---")
    print("Overall pass      :", pct(rows, "pass"))
    print("Refusal accuracy  :", pct(rows, "refusal_ok"))
    print("Retrieval hit@3   :", pct(covered, "retrieval_hit"))
    print("Citation correct  :", pct(covered, "citation_correct"))
    print("Citation valid    :", pct(covered, "citation_valid"))
    print("Keywords present  :", pct(covered, "keywords_ok"))
    print(f"Avg latency       : {sum(r['secs'] for r in rows) / len(rows):.1f}s")

    fails = [r for r in rows if not r["pass"]]
    for r in fails:
        print(f"\n[{r['id']}] {r['question']}\n  -> {r['answer']}")

    (HERE / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
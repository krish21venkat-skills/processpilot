"""Answer a policy question from retrieved clauses, with clause-level citations."""
import argparse
import re
from dataclasses import dataclass, field

from processpilot import bedrock
from processpilot.rag.retrieve import get_section, retrieve

MIN_SCORE = 0.15  # below this, treat the policy as not covering the question
CITE_RE = re.compile(r"POL-\d+ §\d+(?:\.\d+)?")

SYSTEM = (
    "You answer questions about company invoice policy. Use ONLY the policy text provided. "
    "Apply definitions and examples to rules: if one clause defines or gives an example of X "
    "as a kind of Y, and another clause gives a rule for Y, then that rule applies to X. "
    "Match the subject of the question exactly: a clause about a different subject "
    "(for example a different type of record or log) does not answer it. "
    "gives a rule for Y, then that rule applies to X. "
    "Cite the clause for every statement as [POL-01 §2.3]. "
    "Reply exactly NOT COVERED only if none of the provided clauses is relevant to the question. "
    "Be concise: at most 3 sentences."
)


@dataclass
class Answer:
    text: str
    citations: list[str]
    citations_valid: bool
    covered: bool
    used: list[str] = field(default_factory=list)  # sections sent to the LLM


def answer(question: str, k: int = 3) -> Answer:
    hits = [h for h in retrieve(question, k) if h.score >= MIN_SCORE]
    if not hits:
        return Answer("NOT COVERED", [], True, False)

    seen = {h.chunk_id for h in hits}
    for doc_id in dict.fromkeys(h.doc_id for h in hits):
        intro = get_section(doc_id, "1")
        if intro and intro.chunk_id not in seen:
            hits.append(intro)

    used = [h.citation for h in hits]
    context = "\n\n".join(f"[{h.citation}]\n{h.text}" for h in hits)
    text = bedrock.chat(SYSTEM, f"Policy text:\n{context}\n\nQuestion: {question}").strip()
    if text.upper().startswith("NOT COVERED"):
        return Answer("NOT COVERED", [], True, False, used)

    cites = sorted(set(CITE_RE.findall(text)))
    allowed = set(used)
    # a clause cite such as "POL-01 §2.3" is valid if its section "POL-01 §2" was sent
    valid = all(c.rsplit(".", 1)[0] in allowed if "." in c else c in allowed for c in cites)
    return Answer(text, cites, bool(cites) and valid, True, used)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    a = answer(ap.parse_args().question)
    print(a.text)
    print(f"covered={a.covered}  cites={a.citations}  valid={a.citations_valid}")
    print(f"sections sent to LLM: {a.used}")
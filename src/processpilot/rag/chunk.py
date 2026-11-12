"""Split a policy markdown file into one chunk per numbered section."""
import re
from dataclasses import dataclass
from pathlib import Path

TITLE_RE = re.compile(r"^#\s+(POL-\d+)\s+(.+)$")
SECTION_RE = re.compile(r"^##\s+(\d+)\.\s+(.+)$")


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict


def chunk_file(path: Path) -> list[Chunk]:
    doc_id = doc_title = ""
    sections: list[tuple[str, str, list[str]]] = []  # (no, title, clauses)

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if m := TITLE_RE.match(line):
            doc_id, doc_title = m.group(1), m.group(2)
        elif m := SECTION_RE.match(line):
            sections.append((m.group(1), m.group(2), []))
        elif sections:
            sections[-1][2].append(line)

    chunks = []
    for no, title, clauses in sections:
        text = f"{doc_id} {doc_title} - Section {no}: {title}\n" + "\n".join(clauses)
        chunks.append(
            Chunk(
                id=f"{doc_id}-S{no}",
                text=text,
                metadata={
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "section_no": no,
                    "section_title": title,
                    "source": path.name,
                },
            )
        )
    return chunks
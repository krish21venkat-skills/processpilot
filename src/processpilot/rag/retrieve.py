"""Embed a query, search Chroma, return hits with citation labels."""
import argparse
from dataclasses import dataclass
from functools import lru_cache

import chromadb

from processpilot import bedrock, config


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    section_no: str
    section_title: str
    text: str
    score: float  # cosine similarity, higher is better

    @property
    def citation(self) -> str:
        return f"{self.doc_id} §{self.section_no}"


@lru_cache(maxsize=1)
def _collection():
    db = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return db.get_collection(config.COLLECTION)


def retrieve(query: str, k: int = 3) -> list[Hit]:
    res = _collection().query(query_embeddings=[bedrock.embed(query)], n_results=k)
    hits = []
    for cid, doc, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        hits.append(
            Hit(
                chunk_id=cid,
                doc_id=meta["doc_id"],
                section_no=meta["section_no"],
                section_title=meta["section_title"],
                text=doc,
                score=round(1 - dist, 3),
            )
        )
    return hits

def get_section(doc_id: str, section_no: str) -> Hit | None:
    res = _collection().get(ids=[f"{doc_id}-S{section_no}"])
    if not res["ids"]:
        return None
    meta = res["metadatas"][0]
    return Hit(
        chunk_id=res["ids"][0],
        doc_id=meta["doc_id"],
        section_no=meta["section_no"],
        section_title=meta["section_title"],
        text=res["documents"][0],
        score=0.0,
    )

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=3)
    args = ap.parse_args()
    for h in retrieve(args.query, args.k):
        print(f"{h.score:.3f}  {h.citation}  ({h.section_title})")
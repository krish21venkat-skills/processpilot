"""Chunk all policies, embed with Titan, and store in a fresh Chroma collection."""
import logging

import chromadb

from processpilot import bedrock, config
from processpilot.rag.chunk import chunk_file

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ingest")


def main() -> None:
    chunks = [c for p in sorted(config.POLICY_DIR.glob("*.md")) for c in chunk_file(p)]
    log.info("Chunks: %d from %d files", len(chunks), len(list(config.POLICY_DIR.glob("*.md"))))

    db = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    if config.COLLECTION in [c.name for c in db.list_collections()]:
        db.delete_collection(config.COLLECTION)  # rebuild cleanly each run
    col = db.create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})

    col.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
        embeddings=[bedrock.embed(c.text) for c in chunks],
    )
    log.info("Stored %d chunks in %s", col.count(), config.CHROMA_DIR)


if __name__ == "__main__":
    main()
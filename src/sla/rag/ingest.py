"""Ingest pedagogy documents into ChromaDB.

Loads the markdown files in ``data/pedagogy``, splits them into overlapping
chunks, embeds them with the active provider, and upserts them into a Chroma
collection. Upsert with deterministic ids makes re-ingestion idempotent.

Run as a module::

    python -m sla.rag.ingest
"""

from __future__ import annotations

import logging
from pathlib import Path

from sla.config import PROJECT_ROOT, Settings, get_settings
from sla.rag.provider import Embeddings, get_embeddings

log = logging.getLogger(__name__)

DEFAULT_PEDAGOGY_DIR = PROJECT_ROOT / "data" / "pedagogy"


def _title_of(text: str, fallback: str) -> str:
    """Use the first markdown H1 as the document title, else the filename."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def chunk_markdown(text: str, max_chars: int = 700, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks on paragraph boundaries.

    Paragraphs are accumulated until ``max_chars`` is reached; consecutive chunks
    share roughly ``overlap`` characters so context is not lost at boundaries.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n\n" + para if overlap else para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def load_pedagogy_chunks(docs_dir: Path) -> list[dict]:
    """Load and chunk every ``.md`` file in ``docs_dir``.

    Returns a list of ``{id, text, title, source}`` records.
    """
    records: list[dict] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = _title_of(text, path.stem)
        for i, chunk in enumerate(chunk_markdown(text)):
            records.append(
                {
                    "id": f"{path.stem}-{i:03d}",
                    "text": chunk,
                    "title": title,
                    "source": path.name,
                }
            )
    return records


def get_chroma_client(settings: Settings | None = None):
    """Create a Chroma HTTP client (imported lazily)."""
    import chromadb

    settings = settings or get_settings()
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def ingest_pedagogy(
    docs_dir: Path | None = None,
    client=None,
    embeddings: Embeddings | None = None,
    collection_name: str | None = None,
) -> int:
    """Embed and upsert all pedagogy chunks into the Chroma collection.

    Returns the number of chunks ingested. Idempotent via ``upsert``.
    """
    settings = get_settings()
    docs_dir = docs_dir or DEFAULT_PEDAGOGY_DIR
    client = client or get_chroma_client(settings)
    embeddings = embeddings or get_embeddings(settings)
    collection_name = collection_name or settings.chroma_collection

    records = load_pedagogy_chunks(docs_dir)
    if not records:
        log.warning("No pedagogy documents found in %s", docs_dir)
        return 0

    collection = client.get_or_create_collection(collection_name)
    collection.upsert(
        ids=[r["id"] for r in records],
        embeddings=embeddings.embed_documents([r["text"] for r in records]),
        documents=[r["text"] for r in records],
        metadatas=[{"title": r["title"], "source": r["source"]} for r in records],
    )
    log.info("Ingested %s pedagogy chunks into collection '%s'", len(records), collection_name)
    return len(records)


def main() -> None:
    """CLI entry point for ingesting pedagogy documents."""
    logging.basicConfig(level=logging.INFO)
    count = ingest_pedagogy()
    print(f"Ingested {count} pedagogy chunks.")


if __name__ == "__main__":
    main()

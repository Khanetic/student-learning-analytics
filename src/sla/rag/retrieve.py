"""Retrieve the pedagogy chunks most relevant to a student's profile."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from sla.config import Settings, get_settings
from sla.rag.provider import Embeddings, get_embeddings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """A single retrieved pedagogy passage."""

    text: str
    title: str
    source: str


class Retriever(Protocol):
    """Anything that can return the top-k chunks for a query string."""

    def retrieve(self, query: str, k: int = 3) -> list[RetrievedChunk]: ...


class ChromaRetriever:
    """Retriever backed by a ChromaDB collection.

    Resilient by design: if the vector store is unreachable or empty, retrieval
    returns an empty list rather than raising, so feedback generation can still
    proceed from the indicator profile alone.
    """

    def __init__(self, client, collection_name: str, embeddings: Embeddings) -> None:
        self._client = client
        self._collection_name = collection_name
        self._embeddings = embeddings

    def retrieve(self, query: str, k: int = 3) -> list[RetrievedChunk]:
        try:
            collection = self._client.get_collection(self._collection_name)
            result = collection.query(
                query_embeddings=[self._embeddings.embed_query(query)],
                n_results=k,
            )
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            log.warning("Retrieval failed (%s); continuing without context", exc)
            return []

        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        chunks: list[RetrievedChunk] = []
        for doc, meta in zip(docs, metas, strict=False):
            meta = meta or {}
            chunks.append(
                RetrievedChunk(
                    text=doc,
                    title=meta.get("title", ""),
                    source=meta.get("source", ""),
                )
            )
        return chunks


def build_retriever(settings: Settings | None = None) -> ChromaRetriever:
    """Construct a :class:`ChromaRetriever` from configuration (lazy Chroma import)."""
    from sla.rag.ingest import get_chroma_client

    settings = settings or get_settings()
    return ChromaRetriever(
        client=get_chroma_client(settings),
        collection_name=settings.chroma_collection,
        embeddings=get_embeddings(settings),
    )

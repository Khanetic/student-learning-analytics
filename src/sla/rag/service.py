"""Feedback service: the RAG pipeline wired end to end.

Combines retrieval and generation behind one call so the API depends on a single
object that is easy to construct in production and to substitute in tests.
"""

from __future__ import annotations

from sla.config import Settings, get_settings
from sla.rag.generate import (
    FeedbackGenerator,
    FeedbackResult,
    StudentProfile,
    build_profile_query,
)
from sla.rag.retrieve import Retriever


class FeedbackService:
    """Retrieve relevant pedagogy for a profile, then generate feedback."""

    def __init__(self, retriever: Retriever, generator: FeedbackGenerator, top_k: int = 3) -> None:
        self._retriever = retriever
        self._generator = generator
        self._top_k = top_k

    def generate_for(self, profile: StudentProfile) -> FeedbackResult:
        """Run the full pipeline for one student profile."""
        query = build_profile_query(profile)
        context = self._retriever.retrieve(query, k=self._top_k)
        return self._generator.generate(profile, context)


def build_feedback_service(settings: Settings | None = None) -> FeedbackService:
    """Construct the production feedback service from configuration."""
    from sla.rag.retrieve import build_retriever

    settings = settings or get_settings()
    return FeedbackService(
        retriever=build_retriever(settings),
        generator=FeedbackGenerator(),
    )


__all__ = [
    "FeedbackService",
    "FeedbackResult",
    "StudentProfile",
    "build_feedback_service",
]

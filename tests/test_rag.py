"""Phase 4 unit tests for the RAG pipeline (offline / mock provider)."""

from __future__ import annotations

from sla.rag.generate import (
    FeedbackGenerator,
    StudentProfile,
    build_profile_query,
)
from sla.rag.ingest import DEFAULT_PEDAGOGY_DIR, chunk_markdown, load_pedagogy_chunks
from sla.rag.provider import MockEmbeddings
from sla.rag.retrieve import ChromaRetriever, RetrievedChunk
from sla.rag.service import FeedbackService

# --- mock embeddings -------------------------------------------------------


def test_mock_embeddings_are_deterministic_and_normalized() -> None:
    emb = MockEmbeddings()
    v1 = emb.embed_query("active recall and spaced practice")
    v2 = emb.embed_query("active recall and spaced practice")
    assert v1 == v2
    assert len(v1) == emb.dim
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_mock_embeddings_overlap_more_similar() -> None:
    emb = MockEmbeddings()

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    base = emb.embed_query("time management and regular study sessions")
    near = emb.embed_query("regular study sessions and time management tips")
    far = emb.embed_query("quantum chromodynamics lattice gauge theory")
    assert cos(base, near) > cos(base, far)


# --- chunking & loading ----------------------------------------------------


def test_chunk_markdown_respects_size_and_is_nonempty() -> None:
    text = "\n\n".join(f"Paragraph {i} " + "word " * 40 for i in range(10))
    chunks = chunk_markdown(text, max_chars=300, overlap=50)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_load_pedagogy_chunks_reads_all_docs() -> None:
    records = load_pedagogy_chunks(DEFAULT_PEDAGOGY_DIR)
    sources = {r["source"] for r in records}
    assert len(sources) == 6  # six pedagogy markdown files
    assert all(r["id"] and r["text"] and r["title"] for r in records)


# --- profile query ---------------------------------------------------------


def test_build_profile_query_reflects_risk_profile() -> None:
    profile = _profile(engagement=20, trend="negative", regularity=5, submission=30)
    query = build_profile_query(profile).lower()
    assert "low engagement" in query
    assert "declining quiz" in query
    assert "time management" in query
    assert "help-seeking" in query


# --- generation (mock) -----------------------------------------------------


def _profile(engagement=30.0, trend="negative", regularity=4.0, submission=40.0,
             at_risk=True) -> StudentProfile:
    return StudentProfile(
        student_id="S0001",
        name="Alex Doe",
        program="B.Sc. Computer Science",
        engagement_score=engagement,
        time_on_task_hours=1.5,
        quiz_trend=trend,
        quiz_trend_slope=-2.0 if trend == "negative" else 2.0,
        session_regularity=regularity,
        submission_rate=submission,
        at_risk_flag=at_risk,
    )


def test_mock_generator_returns_three_paragraphs() -> None:
    gen = FeedbackGenerator(provider="mock")
    ctx = [
        RetrievedChunk(text="Use active recall.", title="Study Habits", source="x.md"),
        RetrievedChunk(text="Ask for help early.", title="Help-Seeking", source="y.md"),
    ]
    result = gen.generate(_profile(), ctx)
    assert result.provider == "mock"
    paragraphs = [p for p in result.feedback.split("\n\n") if p.strip()]
    assert len(paragraphs) == 3
    assert "Alex Doe" in result.feedback
    # References a retrieved tip title.
    assert "Study Habits" in result.feedback or "Help-Seeking" in result.feedback


def test_mock_generator_works_without_context() -> None:
    gen = FeedbackGenerator(provider="mock")
    result = gen.generate(_profile(at_risk=False, engagement=80, trend="positive"), [])
    assert len([p for p in result.feedback.split("\n\n") if p.strip()]) == 3


# --- service + retriever resilience ----------------------------------------


class _StubRetriever:
    def retrieve(self, query: str, k: int = 3) -> list[RetrievedChunk]:
        return [RetrievedChunk(text="Spaced practice helps.", title="Spacing", source="s.md")]


def test_feedback_service_end_to_end_mock() -> None:
    service = FeedbackService(_StubRetriever(), FeedbackGenerator(provider="mock"))
    result = service.generate_for(_profile())
    assert result.provider == "mock"
    assert result.context and result.context[0].title == "Spacing"


def test_chroma_retriever_degrades_gracefully() -> None:
    class _BoomClient:
        def get_collection(self, name):
            raise RuntimeError("chroma down")

    retriever = ChromaRetriever(_BoomClient(), "pedagogy", MockEmbeddings())
    assert retriever.retrieve("anything") == []

"""LLM provider abstraction: real OpenAI or deterministic offline mock.

The choice is driven entirely by configuration: if ``settings.use_real_llm`` is
true (an OpenAI key is present) the real OpenAI embedding/chat clients are used;
otherwise deterministic mock implementations keep the whole pipeline runnable
offline (demo + CI). Real clients are imported lazily so ``openai`` /
``langchain-openai`` are only required when actually used.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from sla.config import Settings, get_settings

MOCK_EMBEDDING_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embeddings(Protocol):
    """Minimal embedding interface shared by real and mock providers."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    """Minimal chat-completion interface."""

    def complete(self, prompt: str) -> str: ...


# --- mock implementations --------------------------------------------------


class MockEmbeddings:
    """Deterministic feature-hashing embeddings (no network, no key).

    Each token is hashed into a fixed-width vector and the result is
    L2-normalized. Similar texts share tokens and therefore land close together,
    so cosine retrieval still returns sensible neighbours — good enough for an
    offline demo while remaining perfectly reproducible.
    """

    def __init__(self, dim: int = MOCK_EMBEDDING_DIM) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=float)
        for token in _TOKEN_RE.findall(text.lower()):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class MockChat:
    """Offline chat model. Returns the prompt's pre-built fallback section.

    The feedback generator always passes a ready-made templated message as part
    of the prompt (delimited below); the mock simply echoes it, so behaviour is
    deterministic and needs no model. The real provider ignores that section and
    writes its own prose.
    """

    FALLBACK_MARKER = "### OFFLINE_FEEDBACK ###"

    def complete(self, prompt: str) -> str:
        if self.FALLBACK_MARKER in prompt:
            return prompt.split(self.FALLBACK_MARKER, 1)[1].strip()
        return prompt.strip()


# --- real implementations (lazy imports) -----------------------------------


class OpenAIEmbeddingsAdapter:
    """Adapter around ``langchain_openai.OpenAIEmbeddings``."""

    def __init__(self, model: str, api_key: str) -> None:
        from langchain_openai import OpenAIEmbeddings

        self._impl = OpenAIEmbeddings(model=model, api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._impl.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._impl.embed_query(text)


class OpenAIChatAdapter:
    """Adapter around ``langchain_openai.ChatOpenAI``."""

    def __init__(self, model: str, api_key: str) -> None:
        from langchain_openai import ChatOpenAI

        self._impl = ChatOpenAI(model=model, api_key=api_key, temperature=0.4)

    def complete(self, prompt: str) -> str:
        return self._impl.invoke(prompt).content


# --- factories -------------------------------------------------------------


def provider_name(settings: Settings | None = None) -> str:
    """Return ``"openai"`` or ``"mock"`` for the active configuration."""
    settings = settings or get_settings()
    return "openai" if settings.use_real_llm else "mock"


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    """Return the embedding provider for the active configuration."""
    settings = settings or get_settings()
    if settings.use_real_llm:
        return OpenAIEmbeddingsAdapter(settings.openai_embedding_model, settings.openai_api_key)
    return MockEmbeddings()


def get_chat(settings: Settings | None = None) -> ChatModel:
    """Return the chat provider for the active configuration."""
    settings = settings or get_settings()
    if settings.use_real_llm:
        return OpenAIChatAdapter(settings.openai_chat_model, settings.openai_api_key)
    return MockChat()

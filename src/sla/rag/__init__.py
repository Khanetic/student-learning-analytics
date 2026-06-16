"""Retrieval-Augmented Generation pipeline (Phase 4).

Loads pedagogy documents into ChromaDB, retrieves the chunks most relevant to a
student's indicator profile, and generates a personalized feedback message.

The pipeline works with or without an OpenAI key: when ``OPENAI_API_KEY`` is
unset it falls back to a deterministic mock embedding + templated generator, so
the demo and the test suite run fully offline. Heavy optional dependencies
(``chromadb``, ``openai``, ``langchain``) are imported lazily so importing this
package stays cheap.
"""

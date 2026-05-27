"""MamaCare AI prototype package.

The package is organized by responsibility:
- `models.py` for shared dataclasses
- `knowledge_base.py` for loading curated knowledge
- `indexing.py` for turning source files into retrievable cards
- `retriever.py` for lexical fallback retrieval
- `vector_store.py` for ChromaDB semantic retrieval
- `guardrails.py` and `response_chain.py` for safe, warm responses
- `service.py` as the main application-facing entry point
"""

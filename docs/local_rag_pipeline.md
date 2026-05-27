# Local RAG Pipeline

This document explains the upgraded MamaCare retrieval architecture in plain
language so contributors, reviewers, and funders can understand how the
assistant is grounded.

## Goal

MamaCare should answer pregnancy questions from trusted local knowledge instead
of guessing from model memory.

## Architecture

The local pipeline has four layers:

1. Curated knowledge layer
   `data/knowledge/*.json`
   These are the highest-trust maternal FAQ cards and should contain the core
   plain-language answers mothers are most likely to ask for.

2. Source ingestion layer
   `src/mamacare_ai/indexing.py`
   This converts downloaded PDFs, DOCX files, spreadsheets, ZIP contents, and
   text files into normalized `KnowledgeCard` objects.

3. Semantic retrieval layer
   `src/mamacare_ai/vector_store.py`
   This creates sentence-transformer embeddings and stores them in a persisted
   ChromaDB collection under `data/index/chroma_db/`.

4. Hybrid retrieval and response layer
   `src/mamacare_ai/service.py`
   This merges semantic search results with curated lexical FAQ matches before
   passing grounded context into the response chain.

## Why This Is Better Than the Old Index

The earlier index was based on TF-IDF-style lexical similarity. That works for
exact wording, but it struggles when mothers ask the same question in different
natural ways.

The new pipeline improves that by:

- understanding semantically similar phrasing
- preserving strong exact-match FAQ behavior
- keeping all retrieval local to the machine
- remaining inspectable and easy to rebuild

## Query Flow

When a mother asks a question:

1. guardrails check for emergency language, medication, privacy, and scope
2. trimester clues are inferred from the question when possible
3. ChromaDB semantic search finds relevant chunks by meaning
4. the lexical FAQ retriever finds exact or near-exact mother phrasing
5. both result sets are merged and ranked
6. MamaCare answers only from that grounded context

## Current Embedding Model

Default model:

`sentence-transformers/all-MiniLM-L6-v2`

This is a practical default for a lightweight local English-first prototype.

If you later want more multilingual performance, you can swap to a stronger
sentence-transformer model and rebuild the index.

## Operational Notes

- Rebuild the index whenever source documents or curated cards change.
- Keep curated FAQ cards short, direct, and mother-friendly.
- Use external reports and guidelines as supporting evidence, not as the only
  conversational answer source.
- If the semantic stack is unavailable, the application still falls back to the
  curated lexical knowledge base.

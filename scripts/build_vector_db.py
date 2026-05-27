"""Command-line entry point for building the local ChromaDB RAG database.

Run this script after adding or updating source files so the persisted MamaCare
index reflects the latest curated knowledge and downloaded evidence sources.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mamacare_ai.indexing import build_cards_from_paths, discover_source_files
from mamacare_ai.vector_store import ChromaVectorStore


# ---------------------------------------------------------------------------
# CLI Main
# ---------------------------------------------------------------------------
# This script discovers configured sources, converts them into knowledge cards,
# and then stores them inside the ChromaDB-backed local RAG database.
def main() -> None:
    source_dirs = [
        ROOT / "data" / "external" / "cdc",
        ROOT / "data" / "external" / "kenya",
        ROOT / "data" / "external" / "nigeria",
        ROOT / "data" / "external" / "nih",
        ROOT / "data" / "external" / "clinical_guidelines",
        ROOT / "data" / "external" / "docs",
    ]

    paths, skipped = discover_source_files(source_dirs)
    sources, cards, more_skipped = build_cards_from_paths(paths, ROOT)
    store = ChromaVectorStore(ROOT / "data" / "index" / "chroma_db")
    try:
        stats = store.replace_index(sources, cards, skipped_files=[*skipped, *more_skipped])
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    print(
        f"Indexed {stats.source_count} sources into {stats.chunk_count} chunks "
        f"using {stats.backend} ({stats.embedding_model})"
    )
    if stats.skipped_files:
        print("Skipped or failed files:")
        for item in stats.skipped_files:
            print(f"- {item}")


if __name__ == "__main__":
    main()

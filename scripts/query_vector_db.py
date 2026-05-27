"""Small CLI helper for manual retrieval checks.

This script is useful during debugging and curation because it lets developers
see which indexed chunks are being returned for a given question.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mamacare_ai.vector_store import ChromaVectorStore


# ---------------------------------------------------------------------------
# CLI Main
# ---------------------------------------------------------------------------
# This script accepts a free-text question, queries the local Chroma RAG store,
# and prints the top matching chunks with lightweight scoring details.
def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        raise SystemExit("Usage: python scripts/query_vector_db.py \"your question here\"")

    store = ChromaVectorStore(ROOT / "data" / "index" / "chroma_db")
    if not store.dependencies_available():
        raise SystemExit(
            "Local RAG dependencies are missing. Run `pip install -r requirements.txt` "
            "before querying the ChromaDB index."
        )

    results = store.search(query)
    if not results:
        print("No results found.")
        return

    for result in results:
        print("=" * 80)
        print(f"Score: {result.score}")
        print(f"Source: {result.chunk.source_name}")
        print(f"Title: {result.chunk.title}")
        print(result.chunk.answer[:1000])


if __name__ == "__main__":
    main()

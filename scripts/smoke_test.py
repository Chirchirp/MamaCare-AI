"""Quick smoke test for end-to-end MamaCare behavior.

This script is designed for fast confidence checks after major changes to
retrieval, guardrails, or answer formatting.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mamacare_ai.service import MamaCareService


# ---------------------------------------------------------------------------
# Smoke-Test Main
# ---------------------------------------------------------------------------
# The chosen questions intentionally touch multiple areas of the product so
# contributors can verify greeting, symptom, escalation, and trimester behavior.
def main() -> None:
    service = MamaCareService.from_repo_root(ROOT)
    rag_backend = "chroma" if service.vector_store and service.vector_store.has_index() else "lexical-fallback"
    print(f"RETRIEVAL BACKEND: {rag_backend}")
    queries = [
        "I am 11 weeks pregnant and feel nauseated. What should I do?",
        "Is cramping normal in the first trimester?",
        "I have heartburn after meals at 22 weeks. What can help?",
        "My feet are swollen and I have a severe headache at 24 weeks.",
        "What should I prepare before labour in the third trimester?",
        "The baby is moving less today at 31 weeks.",
        "I am thinking about ending this pregnancy.",
        "I feel suicidal and I do not want to live anymore.",
    ]

    for query in queries:
        response = service.ask(query)
        print("=" * 80)
        print(f"QUESTION: {query}")
        print(f"TRIMESTER: {response.trimester_used}")
        print(f"FLAGS: {', '.join(response.flags) or 'none'}")
        print(response.answer)
        if response.citations:
            print("SOURCES:")
            for citation in response.citations:
                print(f"- {citation['source_name']} | {citation['title']}")


if __name__ == "__main__":
    main()

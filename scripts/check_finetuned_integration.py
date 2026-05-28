"""Check whether the fine-tuned MamaCare response model is active.

This script exercises the same service path used by the Streamlit app and
reports whether the fine-tuned response model loaded successfully.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mamacare_ai.generator import _RESPONSE_CHAIN
from mamacare_ai.service import MamaCareService


def main() -> None:
    service = MamaCareService.from_repo_root(ROOT)
    queries = [
        "Tell me more about postpartum depression.",
        "I am in my first trimester and feel nauseated. What can help?",
        "What is preeclampsia and how is it managed?",
    ]

    print(f"Configured model path: {_RESPONSE_CHAIN._response_model_path}")
    print(f"Model path exists: {_RESPONSE_CHAIN._response_model_path.exists()}")
    print(f"Fine-tuned responses enabled: {_RESPONSE_CHAIN._use_fine_tuned_model}")
    print("-" * 80)

    for query in queries:
        response = service.ask(query)
        print(f"QUESTION: {query}")
        print(response.answer)
        print("CITATIONS:")
        for citation in response.citations:
            print(f"- {citation['title']}")
        print("-" * 80)

    print(f"Model loaded: {_RESPONSE_CHAIN._response_model is not None}")
    print(f"Tokenizer loaded: {_RESPONSE_CHAIN._response_tokenizer is not None}")
    print(f"Model error: {_RESPONSE_CHAIN._response_model_error}")


if __name__ == "__main__":
    main()

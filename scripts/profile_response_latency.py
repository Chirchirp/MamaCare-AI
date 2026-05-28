"""Profile the MamaCare response path.

This script measures where time is spent for a single question so contributors
can tell whether latency is coming from retrieval, semantic search, or the
fine-tuned response writer.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mamacare_ai.generator import _RESPONSE_CHAIN
from mamacare_ai.service import MamaCareService


@contextmanager
def timed_method(obj: object, method_name: str, metrics: dict[str, float], label: str):
    original = getattr(obj, method_name)

    def wrapped(*args: Any, **kwargs: Any):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            metrics[label] = metrics.get(label, 0.0) + (time.perf_counter() - started)

    setattr(obj, method_name, wrapped)
    try:
        yield
    finally:
        setattr(obj, method_name, original)


def run_profile(query: str, *, trimester: str = "all") -> None:
    service_started = time.perf_counter()
    service = MamaCareService.from_repo_root(ROOT)
    service_load_seconds = time.perf_counter() - service_started

    metrics: dict[str, float] = {}
    timed_wrappers = [
        timed_method(service.guardrails, "analyze", metrics, "guardrails"),
        timed_method(service.retriever, "search", metrics, "lexical_retrieval"),
        timed_method(_RESPONSE_CHAIN, "_generate_model_answer", metrics, "response_generation"),
    ]
    if service.vector_store is not None:
        timed_wrappers.append(timed_method(service.vector_store, "has_index", metrics, "vector_has_index"))
        timed_wrappers.append(timed_method(service.vector_store, "search", metrics, "semantic_retrieval"))

    total_started = time.perf_counter()
    with timed_wrappers[0]:
        with timed_wrappers[1]:
            with timed_wrappers[2]:
                if len(timed_wrappers) == 5:
                    with timed_wrappers[3]:
                        with timed_wrappers[4]:
                            response = service.ask(query, trimester=trimester)
                else:
                    response = service.ask(query, trimester=trimester)
    total_seconds = time.perf_counter() - total_started

    print("=" * 80)
    print(f"QUESTION: {query}")
    print(f"TRIMESTER: {trimester}")
    print(f"SERVICE LOAD: {service_load_seconds:.3f}s")
    print(f"TOTAL ASK: {total_seconds:.3f}s")
    print()
    print("Stage timings:")
    for label in (
        "guardrails",
        "lexical_retrieval",
        "vector_has_index",
        "semantic_retrieval",
        "response_generation",
    ):
        if label in metrics:
            print(f"- {label}: {metrics[label]:.3f}s")
    print()
    print(f"Fine-tuned model enabled: {_RESPONSE_CHAIN._use_fine_tuned_model}")
    print(f"Fine-tuned model loaded: {_RESPONSE_CHAIN._response_model is not None}")
    print(f"Fine-tuned model error: {_RESPONSE_CHAIN._response_model_error}")
    print()
    print("Answer preview:")
    print(response.answer[:500])


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile MamaCare response latency for a single question.")
    parser.add_argument("query", help="Question to profile")
    parser.add_argument("--trimester", default="all", help="Trimester to use: all, T1, T2, or T3")
    args = parser.parse_args()
    run_profile(args.query, trimester=args.trimester)


if __name__ == "__main__":
    main()

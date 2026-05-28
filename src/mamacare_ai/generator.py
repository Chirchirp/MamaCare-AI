"""Thin answer-generation adapter.

This module keeps the service layer simple by exposing a single `build_answer`
function. The heavier response orchestration lives in `response_chain.py`.
"""

from __future__ import annotations

from mamacare_ai.models import GuardrailOutcome, RetrievalResult
from mamacare_ai.response_chain import MamaCareResponseChain


_RESPONSE_CHAIN = MamaCareResponseChain()


def build_answer(
    query: str,
    trimester: str,
    results: list[RetrievalResult],
    guardrails: GuardrailOutcome,
    conversation_history: list[dict] | None = None,
    supported_topics: list[str] | None = None,
) -> str:
    return _RESPONSE_CHAIN.generate(
        query=query,
        trimester=trimester,
        results=results,
        guardrails=guardrails,
        conversation_history=conversation_history,
        supported_topics=supported_topics or [],
    )

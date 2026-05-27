"""Lightweight lexical retrieval for curated maternal knowledge.

This retriever is intentionally simple and transparent. It normalizes user
questions, scores overlap against curated cards, and strongly rewards exact FAQ
aliases so the prototype can answer common mother questions reliably.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from mamacare_ai.models import KnowledgeCard, RetrievalResult


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
STOPWORDS = {
    "a",
    "am",
    "and",
    "are",
    "at",
    "before",
    "can",
    "do",
    "for",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "should",
    "the",
    "to",
    "what",
    "when",
    "with",
    "you",
    "your",
}
NORMALIZED_TOKENS = {
    "nauseated": "nausea",
    "vomiting": "vomit",
    "swollen": "swelling",
    "labor": "labour",
    "baby": "fetal",
    "healthy": "nutrition",
    "eating": "eat",
    "foods": "food",
    "meals": "meal",
    "headaches": "headache",
    "cramps": "cramping",
    "pregnanct": "pregnant",
    "preganancy": "pregnancy",
    "preganant": "pregnant",
}

# ---------------------------------------------------------------------------
# Text Normalization
# ---------------------------------------------------------------------------
# These helpers reduce wording differences between how mothers ask questions and
# how the knowledge base stores them.
def normalize_text(text: str) -> str:
    return " ".join(tokenize(text))


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text):
        lowered = token.lower()
        if lowered in STOPWORDS:
            continue
        tokens.append(NORMALIZED_TOKENS.get(lowered, lowered))
    return tokens


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    if not numerator:
        return 0.0

    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def source_quality_bonus(chunk: KnowledgeCard) -> float:
    if chunk.document_type == "must_answer_faq":
        return 0.42
    if chunk.document_type == "curated_guidance":
        return 0.28
    if chunk.document_type in {"csv", "xlsx", "xls"}:
        return -0.55

    lowered = f"{chunk.source_name} {chunk.title}".lower()
    penalty = 0.0
    if any(token in lowered for token in ("survey", "table", "documentation", "presentation", "userguide")):
        penalty -= 0.30
    if "report" in lowered and "guideline" not in lowered:
        penalty -= 0.18
    return penalty


def is_trusted_answer_source(chunk: KnowledgeCard) -> bool:
    return chunk.document_type in {"must_answer_faq", "curated_guidance"}


# ---------------------------------------------------------------------------
# In-Memory Retriever
# ---------------------------------------------------------------------------
# This retriever is used when a persisted vector database is not available or
# when the local knowledge files are newer than the stored index.
class SimpleRetriever:
    def __init__(self, chunks: list[KnowledgeCard]) -> None:
        self._chunks = chunks
        self._vectors = {
            chunk.card_id: Counter(tokenize(chunk.search_text()))
            for chunk in chunks
        }
        self._keywords = {
            chunk.card_id: {token for token in tokenize(" ".join(chunk.keywords + chunk.topic_tags))}
            for chunk in chunks
        }
        self._question_aliases = {
            chunk.card_id: {normalize_text(question) for question in chunk.common_questions if question.strip()}
            for chunk in chunks
        }

    def search(
        self,
        query: str,
        trimester: str = "all",
        top_k: int = 4,
    ) -> list[RetrievalResult]:
        query_vector = Counter(tokenize(query))
        query_terms = set(query_vector)
        normalized_query = normalize_text(query)
        results: list[RetrievalResult] = []

        for chunk in self._chunks:
            if trimester != "all" and chunk.trimester not in {trimester, "all"}:
                continue
            score = cosine_similarity(query_vector, self._vectors[chunk.card_id])
            if trimester != "all":
                if chunk.trimester == trimester:
                    score += 0.15
            keyword_overlap = query_terms & self._keywords[chunk.card_id]
            if keyword_overlap:
                score += min(0.12, 0.03 * len(keyword_overlap))
            if normalized_query and normalized_query in self._question_aliases[chunk.card_id]:
                score += 0.85
            score += source_quality_bonus(chunk)
            if score > 0:
                results.append(RetrievalResult(chunk=chunk, score=round(score, 4)))

        results.sort(key=lambda item: item.score, reverse=True)
        if not results:
            return []

        threshold = max(0.08, results[0].score * 0.55)
        filtered = [result for result in results if result.score >= threshold]
        return filtered[:top_k]

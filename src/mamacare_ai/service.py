"""Application-facing orchestration layer for MamaCare.

This is the main service object used by the Streamlit app and test scripts. It
decides whether to read from the persisted index or the local knowledge files,
applies guardrails, performs retrieval, and returns a final assistant response.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from mamacare_ai.generator import build_answer
from mamacare_ai.guardrails import GuardrailEngine
from mamacare_ai.knowledge_base import load_knowledge_base
from mamacare_ai.models import AssistantResponse, RetrievalResult
from mamacare_ai.retriever import SimpleRetriever, is_trusted_answer_source, normalize_text, tokenize
from mamacare_ai.response_chain import detect_query_mode
from mamacare_ai.vector_store import ChromaVectorStore


TRIMESTER_WEEK_RULES = (
    (13, "T1"),
    (26, "T2"),
)
SUPPORTED_TOPIC_CLUSTERS = [
    "early pregnancy and first-trimester questions",
    "nutrition, hydration, and safe food choices",
    "common pregnancy symptoms and warning signs",
    "baby development and fetal movement",
    "antenatal tests, scans, and appointments",
    "second- and third-trimester changes",
    "labor, delivery, and birth preparation",
    "postpartum recovery and immediate newborn basics",
    "breastfeeding and feeding support",
    "emotional wellbeing in pregnancy and after birth",
    "higher-risk pregnancy conditions and when to seek care",
]


# ---------------------------------------------------------------------------
# Main Service
# ---------------------------------------------------------------------------
# Contributors should usually start here when tracing how a user question moves
# through guardrails, retrieval, and response generation.
class MamaCareService:
    def __init__(self, knowledge_base_path: Path | None = None, *, db_path: Path | None = None) -> None:
        if knowledge_base_path is None:
            raise ValueError("knowledge_base_path is required for the local MamaCare knowledge base")
        self.knowledge_base = None
        self.vector_store = ChromaVectorStore(db_path) if db_path else None
        if knowledge_base_path.is_dir():
            manifests = sorted(knowledge_base_path.glob("*.json"))
            knowledge_bases = [load_knowledge_base(path) for path in manifests]
            all_cards = []
            for kb in sorted(knowledge_bases, key=lambda item: item.priority, reverse=True):
                all_cards.extend(kb.cards)
            self.retriever = SimpleRetriever(all_cards)
        else:
            self.knowledge_base = load_knowledge_base(knowledge_base_path)
            self.retriever = SimpleRetriever(self.knowledge_base.cards)
        self.guardrails = GuardrailEngine()
        self.supported_topics = list(SUPPORTED_TOPIC_CLUSTERS)

    @classmethod
    def from_repo_root(cls, root: Path) -> "MamaCareService":
        db_path = root / "data" / "index" / "chroma_db"
        knowledge_dir = root / "data" / "knowledge"
        if db_path.exists():
            if knowledge_dir.exists():
                return cls(knowledge_dir, db_path=db_path)
            return cls(root / "data" / "seed" / "knowledge_base.json", db_path=db_path)
        if knowledge_dir.exists():
            return cls(knowledge_dir)
        return cls(root / "data" / "seed" / "knowledge_base.json")

    def ask(self, query: str, trimester: str = "all") -> AssistantResponse:
        return self.ask_with_history(query, trimester=trimester, conversation_history=None)

    def ask_with_history(
        self,
        query: str,
        *,
        trimester: str = "all",
        conversation_history: list[dict] | None = None,
    ) -> AssistantResponse:
        inferred_trimester = self._infer_trimester(query)
        trimester_used = trimester if trimester != "all" else inferred_trimester
        query_mode = detect_query_mode(query)
        retrieval_query = _rewrite_query_for_retrieval(query)
        effective_query = _augment_query_with_history(retrieval_query, conversation_history)

        outcome = self.guardrails.analyze(query)
        if query_mode != "normal":
            results = []
        elif outcome.out_of_scope or outcome.emergency_message or outcome.crisis_message:
            results = []
        else:
            lexical_results = self.retriever.search(effective_query, trimester=trimester_used, top_k=6)
            if _can_answer_from_fast_path(lexical_results):
                results = _prioritize_trusted_results(lexical_results, top_k=4)
            elif self.vector_store and self.vector_store.has_index():
                try:
                    semantic_results = self.vector_store.search(effective_query, trimester=trimester_used, top_k=6)
                except RuntimeError:
                    semantic_results = []
                merged = _merge_retrieval_results(semantic_results, lexical_results, top_k=6)
                results = _prioritize_trusted_results(merged, top_k=4)
            else:
                results = _prioritize_trusted_results(lexical_results, top_k=4)
            results = _select_specific_grounded_results(
                query,
                results,
                alternate_queries=[effective_query, retrieval_query],
            )
        answer = build_answer(
            query,
            trimester_used,
            results,
            outcome,
            conversation_history=conversation_history,
            supported_topics=self.supported_topics,
        )
        out_of_context = (
            query_mode == "normal"
            and not results
            and not outcome.out_of_scope
            and not outcome.emergency_message
            and not outcome.crisis_message
            and "SENSITIVE_COUNSELLING" not in outcome.flags
        )
        citations = [
            {
                "title": result.chunk.title,
                "source_name": result.chunk.source_name,
                "source_url": result.chunk.source_url,
                "trimester": result.chunk.trimester,
                "score": result.score,
            }
            for result in results
        ]
        return AssistantResponse(
            answer=answer,
            citations=citations,
            flags=outcome.flags,
            trimester_used=trimester_used,
            out_of_context=out_of_context,
            supported_topics=self.supported_topics if out_of_context else [],
        )

    def _infer_trimester(self, query: str) -> str:
        lowered = query.lower()
        if "first trimester" in lowered or "trimester 1" in lowered:
            return "T1"
        if "second trimester" in lowered or "trimester 2" in lowered:
            return "T2"
        if "third trimester" in lowered or "trimester 3" in lowered:
            return "T3"

        match = re.search(r"\b(\d{1,2})\s*weeks?\b", lowered)
        if not match:
            return "all"
        weeks = int(match.group(1))
        for upper_bound, trimester in TRIMESTER_WEEK_RULES:
            if weeks <= upper_bound:
                return trimester
        return "T3"


# ---------------------------------------------------------------------------
# Freshness Helper
# ---------------------------------------------------------------------------
# This helper prevents stale indexes from masking newer curated knowledge files.
def _knowledge_dir_is_newer(knowledge_dir: Path, db_path: Path) -> bool:
    if not knowledge_dir.exists() or not db_path.exists():
        return False
    db_mtime = db_path.stat().st_mtime
    for path in knowledge_dir.glob("*.json"):
        if path.stat().st_mtime > db_mtime:
            return True
    return False


def _rewrite_query_for_retrieval(query: str) -> str:
    normalized = " ".join(query.split())
    lowered = normalized.lower()

    for pattern in (
        r"^(?:can you\s+)?tell me more (?:on|about)\s+(.+)$",
        r"^(?:can you\s+)?explain\s+(.+)$",
        r"^(?:help me understand)\s+(.+)$",
    ):
        match = re.match(pattern, normalized, re.IGNORECASE)
        if match:
            topic = match.group(1).strip().rstrip("?.! ")
            if topic:
                return topic

    symptom_pattern = re.compile(
        r"^(?:i\s+am|i'm|im|i\s+have|i'm\s+having|i\s+am\s+having)\s+(.+?)[,?.!]\s*(what\s+can\s+i\s+do.*)$",
        re.IGNORECASE,
    )
    symptom_match = symptom_pattern.match(normalized)
    if symptom_match:
        symptom = symptom_match.group(1).strip().rstrip("?.! ")
        symptom = re.sub(r"^(?:having|a|an)\s+", "", symptom, flags=re.IGNORECASE).strip()
        ask = symptom_match.group(2).strip().rstrip("?.! ")
        if symptom and ask:
            return f"{ask} about {symptom}"

    pattern = re.compile(
        r"^(?:i am|i'm|im)\s+(?:really\s+)?(?:scared|afraid|worried|anxious)\s+about\s+([^,?.!]+)[, ]+(.*)$",
        re.IGNORECASE,
    )
    match = pattern.match(normalized)
    if match:
        topic = match.group(1).strip()
        rest = match.group(2).strip()
        if rest:
            rest = rest.rstrip("?.! ")
            return f"{rest} about {topic}".strip()

    return normalized


def _augment_query_with_history(query: str, conversation_history: list[dict] | None) -> str:
    if not conversation_history:
        return query
    lowered = query.lower().strip()
    if len(tokenize(query)) > 5:
        return query
    follow_up_markers = (
        "tell me more",
        "what about that",
        "what about this",
        "can you explain more",
        "and that",
        "and this",
    )
    if not any(marker in lowered for marker in follow_up_markers):
        return query

    for item in reversed(conversation_history):
        content = str(item.get("content", "")).strip()
        if item.get("role") == "user" and content:
            return f"{content} {query}".strip()
    return query


def _merge_retrieval_results(
    semantic_results: list[RetrievalResult],
    lexical_results: list[RetrievalResult],
    *,
    top_k: int,
) -> list[RetrievalResult]:
    merged: dict[str, RetrievalResult] = {}

    for result in semantic_results:
        merged[result.chunk.card_id] = RetrievalResult(chunk=result.chunk, score=result.score * 0.92)

    for result in lexical_results:
        existing = merged.get(result.chunk.card_id)
        if existing is None:
            merged[result.chunk.card_id] = RetrievalResult(chunk=result.chunk, score=result.score)
            continue
        blended_score = max(existing.score, result.score) + (0.18 * min(existing.score, result.score))
        merged[result.chunk.card_id] = RetrievalResult(
            chunk=result.chunk,
            score=round(blended_score, 4),
        )

    ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    if not ranked:
        return []
    threshold = max(0.10, ranked[0].score * 0.55)
    return [result for result in ranked if result.score >= threshold][:top_k]


def _can_answer_from_fast_path(results: list[RetrievalResult]) -> bool:
    if not results:
        return False
    top = results[0]
    return is_trusted_answer_source(top.chunk) and top.score >= 0.72


def _prioritize_trusted_results(results: list[RetrievalResult], *, top_k: int) -> list[RetrievalResult]:
    if not results:
        return []
    trusted = [result for result in results if is_trusted_answer_source(result.chunk)]
    if not trusted:
        return results[:top_k]

    ranked: list[RetrievalResult] = []
    seen_ids: set[str] = set()
    for result in trusted + results:
        card_id = result.chunk.card_id
        if card_id in seen_ids:
            continue
        seen_ids.add(card_id)
        ranked.append(result)
        if len(ranked) >= top_k:
            break
    return ranked


def _enforce_context_guardrail(
    query: str,
    results: list[RetrievalResult],
    *,
    alternate_queries: list[str] | None = None,
) -> list[RetrievalResult]:
    if not results:
        return []
    top = results[0]
    if not is_trusted_answer_source(top.chunk):
        return []
    if top.score < 0.68:
        return []
    candidate_queries = [query]
    if alternate_queries:
        candidate_queries.extend(item for item in alternate_queries if item and item not in candidate_queries)
    if not any(_is_specific_grounded_match(candidate_query, top) for candidate_query in candidate_queries):
        return []
    return results


def _select_specific_grounded_results(
    query: str,
    results: list[RetrievalResult],
    *,
    alternate_queries: list[str] | None = None,
) -> list[RetrievalResult]:
    if not results:
        return []
    candidate_queries = [query]
    if alternate_queries:
        candidate_queries.extend(item for item in alternate_queries if item and item not in candidate_queries)

    trusted = [result for result in results if is_trusted_answer_source(result.chunk)]
    if not trusted:
        return []

    specific: list[RetrievalResult] = []
    broad: list[RetrievalResult] = []
    for result in trusted:
        if any(_is_specific_grounded_match(candidate_query, result) for candidate_query in candidate_queries):
            specific.append(result)
        else:
            broad.append(result)

    if not specific:
        return []

    chosen = specific + broad
    return _enforce_context_guardrail(
        query,
        chosen,
        alternate_queries=alternate_queries,
    )


def _is_specific_grounded_match(query: str, result: RetrievalResult) -> bool:
    chunk = result.chunk
    normalized_query = normalize_text(query)
    aliases = {normalize_text(item) for item in chunk.common_questions if item.strip()}
    if normalized_query in aliases:
        return True
    if any(SequenceMatcher(None, normalized_query, alias).ratio() >= 0.83 for alias in aliases):
        return True

    query_terms = set(tokenize(query))
    if not query_terms:
        return False
    keyword_terms = set(tokenize(" ".join(chunk.keywords + chunk.topic_tags)))
    answer_terms = set(tokenize(chunk.title + " " + " ".join(chunk.common_questions)))
    matched_terms = query_terms & (keyword_terms | answer_terms)
    overlap_ratio = len(matched_terms) / max(1, len(query_terms))

    if len(query_terms) <= 2:
        return len(matched_terms) == len(query_terms)
    if len(query_terms) <= 4:
        return overlap_ratio >= 0.6
    return len(matched_terms) >= 2 and overlap_ratio >= 0.45

"""Knowledge-base loading and validation helpers.

This file turns JSON manifests into validated `KnowledgeCard` objects. It is a
good starting point for contributors who want to extend the schema or add new
knowledge packs without changing the retrieval engine itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from mamacare_ai.models import CuratedKnowledgeBase, KnowledgeCard


VALID_TRIMESTERS = {"T1", "T2", "T3", "all"}


# ---------------------------------------------------------------------------
# Normalization Helpers
# ---------------------------------------------------------------------------
# These helpers protect the rest of the pipeline from malformed or inconsistent
# JSON by cleaning common field types during loading.
def _normalize_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        cleaned: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        return cleaned
    raise ValueError(f"Expected a string or list of strings, got {type(value).__name__}")


def _normalize_trimester(value: object, *, card_id: str) -> str:
    trimester = str(value or "all").strip()
    if trimester not in VALID_TRIMESTERS:
        raise ValueError(f"Card {card_id} has invalid trimester '{trimester}'")
    return trimester


# ---------------------------------------------------------------------------
# Card Construction
# ---------------------------------------------------------------------------
# This helper converts a raw JSON object into a fully-typed `KnowledgeCard`.
def _coerce_card(raw: dict, index: int) -> KnowledgeCard:
    card_id = str(raw.get("card_id") or raw.get("chunk_id") or f"card-{index:04d}").strip()
    title = str(raw.get("title") or "").strip()
    if not title:
        raise ValueError(f"Card {card_id} is missing a title")

    answer = str(raw.get("answer") or raw.get("content") or "").strip()
    if not answer:
        raise ValueError(f"Card {card_id} is missing an answer")

    source_name = str(raw.get("source_name") or "Unknown source").strip()
    source_url = str(raw.get("source_url") or "").strip()
    document_type = str(raw.get("document_type") or "curated_guidance").strip()
    topic_tags = _normalize_list(raw.get("topic_tags"))
    keywords = _normalize_list(raw.get("keywords"))
    common_questions = _normalize_list(raw.get("common_questions"))
    when_to_seek_care = _normalize_list(raw.get("when_to_seek_care"))
    danger_signs = _normalize_list(raw.get("danger_signs"))

    if not keywords:
        keywords = list(topic_tags)

    return KnowledgeCard(
        card_id=card_id,
        title=title,
        source_name=source_name,
        source_url=source_url,
        document_type=document_type,
        trimester=_normalize_trimester(raw.get("trimester"), card_id=card_id),
        topic_tags=topic_tags,
        keywords=keywords,
        common_questions=common_questions,
        answer=answer,
        when_to_seek_care=when_to_seek_care,
        danger_signs=danger_signs,
        confidence_score=float(raw.get("confidence_score", 0.7)),
        audience=str(raw.get("audience") or "mothers").strip(),
    )


# ---------------------------------------------------------------------------
# Public Loader
# ---------------------------------------------------------------------------
# This is the main entry point used by the application and index builder.
def load_knowledge_base(path: Path) -> CuratedKnowledgeBase:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        cards = [_coerce_card(item, index) for index, item in enumerate(payload, start=1)]
        return CuratedKnowledgeBase(
            schema_version="legacy-flat-list",
            title="Legacy MamaCare Knowledge Base",
            description="Legacy flat list knowledge cards loaded for backwards compatibility.",
            last_updated=None,
            cards=cards,
        )

    if not isinstance(payload, dict):
        raise ValueError("Knowledge base file must be a JSON object or a legacy JSON array")

    raw_cards = payload.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise ValueError("Knowledge base manifest must include a non-empty 'cards' list")

    cards = [_coerce_card(item, index) for index, item in enumerate(raw_cards, start=1)]
    return CuratedKnowledgeBase(
        schema_version=str(payload.get("schema_version") or "1.0"),
        title=str(payload.get("title") or path.stem),
        description=str(payload.get("description") or ""),
        last_updated=str(payload.get("last_updated")) if payload.get("last_updated") else None,
        cards=cards,
        priority=int(payload.get("priority", 0)),
    )

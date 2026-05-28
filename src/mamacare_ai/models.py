"""Shared data models used across the MamaCare application."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KnowledgeCard:
    card_id: str
    title: str
    source_name: str
    source_url: str
    document_type: str
    trimester: str
    topic_tags: list[str]
    keywords: list[str] = field(default_factory=list)
    common_questions: list[str] = field(default_factory=list)
    answer: str = ""
    when_to_seek_care: list[str] = field(default_factory=list)
    danger_signs: list[str] = field(default_factory=list)
    confidence_score: float = 0.7
    audience: str = "mothers"

    @property
    def content(self) -> str:
        return self.answer

    def search_text(self) -> str:
        weighted_parts = [
            self.title,
            self.title,
            " ".join(self.topic_tags),
            " ".join(self.keywords),
            " ".join(self.keywords),
            " ".join(self.common_questions),
            self.answer,
            " ".join(self.when_to_seek_care),
            " ".join(self.danger_signs),
        ]
        return " ".join(part for part in weighted_parts if part).strip()


@dataclass
class CuratedKnowledgeBase:
    schema_version: str
    title: str
    description: str
    last_updated: str | None
    cards: list[KnowledgeCard]
    priority: int = 0


@dataclass
class RetrievalResult:
    chunk: KnowledgeCard
    score: float


@dataclass
class GuardrailOutcome:
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    emergency_message: str | None = None
    crisis_message: str | None = None
    medication_blocked: bool = False
    out_of_scope: bool = False


@dataclass
class AssistantResponse:
    answer: str
    citations: list[dict]
    flags: list[str]
    trimester_used: str
    out_of_context: bool = False
    supported_topics: list[str] = field(default_factory=list)


@dataclass
class IndexStats:
    source_count: int
    chunk_count: int
    skipped_files: list[str] = field(default_factory=list)
    backend: str = "unknown"
    embedding_model: str | None = None

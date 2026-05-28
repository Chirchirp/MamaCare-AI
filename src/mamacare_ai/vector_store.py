"""ChromaDB-backed local RAG store for MamaCare.

This module keeps semantic retrieval optional. On environments like Streamlit
Cloud where `chromadb` or `sentence-transformers` may be unavailable or fail to
import, MamaCare should still start and fall back to lexical retrieval.
"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

from mamacare_ai.models import IndexStats, KnowledgeCard, RetrievalResult
from mamacare_ai.retriever import normalize_text, source_quality_bonus, tokenize


DEFAULT_COLLECTION_NAME = "mamacare_knowledge"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class ChromaVectorStore:
    def __init__(
        self,
        db_path: Path,
        *,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.db_path = db_path
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._embedding_model = None
        self._chromadb_module = None
        self._sentence_transformer_class = None
        self._dependency_error: Exception | None = None
        self._has_index_cache: bool | None = None
        self._collection_count_cache: int | None = None

    @property
    def manifest_path(self) -> Path:
        return self.db_path / "manifest.json"

    def dependencies_available(self) -> bool:
        return self._load_dependencies()

    def initialize(self) -> None:
        if not self._load_dependencies():
            raise RuntimeError(
                "Optional local RAG dependencies are unavailable in this environment. "
                "MamaCare can still run with lexical retrieval only."
            ) from self._dependency_error
        self._get_client()
        self._get_embedding_model()

    def replace_index(
        self,
        sources: list[dict],
        cards: list[KnowledgeCard],
        *,
        skipped_files: list[str] | None = None,
    ) -> IndexStats:
        self.initialize()
        unique_sources = self._dedupe_sources(sources)
        unique_cards, duplicate_card_count = self._dedupe_cards(cards)
        combined_skips = list(skipped_files or [])
        if duplicate_card_count:
            combined_skips.append(
                f"Deduplicated {duplicate_card_count} repeated chunk ids before storing the index."
            )

        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": self.embedding_model_name,
            },
        )

        batch_size = 64
        for start in range(0, len(unique_cards), batch_size):
            batch = unique_cards[start : start + batch_size]
            embeddings = self._embed_texts([card.search_text() for card in batch])
            collection.upsert(
                ids=[card.card_id for card in batch],
                embeddings=embeddings,
                documents=[card.search_text() for card in batch],
                metadatas=[self._metadata_from_card(card) for card in batch],
            )

        manifest = {
            "backend": "chromadb",
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model_name,
            "indexed_at": datetime.now(UTC).isoformat(),
            "source_count": len(unique_sources),
            "chunk_count": len(unique_cards),
            "source_paths": [source["path"] for source in unique_sources],
        }
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._has_index_cache = True
        self._collection_count_cache = len(unique_cards)

        return IndexStats(
            source_count=len(unique_sources),
            chunk_count=len(unique_cards),
            skipped_files=combined_skips,
            backend="chromadb",
            embedding_model=self.embedding_model_name,
        )

    def has_index(self) -> bool:
        if self._has_index_cache is not None:
            return self._has_index_cache
        if not self._load_dependencies():
            self._has_index_cache = False
            return False
        if not self.db_path.exists() or not self.manifest_path.exists():
            self._has_index_cache = False
            return False
        try:
            collection = self._get_collection()
            count = collection.count()
            self._collection_count_cache = count
            self._has_index_cache = count > 0
            return self._has_index_cache
        except Exception:
            self._has_index_cache = False
            return False

    def search(self, query: str, *, trimester: str = "all", top_k: int = 4) -> list[RetrievalResult]:
        if not self.has_index():
            return []

        collection = self._get_collection()
        query_embedding = self._embed_texts([query])[0]
        collection_size = self._get_collection_size(collection)
        candidate_count = min(max(top_k * 4, 8), max(collection_size, 1))
        payload = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"],
        )

        metadatas = (payload.get("metadatas") or [[]])[0]
        distances = (payload.get("distances") or [[]])[0]
        if not metadatas:
            return []

        query_terms = tokenize(query)
        normalized_query = normalize_text(query)
        results: list[RetrievalResult] = []

        for metadata, distance in zip(metadatas, distances):
            if not metadata:
                continue
            card = self._metadata_to_card(metadata)
            if trimester != "all" and card.trimester not in {trimester, "all"}:
                continue

            score = self._distance_to_similarity(distance)
            if trimester != "all" and card.trimester == trimester:
                score += 0.12
            score += self._keyword_bonus(query_terms, card.keywords)
            score += source_quality_bonus(card)

            question_aliases = {
                normalize_text(question)
                for question in card.common_questions
                if str(question).strip()
            }
            if normalized_query and normalized_query in question_aliases:
                score += 0.85
            if score <= 0:
                continue
            results.append(RetrievalResult(chunk=card, score=round(score, 4)))

        results.sort(key=lambda item: item.score, reverse=True)
        if not results:
            return []
        threshold = max(0.10, results[0].score * 0.55)
        return [result for result in results if result.score >= threshold][:top_k]

    def read_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @property
    def import_diagnostics(self) -> dict[str, str]:
        if self._dependency_error is None:
            return {}
        return {"optional_local_rag": repr(self._dependency_error)}

    def _load_dependencies(self) -> bool:
        if self._chromadb_module is not None and self._sentence_transformer_class is not None:
            return True
        if self._dependency_error is not None:
            return False
        try:
            chromadb_module = importlib.import_module("chromadb")
            sentence_transformers_module = importlib.import_module("sentence_transformers")
            sentence_transformer_class = getattr(sentence_transformers_module, "SentenceTransformer")
        except Exception as exc:  # pragma: no cover - depends on deployment env
            self._dependency_error = exc
            self._chromadb_module = None
            self._sentence_transformer_class = None
            return False
        self._chromadb_module = chromadb_module
        self._sentence_transformer_class = sentence_transformer_class
        return True

    def _get_client(self):
        if not self._load_dependencies():
            raise RuntimeError("ChromaDB client is unavailable in this environment.") from self._dependency_error
        if self._client is None:
            self._client = self._chromadb_module.PersistentClient(path=str(self.db_path))
        return self._client

    def _get_collection(self):
        return self._get_client().get_collection(self.collection_name)

    def _get_collection_size(self, collection) -> int:
        if self._collection_count_cache is not None:
            return self._collection_count_cache
        manifest = self.read_manifest()
        if isinstance(manifest.get("chunk_count"), int):
            self._collection_count_cache = int(manifest["chunk_count"])
            return self._collection_count_cache
        count = collection.count()
        self._collection_count_cache = count
        return count

    def _get_embedding_model(self):
        if not self._load_dependencies():
            raise RuntimeError(
                "The embedding model is unavailable in this environment."
            ) from self._dependency_error
        if self._embedding_model is None:
            try:
                self._embedding_model = self._sentence_transformer_class(self.embedding_model_name)
            except Exception as exc:  # pragma: no cover
                self._dependency_error = exc
                raise RuntimeError(
                    "The local embedding model could not load. MamaCare will fall back to lexical retrieval."
                ) from exc
        return self._embedding_model

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._get_embedding_model()
        embeddings = model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [embedding.tolist() for embedding in embeddings]

    @staticmethod
    def _metadata_from_card(card: KnowledgeCard) -> dict:
        return {
            "card_id": card.card_id,
            "title": card.title,
            "source_name": card.source_name,
            "source_url": card.source_url,
            "document_type": card.document_type,
            "trimester": card.trimester,
            "topic_tags_json": json.dumps(card.topic_tags, ensure_ascii=True),
            "keywords_json": json.dumps(card.keywords, ensure_ascii=True),
            "common_questions_json": json.dumps(card.common_questions, ensure_ascii=True),
            "answer": card.answer,
            "when_to_seek_care_json": json.dumps(card.when_to_seek_care, ensure_ascii=True),
            "danger_signs_json": json.dumps(card.danger_signs, ensure_ascii=True),
            "confidence_score": float(card.confidence_score),
            "audience": card.audience,
        }

    @staticmethod
    def _metadata_to_card(metadata: dict) -> KnowledgeCard:
        return KnowledgeCard(
            card_id=str(metadata["card_id"]),
            title=str(metadata["title"]),
            source_name=str(metadata["source_name"]),
            source_url=str(metadata["source_url"]),
            document_type=str(metadata["document_type"]),
            trimester=str(metadata["trimester"]),
            topic_tags=json.loads(metadata.get("topic_tags_json", "[]")),
            keywords=json.loads(metadata.get("keywords_json", "[]")),
            common_questions=json.loads(metadata.get("common_questions_json", "[]")),
            answer=str(metadata.get("answer", "")),
            when_to_seek_care=json.loads(metadata.get("when_to_seek_care_json", "[]")),
            danger_signs=json.loads(metadata.get("danger_signs_json", "[]")),
            confidence_score=float(metadata.get("confidence_score", 0.7)),
            audience=str(metadata.get("audience", "mothers")),
        )

    @staticmethod
    def _dedupe_sources(sources: list[dict]) -> list[dict]:
        unique: dict[str, dict] = {}
        for source in sources:
            unique[source["source_id"]] = source
        return list(unique.values())

    @staticmethod
    def _dedupe_cards(cards: list[KnowledgeCard]) -> tuple[list[KnowledgeCard], int]:
        unique: dict[str, KnowledgeCard] = {}
        duplicates = 0
        for card in cards:
            if card.card_id in unique:
                duplicates += 1
                continue
            unique[card.card_id] = card
        return list(unique.values()), duplicates

    @staticmethod
    def _distance_to_similarity(distance: float | int | None) -> float:
        if distance is None:
            return 0.0
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, 1.0 - value)

    @staticmethod
    def _keyword_bonus(query_terms: list[str], keywords: list[str]) -> float:
        if not keywords:
            return 0.0
        query_set = set(query_terms)
        keyword_terms = set(tokenize(" ".join(keywords)))
        overlap = len(query_set & keyword_terms)
        return min(0.12, 0.03 * overlap)


SQLiteVectorStore = ChromaVectorStore

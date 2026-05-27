"""Source-file ingestion and chunk construction for MamaCare.

This module translates raw project sources such as PDFs, spreadsheets, text
files, and curated JSON manifests into normalized `KnowledgeCard` objects. It
is the bridge between downloaded evidence sources and searchable RAG content.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from docx import Document
from pypdf import PdfReader

from mamacare_ai.knowledge_base import load_knowledge_base
from mamacare_ai.models import KnowledgeCard


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".docx", ".json", ".txt", ".md", ".zip"}
TEXT_SPLIT_RE = re.compile(r"\n{2,}")
HAS_XLRD = bool(importlib.util.find_spec("xlrd"))
TRIMESTER_PATTERNS = {
    "T1": re.compile(r"\b(first trimester|trimester 1|0-13 weeks?|up to 13 weeks?)\b", re.I),
    "T2": re.compile(r"\b(second trimester|trimester 2|14-26 weeks?)\b", re.I),
    "T3": re.compile(r"\b(third trimester|trimester 3|27\+?\s*weeks?|late pregnancy)\b", re.I),
}
TOPIC_KEYWORDS = {
    "nutrition": ["nutrition", "diet", "food", "meal", "water", "hydration", "caffeine"],
    "symptoms": ["symptom", "pain", "bleeding", "swelling", "headache", "nausea", "vomiting"],
    "labour": ["labour", "labor", "contraction", "delivery", "birth plan"],
    "postpartum": ["postpartum", "after birth", "breastfeeding", "newborn"],
    "tests": ["test", "ultrasound", "screening", "genetic"],
    "danger_signs": ["danger", "emergency", "urgent", "warning sign", "reduced movement"],
}


# ---------------------------------------------------------------------------
# File Discovery and Source Metadata
# ---------------------------------------------------------------------------
# These helpers scan configured source directories and prepare file-level
# metadata used later during indexing and deduplication.
def compute_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_source_files(root_dirs: list[Path]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    skipped: list[str] = []
    for root_dir in root_dirs:
        if not root_dir.exists():
            skipped.append(f"Missing source directory: {root_dir}")
            continue
        for path in root_dir.rglob("*"):
            if not path.is_file():
                continue
            if "__MACOSX" in path.parts:
                continue
            if any(part.endswith("_unzipped") for part in path.parts):
                continue
            suffix = path.suffix.lower()
            if suffix in SUPPORTED_EXTENSIONS:
                files.append(path)
            else:
                skipped.append(f"Skipped unsupported file: {path}")
    return files, skipped


# ---------------------------------------------------------------------------
# Repository-Level Card Assembly
# ---------------------------------------------------------------------------
# This function merges curated JSON knowledge with extracted file-based content
# into a single in-memory list of knowledge cards for indexing.
def build_cards_from_paths(paths: list[Path], repo_root: Path) -> tuple[list[dict], list[KnowledgeCard], list[str]]:
    sources: list[dict] = []
    cards: list[KnowledgeCard] = []
    skipped: list[str] = []
    seen_source_ids: set[str] = set()
    seen_card_ids: set[str] = set()

    knowledge_dir = repo_root / "data" / "knowledge"
    if knowledge_dir.exists():
        for curated_path in sorted(knowledge_dir.glob("*.json")):
            curated_kb = load_knowledge_base(curated_path)
            source_id = _source_id_for_path(curated_path)
            seen_source_ids.add(source_id)
            sources.append(
                {
                    "source_id": source_id,
                    "path": str(curated_path),
                    "source_name": curated_kb.title,
                    "file_type": curated_path.suffix.lower().removeprefix("."),
                    "checksum": compute_checksum(curated_path),
                    "metadata": {"kind": "curated_manifest", "priority": curated_kb.priority},
                }
            )
            for card in curated_kb.cards:
                card.source_url = f"file://{curated_path}"
                if card.card_id in seen_card_ids:
                    skipped.append(f"Skipped duplicate curated card id: {card.card_id}")
                    continue
                seen_card_ids.add(card.card_id)
                cards.append(card)

    for path in paths:
        try:
            file_cards = build_cards_from_file(path)
        except Exception as exc:
            skipped.append(f"Failed to index {path}: {exc}")
            continue

        if not file_cards:
            if path.suffix.lower() == ".pdf":
                skipped.append(
                    f"No usable text extracted from {path}. Add a same-name .txt or .md sidecar file after OCR or text export to include it in the knowledge base."
                )
            else:
                skipped.append(f"No usable text extracted from {path}")
            continue

        source_id = _source_id_for_path(path)
        if source_id in seen_source_ids:
            skipped.append(f"Skipped duplicate source path during indexing: {path}")
            continue
        seen_source_ids.add(source_id)
        sources.append(
            {
                "source_id": source_id,
                "path": str(path),
                "source_name": pretty_source_name(path),
                "file_type": path.suffix.lower().removeprefix("."),
                "checksum": compute_checksum(path),
                "metadata": {"relative_path": str(path.relative_to(repo_root))},
            }
        )
        for card in file_cards:
            if card.card_id in seen_card_ids:
                skipped.append(f"Skipped duplicate chunk id during indexing: {card.card_id}")
                continue
            seen_card_ids.add(card.card_id)
            cards.append(card)

    return sources, cards, skipped


# ---------------------------------------------------------------------------
# File-Type Routing
# ---------------------------------------------------------------------------
# Each source format is routed to a specialized extractor so contributors can
# extend support format by format without touching the entire pipeline.
def build_cards_from_file(path: Path) -> list[KnowledgeCard]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _cards_from_csv(path)
    if suffix == ".xlsx":
        return _cards_from_xlsx(path)
    if suffix == ".xls":
        return _cards_from_xls(path)
    if suffix == ".pdf":
        return _cards_from_pdf(path)
    if suffix == ".docx":
        return _cards_from_docx(path)
    if suffix == ".json":
        return _cards_from_json(path)
    if suffix == ".txt":
        return _cards_from_text(path)
    if suffix == ".md":
        return _cards_from_text(path)
    if suffix == ".zip":
        return _cards_from_zip(path)
    return []


# ---------------------------------------------------------------------------
# Structured Data Extractors
# ---------------------------------------------------------------------------
# These functions index CSV and spreadsheet records. They are more useful for
# analytics and indicators than for conversational guidance, but they still add
# structured evidence to the retrieval base.
def _cards_from_csv(path: Path) -> list[KnowledgeCard]:
    df = pd.read_csv(path)
    return _cards_from_dataframe(df, path, sheet_name=None)


def _cards_from_xlsx(path: Path) -> list[KnowledgeCard]:
    workbook = pd.read_excel(path, sheet_name=None)
    cards: list[KnowledgeCard] = []
    for sheet_name, df in workbook.items():
        cards.extend(_cards_from_dataframe(df, path, sheet_name=sheet_name))
    return cards


def _cards_from_xls(path: Path) -> list[KnowledgeCard]:
    if not HAS_XLRD:
        raise RuntimeError(
            "Legacy .xls support requires the 'xlrd' package. Install it with "
            "'pip install xlrd' or convert the file to .xlsx or .csv."
        )
    workbook = pd.read_excel(path, sheet_name=None, engine="xlrd")
    cards: list[KnowledgeCard] = []
    for sheet_name, df in workbook.items():
        cards.extend(_cards_from_dataframe(df, path, sheet_name=sheet_name))
    return cards


def _cards_from_dataframe(df: pd.DataFrame, path: Path, sheet_name: str | None) -> list[KnowledgeCard]:
    if df.empty:
        return []
    cleaned = df.fillna("").copy()
    cleaned.columns = _make_unique_headers(cleaned.columns)
    cards: list[KnowledgeCard] = []
    columns = [str(column).strip() for column in cleaned.columns]
    title_base = pretty_source_name(path)
    if sheet_name:
        title_base = f"{title_base} - {sheet_name}"

    schema_text = "Columns: " + ", ".join(columns)
    schema_card = _make_card(
        path,
        local_id=f"{sheet_name or 'sheet'}-schema",
        title=f"{title_base} schema",
        answer=schema_text,
        topic_tags=["dataset", "schema"],
        keywords=columns,
        common_questions=[f"What fields are in {title_base}?"],
    )
    cards.append(schema_card)

    max_rows = min(200, len(cleaned))
    for index in range(max_rows):
        row = cleaned.iloc[index]
        parts = []
        for column in columns:
            value = row[column]
            if value == "":
                continue
            parts.append(f"{column}: {value}")
        if not parts:
            continue
        text = "; ".join(parts)
        cards.append(
            _make_card(
                path,
                local_id=f"{sheet_name or 'sheet'}-row-{index}",
                title=f"{title_base} row {index + 1}",
                answer=text,
                topic_tags=_infer_topic_tags(text),
                keywords=columns,
                common_questions=[f"Show me data from {title_base}"],
                trimester=_infer_trimester(text),
            )
        )
    return cards


# ---------------------------------------------------------------------------
# Document and Text Extractors
# ---------------------------------------------------------------------------
# These functions convert long-form reports and guidance documents into text
# chunks suitable for retrieval.
def _cards_from_pdf(path: Path) -> list[KnowledgeCard]:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    extracted = "\n\n".join(pages).strip()
    if len(extracted) < 120:
        sidecar_text = _read_text_sidecar(path)
        if sidecar_text:
            extracted = sidecar_text
    return _cards_from_long_text(extracted, path)


def _cards_from_docx(path: Path) -> list[KnowledgeCard]:
    document = Document(path)
    parts = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)
    return _cards_from_long_text("\n\n".join(parts), path)


def _cards_from_json(path: Path) -> list[KnowledgeCard]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=True, indent=2)
    return _cards_from_long_text(text, path)


def _cards_from_text(path: Path) -> list[KnowledgeCard]:
    return _cards_from_long_text(path.read_text(encoding="utf-8", errors="ignore"), path)


def _cards_from_zip(path: Path) -> list[KnowledgeCard]:
    extract_dir = path.with_name(f"{path.stem}_unzipped")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(path) as archive:
        archive.extractall(extract_dir)

    cards: list[KnowledgeCard] = []
    for child in sorted(extract_dir.rglob("*")):
        if not child.is_file() or "__MACOSX" in child.parts:
            continue
        if child.suffix.lower() not in SUPPORTED_EXTENSIONS - {".zip"}:
            continue
        cards.extend(build_cards_from_file(child))
    return cards


def _cards_from_long_text(text: str, path: Path) -> list[KnowledgeCard]:
    normalized = text.replace("\r\n", "\n")
    paragraphs = [block.strip() for block in TEXT_SPLIT_RE.split(normalized) if block.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    target_size = 1400
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= target_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= target_size:
            current = paragraph
        else:
            for start in range(0, len(paragraph), target_size):
                piece = paragraph[start : start + target_size]
                chunks.append(piece.strip())
            current = ""
    if current:
        chunks.append(current)

    cards: list[KnowledgeCard] = []
    for index, chunk in enumerate(chunks, start=1):
        cards.append(
            _make_card(
                path,
                local_id=f"chunk-{index}",
                title=f"{pretty_source_name(path)} section {index}",
                answer=chunk,
                topic_tags=_infer_topic_tags(chunk),
                keywords=_keywords_from_text(chunk),
                common_questions=[f"What does {pretty_source_name(path)} say?"],
                trimester=_infer_trimester(chunk),
            )
        )
    return cards


def _read_text_sidecar(path: Path) -> str:
    for suffix in (".txt", ".md"):
        sidecar = path.with_suffix(suffix)
        if sidecar.exists() and sidecar.is_file():
            return sidecar.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


# ---------------------------------------------------------------------------
# Card Construction Helpers
# ---------------------------------------------------------------------------
# These utilities create stable card identifiers and add lightweight inferred
# metadata such as trimester and topic tags.
def _make_card(
    path: Path,
    *,
    local_id: str,
    title: str,
    answer: str,
    topic_tags: list[str],
    keywords: list[str],
    common_questions: list[str],
    trimester: str = "all",
) -> KnowledgeCard:
    file_name = pretty_source_name(path)
    return KnowledgeCard(
        card_id=f"{_source_id_for_path(path)}::{local_id}",
        title=title,
        source_name=file_name,
        source_url=f"file://{path}",
        document_type=path.suffix.lower().removeprefix(".") or "text",
        trimester=trimester,
        topic_tags=topic_tags or ["general"],
        keywords=keywords[:24],
        common_questions=common_questions,
        answer=answer.strip(),
        when_to_seek_care=[],
        danger_signs=[],
        confidence_score=0.68,
        audience="mothers",
    )


def pretty_source_name(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip()


def _source_id_for_path(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()


def _make_unique_headers(headers: pd.Index) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for header in headers:
        base = str(header).strip() or "column"
        count = seen.get(base, 0)
        if count == 0:
            unique_name = base
        else:
            unique_name = f"{base}__{count + 1}"
        seen[base] = count + 1
        unique.append(unique_name)
    return unique


def _infer_trimester(text: str) -> str:
    for trimester, pattern in TRIMESTER_PATTERNS.items():
        if pattern.search(text):
            return trimester
    return "all"


def _infer_topic_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [topic for topic, keywords in TOPIC_KEYWORDS.items() if any(word in lowered for word in keywords)]
    return tags or ["general"]


def _keywords_from_text(text: str) -> list[str]:
    lowered = text.lower()
    keywords: list[str] = []
    for values in TOPIC_KEYWORDS.values():
        for word in values:
            if word in lowered and word not in keywords:
                keywords.append(word)
    return keywords

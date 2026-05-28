"""Build supervised fine-tuning data for MamaCare response modeling.

This script turns the curated knowledge cards into instruction-answer examples
that can be used to fine-tune a local response model. The output is JSONL so it
works with common `transformers` and `datasets` training flows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mamacare_ai.knowledge_base import load_knowledge_base


OUTPUT_PATH = ROOT / "data" / "training" / "mamacare_sft.jsonl"
EVAL_PATH = ROOT / "data" / "training" / "mamacare_eval.jsonl"

TRAINING_SYSTEM_PROMPT = (
    "You are MamaCare AI. Answer only from grounded pregnancy knowledge. "
    "Be specific to the question asked, speak naturally, avoid filler, and do not guess."
)


def _load_cards() -> list[dict]:
    knowledge_dir = ROOT / "data" / "knowledge"
    manifests = sorted(knowledge_dir.glob("*.json"))
    cards: list[dict] = []
    for manifest in manifests:
        kb = load_knowledge_base(manifest)
        for card in kb.cards:
            cards.append(
                {
                    "card_id": card.card_id,
                    "title": card.title,
                    "trimester": card.trimester,
                    "keywords": card.keywords,
                    "topic_tags": card.topic_tags,
                    "common_questions": card.common_questions,
                    "answer": card.answer,
                    "when_to_seek_care": card.when_to_seek_care,
                    "danger_signs": card.danger_signs,
                    "source_name": card.source_name,
                }
            )
    return cards


def _build_target(card: dict) -> str:
    parts = [card["answer"].strip()]
    if card["when_to_seek_care"]:
        parts.append(
            "Please arrange a check sooner if: "
            + "; ".join(item.strip().rstrip(".") for item in card["when_to_seek_care"])
            + "."
        )
    if card["danger_signs"]:
        parts.append(
            "Important warning signs: "
            + "; ".join(item.strip().rstrip(".") for item in card["danger_signs"])
            + "."
        )
    parts.append(f"(Source: {card['source_name']})")
    return "\n\n".join(part for part in parts if part.strip())


def _build_examples(card: dict) -> list[dict]:
    examples: list[dict] = []
    target = _build_target(card)
    source_context = (
        f"Title: {card['title']}\n"
        f"Trimester: {card['trimester']}\n"
        f"Keywords: {', '.join(card['keywords'])}\n"
        f"Topic tags: {', '.join(card['topic_tags'])}\n"
        f"Grounded answer: {card['answer']}"
    )

    prompts = list(dict.fromkeys(card["common_questions"] + [card["title"]]))
    for prompt in prompts:
        prompt_text = str(prompt).strip()
        if not prompt_text:
            continue
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": TRAINING_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Retrieved context:\n{source_context}\n\n"
                            f"Question: {prompt_text}"
                        ),
                    },
                    {"role": "assistant", "content": target},
                ],
                "metadata": {
                    "card_id": card["card_id"],
                    "trimester": card["trimester"],
                    "source_name": card["source_name"],
                },
            }
        )
    return examples


def main() -> None:
    cards = _load_cards()
    examples: list[dict] = []
    for card in cards:
        examples.extend(_build_examples(card))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    split_index = max(1, int(len(examples) * 0.9))
    train_examples = examples[:split_index]
    eval_examples = examples[split_index:]

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for example in train_examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    with EVAL_PATH.open("w", encoding="utf-8") as handle:
        for example in eval_examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"Built {len(train_examples)} training examples -> {OUTPUT_PATH}")
    print(f"Built {len(eval_examples)} evaluation examples -> {EVAL_PATH}")


if __name__ == "__main__":
    main()

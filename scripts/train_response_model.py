"""Train a local question-focused MamaCare response model.

This script is intentionally lightweight. It fine-tunes a seq2seq model such as
`google/flan-t5-base` on the dataset built from the curated knowledge cards.
It is a practical next step when the team wants more natural, question-specific
answers on top of the current RAG pipeline.
"""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN_PATH = ROOT / "data" / "training" / "mamacare_sft.jsonl"
DEFAULT_EVAL_PATH = ROOT / "data" / "training" / "mamacare_eval.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "mamacare-flan-response-model"


def _lazy_imports():
    try:
        from datasets import Dataset
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
        )
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Fine-tuning dependencies are not installed. Run "
            "`pip install -r requirements-finetune.txt` first."
        ) from exc
    return (
        Dataset,
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _format_pair(record: dict) -> dict:
    messages = record["messages"]
    user_message = next(item["content"] for item in messages if item["role"] == "user")
    assistant_message = next(item["content"] for item in messages if item["role"] == "assistant")
    return {
        "input_text": user_message,
        "target_text": assistant_message,
    }


def _build_training_arguments(Seq2SeqTrainingArguments, args, *, has_eval_data: bool):
    signature = inspect.signature(Seq2SeqTrainingArguments.__init__)
    parameters = signature.parameters

    kwargs = {
        "output_dir": str(args.output_dir),
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "num_train_epochs": args.epochs,
        "predict_with_generate": True,
        "logging_steps": 10,
        "load_best_model_at_end": False,
    }

    if "report_to" in parameters:
        kwargs["report_to"] = []

    if has_eval_data:
        if "evaluation_strategy" in parameters:
            kwargs["evaluation_strategy"] = "epoch"
        elif "eval_strategy" in parameters:
            kwargs["eval_strategy"] = "epoch"
        else:
            kwargs["do_eval"] = True

        if "save_strategy" in parameters:
            kwargs["save_strategy"] = "epoch"
    else:
        if "do_eval" in parameters:
            kwargs["do_eval"] = False
        if "save_strategy" in parameters:
            kwargs["save_strategy"] = "epoch"

    return Seq2SeqTrainingArguments(**kwargs)


def _build_trainer(
    Seq2SeqTrainer,
    *,
    model,
    training_args,
    train_dataset,
    eval_dataset,
    tokenizer,
    data_collator,
):
    signature = inspect.signature(Seq2SeqTrainer.__init__)
    parameters = signature.parameters

    kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_dataset,
        "data_collator": data_collator,
    }

    if eval_dataset is not None and "eval_dataset" in parameters:
        kwargs["eval_dataset"] = eval_dataset

    if "tokenizer" in parameters:
        kwargs["tokenizer"] = tokenizer
    elif "processing_class" in parameters:
        kwargs["processing_class"] = tokenizer

    return Seq2SeqTrainer(**kwargs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="google/flan-t5-base")
    parser.add_argument("--train-file", type=Path, default=DEFAULT_TRAIN_PATH)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-input-length", type=int, default=768)
    parser.add_argument("--max-target-length", type=int, default=256)
    args = parser.parse_args()

    (
        Dataset,
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    ) = _lazy_imports()

    train_rows = [_format_pair(item) for item in _read_jsonl(args.train_file)]
    eval_rows = [_format_pair(item) for item in _read_jsonl(args.eval_file)]

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_name)

    train_dataset = Dataset.from_list(train_rows)
    eval_dataset = Dataset.from_list(eval_rows)

    def preprocess(batch: dict) -> dict:
        model_inputs = tokenizer(
            batch["input_text"],
            max_length=args.max_input_length,
            truncation=True,
        )
        labels = tokenizer(
            text_target=batch["target_text"],
            max_length=args.max_target_length,
            truncation=True,
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    train_dataset = train_dataset.map(preprocess, batched=True, remove_columns=train_dataset.column_names)
    eval_dataset = eval_dataset.map(preprocess, batched=True, remove_columns=eval_dataset.column_names)

    training_args = _build_training_arguments(
        Seq2SeqTrainingArguments,
        args,
        has_eval_data=bool(eval_rows),
    )

    trainer = _build_trainer(
        Seq2SeqTrainer,
        model=model,
        training_args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset if eval_rows else None,
        tokenizer=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model),
    )

    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    print(f"Saved fine-tuned model to {args.output_dir}")


if __name__ == "__main__":
    main()

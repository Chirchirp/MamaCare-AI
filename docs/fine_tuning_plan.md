## Fine-Tuning Plan

MamaCare already has a grounded local RAG pipeline. Fine-tuning should be used
to improve **how** answers are phrased, not to replace retrieval as the source
of truth.

### What Fine-Tuning Helps

- more natural conversational phrasing
- better handling of follow-up questions
- stronger question-specific answers instead of broad summaries
- more consistent tone for emotional, practical, and warning-sign questions

### What Fine-Tuning Does Not Replace

- curated knowledge coverage
- retrieval quality
- safety guardrails
- out-of-context refusal logic

### Recommended Model Choices

For a practical local prototype:

- `google/flan-t5-base`
  - easiest supervised fine-tuning starting point
  - good for grounded question-to-answer generation
- `google/flan-t5-large`
  - stronger quality if hardware allows
- `Qwen2.5-1.5B-Instruct`
  - better long-form conversational quality, but heavier to fine-tune

### Dataset Strategy

The project now includes a dataset builder:

- [build_finetune_dataset.py](/E:/MamaCare%20AI/scripts/build_finetune_dataset.py)

It creates:

- [mamacare_sft.jsonl](/E:/MamaCare%20AI/data/training/mamacare_sft.jsonl)
- [mamacare_eval.jsonl](/E:/MamaCare%20AI/data/training/mamacare_eval.jsonl)

Each example includes:

- system instruction
- retrieved context summary
- user question
- grounded target answer

### Training Script

The repo also includes:

- [train_response_model.py](/E:/MamaCare%20AI/scripts/train_response_model.py)

This script fine-tunes a seq2seq response model using `transformers`.

### Install

Install the optional fine-tuning dependencies:

```bash
pip install -r requirements-finetune.txt
```

### Build Dataset

```bash
python scripts/build_finetune_dataset.py
```

### Train

```bash
python scripts/train_response_model.py --model-name google/flan-t5-base
```

### Recommended Evaluation

After training, compare the base and fine-tuned model on:

- postpartum mental-health follow-ups
- first-trimester symptom questions
- broad capability-topic questions
- multi-part questions
- emotional phrasing
- out-of-context refusals

### Recommendation

For MamaCare, the best architecture is:

1. retrieve grounded cards first
2. optionally pass the top card context into a fine-tuned local response model
3. keep emergency and medication guardrails outside the model
4. refuse unsupported questions when grounding is weak

That gives better conversational quality without losing safety or traceability.

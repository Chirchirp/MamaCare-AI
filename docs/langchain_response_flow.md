# LangChain Response Flow

MamaCare now uses a LangChain-style response layer for retrieval-grounded answers.

## What Changed

The project keeps the local retrieval database, but the answer generation step now follows:

1. retrieve relevant chunks from the local knowledge store
2. build a structured context block
3. apply the MamaCare system prompt
4. generate a warm, trimester-aware answer

## Prompt Source Of Truth

The full prompt lives in:

`src/mamacare_ai/prompts.py`

## Runtime Behavior

- If `OPENAI_API_KEY` is available and `langchain-openai` is installed, the response chain can call a chat model such as `gpt-4o-mini`.
- If no external model is configured, the project still uses the same MamaCare prompt rules through a deterministic fallback formatter.

## Environment Variables

- `OPENAI_API_KEY`: optional, enables live LLM generation
- `MAMACARE_LLM_MODEL`: optional, defaults to `gpt-4o-mini`

## Why This Helps

The earlier build retrieved relevant knowledge but answered in a generic template.
This response layer makes answers:

- warmer
- more contextual
- trimester-aware
- citation-aware
- safer around medication, uncertainty, privacy, and escalation

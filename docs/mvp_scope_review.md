# MamaCare AI Scope Review

This note summarizes the scope extracted from `MamaCare_AI_Project_Plan.docx` and narrows it into a realistic MVP.

## Core Product Goal

Build a pregnancy-support assistant that helps mothers ask questions at different stages of pregnancy and receive:

- grounded answers
- clear safety escalation when symptoms are dangerous
- citations to supporting guidance
- language that is simple and compassionate

## Primary Users

- Pregnant mothers
- Midwives and health workers during pilot testing

## True MVP

The document includes a wide roadmap, but the first useful product is much smaller:

- Streamlit chat interface
- pregnancy-stage or trimester selection
- curated maternal-health knowledge base
- retrieval pipeline
- deterministic safety guardrails
- citations in responses
- sample health records for testing and demos

## Features That Should Wait Until After MVP

- government dashboards
- mobile apps
- USSD or SMS channels
- webhook alerts to facilities
- direct integration with real EHR systems
- multilingual production support
- research-export workflows

## Architecture Decision

The plan proposes embeddings, FAISS or ChromaDB, LangChain, and an external LLM. For a first working prototype, the safest path is:

- local seeded knowledge base
- simple retrieval and citation pipeline
- strong rule-based safety layer
- Streamlit interface

This keeps the app easy to run and easy to validate while preserving the same future architecture shape.

## Non-Negotiable Requirements

- no medication prescriptions or dosage advice
- immediate emergency escalation for danger signs
- privacy reminder when users share identifying information
- clear uncertainty language when retrieval is weak
- citations for grounded responses
- explicit prototype disclaimer

## Risks In The Original Plan

- It mixes MVP goals with long-term platform ambitions.
- It assumes authoritative datasets will be available quickly, but licensing and cleaning can take time.
- It introduces dashboards and policy analytics before the chat assistant is validated.
- It treats guardrails as a single step, but they need repeated testing and clinical review.
- It mentions EHR ingestion, which should stay out of scope until governance is settled.

## Recommended Delivery Sequence

1. Validate the chat experience with seeded and approved guidance.
2. Add document ingestion and chunking for official sources.
3. Upgrade retrieval to embeddings and vector storage.
4. Add structured evaluations and clinical review.
5. Add API and secondary channels only after answer quality is trusted.

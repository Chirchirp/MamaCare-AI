# Contributing To MamaCare AI

Thank you for contributing to MamaCare AI.

This project is building toward a practical maternal-health support assistant, so every contribution should improve one or more of these areas:

- answer quality
- grounding and retrieval
- safety and guardrails
- usability for mothers
- maintainability for future collaborators

## Where Contributors Can Help Most

- add reviewed maternal knowledge cards
- improve retrieval quality and ranking
- improve source ingestion for PDFs and scanned documents
- expand support for local languages
- strengthen test coverage for must-answer maternal questions
- improve UX for clarity, accessibility, and trust

## Knowledge Contribution Rules

When adding knowledge:

- prefer curated maternal guidance over raw report text
- write answers in clear, mother-friendly language
- add `common_questions` using natural wording mothers actually use
- include `when_to_seek_care` and `danger_signs` when relevant
- keep medication advice non-prescriptive
- never add content that sounds diagnostic or gives drug doses

## Source Priorities

Highest-priority sources:

- WHO maternal and antenatal care guidance
- CDC pregnancy guidance
- approved ministry of health guidance
- clinically reviewed educational material

Lower-priority sources:

- large surveys
- indicator tables
- demographic reports
- documentation files

These can support retrieval, but they should not become the primary mother-facing answer source.

## Handling Non-Searchable PDFs

If a PDF has no extractable text:

1. OCR or export the text
2. create a same-name `.txt` or `.md` file beside the PDF
3. rebuild the index

Example:

- `Federal Ministry of Health Family Health.pdf`
- `Federal Ministry of Health Family Health.txt`

## Local Development Workflow

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Build the knowledge index:

```bash
python scripts/build_vector_db.py
```

Run retrieval checks:

```bash
python scripts/query_vector_db.py "How can I ensure I am eating healthy?"
```

Run the smoke test:

```bash
python scripts/smoke_test.py
```

Start the app:

```bash
python -m streamlit run app.py
```

## Quality Expectations

Good changes should:

- improve grounded answers
- reduce hallucination risk
- preserve emergency handling
- avoid replacing curated maternal guidance with raw report fragments
- stay understandable for future contributors

## Suggested Next Contribution Areas

- add more trimester-specific FAQ cards
- enrich breastfeeding and postpartum guidance
- improve Swahili or multilingual retrieval
- add evaluation scripts for must-answer question coverage
- improve OCR ingestion for health documents

# Curated Knowledge Base Format

The project now uses a curated knowledge-base manifest instead of a flat list of seed chunks.

## File Location

The active knowledge base is:

`data/knowledge/curated_kb.json`

## Manifest Shape

```json
{
  "schema_version": "2.0",
  "title": "MamaCare Curated Maternal Knowledge Base",
  "description": "Starter maternal knowledge cards for the prototype.",
  "last_updated": "2026-05-27",
  "cards": [
    {
      "card_id": "t1-nausea-001",
      "title": "Morning sickness in the first trimester",
      "source_name": "MamaCare curated maternal guidance",
      "source_url": "internal://curated-kb/t1-nausea-001",
      "document_type": "curated_guidance",
      "trimester": "T1",
      "topic_tags": ["nausea", "nutrition", "symptoms"],
      "keywords": ["morning sickness", "nausea", "vomiting"],
      "common_questions": [
        "Is it normal to feel nauseated at 9 weeks?",
        "What can I do if I keep vomiting in early pregnancy?"
      ],
      "answer": "Short grounded answer shown to the user.",
      "when_to_seek_care": [
        "You cannot keep fluids down.",
        "You feel dizzy or faint."
      ],
      "danger_signs": [
        "Vomiting with dehydration",
        "Severe abdominal pain"
      ],
      "confidence_score": 0.82
    }
  ]
}
```

## Field Notes

- `card_id`: stable unique identifier for the card
- `trimester`: one of `T1`, `T2`, `T3`, or `all`
- `topic_tags`: normalized topic labels for filtering and analytics
- `keywords`: user-language terms and synonyms to improve retrieval
- `common_questions`: realistic question variants mothers might type
- `answer`: the main grounded answer returned by the app
- `when_to_seek_care`: non-emergency reasons to contact a clinician soon
- `danger_signs`: urgent warning signs related to the topic

## Loader Behavior

The loader validates the manifest and normalizes list fields. It also keeps backwards compatibility with the older flat JSON array format so existing seed files can still be read if needed.

## Recommended Authoring Rules

- Keep one main concept per card.
- Write answers in plain language for mothers.
- Put formal clinical terms into `keywords`, not only in `answer`.
- Add at least 2-4 realistic `common_questions` per card.
- Keep `when_to_seek_care` and `danger_signs` short and actionable.

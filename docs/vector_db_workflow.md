# Vector DB Workflow

MamaCare now uses a local RAG pipeline built with:

- `sentence-transformers` embeddings
- ChromaDB for persistent vector storage
- curated maternal FAQ cards for high-trust grounding
- lexical fallback for exact question coverage

## Important Clarification

For this project, we are still not fine-tuning the language model itself.

The practical "training" step for this prototype is:

1. collect trusted source files
2. extract and chunk their text
3. embed each chunk with a sentence-transformer model
4. store those embeddings in a local ChromaDB collection
5. retrieve the best chunks at question time

That is the correct workflow for a local RAG assistant.

## Database Location

The persistent knowledge index now lives in:

`data/index/chroma_db/`

This folder contains the Chroma collection plus a `manifest.json` file that
records the active embedding model and the last index build.

## Embedding Model

The default semantic embedding model is:

`sentence-transformers/all-MiniLM-L6-v2`

This is a good lightweight local choice for English maternal-health retrieval.

## Source Folders

The index builder reads from:

- `data/external/cdc`
- `data/external/kenya`
- `data/external/nigeria`
- `data/external/nih`
- `data/external/clinical_guidelines`
- `data/external/docs`

It also always loads curated JSON knowledge packs from:

- `data/knowledge`

## Supported File Types

- `.csv`
- `.xlsx`
- `.xls`
- `.pdf`
- `.docx`
- `.json`
- `.txt`
- `.md`
- `.zip`

If a PDF contains no selectable text, you can place a same-name `.txt` or `.md`
sidecar file beside it after OCR or text export. MamaCare will use that text
sidecar automatically during indexing.

## How To Build The Local RAG Index

Install project dependencies first:

```bash
pip install -r requirements.txt
```

Important:
Use the same Python interpreter for `pip install`, `build_vector_db.py`,
`query_vector_db.py`, `smoke_test.py`, and Streamlit. If your machine has more
than one Python installation, the indexer may fail simply because the packages
were installed into a different interpreter than the one running the scripts.

Then build the index:

```bash
python scripts/build_vector_db.py
```

This will:

- scan the source folders
- load the curated FAQ knowledge base
- extract additional content from your downloaded files
- chunk the content into retrievable knowledge cards
- create sentence-transformer embeddings
- store them in the local ChromaDB collection

## How To Test Retrieval

Run:

```bash
python scripts/query_vector_db.py "What are warning signs that need urgent care in pregnancy?"
```

## How The App Uses The DB

If the local ChromaDB index exists and its `manifest.json` is newer than the
knowledge files, the MamaCare app uses:

1. semantic search from ChromaDB
2. lexical FAQ retrieval from the curated knowledge base
3. merged ranking for the final context

If the Chroma dependencies are not installed or the index does not exist, the
app falls back to the curated lexical retriever.

## Recommended "Training" Routine

Whenever you add or update source files:

1. place them into the correct `data/external/...` folder
2. run `python scripts/build_vector_db.py`
3. test retrieval with `python scripts/query_vector_db.py "..."`
4. run `python scripts/smoke_test.py`
5. restart the Streamlit app if it was already open

## Best Practice

- Use curated FAQ cards for common mother questions and safe plain-language answers.
- Use guideline PDFs and DOCX files to strengthen grounding for symptom, labour, breastfeeding, and safety topics.
- Use CSV and XLSX sources mainly for indicators, trends, and structured evidence.
- Keep adding mother-style paraphrases to `common_questions` so the hybrid retriever keeps improving.

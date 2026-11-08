# notes-rag

Chat with your class notes: a RAG app that answers questions from your PDFs and cites document and page. Python, FastAPI, ChromaDB, Gemini.

## Status

Under development: phase 5 of 6 (FastAPI: upload PDFs, list them and ask questions over HTTP).

## Planned stack

- Python 3.11+
- pypdf (PDF text extraction)
- Gemini via `google-genai` (embeddings and answers)
- ChromaDB (local persistent vector store)
- FastAPI (API)
- Minimal web frontend
- pytest, Docker

## Planned phases

1. Setup: project structure and tooling.
2. Ingestion: extract text per page and split it into overlapping chunks.
3. Embeddings and ChromaDB with document/page metadata; console search.
4. RAG on console: answer only from retrieved context, cite sources, say "I don't know" when needed.
5. FastAPI: upload PDF, ask questions, list documents.
6. Frontend, Docker, tests and final README.

## Getting started

Windows:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (get one in Google AI Studio).

Put your PDFs in `data/`, then:

```
python -m app.ingest                      # chunk, embed and store the PDFs (safe to re-run)
python -m app.store "your question"       # show the most similar chunks with document and page
python -m app.rag "your question"          # answers from your notes, with document and page
```

Note: if `EMBEDDING_DIM` in `app/embeddings.py` changes, delete `chroma_db/` and re-ingest.

## Run the API

```
uvicorn app.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/documents` | Indexed documents with chunk counts |
| POST | `/documents` | Upload a PDF (multipart field `file`); chunks, embeds and indexes it |
| POST | `/ask` | JSON `{"question": "..."}`; answer with sources, or `found: false` ("I don't know") |

Uploading the same file twice is free: the SHA-256 of the PDF is stored in the index, and an identical
upload returns `"status": "unchanged"` without parsing or calling Gemini. Indexing with
`python -m app.ingest` does not store the hash, so the first API upload of a PDF re-embeds it once.

Errors: 400 empty/unnamed file, 409 nothing indexed yet, 413 file over 20 MB, 415 not a PDF,
422 unreadable PDF or no extractable text, 429 Gemini quota reached, 502 other Gemini errors,
503 `GEMINI_API_KEY` missing.

```
curl.exe http://127.0.0.1:8000/documents
curl.exe -F "file=@data/my-notes.pdf" http://127.0.0.1:8000/documents
curl.exe -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d "@question.json"
```

where `question.json` contains `{"question": "How does Android store data?"}` (a file avoids
PowerShell quoting problems).

## License

MIT, see [LICENSE](LICENSE).

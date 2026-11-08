# notes-rag

Chat with your class notes: a RAG app that answers questions from your PDFs and cites document and page. Python, FastAPI, ChromaDB, Gemini.

## Status

Under development: phase 4 of 6 (RAG on console: answers from your notes with document and page).

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

## License

MIT, see [LICENSE](LICENSE).

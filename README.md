# notes-rag

Chat with your class notes: a RAG app that answers questions from your PDFs and cites document and page. Python, FastAPI, ChromaDB, Gemini.

## Status

Under development: phase 1 of 6 (setup) is done. There is nothing to run yet.

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

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` once the Gemini phases land.

## License

MIT, see [LICENSE](LICENSE).

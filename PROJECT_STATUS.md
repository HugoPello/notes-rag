# Project Status

Single source of truth for progress. **Read this before touching anything.**
- `[x]` = done and committed by the user. **Do not modify** unless the user asks.
- `[ ]` = pending. Only work on the current phase.
- Updated by the orchestrator when the user approves a phase's commit, BEFORE the user commits
  (so the update lands in the same commit). Keep entries short: what was done, what changed vs. plan.

Current phase: **3**

## Phase 1 — Setup
- [x] Folder structure (`app/__init__.py`, `data/.gitkeep`, `pytest.ini`)
- [x] `.gitignore` (Python, venv, `.env`, `data/*`, `chroma_db/`, `.claude/settings.local.json`)
- [x] `.env.example`
- [x] `requirements.txt` (`pypdf==7.0.0`, `pytest==9.2.0`; transitive deps not pinned)
- [x] Initial README (English)
- Branch: `chore/phase-1-setup` (includes team config: `CLAUDE.md`, `.claude/agents/`, this file).
- Notes: LICENSE (MIT) already exists. Deviation: `tests/` is created in phase 2 together with
  `test_chunking.py` (git does not track empty folders).

## Phase 2 — Ingestion
- [x] `app/chunking.py` (pure function, page-aware, ~700 chars / ~100 overlap)
- [x] `app/ingest.py` (`python -m app.ingest` prints chunks per document)
- [x] `tests/test_chunking.py` (10 tests, strings only)
- Branch: `feat/phase-2-ingestion`.
- Notes: deviation: no `ingest_pdf` wrapper; `main()` calls `read_pdf_pages` + `chunk_pages` so each
  PDF is read once. Known limit: some PDFs extract with spaced letters ("SISTE MAS"); comes from the PDF.

## Phase 3 — Embeddings + ChromaDB
- [x] Check ChromaDB installs on Python 3.14 (chromadb 1.5.9 installs and runs; no downgrade needed)
- [x] `app/embeddings.py`, `app/store.py`, console similarity search (`python -m app.store "question"`)
- Branch: `feat/phase-3-embeddings-store`.
- Notes: `gemini-embedding-001`, 768 dims, cosine, batch size 50 (API max is 100). `ingest` now also
  stores (embed first, then delete-by-document + add). `python-dotenv` pinned explicitly.
  Known limits: a PDF removed from `data/` stays in the index; failed PDFs still count in the total line.

## Phase 4 — RAG on console
- [ ] `app/rag.py` (top-k retrieval, Gemini answer, sources, "I don't know")

## Phase 5 — FastAPI
- [ ] `app/main.py` (upload PDF, ask, list documents)

## Phase 6 — Frontend, Docker, tests, final README
- [ ] Minimal frontend
- [ ] Dockerfile + docker-compose
- [ ] Basic tests
- [ ] Final README (GIF, technical decisions, how to run)

# Project Status

Single source of truth for progress. **Read this before touching anything.**
- `[x]` = done and committed by the user. **Do not modify** unless the user asks.
- `[ ]` = pending. Only work on the current phase.
- Updated by the orchestrator when the user approves a phase's commit, BEFORE the user commits
  (so the update lands in the same commit). Keep entries short: what was done, what changed vs. plan.

Current phase: **done** (all 6 phases complete)

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
- [x] `app/rag.py` (top-k retrieval, Gemini answer, sources, "I don't know") + `tests/test_rag.py`
- Branch: `feat/phase-4-rag`. Run with `python -m app.rag "question"`.
- Notes: model `gemini-3.5-flash-lite` (`MODEL` constant), `thinking_level="minimal"`, no temperature.
  Sources are built by Python from `[n]` citations (the model only writes numbers). "I don't know" is
  decided by the model via the `NOT_IN_NOTES` code word; no similarity threshold (scores cluster at
  ~0.73). Retry loop duplicated from `embeddings.py` on purpose (that phase is closed).
  Real smoke test: single-doc OK, unanswerable -> "I don't know" OK.
  Known limits: k=5 can miss pages in cross-document questions (TCP/UDP case); not checked whether the
  model is a preview; free-tier embedding quota is easy to exhaust when re-ingesting (each text counts
  as a request); the "I don't know" message is always in English.

## Phase 5 — FastAPI
- [x] `app/main.py` (upload PDF, ask, list documents) + `tests/test_main.py`
- Branch: `feat/phase-5-fastapi`. Run with `uvicorn app.main:app --reload` (docs at `/docs`).
- Endpoints: `GET /health`, `GET /documents`, `POST /documents`, `POST /ask`. Sync `def` endpoints.
  Upload: validate -> embed -> save to `data/` -> index; sha256 stored in chunk metadata, identical
  re-upload returns `unchanged` with no API calls. No CORS (phase 6 serves the frontend from this app).
- Deviations (user-authorized, closed files touched): `app/store.py` (additive: `file_hash`,
  `document_hash`, `list_documents`), `app/ingest.py` (type hint of `read_pdf_pages` only),
  `tests/test_store.py` (new tests + one import).
- Notes: pinned `fastapi==0.162.2`, `uvicorn==0.54.0`, `python-multipart==0.0.33`, `httpx==0.28.1`.
  Known limits: docs indexed before this phase have no hash (re-embedded once on first API upload);
  `python -m app.ingest` clears the hash; unusual pypdf errors other than `PdfReadError` give a 500.

## Phase 6 — Frontend, Docker, tests, final README
- [x] Minimal frontend (phase 6a, branch `feat/phase-6a-frontend`)
  - Plain HTML/CSS/JS in `app/static/` (no framework, no build, works offline), served by FastAPI:
    `GET /` returns `index.html`, files under `/static`. CSP `default-src 'self'`; server text is
    rendered with `textContent` only (a test guards against `innerHTML`). `tests/test_frontend.py`.
  - Deviation (user-authorized, closed file touched): `app/main.py`, additive lines only (static mount,
    `GET /`, `.js` mimetype fix for Windows).
  - Notes: JS logic is checked manually in the browser, not unit-tested. Run with
    `python -m uvicorn ...` (the `uvicorn.exe` launcher can be blocked on Windows).
  - Idea for later (optional): conversation memory (send last turns, rewrite the question before search).
- [x] Dockerfile + docker-compose (phase 6b, branch `chore/phase-6b-docker-readme`)
  - `python:3.14-slim` (no fallback needed), deps layer cached, non-root user, only `app/` copied
    (no `.env`/PDFs/index in the image), HEALTHCHECK on `/health`, one uvicorn worker.
  - Compose: `env_file: .env`, named volumes `chroma_db` and `pdfs`, port bound to `127.0.0.1`.
  - Verified for real: build ~70 s, image 875 MB on disk, healthy in ~6 s, upload + ask worked,
    index persisted across `down`/`up`, key not found in image history/inspect/logs.
- [x] Basic tests: added `tests/test_ingest.py` (3 tests); suite covers chunking, embeddings, store,
  rag, ingest, API and frontend with no network or API calls.
- [x] Final README (portfolio version with Mermaid diagram, decisions, limitations, Docker + local run).
  - Demo GIF/video skipped for now (a 38 MB GIF was too big for the repo); the image line and the
    `docs/` entry were removed from the README. Option for later: upload a short MP4 through the
    GitHub README editor, or add a GIF under 3 MB as `docs/demo.gif`.
- Project complete: all phases merged into `main`. Optional future work: conversation memory, delete endpoint, OCR, CI.

## Polish (portfolio) — branch `chore/polish`, one commit per step
- [x] CI: `.github/workflows/ci.yml` runs `pytest` on push/PR to `main`, Python 3.14 (same as the
  Dockerfile), pip cache, read-only token, no secrets. Verified locally on 3.14.6: 82 passed, also
  with no API key and network blocked. No ruff (not needed; default rules already pass).
- [x] README: CI, MIT and Python 3.14 badges; `![Demo](docs/demo.gif)` slot + `docs/.gitkeep`
  (GIF pending, recorded by the user); short "Built with AI agents" section. Relative links checked.
- [x] Hygiene audit, no issues found: `.gitignore` covers `.env`, `chroma_db/`, `data/*`, `.venv/`,
  `.pytest_cache/` (checked with `git check-ignore`). Full history (all branches) scanned for API key
  patterns, PDFs/`.env`/DB files and blobs > 200 KB: nothing found. Decided to keep `CLAUDE.md`,
  `.claude/` and this file in the root (`.claude/agents/` must stay there; the workflow is part of the story).

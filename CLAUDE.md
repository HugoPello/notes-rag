# notes-rag

"Chat with your class notes": upload class PDFs, ask questions in natural language, and the app
answers ONLY from those documents, citing document and page. Portfolio project of a DAM
(2nd year) student looking for an internship: code must be clean and explainable in an interview.

Repo description: "Chat with your class notes: a RAG app that answers questions from your PDFs and cites document and page. Python, FastAPI, ChromaDB, Gemini."

**First step in every task: read `PROJECT_STATUS.md`.** Do not touch anything marked `[x]`.

## Stack
Python 3.11+ (user: 3.14.4) · venv · pypdf · google-genai (Gemini, key in `.env`) ·
ChromaDB persistent local · FastAPI · minimal frontend (proposed in phase 6) · pytest · Docker.

## Target structure
```
notes-rag/
  app/ (ingest.py, chunking.py, embeddings.py, store.py, rag.py, main.py)
  data/ (user PDFs, git-ignored except data/.gitkeep)
  tests/
  .env.example, .gitignore, requirements.txt, README.md, PROJECT_STATUS.md
```
Modules are created in their own phase; never create empty files for future phases.

## Phases (one at a time; do NOT advance without user OK)
1. Setup: structure, .gitignore, .env.example, requirements.txt, initial README.
2. Ingestion: pypdf, text per page, ~700-char chunks with ~100 overlap; print chunks per document.
3. Embeddings + ChromaDB with metadata (document, page); console search.
   Check EARLY that ChromaDB installs on Python 3.14; if not, warn the user and decide (3.12/3.13 or another approach).
4. RAG on console: top-k, Gemini answers using only the context, returns sources; if insufficient, say "I don't know".
5. FastAPI: upload PDF, ask, list documents.
6. Minimal frontend, Dockerfile + docker-compose, basic tests, final README (GIF, decisions, how to run).

Detailed checklist and progress: `PROJECT_STATUS.md`.

## Decisions already made (do not reopen)
- PDF: pypdf (pure Python, enough for text-based notes).
- Chunking: fixed ~700-char window, ~100 overlap (~15%), cut at the last space to avoid splitting words.
  `CHUNK_SIZE` and `CHUNK_OVERLAP` are constants.
- Chunks never cross a page boundary (exact citations). Each chunk: document, page, text.
- `requirements.txt` only has what the current phase uses (phases 1-2: `pypdf`, `pytest`).
- `.gitignore`: Python, venv, `.env`, `data/*` (except `data/.gitkeep`), `chroma_db/`.
- `python -m app.ingest` prints chunks per document. `tests/test_chunking.py` tests the pure function.
- `.claude/agents/` and `CLAUDE.md` are versioned in the repo.

## Team workflow (subagents)
The user reviews and decides; we propose and code. Run this session with **Sonnet** as orchestrator
(`/model sonnet` or `claude --model sonnet`). Subagents live in `.claude/agents/`:

| Role | Agent | Model | Purpose |
|---|---|---|---|
| Orchestrator | main session | Sonnet | Talks to the user, delegates, integrates, verifies, summarizes |
| Architect | `architect` | Opus | Planning, design, technical decisions, alternatives with pros/cons |
| Implementer | `implementer` | Sonnet | Writes code and tests from an approved design |
| Researcher | `researcher` | Haiku | Reads docs, version compatibility, summaries (read-only) |

Per-phase flow:
1. **Research** (if needed): one or more `researcher` in parallel, with concrete questions.
2. **Design**: `architect` gets the phase, decisions made, and the researcher's findings.
3. **Summary to the user**: 3-5 lines on what will be done and why. If there are reasonable options,
   give alternatives with pros/cons and **wait for the user's choice** before coding.
4. **Implement**: `implementer`, small changes, approved design.
5. **Verify**: orchestrator reviews the diff, runs tests, checks it matches the decisions.
6. **Close the phase**: explain non-trivial decisions "for the interview", propose a conventional
   commit message. When the user approves the commit, update `PROJECT_STATUS.md` (tick `[x]`,
   short note on what was done and any deviation from plan), then wait for the user to commit.

The orchestrator may make trivial edits itself. Subagents cannot spawn subagents: all delegation
goes through the orchestrator. Every subagent must read `PROJECT_STATUS.md` first.

## Git workflow
- One branch per phase, named `<type>/phase-N-<slug>` (e.g. `chore/phase-1-setup`, `feat/phase-2-ingestion`).
  The orchestrator creates the branch (`git switch -c ...`) from an up-to-date `main` before any work.
- No worktrees per agent: phases are sequential and only the implementer writes code.
- The user commits, pushes, opens the PR and merges into `main`. `main` stays stable.
- Before starting a new phase, check that the previous branch is merged and `main` is pulled.

## Rules for everyone
- **No commits, pushes or `git add`**: the user does them. Propose a conventional message
  (`feat:`, `fix:`, `docs:`, `test:`).
- Before writing code in each phase: 3-5 line summary (what and why).
- Small changes. Simple, readable code over "elegant" code. No dependencies or abstractions we don't need.
- Explain non-trivial decisions (chunk size, k, etc.) as interview preparation.
- If something can't be verified or run, say so and give the exact command for the user to try.
- **Never** write keys or secrets in code or commits. The Gemini key goes in `.env` (ignored);
  `.env.example` only has empty variable names.
- Language: all docs, `.md` files, agent instructions, code, comments and commit messages in
  **English** (saves tokens). Conversation with the user stays in Spanish.

## Commands (completed as phases land)
```
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
python -m app.ingest                                # phase 2 (3: also embeds and stores)
python -m app.store "question"                      # phase 3: similarity search
python -m app.rag "question"                        # phase 4: answer with sources
python -m uvicorn app.main:app --reload             # phase 5: API, docs at /docs (UI at /)
pytest
```

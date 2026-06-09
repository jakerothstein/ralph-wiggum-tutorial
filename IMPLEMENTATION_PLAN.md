# Implementation Plan — Research Paper Comprehension Tutor

Spec: `specs/paper-comprehension-tutor.md` (comprehensive, self-contained).

This feature **replaces Space Invaders** with a Flask + React Islands app that
ingests a PDF research paper, analyzes it (GitHub Models chat in JSON mode),
embeds its chunks into pgvector, and runs a hybrid-Socratic RAG tutor that tracks
a 0-100 comprehension score.

## Status — FEATURE COMPLETE ✅

Both definition-of-done conditions are met and verified:

1. **All Space Invaders content removed.** `grep -ri "invader\|SpaceInvaders\|AlienGrid"
   src frontend e2e tests` returns nothing. Deleted: `views/game.py`,
   `templates/game.html`, `tests/test_game_view.py`, `frontend/src/islands/game/`,
   `frontend/src/game/`, `frontend/tests/game/`, `e2e/game.spec.ts`.
2. **Full tutor UI built and serving at `/`.** Upload, analysis, and chat islands
   are wired to live routes/templates; `/` renders the upload page and
   `/papers/<id>` the analysis + chat workspace.

Validation (this increment):
- `PYTHONPATH=src pytest tests/` → **47 passed** (services + models + session +
  paper/chat view integration + error handlers).
- `cd frontend && npm test` → **6 passed** (UploadIsland + ChatIsland).
- `mypy src/ --ignore-missing-imports` → clean (strict).
- `flake8 src/ tests/` → clean. `npm run lint` + `npm run typecheck` → clean.
- **Full flow verified against real Postgres + pgvector** (docker pgvector:pg16,
  migration applied) via the Flask test client: home → upload (extract→chunk→
  embed→analyze→persist) → workspace → analysis JSON → conversation → tutor turn
  with **native pgvector cosine-search citations** + comprehension score.

## Increment log (2026-06-09) — integration + game removal

### Backend
- `controllers/paper.py` — `ingest` (full pipeline, single transaction: a stored
  Paper always has chunks + analysis), `get`/`get_analysis`/`list_papers`, all
  session-scoped (cross-session = `PaperNotFoundError` → 404).
- `controllers/conversation.py` — `get_or_create_conversation` (idempotent per
  paper+session), `append_turn` (retrieve top-k → tutor → persist user+assistant
  in one commit), `get_messages`.
- `views/paper.py` — `GET /`, `POST /api/papers`, `GET /papers/<id>`,
  `GET /api/papers/<id>`, `GET /api/papers`.
- `views/chat.py` — `POST /api/papers/<id>/conversation`,
  `POST|GET /api/conversations/<cid>/messages`.
- `views/__init__.py` registers `paper_bp` + `chat_bp`; `game_bp` dropped.
- `templates/index.html` (upload island) + `templates/paper.html` (analysis +
  chat islands, `paperId` via `data-props`).

### Frontend
- `types/paper.ts` (DTOs mirroring Pydantic), `lib/api.ts` (typed fetch +
  `ApiError`).
- `islands/upload` (drag/drop, client validation, redirect), `islands/analysis`
  (read-only sections), `islands/chat` (react-markdown messages, score meter,
  citations, input disabled while pending).
- `main.ts` registry → `upload`/`analysis`/`chat`. `react-markdown` added.
- jest-dom matchers wired for tsc via `src/vitest-env.d.ts` +
  `tests/setup.ts` (`@testing-library/jest-dom/vitest`).

### Bug fixed
- **Native pgvector search path** previously threw `'float' object is not
  subscriptable` and silently fell back to the NumPy path. Cause: the `<=>`
  expression inherited the `EmbeddingVector` type decorator, so the scalar
  distance was decoded as a vector. Fix in `services/embeddings._search_pgvector`:
  cast both operands to `Vector(dims)` and pin `op('<=>', return_type=Float)`.
  Verified the DB path now returns grounded citations with no fallback warning.

## Known environment limitation
- The browser-based Playwright run (`e2e/paper_tutor.spec.ts`) could **not** be
  executed here: `npx playwright install chromium` is network-blocked and the
  system Chrome path is inaccessible. The spec is committed and correct (gated
  behind `USE_FAKE_AI=1`, fixture at `e2e/fixtures/sample-paper.pdf`, playwright
  `webServer.env` exports the flag). The exact integration it exercises was
  instead validated against real Postgres+pgvector via the Flask test client
  (see Status). Run it in any env with chromium available.

## Out of scope (per spec)
Token streaming (SSE), accounts/auth, multi-paper cross-referencing, OCR for
scanned PDFs.

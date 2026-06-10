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

## Increment log (2026-06-09) — UX: PDF preview, tutor speaks first, analysis behind toggle

Why: the workspace previously showed a structured-analysis panel next to the
chat and left the user staring at an empty conversation. Readers want to see the
*actual paper* while being tutored, and a blank chat creates a cold-start
("what do I even say?"). This increment makes the tutor proactive and keeps the
source document in view; the derived analysis becomes secondary (opt-in).

- **Inline PDF preview.** Raw upload bytes are now persisted (`Paper.pdf_data`,
  `LargeBinary`, `deferred=True` so list/read queries don't drag the blob).
  Migration `b2c3d4e5f6a7_add_pdf_data_to_paper` (nullable → legacy rows stay
  valid, they just 404 the preview). New route `GET /papers/<id>/pdf` streams
  `application/pdf` with a `secure_filename`-sanitized inline Content-Disposition,
  session-scoped (cross-session/no-bytes → 404). `paper.html` renders it in an
  `<iframe>` where the analysis panel used to be.
- **Tutor speaks first.** `get_or_create_conversation` now seeds one opening
  assistant message on creation: `tutor.generate_opening` retrieves the paper's
  most representative chunks (query = analysis summary, else title) and asks a
  single grounded guiding question. Any AI failure (embed or chat) degrades to
  `tutor.DEFAULT_OPENING` instead of 500-ing the workspace, so the tutor always
  speaks first. Chat island empty-state copy updated to "Starting the
  conversation…".
- **Analysis behind a toggle.** `paper.html` moves the analysis island into a
  collapsed `<details>` ("Show paper analysis"); E2E asserts it's hidden until
  revealed.
- Tests: `test_paper_views` (+pdf preview: owned 200/%PDF, cross-session 404,
  no-bytes 404), `test_chat_views` (opening seeded + idempotent, AI-failure
  fallback, history ordering starts with assistant). E2E `paper_tutor.spec.ts`
  updated for iframe + seeded message + analysis toggle.

Validation: backend **51 passed**, frontend **6 passed**, mypy/flake8/tsc/eslint
clean. Full flow re-verified against real Postgres+pgvector (ralph-pg, migration
applied) via Flask test client: upload→PDF preview (200, `%PDF`)→seeded opening
→graded turn (score + native pgvector cosine citation). Browser Playwright still
blocked here (no chromium/network); spec committed and correct.

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

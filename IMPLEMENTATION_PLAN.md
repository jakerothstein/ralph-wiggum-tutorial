# Implementation Plan — Research Paper Comprehension Tutor

Spec: `specs/paper-comprehension-tutor.md` (comprehensive, self-contained).

This feature **replaces Space Invaders** with a Flask + React Islands app that
ingests a PDF research paper, analyzes it (GitHub Models chat in JSON mode),
embeds its chunks into pgvector, and runs a hybrid-Socratic RAG tutor that tracks
a 0-100 comprehension score.

## Status

> **Backend foundation + service layer: COMPLETE & green.**
> Space Invaders is still present (frontend + `/` route) and will be removed in
> the integration step once the paper views/islands exist (avoids a broken
> half-state — see the "single source of truth" rule).

Validation green as of this increment:
- `PYTHONPATH=src pytest tests/` -> 34 passed (services + models + session + retained game view tests).
- `mypy src/ --ignore-missing-imports` -> clean (strict).
- `flake8 src/ tests/` -> clean.
- `cd frontend && npm test` -> unchanged (game tests still pass; frontend not yet touched).

---

## What was built (2026-06-09)

### Phase 1 — Foundation (DONE)
- `requirements.txt`: added `pypdf`, `openai`, `pgvector`, `numpy`.
- `config.py`: `GITHUB_TOKEN`, `GITHUB_MODELS_ENDPOINT`, chat/embedding model
  ids, `EMBEDDING_DIMS`, `MAX_UPLOAD_BYTES`, `CHUNK_SIZE_TOKENS`,
  `CHUNK_OVERLAP_TOKENS`, `RETRIEVAL_TOP_K`, `USE_FAKE_AI`, AI timeout/retries.
  TestingConfig forces `USE_FAKE_AI=True` and `EMBEDDING_DIMS=16`.
- `.env.example` documents all new vars.
- `services/ai_client.py`: single AI integration point. `GitHubModelsClient`
  (OpenAI SDK, JSON mode, retry, typed `AiClientError`) + `FakeAiClient`
  (deterministic, hash-based embeddings + canned schema-valid analysis/tutor
  payloads). `build_ai_client(config)` picks the fake when `USE_FAKE_AI` or no
  token. Stored on `app.extensions['ai_client']`.
- `services/session.py`: signed-cookie anonymous session id via
  `before_request`/`after_request` (no custom decorators). `current_session_id()`.
  NOTE: resets the per-request "set cookie" flag each request because `g` is
  app-context scoped (the test client shares one app context across requests).

### Phase 1 — Models + migration (DONE)
- `models/types.py`: `EmbeddingVector(TypeDecorator)` — pgvector `Vector` on
  PostgreSQL, JSON-text fallback on SQLite (single model def works in both;
  satisfies the SQLite-vs-pgvector caveat). Models subclass `Base` (not
  `db.Model`) to satisfy mypy strict `disallow_subclassing_any`.
- `models/paper.py`: `Paper`, `PaperChunk` (embedding col), `PaperAnalysis`
  (summary + JSON `data`). `models/conversation.py`: `Conversation`, `Message`
  (role, content, cited_chunk_ids JSON, comprehension_score, score_rationale).
  All top-level rows carry `session_id`.
- `migrations/versions/a1b2c3d4e5f6_*`: `CREATE EXTENSION vector` + all tables +
  IVFFlat cosine index. Chained after the drop-hello migration.
  **Not yet applied** (no local PostgreSQL/psql in this environment).

### Phase 2 — Services (DONE, pure/unit-tested)
- `schemas/paper.py`, `schemas/conversation.py`: Pydantic DTOs incl.
  `PaperAnalysisSchema` and `TutorTurn` (clamps comprehension_score 0-100).
- `services/pdf_extractor.py`: `extract()` -> `ExtractedDoc`; typed
  `PdfExtractionError` for non-PDF/empty/oversized/encrypted/image-only.
- `services/chunker.py`: overlapping, page-labelled, ordered chunks.
- `services/embeddings.py`: `embed_chunks`, pure `cosine_similarity` /
  `rank_by_cosine`, and `search()`/`retrieve()` with a pgvector path on
  PostgreSQL and a NumPy in-Python path elsewhere (same return shape).
- `services/analyzer.py`: JSON-mode analysis prompt + Pydantic validation;
  typed `AnalysisError` on malformed output.
- `services/tutor.py`: Socratic system prompt, context block, history
  truncation, score clamp, citation sanitization (falls back to retrieved ids);
  typed `TutorError`.

### Tests (DONE)
`tests/helpers.py` (valid 1-page PDF generator) + `test_ai_client`,
`test_session`, `test_models`, `test_pdf_extractor`, `test_chunker`,
`test_embeddings`, `test_analyzer`, `test_tutor`. Game view tests retained.

---

## Remaining work (next increments, in order)

1. **Controllers** — `controllers/paper.py` (`ingest(file, session_id)`:
   extract -> chunk -> embed -> persist Paper+chunks -> analyze+persist;
   `get`/`list` scoped by session) and `controllers/conversation.py`
   (start conversation, append turn via `tutor.generate_turn` + persist both
   messages, read history). Integration tests with the fake AI client incl.
   cross-session 404 scoping.
2. **Views** — `views/paper.py` (`GET /`, `POST /api/papers`,
   `GET /papers/<id>`, `GET /api/papers/<id>`, `GET /api/papers`) and
   `views/chat.py` (conversation + messages routes). Register `paper_bp` +
   `chat_bp`, drop `game_bp`.
3. **Templates** — `index.html` (upload island), `paper.html` (analysis + chat
   islands). Remove `game.html`.
4. **Frontend** — `types/paper.ts`, `lib/api.ts`, `islands/upload`,
   `islands/analysis`, `islands/chat` (react-markdown, score meter, citations).
   Update `main.ts` registry; remove `islands/game` + `game/` engine + their
   tests. Add `react-markdown` to `frontend/package.json`.
5. **Remove Space Invaders** — delete game view/template/island/engine/tests +
   `e2e/game.spec.ts`; update `tests/conftest.py` fixtures as needed.
6. **E2E** — `e2e/paper_tutor.spec.ts` happy path gated behind `USE_FAKE_AI=1`
   (committed fixture PDF under `e2e/fixtures/`). `script/server` must export
   the flag for the Playwright webServer in CI.
7. **Apply migration** against PostgreSQL when an environment with a running DB
   is available; verify the pgvector search path end-to-end.

## Notes / learnings
- Models subclass `Base` from `models/base.py` (mypy strict rejects subclassing
  `db.Model`, which is `Any`).
- `EmbeddingVector` keeps pgvector isolated so SQLite unit tests run unmodified;
  pgvector-dependent retrieval is covered by the Postgres-backed E2E path.
- The fake AI client is the single hermetic seam for tests + E2E
  (`USE_FAKE_AI=1`); no network/token needed.
- No local `psql`/PostgreSQL in this dev environment — migration not yet applied;
  unit tests use SQLite in-memory.

## Out of scope (per spec)
Token streaming (SSE), accounts/auth, multi-paper cross-referencing, OCR for
scanned PDFs.

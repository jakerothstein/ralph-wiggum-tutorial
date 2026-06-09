# Feature: Research Paper Comprehension Tutor

## Feature Description
A web application that lets a user upload a research paper as a PDF, runs a
deep analysis pipeline over it to understand the paper in context, and then
engages the user in a guided, Socratic-style conversation. The conversation's
goal is twofold: **evaluate** the user's understanding of how the paper works
(its problem, methods, claims, evidence, and limitations) and **improve** that
understanding by probing with questions, offering hints, and explaining when
the user is stuck. The assistant tracks a running comprehension score.

The analysis combines two strategies:
1. **Upfront structured analysis** computed once at upload time (summary, key
   claims, methodology, contributions, limitations, glossary, and a set of
   comprehension questions of varying difficulty).
2. **On-demand retrieval (RAG)** during the conversation: the paper is chunked
   and embedded into a pgvector store so the tutor can ground every answer and
   question in the most relevant passages of the actual paper.

The AI backend is the **GitHub Models API** (OpenAI-compatible chat +
embeddings). This feature **replaces the existing Space Invaders game** as the
application's primary experience.

## User Story
As a student or researcher reading an unfamiliar paper
I want to upload the paper and be guided through a conversation that tests and
deepens my understanding
So that I can verify I truly understand how the paper works and fill the gaps in
my comprehension

## Problem Statement
Reading a research paper passively often leaves readers with an illusion of
understanding. They can recognize the words but cannot explain the core
contribution, reproduce the argument, or identify limitations. There is no
lightweight tool that ingests a specific paper, understands it in depth, and
then actively interrogates the reader to surface and close comprehension gaps,
grounded in the paper's own text rather than generic knowledge.

## Solution Statement
Build a Flask + React Islands feature with three stages:

1. **Ingest** — User uploads a PDF. The backend extracts text, splits it into
   sections and overlapping chunks, embeds the chunks via the GitHub Models
   embeddings endpoint, and stores everything in PostgreSQL (with pgvector for
   the chunk embeddings).
2. **Analyze** — A structured-analysis controller calls the GitHub Models chat
   endpoint to produce a JSON analysis (summary, contributions, methods,
   claims+evidence, limitations, glossary, and a graded question bank). This is
   persisted alongside the paper.
3. **Converse** — A chat island drives a "hybrid Socratic tutor": the AI asks
   probing questions, withholds answers to encourage recall, but gives hints
   and full explanations when the user is stuck. Each turn retrieves the most
   relevant chunks (pgvector cosine search) to ground the tutor, and the tutor
   updates a comprehension score (0–100) with a short rationale that is shown to
   the user and persisted.

Sessions are anonymous and **session-based** (a per-browser UUID stored in a
signed Flask cookie); all papers, analyses, chunks, and conversations are scoped
to that session id so a user sees only their own work without needing accounts.

## Relevant Files
Use these files to implement the feature:

**Backend — existing files to modify**
- `src/app/__init__.py` — Register new blueprints; initialize the session-id
  middleware and the GitHub Models client config.
- `src/app/config.py` — Add config for `GITHUB_TOKEN`, `GITHUB_MODELS_ENDPOINT`,
  chat/embedding model names, max upload size, and chunking parameters.
- `src/app/views/__init__.py` — Register the new `papers` and `chat` blueprints;
  remove the `game` blueprint registration.
- `src/app/models/__init__.py` — Import and export the new SQLAlchemy models.
- `src/app/views/game.py` — **Remove** (replaced by paper views).
- `src/app/templates/game.html` — **Remove** (replaced by paper templates).
- `src/app/templates/base.html` — No structural change needed, but confirm the
  Vite island bootstrap still loads `main.ts`.
- `requirements.txt` — Add `pypdf`, `openai`, `pgvector`, `numpy` (see Phase 1).
- `tests/conftest.py` — Add fixtures: a session-scoped client, a fake GitHub
  Models client, and a sample-paper fixture. Note the SQLite-vs-pgvector caveat
  (see Testing Strategy).
- `tests/test_game_view.py` — **Remove** (replaced by paper/chat tests).
- `AGENTS.md` — Add a short note documenting the new env vars and the AI client.
- `.env.example` — Add the new environment variables with placeholder values.

**Frontend — existing files to modify**
- `frontend/src/main.ts` — Replace the `game` island registration with the new
  `upload`, `analysis`, and `chat` island registrations.
- `frontend/package.json` — Add `react-markdown` (render tutor messages) and
  any small fetch helper if needed; otherwise use native `fetch`.
- `frontend/src/islands/game/` — **Remove** the entire game island directory.
- `frontend/src/game/` — **Remove** the entire pure-TS game engine directory.
- `frontend/src/types/` — Replace game types with paper/chat DTO types.

**Tests / E2E — existing files to modify**
- `e2e/game.spec.ts` — **Remove** (replaced by paper-flow E2E spec).
- `playwright.config.ts` — No change expected; confirm base URL still `/`.

### New Files

**Backend**
- `src/app/models/paper.py` — `Paper`, `PaperChunk`, `PaperAnalysis` models.
- `src/app/models/conversation.py` — `Conversation`, `Message` models (Message
  stores role, content, retrieved chunk ids, comprehension score + rationale).
- `src/app/schemas/paper.py` — Pydantic schemas for upload responses, analysis
  payloads, and chunk DTOs.
- `src/app/schemas/conversation.py` — Pydantic schemas for chat request/response
  (user message in, tutor message + score + citations out).
- `src/app/services/__init__.py` — Services package init.
- `src/app/services/ai_client.py` — Thin wrapper over the GitHub Models
  OpenAI-compatible API (chat completion + embeddings) using the `openai` SDK
  with a configurable `base_url`. Centralizes retries, timeouts, and JSON-mode
  parsing. No custom decorators.
- `src/app/services/pdf_extractor.py` — Extract text per page/section from an
  uploaded PDF using `pypdf`; returns clean text + page map.
- `src/app/services/chunker.py` — Split extracted text into overlapping chunks
  with stable ordering and section labels.
- `src/app/services/embeddings.py` — Embed chunk text via `ai_client`; helpers
  to store/query vectors with pgvector (cosine distance).
- `src/app/services/analyzer.py` — Build the structured upfront analysis by
  prompting the chat model in JSON mode; validate with the Pydantic schema.
- `src/app/services/tutor.py` — Orchestrates a chat turn: retrieve top-k chunks,
  assemble the Socratic system prompt + history, call the chat model, parse the
  tutor reply + updated comprehension score, and persist the message.
- `src/app/services/session.py` — Resolve/create the anonymous session id from a
  signed cookie (Flask `before_request` hook, not a custom decorator).
- `src/app/controllers/paper.py` — Coordinates upload → extract → chunk → embed
  → analyze and exposes read helpers, scoped by session id.
- `src/app/controllers/conversation.py` — Create conversation, append turns,
  read history; scoped by session id.
- `src/app/views/paper.py` — Blueprint: `GET /` (upload/home page),
  `POST /api/papers` (upload), `GET /papers/<id>` (reader+analysis page),
  `GET /api/papers/<id>` (analysis JSON), `GET /api/papers` (list).
- `src/app/views/chat.py` — Blueprint: `POST /api/papers/<id>/conversation`
  (start/get conversation), `POST /api/conversations/<cid>/messages` (send a
  turn), `GET /api/conversations/<cid>/messages` (history).
- `src/app/templates/index.html` — Upload/landing page with the upload island.
- `src/app/templates/paper.html` — Paper workspace: analysis panel island + chat
  island side by side.
- `migrations/versions/<rev>_enable_pgvector_and_paper_tables.py` — Alembic
  migration: `CREATE EXTENSION IF NOT EXISTS vector` + create all new tables.

**Frontend**
- `frontend/src/islands/upload/index.tsx` — Mounts the upload island.
- `frontend/src/islands/upload/UploadIsland.tsx` — Drag/drop + file input,
  uploads PDF, shows ingest/analysis progress, redirects to the paper page.
- `frontend/src/islands/analysis/index.tsx` — Mounts the analysis island.
- `frontend/src/islands/analysis/AnalysisIsland.tsx` — Renders the structured
  analysis (summary, contributions, methods, claims, limitations, glossary).
- `frontend/src/islands/chat/index.tsx` — Mounts the chat island.
- `frontend/src/islands/chat/ChatIsland.tsx` — Conversation UI: message list,
  input box, comprehension-score meter, and chunk citations.
- `frontend/src/lib/api.ts` — Typed `fetch` helpers for the backend endpoints.
- `frontend/src/types/paper.ts` — Shared DTO types matching the Pydantic schemas.

**Tests**
- `tests/test_pdf_extractor.py`, `tests/test_chunker.py`,
  `tests/test_embeddings.py`, `tests/test_analyzer.py`, `tests/test_tutor.py`
  — Unit tests for services (AI + DB calls mocked/faked).
- `tests/test_paper_views.py`, `tests/test_chat_views.py` — Route/integration
  tests using the fake AI client.
- `frontend/src/islands/upload/UploadIsland.test.tsx`,
  `frontend/src/islands/chat/ChatIsland.test.tsx` — Vitest component tests.
- `e2e/paper_tutor.spec.ts` — End-to-end happy-path flow (see E2E task below).

## Implementation Plan
### Phase 1: Foundation
- Add Python dependencies: `pypdf` (PDF text extraction), `openai` (GitHub
  Models OpenAI-compatible client), `pgvector` (SQLAlchemy `Vector` column +
  cosine ops), `numpy` (vector math/fallback). Add `react-markdown` to the
  frontend.
- Add configuration in `config.py` and `.env.example`:
  - `GITHUB_TOKEN` (PAT with `models: read` permission)
  - `GITHUB_MODELS_ENDPOINT` (default `https://models.github.ai/inference`;
    OpenAI-compatible — verify against current GitHub Models docs at build time)
  - `GITHUB_MODELS_CHAT_MODEL` (e.g. `gpt-4o-mini`)
  - `GITHUB_MODELS_EMBEDDING_MODEL` (e.g. `text-embedding-3-small`, 1536 dims)
  - `MAX_UPLOAD_BYTES`, `CHUNK_SIZE_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `RETRIEVAL_TOP_K`
- Create the Alembic migration that runs `CREATE EXTENSION IF NOT EXISTS vector`
  and creates the new tables. The `PaperChunk.embedding` column uses
  pgvector's `Vector(<embedding_dims>)` type with an index for cosine distance.
- Build `services/ai_client.py` as the single integration point for the GitHub
  Models API, so every other service depends on an injectable client (this makes
  faking trivial in tests).
- Build `services/session.py` and wire a `before_request` hook in the app
  factory that ensures every request has a session id cookie.

### Phase 2: Core Implementation
- **Ingest pipeline**: `pdf_extractor` → `chunker` → `embeddings` → persist
  `Paper` + `PaperChunk` rows. Orchestrated by `controllers/paper.py`.
- **Upfront analysis**: `analyzer.py` prompts the chat model in JSON mode to
  produce a `PaperAnalysis` (validated by Pydantic), persisted and returned.
- **Tutor turn**: `tutor.py` retrieves top-k chunks via pgvector cosine search,
  assembles the hybrid-Socratic system prompt + truncated history + retrieved
  context, calls the chat model, parses `{reply, comprehension_score,
  score_rationale, cited_chunk_ids}`, and persists a `Message`.
- **Views**: implement the `paper` and `chat` blueprints and Jinja templates
  with island mount points (`data-island="upload"`, `"analysis"`, `"chat"`).
- **Frontend islands**: upload (with progress states), analysis (read-only
  render), chat (streaming-optional; start with request/response, render
  markdown, show score meter + citations).

### Phase 3: Integration
- Remove all Space Invaders code (views, template, game island, game engine,
  game tests, game E2E) and update the island registry + blueprint registration
  so `/` serves the new upload page.
- Wire end-to-end: upload returns a paper id → redirect to `/papers/<id>` →
  analysis island fetches analysis JSON → chat island starts a conversation and
  exchanges turns.
- Add the E2E spec and run the full validation suite to confirm zero
  regressions.

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Add dependencies and configuration
- Add `pypdf`, `openai`, `pgvector`, `numpy` to `requirements.txt`; install.
- Add `react-markdown` to `frontend/package.json`; install.
- Add all new settings to `src/app/config.py` and document them in
  `.env.example` and `AGENTS.md`.

### 2. Create the AI client service
- Implement `src/app/services/ai_client.py` wrapping the `openai` SDK pointed at
  `GITHUB_MODELS_ENDPOINT` with `GITHUB_TOKEN`. Expose `chat_json(messages,
  schema_hint)` and `embed(texts) -> list[list[float]]`. Centralize timeouts and
  a small retry. Keep it dependency-injectable (constructed in the app factory,
  stored on `app.extensions` or passed into services).
- Unit-test with a fake transport (no real network calls).

### 3. Create the session middleware
- Implement `src/app/services/session.py` to read/create a signed
  `paper_session` cookie and expose `current_session_id()`.
- Register a `before_request` hook in `src/app/__init__.py`.
- Test that requests without a cookie get one and that the id is stable.

### 4. Create models and the migration
- Implement `src/app/models/paper.py` and `src/app/models/conversation.py`.
- `PaperChunk.embedding` uses `pgvector.sqlalchemy.Vector(<dims>)`.
- All top-level rows carry a `session_id` column for scoping.
- Write the Alembic migration enabling the `vector` extension and creating the
  tables + a cosine index on `paper_chunk.embedding`.
- Run `script/setup` (or `flask db upgrade`) against PostgreSQL and confirm.

### 5. Implement the ingest services
- `pdf_extractor.py`: `extract(file_bytes) -> ExtractedDoc` (text + page map);
  reject non-PDF / oversized / empty inputs with a clear error.
- `chunker.py`: `chunk(extracted) -> list[Chunk]` with overlap + section labels.
- `embeddings.py`: `embed_chunks(chunks)` via `ai_client`; `search(paper_id,
  query, top_k)` using pgvector cosine distance.
- Unit-test each with fixtures and the fake AI client.

### 6. Implement the analyzer service
- `analyzer.py`: `analyze(paper) -> PaperAnalysis` using a JSON-mode chat prompt;
  validate with the Pydantic schema; persist.
- Unit-test the prompt assembly and that malformed model output is handled
  (raises a typed error, not a crash).

### 7. Implement the paper controller and views
- `controllers/paper.py`: `ingest(file, session_id)` orchestrates extract →
  chunk → embed → persist → analyze; plus `get`, `list` scoped by session.
- `views/paper.py`: routes for the home/upload page, upload API, paper page, and
  analysis JSON. Enforce session scoping (404 on cross-session access).
- Integration-test the routes with the fake AI client.

### 8. Implement the tutor service, conversation controller and chat views
- `tutor.py`: assemble the hybrid-Socratic system prompt (ask questions,
  withhold answers, hint, then explain when stuck; always ground in retrieved
  chunks; output a structured turn with an updated 0–100 comprehension score and
  rationale). Retrieve top-k chunks per turn.
- `controllers/conversation.py`: start conversation, append turn, read history.
- `views/chat.py`: conversation + messages routes, session-scoped.
- Integration-test a full multi-turn exchange with the fake AI client, asserting
  the score is persisted and citations reference real chunks.

### 9. Build the frontend DTO types and API layer
- `frontend/src/types/paper.ts` mirrors the Pydantic schemas.
- `frontend/src/lib/api.ts` typed `fetch` helpers for all endpoints.

### 10. Build the upload island
- `UploadIsland.tsx`: file input + drag/drop, client-side PDF/size validation,
  POST to `/api/papers`, progress states (uploading → analyzing → done), then
  redirect to `/papers/<id>`. Show errors clearly.
- Vitest component test.

### 11. Build the analysis island
- `AnalysisIsland.tsx`: fetch and render the structured analysis sections.

### 12. Build the chat island
- `ChatIsland.tsx`: message list (markdown), input box, comprehension-score
  meter with rationale tooltip, and per-message chunk citations. Disable input
  while awaiting a reply; handle errors.
- Vitest component test.

### 13. Wire templates and the island registry
- Create `templates/index.html` (upload island) and `templates/paper.html`
  (analysis + chat islands).
- Update `frontend/src/main.ts` island registry with `upload`, `analysis`,
  `chat`.

### 14. Remove Space Invaders
- Delete `src/app/views/game.py`, `src/app/templates/game.html`,
  `frontend/src/islands/game/`, `frontend/src/game/`, `tests/test_game_view.py`,
  `e2e/game.spec.ts`.
- Update `src/app/views/__init__.py` to register `paper_bp` and `chat_bp` and
  drop `game_bp`. Remove the `game` island from `main.ts`.
- Update/replace any game-specific frontend types.

### 15. Create the E2E test file
- Create `e2e/paper_tutor.spec.ts` validating the minimal happy path:
  1. Go to `/`, assert the upload page renders (title + upload island visible).
  2. Upload a small fixture PDF (committed under `e2e/fixtures/`).
  3. Assert redirect to `/papers/<id>` and that the analysis island renders a
     summary.
  4. Send one chat message; assert a tutor reply appears and the
     comprehension-score meter is visible.
  5. Capture a screenshot of the paper workspace as evidence.
- To keep E2E hermetic, gate the AI calls behind a test mode: when an env flag
  (e.g. `USE_FAKE_AI=1`) is set, `ai_client` returns canned analysis + tutor
  responses so the E2E run needs no GitHub Models token or network. The
  Playwright `webServer`/`script/server` must export this flag in CI.

### 16. Run all validation commands
- Run the full `Validation Commands` section below and fix everything until it
  is green with zero regressions.

## Testing Strategy
### Unit Tests
- `pdf_extractor`: extracts text from a known small PDF; rejects non-PDF,
  empty, and oversized inputs.
- `chunker`: correct chunk count, overlap, ordering, and section labeling for a
  known input.
- `embeddings`: calls the AI client with the right batched inputs; `search`
  orders results by cosine similarity (can be tested with a fake/in-memory
  vector set independent of pgvector).
- `analyzer`: builds the expected prompt; validates good JSON; raises a typed
  error on malformed JSON.
- `tutor`: assembles system prompt + retrieved context + history; parses the
  structured turn; clamps/persists the comprehension score; cites real chunks.
- `ai_client`: builds correct request shape; retries once on transient failure;
  surfaces a typed error on hard failure. All without real network.
- View/integration tests: upload → analysis → conversation happy path, plus
  session scoping (cross-session access returns 404) — all with the fake AI
  client.
- Frontend (Vitest): UploadIsland validation + state transitions; ChatIsland
  renders messages, disables input while pending, shows the score meter.

### Edge Cases
- Non-PDF upload, corrupt PDF, password-protected PDF, empty/zero-page PDF.
- Upload exceeding `MAX_UPLOAD_BYTES`.
- Very large paper (chunk batching; embedding request batching/limits).
- Scanned/image-only PDF with little or no extractable text (clear user error,
  no crash).
- GitHub Models API errors / timeouts / rate limits (graceful, typed errors
  surfaced to the UI).
- Malformed JSON from the model for analysis or a tutor turn.
- Comprehension score out of range → clamped to 0–100.
- Cross-session access to another session's paper/conversation → 404.
- **pgvector/SQLite caveat**: the testing config uses SQLite in-memory, which has
  no `vector` type. Keep pgvector usage isolated in `embeddings.py` so unit tests
  exercise retrieval via a fake/in-memory path, and run pgvector-dependent
  coverage against PostgreSQL (the E2E flow / a dedicated Postgres-backed test).
  Do **not** let SQLite-incompatible columns break the SQLite test suite (e.g.
  conditionally define the `Vector` column type, or skip those tests when the
  bound dialect is SQLite).

## Acceptance Criteria
- Visiting `/` shows the paper upload page (Space Invaders is fully removed).
- Uploading a valid research-paper PDF stores the paper, extracts and chunks its
  text, embeds the chunks into pgvector, and produces a persisted structured
  analysis.
- The paper workspace (`/papers/<id>`) renders the analysis (summary,
  contributions, methods, claims, limitations, glossary).
- The chat tutor asks Socratic questions grounded in the paper, withholds
  answers until the user is stuck, then hints/explains, and displays + persists
  an updated comprehension score with a rationale on each turn.
- Tutor replies cite the specific chunks they were grounded in.
- All data (papers, chunks, analyses, conversations, messages) is persisted in
  PostgreSQL and scoped to the anonymous browser session; users cannot access
  another session's data.
- `script/test`, `script/typecheck`, `script/lint`, and `script/test-e2e` all
  pass with zero regressions.

## Validation Commands
Execute every command to validate the feature works correctly with zero regressions.

- `script/setup` — Apply the pgvector migration and new tables against PostgreSQL.
- `script/test` — Run `pytest` + `vitest` (backend services/views + frontend
  islands). Direct: `PYTHONPATH=src pytest tests/` and `cd frontend && npm test`.
- `script/typecheck` — `mypy src/ --ignore-missing-imports` + `cd frontend && npm run typecheck`.
- `script/lint` — `flake8 src/ tests/` + `cd frontend && npm run lint`.
- `npx playwright install chromium` — First-run browser install (if needed).
- `USE_FAKE_AI=1 script/test-e2e` — Run `e2e/paper_tutor.spec.ts` end-to-end with
  the deterministic fake AI client (no token/network). Use `--reporter=list`.

All tests must pass using the scripts in `AGENTS.md` plus the new tests added for
this feature.

## Notes
- **GitHub Models specifics**: The endpoint and model ids should be verified
  against the current GitHub Models docs during implementation, since the
  service is evolving. Because the client is OpenAI-compatible, the `openai` SDK
  with a custom `base_url` and the `GITHUB_TOKEN` as the API key is the simplest
  integration. Keep the embedding dimension in config so a model swap only
  touches config + migration.
- **No custom decorators**: per project convention, avoid writing custom
  decorators. Standard Flask blueprint route decorators and `before_request`
  hooks are fine; session scoping is enforced inside view functions.
- **Streaming (future)**: Start with simple request/response chat turns. Token
  streaming for tutor replies can be added later via Server-Sent Events without
  changing the data model.
- **Cost/safety**: Batch embeddings, truncate conversation history sent to the
  model, and cap retrieved context size to control token usage.
- **Extensibility**: The service layer (`ai_client`, `pdf_extractor`, `chunker`,
  `embeddings`, `analyzer`, `tutor`) is deliberately decoupled so the AI provider
  or retrieval strategy can change without touching views or the frontend.

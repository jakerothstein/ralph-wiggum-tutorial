"""The hybrid-Socratic tutor.

Orchestrates a single chat turn: given the retrieved chunks (RAG context), the
truncated conversation history, and the new user message, it assembles the
Socratic system prompt, calls the chat model in JSON mode, and parses a
structured :class:`TutorTurn` (reply + updated 0–100 comprehension score +
rationale + citations).

Pedagogy encoded in the system prompt:
* Ask probing questions; **withhold** direct answers to encourage recall.
* Offer a hint when the user struggles, and a full explanation only once they
  are clearly stuck — then re-probe.
* **Always ground** statements in the retrieved passages, never generic
  knowledge, and cite the chunks used.

Two guarantees enforced in code (not left to the model):
* The comprehension score is clamped to 0–100 (via the Pydantic schema).
* ``cited_chunk_ids`` is sanitized to only reference chunks actually retrieved
  for this turn; if the model cites nothing valid we fall back to the retrieved
  chunk ids so a grounded reply always carries provenance.
"""
from __future__ import annotations

from typing import Protocol, Sequence

from pydantic import ValidationError

from ..schemas.conversation import TutorTurn
from .ai_client import AiClient, AiClientError

# Keep the model focused and the token budget bounded.
_MAX_HISTORY_MESSAGES = 12
_MAX_CHUNK_CHARS = 1200


class TutorError(Exception):
    """Raised when a tutor turn cannot be produced or parsed."""


# Static fallback used when the model can't produce an opening question, so a
# new conversation always begins with the tutor inviting the user in.
DEFAULT_OPENING = (
    "Welcome! I'm your tutor for this paper. To get us started: in your own "
    'words, what do you think the core problem this paper sets out to solve is, '
    'and what made you want to dig into it?'
)


class _ChunkLike(Protocol):
    id: int
    section: str
    content: str


_SYSTEM_PROMPT = (
    'You are a Socratic tutor helping a user deeply understand a specific '
    'research paper. Your goals: (1) evaluate the user\'s understanding of the '
    'paper\'s problem, methods, claims, evidence, and limitations; (2) improve '
    'it. Ask focused, probing questions and withhold direct answers to encourage '
    'recall. If the user struggles, give a hint; if they are clearly stuck, give '
    'a concise explanation, then ask a follow-up. Ground EVERY statement in the '
    'provided paper excerpts — never rely on outside knowledge — and cite the '
    'excerpt ids you used. Respond with a single JSON object: '
    '{"reply": string, "comprehension_score": integer 0-100, '
    '"score_rationale": string, "cited_chunk_ids": array of integers}. The score '
    'is your current estimate of how well the user understands the paper.'
)


_OPENING_SYSTEM_PROMPT = (
    'You are a Socratic tutor helping a user deeply understand a specific '
    'research paper. The conversation is just beginning and the user has not '
    'said anything yet. Open warmly and ask a single, inviting guiding question '
    'that gets the user engaging with the paper (for example, what they think '
    'its core problem is or what drew them to it). Keep it to one or two '
    'sentences, ground it in the provided excerpts, and do NOT lecture or give '
    'answers. Respond with a single JSON object: '
    '{"reply": string, "comprehension_score": integer 0-100, '
    '"score_rationale": string, "cited_chunk_ids": array of integers}.'
)


def build_context_block(chunks: Sequence[_ChunkLike]) -> str:
    """Render retrieved chunks as a labelled, id-tagged context block."""
    if not chunks:
        return '(no relevant excerpts retrieved)'
    parts = []
    for c in chunks:
        snippet = c.content[:_MAX_CHUNK_CHARS]
        parts.append(f'[chunk {c.id} — {c.section}]\n{snippet}')
    return '\n\n'.join(parts)


def build_messages(
    chunks: Sequence[_ChunkLike],
    history: Sequence[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """Assemble system + context + truncated history + new user message."""
    context = build_context_block(chunks)
    messages: list[dict[str, str]] = [
        {'role': 'system', 'content': _SYSTEM_PROMPT},
        {
            'role': 'system',
            'content': f'Relevant excerpts from the paper:\n{context}',
        },
    ]
    for msg in list(history)[-_MAX_HISTORY_MESSAGES:]:
        role = msg.get('role', 'user')
        if role not in ('user', 'assistant'):
            continue
        messages.append({'role': role, 'content': msg.get('content', '')})
    messages.append({'role': 'user', 'content': user_message})
    return messages


def _sanitize_citations(
    turn: TutorTurn, retrieved_ids: Sequence[int]
) -> list[int]:
    """Drop cited ids that weren't retrieved; fall back to retrieved ids."""
    allowed = set(retrieved_ids)
    valid = [cid for cid in turn.cited_chunk_ids if cid in allowed]
    if not valid:
        return list(retrieved_ids)
    return valid


def generate_turn(
    ai_client: AiClient,
    chunks: Sequence[_ChunkLike],
    history: Sequence[dict[str, str]],
    user_message: str,
) -> TutorTurn:
    """Produce a structured tutor turn grounded in the retrieved chunks."""
    messages = build_messages(chunks, history, user_message)
    try:
        raw = ai_client.chat_json(messages, schema_hint='tutor_turn')
    except AiClientError as exc:
        raise TutorError(f'tutor request failed: {exc}') from exc
    try:
        turn = TutorTurn.model_validate(raw)
    except ValidationError as exc:
        raise TutorError(f'model returned an invalid tutor turn: {exc}') from exc

    retrieved_ids = [c.id for c in chunks]
    turn.cited_chunk_ids = _sanitize_citations(turn, retrieved_ids)
    return turn


def generate_opening(
    ai_client: AiClient,
    chunks: Sequence[_ChunkLike],
) -> TutorTurn:
    """Produce the tutor's opening guiding question, grounded in the chunks.

    The user has not spoken yet, so there is no history and no comprehension
    score to report — the caller should treat only ``reply`` (and optionally the
    citations) as meaningful.

    Raises:
        TutorError: If the model turn cannot be produced/parsed.
    """
    context = build_context_block(chunks)
    messages: list[dict[str, str]] = [
        {'role': 'system', 'content': _OPENING_SYSTEM_PROMPT},
        {
            'role': 'system',
            'content': f'Relevant excerpts from the paper:\n{context}',
        },
        {
            'role': 'user',
            'content': 'Please greet me and ask your opening guiding question.',
        },
    ]
    try:
        raw = ai_client.chat_json(messages, schema_hint='tutor_turn')
    except AiClientError as exc:
        raise TutorError(f'tutor opening request failed: {exc}') from exc
    try:
        turn = TutorTurn.model_validate(raw)
    except ValidationError as exc:
        raise TutorError(f'model returned an invalid tutor turn: {exc}') from exc

    turn.cited_chunk_ids = _sanitize_citations(turn, [c.id for c in chunks])
    return turn

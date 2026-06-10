"""Conversation controller — drives the hybrid-Socratic tutor loop.

Responsibilities:

* ``get_or_create_conversation`` — one conversation per (paper, session); the
  chat island calls this on mount and gets a stable conversation id back.
* ``append_turn`` — the core RAG turn. For each user message we (1) retrieve the
  top-k most relevant chunks via cosine search, (2) feed the truncated history +
  retrieved context to :func:`tutor.generate_turn`, and (3) persist BOTH the user
  message and the assistant reply (with its citations + comprehension score) in a
  single commit so the stored history can never be left half-written.
* ``get_messages`` — read history for the UI / page reloads.

All access is session-scoped: a conversation is only reachable through a paper
the session owns, so cross-session access raises
:class:`~app.controllers.paper.PaperNotFoundError` (surfaced as a 404).
"""
from __future__ import annotations

from typing import Any

from flask import current_app
from sqlalchemy import select

from ..models import Conversation, Message, db
from ..services import embeddings, tutor
from ..services.ai_client import AiClient, AiClientError
from . import paper as paper_controller


class ConversationNotFoundError(Exception):
    """Raised when a conversation does not exist or is not session-owned."""


def _ai_client() -> AiClient:
    client: AiClient = current_app.extensions['ai_client']
    return client


def get_or_create_conversation(paper_id: int, session_id: str) -> Conversation:
    """Return the session's conversation for a paper, creating it if needed.

    A newly created conversation is seeded with an opening assistant message —
    a guiding question — so the tutor speaks first and the user never has to
    start the conversation from a blank slate.
    """
    # Ensures the paper exists and is owned by this session (404 otherwise).
    paper = paper_controller.get(paper_id, session_id)

    conversation = db.session.execute(
        select(Conversation).where(
            Conversation.paper_id == paper_id,
            Conversation.session_id == session_id,
        )
    ).scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(paper_id=paper_id, session_id=session_id)
        db.session.add(conversation)
        db.session.flush()  # assign conversation.id for the opening message FK
        _seed_opening(conversation, paper)
        db.session.commit()
    return conversation


def _seed_opening(conversation: Conversation, paper: Any) -> None:
    """Persist the tutor's opening guiding question for a new conversation.

    The opening is grounded in the paper's most representative chunks (retrieved
    using the analysis summary as the query). If the model can't produce one we
    fall back to a static guiding question so the conversation always starts
    with the tutor speaking.
    """
    ai_client = _ai_client()
    top_k = int(current_app.config['RETRIEVAL_TOP_K'])
    summary = paper.analysis.summary if paper.analysis else ''
    query = summary or paper.title

    # Creating a conversation now makes AI calls (embed + chat). Any failure on
    # either degrades to a static guiding question rather than 500-ing the
    # workspace, so the tutor always speaks first.
    try:
        retrieved = embeddings.retrieve(
            ai_client, db.session(), paper.id, query, top_k
        )
        chunks: list[Any] = [chunk for chunk, _score in retrieved]
        turn = tutor.generate_opening(ai_client, chunks)
        reply, cited = turn.reply, turn.cited_chunk_ids
    except (tutor.TutorError, AiClientError):
        reply, cited = tutor.DEFAULT_OPENING, []

    db.session.add(
        Message(
            conversation_id=conversation.id,
            role='assistant',
            content=reply,
            cited_chunk_ids=cited,
        )
    )


def get_conversation(conversation_id: int, session_id: str) -> Conversation:
    """Return a session-owned conversation or raise."""
    conversation = db.session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.session_id == session_id,
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise ConversationNotFoundError(
            f'conversation {conversation_id} not found'
        )
    return conversation


def get_messages(conversation_id: int, session_id: str) -> list[Message]:
    """Return the full ordered message history for a conversation."""
    conversation = get_conversation(conversation_id, session_id)
    return list(conversation.messages)


def append_turn(
    conversation_id: int, session_id: str, user_message: str
) -> tuple[Message, Message]:
    """Run one tutor turn and persist the user + assistant messages.

    Returns the persisted ``(user_message, assistant_message)`` pair.

    Raises:
        tutor.TutorError: If the model turn cannot be produced/parsed.
    """
    conversation = get_conversation(conversation_id, session_id)
    ai_client = _ai_client()
    top_k = int(current_app.config['RETRIEVAL_TOP_K'])

    retrieved = embeddings.retrieve(
        ai_client, db.session(), conversation.paper_id, user_message, top_k
    )
    chunks: list[Any] = [chunk for chunk, _score in retrieved]
    history = [
        {'role': m.role, 'content': m.content} for m in conversation.messages
    ]

    turn = tutor.generate_turn(ai_client, chunks, history, user_message)

    user_row = Message(
        conversation_id=conversation.id,
        role='user',
        content=user_message,
        cited_chunk_ids=[],
    )
    assistant_row = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=turn.reply,
        cited_chunk_ids=turn.cited_chunk_ids,
        comprehension_score=turn.comprehension_score,
        score_rationale=turn.score_rationale,
    )
    db.session.add(user_row)
    db.session.add(assistant_row)
    db.session.commit()
    return user_row, assistant_row

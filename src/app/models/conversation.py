"""Conversation-related SQLAlchemy models.

A :class:`Conversation` is a single tutoring session about one paper, scoped to
the same anonymous ``session_id`` as the paper. Each :class:`Message` records one
turn. Assistant turns additionally store:

* ``cited_chunk_ids`` — the paper chunks the tutor grounded its reply in (RAG
  provenance, shown to the user as citations).
* ``comprehension_score`` / ``score_rationale`` — the running 0–100 estimate of
  the user's understanding and a short justification. Persisting these per turn
  lets the UI render a score history and survives page reloads.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .paper import Paper


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    """A tutoring conversation about a single paper."""

    __tablename__ = 'conversation'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey('paper.id', ondelete='CASCADE'), index=True, nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    paper: Mapped['Paper'] = relationship(back_populates='conversations')
    messages: Mapped[list['Message']] = relationship(
        back_populates='conversation',
        cascade='all, delete-orphan',
        order_by='Message.id',
    )


class Message(Base):
    """A single turn in a conversation (user or assistant)."""

    __tablename__ = 'message'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey('conversation.id', ondelete='CASCADE'), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Assistant-only fields (null for user turns).
    cited_chunk_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    comprehension_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    conversation: Mapped['Conversation'] = relationship(back_populates='messages')

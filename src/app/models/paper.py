"""Paper-related SQLAlchemy models.

These models persist everything produced by the ingest + analysis pipeline:

* :class:`Paper` — one uploaded research paper, scoped to an anonymous browser
  ``session_id`` so users only ever see their own uploads.
* :class:`PaperChunk` — an overlapping slice of the paper's text plus its
  embedding. Chunks are what the tutor retrieves (RAG) to ground every answer in
  the paper's own words.
* :class:`PaperAnalysis` — the structured, upfront analysis (summary,
  contributions, methods, claims, limitations, glossary, question bank) computed
  once at upload time and stored as JSON.

Why ``session_id`` on the top-level rows: sessions are anonymous (no accounts),
so scoping by the signed-cookie session id is the only access-control boundary.
Storing it directly on ``Paper`` and ``Conversation`` lets every view enforce
"you can only touch your own data" with a simple ``WHERE session_id = ...``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .types import EmbeddingVector

# Embedding dimensionality used for the pgvector column. The value only matters
# for the PostgreSQL ``Vector`` type; SQLite stores embeddings as JSON text.
EMBEDDING_DIMS = 1536


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Paper(Base):
    """An uploaded research paper, scoped to an anonymous session."""

    __tablename__ = 'paper'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    num_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    chunks: Mapped[list['PaperChunk']] = relationship(
        back_populates='paper',
        cascade='all, delete-orphan',
        order_by='PaperChunk.chunk_index',
    )
    analysis: Mapped['PaperAnalysis | None'] = relationship(
        back_populates='paper', cascade='all, delete-orphan', uselist=False
    )
    conversations: Mapped[list['Conversation']] = relationship(
        back_populates='paper', cascade='all, delete-orphan'
    )


class PaperChunk(Base):
    """An overlapping slice of a paper's text plus its embedding vector."""

    __tablename__ = 'paper_chunk'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey('paper.id', ondelete='CASCADE'), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(256), nullable=False, default='')
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        EmbeddingVector(EMBEDDING_DIMS), nullable=True
    )

    paper: Mapped['Paper'] = relationship(back_populates='chunks')


class PaperAnalysis(Base):
    """The structured upfront analysis for a paper, stored as JSON."""

    __tablename__ = 'paper_analysis'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey('paper.id', ondelete='CASCADE'), unique=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default='')
    # Full validated analysis payload (contributions, methodology, key_claims,
    # limitations, glossary, questions). Kept as JSON so a schema tweak does not
    # require a migration.
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    paper: Mapped['Paper'] = relationship(back_populates='analysis')


# Imported at the bottom to avoid a circular import at module load: the
# Conversation model references Paper via a string relationship.
from .conversation import Conversation  # noqa: E402  (placed last intentionally)

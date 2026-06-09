"""Embeddings + vector retrieval.

This module owns the only pgvector-dependent code in the app, keeping the
SQLite-vs-pgvector split contained (see the spec's testing caveat):

* In **PostgreSQL**, similarity search runs in the database using pgvector's
  cosine-distance operator (``<=>``) for speed and correctness at scale.
* On **other dialects** (SQLite, used by the unit tests), there is no ``vector``
  type, so we load the candidate chunks and rank them in Python with NumPy. The
  pure ranking helpers (:func:`cosine_similarity`, :func:`rank_by_cosine`) are
  also directly unit-tested without any database at all.

Both paths return the same ``(PaperChunk, score)`` shape, so callers are
dialect-agnostic.
"""
from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PaperChunk
from .ai_client import AiClient
from .chunker import Chunk

logger = logging.getLogger(__name__)


def embed_texts(
    ai_client: AiClient, texts: Sequence[str], batch_size: int = 64
) -> list[list[float]]:
    """Embed texts, batching requests to bound per-call token usage."""
    out: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start: start + batch_size])
        out.extend(ai_client.embed(batch))
    return out


def embed_chunks(ai_client: AiClient, chunks: Sequence[Chunk]) -> list[list[float]]:
    """Embed the text of each chunk, preserving order."""
    return embed_texts(ai_client, [c.content for c in chunks])


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]; 0 if either vector is degenerate."""
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def rank_by_cosine(
    query: Sequence[float],
    candidates: Sequence[tuple[int, Sequence[float]]],
    top_k: int,
) -> list[tuple[int, float]]:
    """Rank ``(id, vector)`` candidates by descending cosine similarity."""
    scored = [(cid, cosine_similarity(query, vec)) for cid, vec in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[: max(0, top_k)]


def search(
    session: Session,
    paper_id: int,
    query_embedding: Sequence[float],
    top_k: int,
) -> list[tuple[PaperChunk, float]]:
    """Return the ``top_k`` most similar chunks for a paper to a query vector."""
    dialect = session.get_bind().dialect.name
    if dialect == 'postgresql':
        try:
            return _search_pgvector(session, paper_id, query_embedding, top_k)
        except Exception as exc:  # noqa: BLE001 - fall back to in-Python ranking
            logger.warning('pgvector search failed, using Python fallback: %s', exc)
    return _search_python(session, paper_id, query_embedding, top_k)


def _search_pgvector(
    session: Session,
    paper_id: int,
    query_embedding: Sequence[float],
    top_k: int,
) -> list[tuple[PaperChunk, float]]:
    # Cast both operands to pgvector's ``Vector`` so the ``<=>`` cosine-distance
    # operator binds correctly, and pin the result type to ``Float`` so the
    # scalar distance is NOT decoded through the EmbeddingVector type decorator
    # (which wraps the column and would mis-handle a bare float). Cosine
    # distance = 1 - cosine similarity, so we convert back for the caller.
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import Float, cast

    dims = len(query_embedding)
    vec_type = Vector(dims)
    column = cast(PaperChunk.embedding, vec_type)
    query_vec = cast(list(query_embedding), vec_type)
    distance = column.op('<=>', return_type=Float)(query_vec)
    stmt = (
        select(PaperChunk, distance.label('distance'))
        .where(PaperChunk.paper_id == paper_id)
        .order_by(distance)
        .limit(top_k)
    )
    rows = session.execute(stmt).all()
    return [(row[0], 1.0 - float(row[1])) for row in rows]


def _search_python(
    session: Session,
    paper_id: int,
    query_embedding: Sequence[float],
    top_k: int,
) -> list[tuple[PaperChunk, float]]:
    chunks = list(
        session.execute(
            select(PaperChunk).where(PaperChunk.paper_id == paper_id)
        ).scalars()
    )
    candidates = [
        (c.id, c.embedding) for c in chunks if c.embedding is not None
    ]
    ranked = rank_by_cosine(query_embedding, candidates, top_k)
    by_id = {c.id: c for c in chunks}
    return [(by_id[cid], score) for cid, score in ranked]


def retrieve(
    ai_client: AiClient,
    session: Session,
    paper_id: int,
    query_text: str,
    top_k: int,
) -> list[tuple[PaperChunk, float]]:
    """Embed a query and return the most relevant chunks for a paper."""
    query_embedding = ai_client.embed([query_text])[0]
    return search(session, paper_id, query_embedding, top_k)

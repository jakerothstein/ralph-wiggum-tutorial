"""Tests for embeddings + retrieval (pure ranking + SQLite search path)."""
from __future__ import annotations

from typing import cast

from flask import Flask
from sqlalchemy.orm import Session

from app.models import Paper, PaperChunk, db
from app.services.ai_client import FakeAiClient
from app.services.embeddings import (
    cosine_similarity,
    embed_texts,
    rank_by_cosine,
    retrieve,
)


def test_cosine_similarity_bounds() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([0, 0], [1, 1]) == 0.0


def test_rank_by_cosine_orders_desc() -> None:
    query = [1.0, 0.0]
    candidates = [(1, [0.0, 1.0]), (2, [1.0, 0.0]), (3, [0.9, 0.1])]
    ranked = rank_by_cosine(query, candidates, top_k=2)
    assert [cid for cid, _ in ranked] == [2, 3]


def test_embed_texts_batches_and_sizes() -> None:
    client = FakeAiClient(embedding_dims=16)
    vecs = embed_texts(client, ['a', 'b', 'c'], batch_size=2)
    assert len(vecs) == 3 and all(len(v) == 16 for v in vecs)


def test_retrieve_returns_most_similar_chunk(app: Flask) -> None:
    client = FakeAiClient(embedding_dims=16)
    with app.app_context():
        session = cast(Session, db.session)
        paper = Paper(session_id='s1', title='T', filename='f.pdf', num_pages=1)
        db.session.add(paper)
        db.session.flush()
        texts = ['transformers use attention', 'bananas are yellow fruit', 'cats nap']
        embeds = client.embed(texts)
        for i, (t, e) in enumerate(zip(texts, embeds)):
            db.session.add(
                PaperChunk(
                    paper_id=paper.id, chunk_index=i, section='Page 1',
                    content=t, embedding=e,
                )
            )
        db.session.commit()

        results = retrieve(client, session, paper.id, 'attention mechanism', top_k=2)
        assert len(results) == 2
        top_chunk, score = results[0]
        assert top_chunk.embedding is not None
        assert isinstance(score, float)
        # Identical-text query retrieves that exact chunk first (similarity 1.0).
        exact = retrieve(client, session, paper.id, 'cats nap', top_k=1)
        assert exact[0][0].content == 'cats nap'
        assert abs(exact[0][1] - 1.0) < 1e-6

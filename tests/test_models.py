"""Tests that the new models persist and round-trip on SQLite.

These exercise the dialect-adaptive ``EmbeddingVector`` column: on SQLite the
embedding is stored as JSON text and must come back as a list of floats.
"""
from __future__ import annotations

from flask import Flask

from app.models import (
    Conversation,
    Message,
    Paper,
    PaperAnalysis,
    PaperChunk,
    db,
)


def test_paper_graph_round_trips(app: Flask) -> None:
    with app.app_context():
        paper = Paper(session_id='sess', title='T', filename='f.pdf', num_pages=2)
        db.session.add(paper)
        db.session.flush()

        db.session.add(
            PaperChunk(
                paper_id=paper.id, chunk_index=0, section='Page 1',
                content='hello', embedding=[0.1, 0.2, 0.3],
            )
        )
        db.session.add(
            PaperAnalysis(paper_id=paper.id, summary='sum', data={'questions': []})
        )
        conv = Conversation(paper_id=paper.id, session_id='sess')
        db.session.add(conv)
        db.session.flush()
        db.session.add(
            Message(
                conversation_id=conv.id, role='assistant', content='hi',
                cited_chunk_ids=[1, 2], comprehension_score=42, score_rationale='r',
            )
        )
        db.session.commit()

        loaded = db.session.get(Paper, paper.id)
        assert loaded is not None
        assert loaded.num_pages == 2
        assert len(loaded.chunks) == 1
        assert loaded.chunks[0].embedding == [0.1, 0.2, 0.3]
        assert loaded.analysis is not None
        assert loaded.analysis.summary == 'sum'
        assert loaded.conversations[0].messages[0].comprehension_score == 42
        assert loaded.conversations[0].messages[0].cited_chunk_ids == [1, 2]

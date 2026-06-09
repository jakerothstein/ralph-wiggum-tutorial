"""Tests for the Socratic tutor service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import pytest

from app.services.ai_client import FakeAiClient
from app.services.tutor import (
    TutorError,
    build_context_block,
    build_messages,
    generate_turn,
)


@dataclass
class _Chunk:
    id: int
    section: str
    content: str


def _chunks() -> list[_Chunk]:
    return [
        _Chunk(id=10, section='Page 1', content='The problem is X.'),
        _Chunk(id=11, section='Page 2', content='The method is Y.'),
    ]


def test_build_context_block_tags_chunk_ids() -> None:
    block = build_context_block(_chunks())
    assert '[chunk 10' in block and '[chunk 11' in block


def test_build_messages_truncates_history() -> None:
    history = [{'role': 'user', 'content': f'm{i}'} for i in range(30)]
    messages = build_messages(_chunks(), history, 'new question')
    # 2 system messages + truncated history + 1 new user message.
    assert messages[0]['role'] == 'system'
    assert messages[-1]['content'] == 'new question'
    history_msgs = [m for m in messages if m['role'] in ('user', 'assistant')]
    assert len(history_msgs) <= 12 + 1


def test_generate_turn_citations_fall_back_to_retrieved() -> None:
    turn = generate_turn(FakeAiClient(8), _chunks(), [], 'I think it solves X')
    assert 0 <= turn.comprehension_score <= 100
    # Fake returns no citations -> falls back to retrieved chunk ids.
    assert set(turn.cited_chunk_ids) == {10, 11}


class _ScoreClient:
    def __init__(self, score: int, cited: list[int]) -> None:
        self.score = score
        self.cited = cited

    def chat_json(
        self, messages: Sequence[dict[str, str]], schema_hint: str | None = None
    ) -> dict[str, Any]:
        return {
            'reply': 'ok',
            'comprehension_score': self.score,
            'score_rationale': 'r',
            'cited_chunk_ids': self.cited,
        }

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def test_score_is_clamped() -> None:
    high = generate_turn(_ScoreClient(999, [10]), _chunks(), [], 'x')
    assert high.comprehension_score == 100
    low = generate_turn(_ScoreClient(-50, [11]), _chunks(), [], 'x')
    assert low.comprehension_score == 0


def test_invalid_citations_dropped() -> None:
    turn = generate_turn(_ScoreClient(50, [999, 11]), _chunks(), [], 'x')
    assert turn.cited_chunk_ids == [11]


class _BadClient:
    def chat_json(
        self, messages: Sequence[dict[str, str]], schema_hint: str | None = None
    ) -> dict[str, Any]:
        return {'comprehension_score': 5}  # missing required 'reply'

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def test_generate_turn_raises_on_invalid_output() -> None:
    with pytest.raises(TutorError):
        generate_turn(_BadClient(), _chunks(), [], 'x')

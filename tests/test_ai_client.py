"""Tests for the AI client (fake + real-client error handling)."""
from __future__ import annotations

from typing import Any, Sequence

import pytest

from app.services.ai_client import (
    AiClientError,
    FakeAiClient,
    GitHubModelsClient,
    _parse_json_object,
    build_ai_client,
)


def test_fake_embed_is_deterministic_and_sized() -> None:
    client = FakeAiClient(embedding_dims=16)
    a = client.embed(['hello'])
    b = client.embed(['hello'])
    assert len(a) == 1 and len(a[0]) == 16
    assert a == b
    assert client.embed(['different'])[0] != a[0]


def test_fake_chat_json_branches() -> None:
    client = FakeAiClient(embedding_dims=8)
    analysis = client.chat_json([{'role': 'user', 'content': 'Title: X'}], 'paper_analysis')
    assert 'summary' in analysis and len(analysis['questions']) == 3
    turn = client.chat_json([{'role': 'user', 'content': 'hi'}], 'tutor_turn')
    assert 0 <= turn['comprehension_score'] <= 100
    assert 'reply' in turn


def test_parse_json_object_handles_fences() -> None:
    assert _parse_json_object('```json\n{"a": 1}\n```') == {'a': 1}
    with pytest.raises(AiClientError):
        _parse_json_object('not json')
    with pytest.raises(AiClientError):
        _parse_json_object('[1, 2, 3]')


def test_build_ai_client_uses_fake_without_token() -> None:
    cfg: dict[str, Any] = {'USE_FAKE_AI': False, 'GITHUB_TOKEN': '', 'EMBEDDING_DIMS': 8}
    assert isinstance(build_ai_client(cfg), FakeAiClient)
    cfg2: dict[str, Any] = {'USE_FAKE_AI': True, 'GITHUB_TOKEN': 'tok', 'EMBEDDING_DIMS': 8}
    assert isinstance(build_ai_client(cfg2), FakeAiClient)


class _BoomCompletions:
    def create(self, **kwargs: Any) -> Any:
        raise RuntimeError('network down')


class _BoomClient:
    def __init__(self) -> None:
        self.chat = type('C', (), {'completions': _BoomCompletions()})()
        self.embeddings = _BoomCompletions()


def test_real_client_surfaces_typed_error() -> None:
    client = GitHubModelsClient.__new__(GitHubModelsClient)
    client._client = _BoomClient()
    client._chat_model = 'm'
    client._embedding_model = 'e'
    client._max_retries = 1
    with pytest.raises(AiClientError):
        client.chat_json([{'role': 'user', 'content': 'hi'}])
    with pytest.raises(AiClientError):
        client.embed(['x'])


def test_embed_empty_returns_empty() -> None:
    client = FakeAiClient(embedding_dims=8)
    texts: Sequence[str] = []
    assert client.embed(texts) == []

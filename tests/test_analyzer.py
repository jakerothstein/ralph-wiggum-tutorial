"""Tests for the upfront analyzer service."""
from __future__ import annotations

from typing import Any, Sequence

import pytest

from app.schemas.paper import PaperAnalysisSchema
from app.services.analyzer import AnalysisError, analyze, build_messages
from app.services.ai_client import FakeAiClient
from app.services.pdf_extractor import ExtractedDoc


def _doc() -> ExtractedDoc:
    return ExtractedDoc(
        title='A Great Paper',
        text='We introduce a method and evaluate it against baselines.',
        pages=['We introduce a method and evaluate it against baselines.'],
    )


def test_build_messages_includes_title_and_system_prompt() -> None:
    messages = build_messages(_doc())
    assert messages[0]['role'] == 'system'
    assert 'JSON' in messages[0]['content']
    assert 'Title: A Great Paper' in messages[1]['content']


def test_analyze_returns_valid_schema() -> None:
    result = analyze(FakeAiClient(embedding_dims=8), _doc())
    assert isinstance(result, PaperAnalysisSchema)
    assert result.summary
    assert len(result.questions) == 3


class _MalformedClient:
    def chat_json(
        self, messages: Sequence[dict[str, str]], schema_hint: str | None = None
    ) -> dict[str, Any]:
        return {'not_summary': 'oops'}  # missing required 'summary'

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def test_analyze_raises_typed_error_on_malformed_output() -> None:
    with pytest.raises(AnalysisError):
        analyze(_MalformedClient(), _doc())

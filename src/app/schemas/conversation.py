"""Pydantic schemas for the tutoring conversation.

``TutorTurn`` is the structured shape the chat model must return for every turn.
The ``comprehension_score`` is clamped to 0–100 on validation so an
out-of-range value from the model can never be persisted.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TutorTurn(BaseModel):
    """The structured result of a single tutor turn from the chat model."""

    reply: str
    comprehension_score: int = 0
    score_rationale: str = ''
    cited_chunk_ids: list[int] = Field(default_factory=list)

    @field_validator('comprehension_score', mode='before')
    @classmethod
    def _coerce_score(cls, value: object) -> int:
        """Coerce to int and clamp into the valid 0–100 range."""
        try:
            score = int(round(float(value)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            score = 0
        return max(0, min(100, score))


class ChatRequest(BaseModel):
    """Incoming user message for a conversation turn."""

    message: str

    @field_validator('message')
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError('message must not be empty')
        return value.strip()


class MessageDTO(BaseModel):
    """A single persisted message returned to the frontend."""

    id: int
    role: str
    content: str
    cited_chunk_ids: list[int] = Field(default_factory=list)
    comprehension_score: int | None = None
    score_rationale: str | None = None


class ConversationDTO(BaseModel):
    """A conversation with its full message history."""

    id: int
    paper_id: int
    messages: list[MessageDTO] = Field(default_factory=list)

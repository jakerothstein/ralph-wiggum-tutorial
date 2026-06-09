"""Pydantic schemas for papers, chunks, and the structured analysis.

These schemas are the single source of truth for the JSON shapes exchanged with
the AI model (analysis output) and the frontend (DTOs). The frontend
``types/paper.ts`` mirrors these.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClaimEvidence(BaseModel):
    """A key claim from the paper paired with its supporting evidence."""

    claim: str
    evidence: str = ''


class GlossaryItem(BaseModel):
    """A domain term and its plain-language definition."""

    term: str
    definition: str


class ComprehensionQuestion(BaseModel):
    """A graded comprehension question used to probe the reader."""

    question: str
    difficulty: str = 'medium'  # easy | medium | hard
    ideal_answer: str = ''


class PaperAnalysisSchema(BaseModel):
    """The full structured analysis produced once at upload time.

    Validated against the chat model's JSON output so malformed model responses
    raise a typed error instead of silently corrupting the stored analysis.
    """

    model_config = ConfigDict(extra='ignore')

    summary: str
    contributions: list[str] = Field(default_factory=list)
    methodology: str = ''
    key_claims: list[ClaimEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    glossary: list[GlossaryItem] = Field(default_factory=list)
    questions: list[ComprehensionQuestion] = Field(default_factory=list)


class ChunkDTO(BaseModel):
    """A retrieved chunk surfaced to the frontend as a citation."""

    id: int
    chunk_index: int
    section: str
    content: str


class PaperDTO(BaseModel):
    """A paper summary returned by the API."""

    id: int
    title: str
    filename: str
    num_pages: int


class UploadResponse(BaseModel):
    """Response returned after a successful upload + ingest + analyze."""

    paper: PaperDTO
    analysis: PaperAnalysisSchema


class PaperListItem(BaseModel):
    """A paper as it appears in the session's paper list."""

    id: int
    title: str
    num_pages: int

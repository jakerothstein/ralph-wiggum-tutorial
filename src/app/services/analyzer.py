"""Upfront structured analysis of a paper.

Prompts the chat model in JSON mode to produce a :class:`PaperAnalysisSchema`
(summary, contributions, methodology, key claims + evidence, limitations,
glossary, and a graded question bank). The model output is validated by Pydantic
so malformed responses raise a typed :class:`AnalysisError` instead of silently
corrupting the stored analysis.

Why upfront analysis (vs. only RAG at chat time): a one-shot structured pass
gives the user an immediate overview and seeds the tutor with a stable mental
model of the paper, while retrieval handles grounding individual turns.
"""
from __future__ import annotations

from pydantic import ValidationError

from ..schemas.paper import PaperAnalysisSchema
from .ai_client import AiClient, AiClientError
from .pdf_extractor import ExtractedDoc

# Cap how much of the paper we send so a long paper doesn't blow the token
# budget; the opening of a paper carries most of the framing needed here.
_MAX_ANALYSIS_CHARS = 16000


class AnalysisError(Exception):
    """Raised when the model output cannot be parsed into a valid analysis."""


_SYSTEM_PROMPT = (
    'You are an expert research assistant. Analyze the given research paper and '
    'return a single JSON object describing it. Be faithful to the paper; do not '
    'invent results. The JSON must have these keys: '
    '"summary" (string), "contributions" (array of strings), '
    '"methodology" (string), "key_claims" (array of {"claim","evidence"}), '
    '"limitations" (array of strings), '
    '"glossary" (array of {"term","definition"}), and '
    '"questions" (array of {"question","difficulty","ideal_answer"} where '
    'difficulty is one of easy|medium|hard). Return ONLY the JSON object.'
)


def build_messages(extracted: ExtractedDoc) -> list[dict[str, str]]:
    """Assemble the chat messages for the analysis request."""
    body = extracted.text[:_MAX_ANALYSIS_CHARS]
    user = (
        f'Title: {extracted.title}\n\n'
        f'Paper text (may be truncated):\n"""\n{body}\n"""\n\n'
        'Produce the analysis JSON now.'
    )
    return [
        {'role': 'system', 'content': _SYSTEM_PROMPT},
        {'role': 'user', 'content': user},
    ]


def analyze(ai_client: AiClient, extracted: ExtractedDoc) -> PaperAnalysisSchema:
    """Run the structured analysis for an extracted document."""
    messages = build_messages(extracted)
    try:
        raw = ai_client.chat_json(messages, schema_hint='paper_analysis')
    except AiClientError as exc:
        raise AnalysisError(f'analysis request failed: {exc}') from exc
    try:
        return PaperAnalysisSchema.model_validate(raw)
    except ValidationError as exc:
        raise AnalysisError(f'model returned an invalid analysis: {exc}') from exc

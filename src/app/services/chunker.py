"""Text chunking for retrieval.

Splits an :class:`~app.services.pdf_extractor.ExtractedDoc` into overlapping,
stably-ordered chunks with a section label (the source page). Overlap preserves
context across chunk boundaries so retrieval doesn't sever a sentence's meaning.

"Tokens" here are approximated by whitespace-delimited words. This is good
enough for chunk sizing and keeps the chunker dependency-free and deterministic;
the exact token count only affects how much context we pack per embedding.
"""
from __future__ import annotations

from dataclasses import dataclass

from .pdf_extractor import ExtractedDoc


@dataclass
class Chunk:
    """One retrievable slice of the paper."""

    index: int
    section: str
    content: str


def chunk(
    extracted: ExtractedDoc,
    chunk_size_tokens: int = 400,
    overlap_tokens: int = 80,
) -> list[Chunk]:
    """Split a document into overlapping chunks, labelled by source page.

    Args:
        extracted: The extracted document.
        chunk_size_tokens: Approx words per chunk.
        overlap_tokens: Approx words of overlap between consecutive chunks.
    """
    if chunk_size_tokens <= 0:
        raise ValueError('chunk_size_tokens must be positive')
    overlap = max(0, min(overlap_tokens, chunk_size_tokens - 1))
    step = chunk_size_tokens - overlap

    chunks: list[Chunk] = []
    index = 0
    pages = extracted.pages or [extracted.text]
    for page_no, page_text in enumerate(pages, start=1):
        words = page_text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            window = words[start: start + chunk_size_tokens]
            content = ' '.join(window).strip()
            if content:
                chunks.append(
                    Chunk(index=index, section=f'Page {page_no}', content=content)
                )
                index += 1
            if start + chunk_size_tokens >= len(words):
                break
            start += step
    return chunks

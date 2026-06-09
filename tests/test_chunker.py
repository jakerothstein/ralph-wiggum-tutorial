"""Tests for the text chunker."""
from __future__ import annotations

from app.services.chunker import chunk
from app.services.pdf_extractor import ExtractedDoc


def _doc(pages: list[str]) -> ExtractedDoc:
    return ExtractedDoc(title='T', text='\n\n'.join(pages), pages=pages)


def test_chunk_count_and_overlap() -> None:
    words = ' '.join(f'w{i}' for i in range(100))
    doc = _doc([words])
    chunks = chunk(doc, chunk_size_tokens=40, overlap_tokens=10)
    # step = 30 -> windows [0:40], [30:70], [60:100] cover all 100 words.
    assert len(chunks) == 3
    assert [c.index for c in chunks] == [0, 1, 2]
    # Overlap: last 10 words of chunk 0 equal first 10 of chunk 1.
    c0 = chunks[0].content.split()
    c1 = chunks[1].content.split()
    assert c0[-10:] == c1[:10]


def test_sections_are_page_labelled() -> None:
    doc = _doc(['alpha beta gamma', 'delta epsilon zeta'])
    chunks = chunk(doc, chunk_size_tokens=10, overlap_tokens=2)
    sections = {c.section for c in chunks}
    assert sections == {'Page 1', 'Page 2'}


def test_empty_pages_skipped() -> None:
    doc = _doc(['', 'only this page has words here'])
    chunks = chunk(doc, chunk_size_tokens=10, overlap_tokens=0)
    assert len(chunks) == 1
    assert chunks[0].section == 'Page 2'

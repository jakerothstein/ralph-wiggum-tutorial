"""Tests for the PDF text extractor."""
from __future__ import annotations

import pytest

from app.services.pdf_extractor import ExtractedDoc, PdfExtractionError, extract
from tests.helpers import build_simple_pdf

MAX = 10 * 1024 * 1024


def test_extracts_text_and_title() -> None:
    pdf = build_simple_pdf(['Attention Is All You Need', 'We propose the Transformer.'])
    doc = extract(pdf, MAX, filename='paper.pdf')
    assert isinstance(doc, ExtractedDoc)
    assert doc.num_pages == 1
    assert 'Transformer' in doc.text
    assert doc.title == 'Attention Is All You Need'


def test_rejects_non_pdf() -> None:
    with pytest.raises(PdfExtractionError):
        extract(b'this is not a pdf', MAX, filename='x.txt')


def test_rejects_empty() -> None:
    with pytest.raises(PdfExtractionError):
        extract(b'', MAX)


def test_rejects_oversized() -> None:
    pdf = build_simple_pdf(['Hello'])
    with pytest.raises(PdfExtractionError):
        extract(pdf, max_bytes=10)


def test_rejects_image_only_pdf() -> None:
    # No text operators -> simulates a scanned/image-only PDF.
    pdf = build_simple_pdf([])
    with pytest.raises(PdfExtractionError):
        extract(pdf, MAX)

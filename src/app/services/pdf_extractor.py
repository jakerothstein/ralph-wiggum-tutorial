"""PDF text extraction.

Extracts plain text per page from an uploaded PDF using ``pypdf`` and returns it
alongside a page map. Invalid inputs (non-PDF bytes, empty/zero-page files,
oversized uploads, or scanned/image-only PDFs with no extractable text) raise a
typed :class:`PdfExtractionError` so callers can surface a clear user-facing
message instead of crashing.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be read or yields no usable text."""


@dataclass
class ExtractedDoc:
    """Cleaned text from a PDF plus its per-page breakdown."""

    title: str
    text: str
    pages: list[str] = field(default_factory=list)

    @property
    def num_pages(self) -> int:
        return len(self.pages)


def extract(file_bytes: bytes, max_bytes: int, filename: str = '') -> ExtractedDoc:
    """Extract text from PDF bytes.

    Args:
        file_bytes: Raw uploaded file content.
        max_bytes: Reject uploads larger than this.
        filename: Original filename (used as a title fallback).

    Raises:
        PdfExtractionError: On oversized, non-PDF, empty, or text-less input.
    """
    if not file_bytes:
        raise PdfExtractionError('The uploaded file is empty.')
    if len(file_bytes) > max_bytes:
        raise PdfExtractionError(
            f'File is too large ({len(file_bytes)} bytes; limit is {max_bytes}).'
        )
    if not file_bytes.lstrip()[:5].startswith(b'%PDF-'):
        raise PdfExtractionError('The uploaded file is not a valid PDF.')

    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as exc:
        raise PdfExtractionError(f'Could not read the PDF: {exc}') from exc
    except Exception as exc:  # noqa: BLE001 - normalize parser errors
        raise PdfExtractionError(f'Could not read the PDF: {exc}') from exc

    if getattr(reader, 'is_encrypted', False):
        # Try an empty-password decrypt; bail out cleanly if it fails.
        try:
            if reader.decrypt('') == 0:
                raise PdfExtractionError('The PDF is password-protected.')
        except PdfExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PdfExtractionError('The PDF is password-protected.') from exc

    pages = reader.pages
    if not pages:
        raise PdfExtractionError('The PDF has no pages.')

    page_texts: list[str] = []
    for page in pages:
        try:
            page_texts.append((page.extract_text() or '').strip())
        except Exception:  # noqa: BLE001 - a bad page should not kill the doc
            page_texts.append('')

    full_text = '\n\n'.join(t for t in page_texts if t).strip()
    if not full_text:
        raise PdfExtractionError(
            'No extractable text found — the PDF may be scanned or image-only.'
        )

    title = _derive_title(page_texts, filename)
    return ExtractedDoc(title=title, text=full_text, pages=page_texts)


def _derive_title(page_texts: list[str], filename: str) -> str:
    """Use the first non-empty line of page one, else the filename stem."""
    if page_texts:
        for line in page_texts[0].splitlines():
            line = line.strip()
            if len(line) >= 4:
                return line[:200]
    stem = filename.rsplit('/', 1)[-1]
    if stem.lower().endswith('.pdf'):
        stem = stem[:-4]
    return stem or 'Untitled Paper'

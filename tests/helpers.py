"""Test helpers, including a tiny valid-PDF generator.

``build_simple_pdf`` emits a minimal but spec-valid single-page PDF with real,
extractable text so ``pdf_extractor`` tests (and the E2E fixture) don't need a
binary blob checked into the repo or a heavyweight PDF library.
"""
from __future__ import annotations

from typing import Sequence


def build_simple_pdf(text_lines: Sequence[str]) -> bytes:
    """Build a one-page PDF containing the given lines of text.

    Passing an empty sequence yields a page with no text operators, which is how
    we simulate a scanned/image-only PDF (no extractable text).
    """
    content_ops = ['BT', '/F1 12 Tf', '72 720 Td', '14 TL']
    for i, line in enumerate(text_lines):
        esc = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        if i > 0:
            content_ops.append('T*')
        content_ops.append(f'({esc}) Tj')
    content_ops.append('ET')
    content = '\n'.join(content_ops).encode('latin-1')

    objects: dict[int, bytes] = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        3: (
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            b'/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>'
        ),
        4: b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream',
        5: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    }

    pdf = b'%PDF-1.4\n'
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(pdf)
        pdf += b'%d 0 obj\n' % num + objects[num] + b'\nendobj\n'

    xref_pos = len(pdf)
    count = len(objects) + 1
    pdf += b'xref\n0 %d\n' % count
    pdf += b'0000000000 65535 f \n'
    for num in sorted(objects):
        pdf += b'%010d 00000 n \n' % offsets[num]
    pdf += (
        b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF'
        % (count, xref_pos)
    )
    return pdf

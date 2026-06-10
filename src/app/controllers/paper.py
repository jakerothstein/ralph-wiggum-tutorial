"""Paper controller — orchestrates the ingest pipeline and read access.

This is the coordination layer between the HTTP views and the pure service
functions. ``ingest`` runs the full upload pipeline as one transaction so a
half-ingested paper (chunks without an analysis, say) can never be persisted:

    extract (pypdf) -> chunk -> embed -> persist Paper + chunks -> analyze -> persist

Every read is scoped by ``session_id`` because sessions are the only
access-control boundary in this anonymous app: a caller can only ever touch the
papers created under their own signed-cookie session. ``get`` raises
:class:`PaperNotFoundError` for both "no such id" and "belongs to another
session" so cross-session probing is indistinguishable from a genuine 404.
"""
from __future__ import annotations

from flask import current_app
from sqlalchemy import select

from ..models import Paper, PaperAnalysis, PaperChunk, db
from ..services import analyzer, chunker, embeddings
from ..services import pdf_extractor
from ..services.ai_client import AiClient


class PaperNotFoundError(Exception):
    """Raised when a paper does not exist or is not owned by the session."""


def _ai_client() -> AiClient:
    client: AiClient = current_app.extensions['ai_client']
    return client


def ingest(file_bytes: bytes, filename: str, session_id: str) -> Paper:
    """Run the full ingest + analysis pipeline and persist the result.

    Raises:
        pdf_extractor.PdfExtractionError: For invalid/oversized/text-less PDFs.
        analyzer.AnalysisError: If the model returns an unusable analysis.
    """
    config = current_app.config
    ai_client = _ai_client()

    extracted = pdf_extractor.extract(
        file_bytes, int(config['MAX_UPLOAD_BYTES']), filename
    )
    chunks = chunker.chunk(
        extracted,
        chunk_size_tokens=int(config['CHUNK_SIZE_TOKENS']),
        overlap_tokens=int(config['CHUNK_OVERLAP_TOKENS']),
    )
    vectors = embeddings.embed_chunks(ai_client, chunks)

    # Analyze before we commit so a failed analysis aborts the whole ingest
    # (single source of truth: a stored Paper always has an analysis).
    analysis = analyzer.analyze(ai_client, extracted)

    paper = Paper(
        session_id=session_id,
        title=extracted.title,
        filename=filename,
        num_pages=extracted.num_pages,
        pdf_data=file_bytes,
    )
    db.session.add(paper)
    db.session.flush()  # assign paper.id for the chunk FKs

    for chunk, vector in zip(chunks, vectors):
        db.session.add(
            PaperChunk(
                paper_id=paper.id,
                chunk_index=chunk.index,
                section=chunk.section,
                content=chunk.content,
                embedding=vector,
            )
        )

    db.session.add(
        PaperAnalysis(
            paper_id=paper.id,
            summary=analysis.summary,
            data=analysis.model_dump(),
        )
    )
    db.session.commit()
    return paper


def get(paper_id: int, session_id: str) -> Paper:
    """Return a session-owned paper or raise :class:`PaperNotFoundError`."""
    paper = db.session.execute(
        select(Paper).where(
            Paper.id == paper_id, Paper.session_id == session_id
        )
    ).scalar_one_or_none()
    if paper is None:
        raise PaperNotFoundError(f'paper {paper_id} not found')
    return paper


def get_analysis(paper_id: int, session_id: str) -> PaperAnalysis:
    """Return the analysis for a session-owned paper."""
    paper = get(paper_id, session_id)
    if paper.analysis is None:  # pragma: no cover - ingest always persists one
        raise PaperNotFoundError(f'analysis for paper {paper_id} not found')
    return paper.analysis


def list_papers(session_id: str) -> list[Paper]:
    """Return all papers for a session, newest first."""
    return list(
        db.session.execute(
            select(Paper)
            .where(Paper.session_id == session_id)
            .order_by(Paper.created_at.desc(), Paper.id.desc())
        ).scalars()
    )

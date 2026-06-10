"""Paper blueprint — pages + JSON API for upload, analysis, and listing.

Routes:

* ``GET  /``                — upload/home page (renders the upload island).
* ``POST /api/papers``      — upload a PDF; runs ingest+analyze; returns
  ``{paper, analysis}`` so the client can redirect to the workspace.
* ``GET  /papers/<id>``     — the paper workspace page (PDF preview + chat islands).
* ``GET  /papers/<id>/pdf`` — stream the original PDF for inline preview.
* ``GET  /api/papers/<id>`` — the structured analysis JSON for an owned paper.
* ``GET  /api/papers``      — list the session's papers.

Session scoping is enforced inside each view via ``current_session_id()`` (no
custom decorators, per project convention). Cross-session access is a 404.
"""
from __future__ import annotations

from flask import Blueprint, Response, abort, jsonify, render_template, request
from werkzeug.utils import secure_filename

from ..controllers import paper as paper_controller
from ..schemas.paper import (
    PaperAnalysisSchema,
    PaperDTO,
    PaperListItem,
    UploadResponse,
)
from ..services.analyzer import AnalysisError
from ..services.pdf_extractor import PdfExtractionError
from ..services.session import current_session_id

paper_bp = Blueprint('paper', __name__)


@paper_bp.route('/')
def index() -> str:
    """Render the upload/home page."""
    return render_template('index.html')


@paper_bp.route('/papers/<int:paper_id>')
def workspace(paper_id: int):  # type: ignore[no-untyped-def]
    """Render the paper workspace (analysis + chat) or a 404 page."""
    session_id = current_session_id()
    try:
        paper = paper_controller.get(paper_id, session_id)
    except paper_controller.PaperNotFoundError:
        return render_template('errors/404.html'), 404
    return render_template('paper.html', paper_id=paper.id, paper_title=paper.title)


@paper_bp.route('/papers/<int:paper_id>/pdf')
def pdf_preview(paper_id: int):  # type: ignore[no-untyped-def]
    """Stream a session-owned paper's original PDF for inline preview."""
    session_id = current_session_id()
    try:
        paper = paper_controller.get(paper_id, session_id)
    except paper_controller.PaperNotFoundError:
        abort(404)
    if not paper.pdf_data:
        abort(404)
    # secure_filename strips quotes/control chars, so the user-supplied name
    # can't break out of (or inject into) the Content-Disposition header.
    safe_name = secure_filename(paper.filename) or 'paper.pdf'
    return Response(
        paper.pdf_data,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{safe_name}"'},
    )


@paper_bp.route('/api/papers', methods=['POST'])
def upload():  # type: ignore[no-untyped-def]
    """Accept a PDF upload, ingest+analyze it, and return the result."""
    session_id = current_session_id()
    file = request.files.get('file')
    if file is None or not file.filename:
        return jsonify({'error': 'No file provided.'}), 400

    file_bytes = file.read()
    try:
        paper = paper_controller.ingest(file_bytes, file.filename, session_id)
    except PdfExtractionError as exc:
        return jsonify({'error': str(exc)}), 400
    except AnalysisError as exc:
        return jsonify({'error': f'Analysis failed: {exc}'}), 502

    analysis = paper_controller.get_analysis(paper.id, session_id)
    payload = UploadResponse(
        paper=PaperDTO(
            id=paper.id,
            title=paper.title,
            filename=paper.filename,
            num_pages=paper.num_pages,
        ),
        analysis=PaperAnalysisSchema.model_validate(analysis.data),
    )
    return jsonify(payload.model_dump()), 201


@paper_bp.route('/api/papers/<int:paper_id>')
def analysis_json(paper_id: int):  # type: ignore[no-untyped-def]
    """Return the structured analysis JSON for an owned paper."""
    session_id = current_session_id()
    try:
        paper = paper_controller.get(paper_id, session_id)
        analysis = paper_controller.get_analysis(paper_id, session_id)
    except paper_controller.PaperNotFoundError:
        return jsonify({'error': 'Paper not found.'}), 404

    payload = UploadResponse(
        paper=PaperDTO(
            id=paper.id,
            title=paper.title,
            filename=paper.filename,
            num_pages=paper.num_pages,
        ),
        analysis=PaperAnalysisSchema.model_validate(analysis.data),
    )
    return jsonify(payload.model_dump())


@paper_bp.route('/api/papers')
def list_papers():  # type: ignore[no-untyped-def]
    """Return the session's papers, newest first."""
    session_id = current_session_id()
    papers = paper_controller.list_papers(session_id)
    items = [
        PaperListItem(id=p.id, title=p.title, num_pages=p.num_pages).model_dump()
        for p in papers
    ]
    return jsonify({'papers': items})

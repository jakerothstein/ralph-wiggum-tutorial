"""Integration tests for the paper blueprint (upload + analysis + listing).

These exercise the full HTTP surface with the deterministic fake AI client
(forced by the testing config), covering the happy path, input validation, and —
critically — session scoping: a paper uploaded under one browser session must be
invisible (404) to another. The fake client makes the whole ingest+analyze
pipeline hermetic, so these run against SQLite with no network.
"""
from __future__ import annotations

import io
import json
from typing import Any

from flask.testing import FlaskClient

from .helpers import build_simple_pdf

_PDF_LINES = [
    'Attention Is All You Need',
    'We propose the Transformer, a model architecture relying entirely on',
    'self-attention to draw global dependencies between input and output.',
    'Experiments show it is superior in quality while being more parallelizable.',
]


def _upload(client: FlaskClient[Any], lines: list[str] | None = None,
            filename: str = 'paper.pdf') -> Any:
    pdf = build_simple_pdf(lines if lines is not None else _PDF_LINES)
    return client.post(
        '/api/papers',
        data={'file': (io.BytesIO(pdf), filename)},
        content_type='multipart/form-data',
    )


class TestUpload:
    def test_upload_returns_paper_and_analysis(self, client: FlaskClient[Any]) -> None:
        resp = _upload(client)
        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert body['paper']['id'] >= 1
        assert body['paper']['num_pages'] == 1
        assert body['analysis']['summary']
        assert isinstance(body['analysis']['questions'], list)

    def test_upload_rejects_non_pdf(self, client: FlaskClient[Any]) -> None:
        resp = client.post(
            '/api/papers',
            data={'file': (io.BytesIO(b'not a pdf'), 'note.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert 'error' in json.loads(resp.data)

    def test_upload_requires_file(self, client: FlaskClient[Any]) -> None:
        resp = client.post('/api/papers', data={}, content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_rejects_textless_pdf(self, client: FlaskClient[Any]) -> None:
        resp = _upload(client, lines=[])
        assert resp.status_code == 400


class TestReadAndScope:
    def test_analysis_json_for_owned_paper(self, client: FlaskClient[Any]) -> None:
        paper_id = json.loads(_upload(client).data)['paper']['id']
        resp = client.get(f'/api/papers/{paper_id}')
        assert resp.status_code == 200
        assert json.loads(resp.data)['analysis']['summary']

    def test_workspace_page_renders(self, client: FlaskClient[Any]) -> None:
        paper_id = json.loads(_upload(client).data)['paper']['id']
        resp = client.get(f'/papers/{paper_id}')
        assert resp.status_code == 200
        assert b'data-island="analysis"' in resp.data
        assert b'data-island="chat"' in resp.data
        # PDF preview iframe replaces the side analysis panel.
        assert f'/papers/{paper_id}/pdf'.encode() in resp.data

    def test_pdf_preview_serves_owned_paper(self, client: FlaskClient[Any]) -> None:
        paper_id = json.loads(_upload(client).data)['paper']['id']
        resp = client.get(f'/papers/{paper_id}/pdf')
        assert resp.status_code == 200
        assert resp.mimetype == 'application/pdf'
        assert resp.data.startswith(b'%PDF')

    def test_pdf_preview_cross_session_is_404(self, app: Any) -> None:
        owner = app.test_client()
        other = app.test_client()
        paper_id = json.loads(_upload(owner).data)['paper']['id']
        assert other.get(f'/papers/{paper_id}/pdf').status_code == 404

    def test_pdf_preview_404_when_no_bytes(self, app: Any) -> None:
        # Legacy rows (uploaded before the pdf_data column existed) have no
        # bytes to preview and must 404 rather than serve an empty body.
        from app.models import Paper, db

        client = app.test_client()
        # Establish a session and capture its id from a real upload...
        paper_id = json.loads(_upload(client).data)['paper']['id']
        with app.app_context():
            paper = db.session.get(Paper, paper_id)
            assert paper is not None
            paper.pdf_data = None
            db.session.commit()
        assert client.get(f'/papers/{paper_id}/pdf').status_code == 404

    def test_list_papers_scoped(self, client: FlaskClient[Any]) -> None:
        _upload(client)
        resp = client.get('/api/papers')
        assert resp.status_code == 200
        assert len(json.loads(resp.data)['papers']) == 1

    def test_cross_session_paper_is_404(self, app: Any) -> None:
        # Two independent clients => two independent signed-cookie sessions.
        owner = app.test_client()
        other = app.test_client()
        paper_id = json.loads(_upload(owner).data)['paper']['id']

        assert other.get(f'/api/papers/{paper_id}').status_code == 404
        assert other.get(f'/papers/{paper_id}').status_code == 404
        assert json.loads(other.get('/api/papers').data)['papers'] == []


class TestIndex:
    def test_index_serves_upload_page(self, client: FlaskClient[Any]) -> None:
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'data-island="upload"' in resp.data
        assert b'Research Paper Comprehension Tutor' in resp.data

    def test_index_has_no_legacy_game(self, client: FlaskClient[Any]) -> None:
        resp = client.get('/')
        assert b'data-island="game"' not in resp.data
        assert b'<canvas' not in resp.data

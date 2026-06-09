"""Error-handler coverage (retained from the original scaffold).

Verifies the content-negotiated error handlers still work after the homepage
moved from the game to the tutor: HTML for browser requests, JSON for API
clients.
"""
from __future__ import annotations

import json
from typing import Any

from flask.testing import FlaskClient


class TestErrorHandlers:
    def test_404_html(self, client: FlaskClient[Any]) -> None:
        response = client.get('/nonexistent')
        assert response.status_code == 404
        assert b'Page Not Found' in response.data or b'404' in response.data

    def test_404_json(self, client: FlaskClient[Any]) -> None:
        response = client.get(
            '/nonexistent', headers={'Accept': 'application/json'}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

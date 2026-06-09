"""Tests for the anonymous session middleware."""
from __future__ import annotations

from typing import Any

from flask import Flask
from flask.testing import FlaskClient

from app.services.session import current_session_id


def test_session_cookie_is_set_and_stable(client: FlaskClient[Any]) -> None:
    r1 = client.get('/')
    set_cookie = r1.headers.get('Set-Cookie', '')
    assert 'paper_session=' in set_cookie

    # The test client persists cookies; a second request must NOT set a new one
    # (the id is stable across requests).
    r2 = client.get('/')
    assert 'paper_session=' not in r2.headers.get('Set-Cookie', '')


def test_current_session_id_is_stable_within_request(app: Flask) -> None:
    # Even without the before_request hook, current_session_id() lazily creates
    # and then reuses one id for the life of the request/app context.
    with app.test_request_context('/'):
        sid = current_session_id()
        assert sid
        assert current_session_id() == sid

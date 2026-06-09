"""Anonymous session management.

Sessions are anonymous (no accounts). Each browser gets a stable UUID stored in a
signed cookie; every paper, analysis, chunk, and conversation is scoped to that
id so a user only ever sees their own work.

Per project convention we avoid custom decorators: scoping is enforced inside
view functions, and the cookie is established by a standard Flask
``before_request`` / ``after_request`` pair registered by :func:`init_session`.
"""
from __future__ import annotations

import uuid
from typing import cast

from flask import Flask, Request, Response, g, request
from itsdangerous import BadSignature, URLSafeSerializer

_SALT = 'paper-session'
_G_KEY = 'paper_session_id'
_SET_FLAG = '_paper_session_set'


def _serializer(app: Flask) -> URLSafeSerializer:
    return URLSafeSerializer(app.config['SECRET_KEY'], salt=_SALT)


def _cookie_name(app: Flask) -> str:
    return str(app.config.get('SESSION_COOKIE_NAME_PAPER', 'paper_session'))


def _read_session_id(app: Flask, req: Request) -> str | None:
    raw = req.cookies.get(_cookie_name(app))
    if not raw:
        return None
    try:
        value = _serializer(app).loads(raw)
    except BadSignature:
        return None
    return value if isinstance(value, str) else None


def current_session_id() -> str:
    """Return the resolved session id for the current request.

    Falls back to creating one on demand if accessed outside the normal
    ``before_request`` flow (e.g. in a CLI command).
    """
    sid = g.get(_G_KEY)
    if not sid:
        sid = uuid.uuid4().hex
        setattr(g, _G_KEY, sid)
        setattr(g, _SET_FLAG, True)
    return cast(str, sid)


def init_session(app: Flask) -> None:
    """Register the session cookie lifecycle hooks on the app."""

    @app.before_request
    def _ensure_session() -> None:
        # Reset the per-request "needs cookie" flag. ``g`` is app-context
        # scoped, so without this reset the flag could leak between requests
        # that share an app context (e.g. the test client).
        setattr(g, _SET_FLAG, False)
        sid = _read_session_id(app, request)
        if sid is None:
            sid = uuid.uuid4().hex
            setattr(g, _SET_FLAG, True)
        setattr(g, _G_KEY, sid)

    @app.after_request
    def _persist_session(response: Response) -> Response:
        if getattr(g, _SET_FLAG, False) and g.get(_G_KEY):
            signed = _serializer(app).dumps(g.get(_G_KEY))
            response.set_cookie(
                _cookie_name(app),
                signed,
                httponly=True,
                samesite='Lax',
                secure=app.config.get('SESSION_COOKIE_SECURE', False),
                max_age=60 * 60 * 24 * 365,
            )
        return response

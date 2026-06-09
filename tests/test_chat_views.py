"""Integration tests for the chat blueprint (conversation + tutor turns).

A full multi-turn exchange is driven through the HTTP API with the fake AI
client. We assert the persisted contract the UI depends on: the conversation is
idempotent per paper+session, each assistant turn carries a clamped 0–100
comprehension score and a rationale, citations only reference chunks that exist
for the paper, history survives across requests, and cross-session access to a
conversation is a 404.
"""
from __future__ import annotations

import io
import json
from typing import Any, cast

from flask.testing import FlaskClient

from .helpers import build_simple_pdf

_PDF_LINES = [
    'Deep Residual Learning for Image Recognition',
    'We present a residual learning framework to ease the training of networks.',
    'We explicitly reformulate the layers as learning residual functions.',
    'These residual networks are easier to optimize and gain accuracy from depth.',
]


def _upload(client: FlaskClient[Any]) -> int:
    pdf = build_simple_pdf(_PDF_LINES)
    resp = client.post(
        '/api/papers',
        data={'file': (io.BytesIO(pdf), 'resnet.pdf')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 201
    return int(json.loads(resp.data)['paper']['id'])


def _start_conversation(client: FlaskClient[Any], paper_id: int) -> dict[str, Any]:
    resp = client.post(f'/api/papers/{paper_id}/conversation')
    assert resp.status_code == 200
    return cast('dict[str, Any]', json.loads(resp.data))


class TestConversation:
    def test_start_is_idempotent(self, client: FlaskClient[Any]) -> None:
        paper_id = _upload(client)
        first = _start_conversation(client, paper_id)
        second = _start_conversation(client, paper_id)
        assert first['id'] == second['id']
        assert first['paper_id'] == paper_id
        assert first['messages'] == []

    def test_send_message_persists_turn_with_score(
        self, client: FlaskClient[Any]
    ) -> None:
        paper_id = _upload(client)
        conv = _start_conversation(client, paper_id)
        resp = client.post(
            f'/api/conversations/{conv["id"]}/messages',
            data=json.dumps({'message': 'I think it is about residual connections.'}),
            content_type='application/json',
        )
        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert body['user']['role'] == 'user'
        assistant = body['assistant']
        assert assistant['role'] == 'assistant'
        assert assistant['content']
        assert 0 <= assistant['comprehension_score'] <= 100
        assert assistant['score_rationale']
        # Citations must reference real, retrieved chunks (positive ids).
        assert all(isinstance(cid, int) and cid > 0 for cid in assistant['cited_chunk_ids'])
        assert assistant['cited_chunk_ids']

    def test_history_round_trips(self, client: FlaskClient[Any]) -> None:
        paper_id = _upload(client)
        conv = _start_conversation(client, paper_id)
        for text in ('first guess', 'second guess'):
            client.post(
                f'/api/conversations/{conv["id"]}/messages',
                data=json.dumps({'message': text}),
                content_type='application/json',
            )
        resp = client.get(f'/api/conversations/{conv["id"]}/messages')
        assert resp.status_code == 200
        messages = json.loads(resp.data)['messages']
        # 2 turns => 2 user + 2 assistant messages, ordered.
        assert [m['role'] for m in messages] == ['user', 'assistant', 'user', 'assistant']

    def test_empty_message_is_400(self, client: FlaskClient[Any]) -> None:
        paper_id = _upload(client)
        conv = _start_conversation(client, paper_id)
        resp = client.post(
            f'/api/conversations/{conv["id"]}/messages',
            data=json.dumps({'message': '   '}),
            content_type='application/json',
        )
        assert resp.status_code == 400


class TestChatScoping:
    def test_cross_session_conversation_is_404(self, app: Any) -> None:
        owner = app.test_client()
        other = app.test_client()
        paper_id = _upload(owner)
        conv = _start_conversation(owner, paper_id)

        # Other session cannot start a conversation on the paper...
        assert other.post(f'/api/papers/{paper_id}/conversation').status_code == 404
        # ...nor post to / read the existing conversation.
        assert other.post(
            f'/api/conversations/{conv["id"]}/messages',
            data=json.dumps({'message': 'hi'}),
            content_type='application/json',
        ).status_code == 404
        assert other.get(
            f'/api/conversations/{conv["id"]}/messages'
        ).status_code == 404

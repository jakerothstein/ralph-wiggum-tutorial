"""Chat blueprint — JSON API for the tutoring conversation.

Routes:

* ``POST /api/papers/<paper_id>/conversation``    — start/get the conversation
  for a paper (idempotent: one conversation per paper+session). Returns the
  conversation id and any existing history.
* ``POST /api/conversations/<cid>/messages``      — send a user turn; returns the
  persisted user + assistant messages (assistant carries the updated score +
  citations).
* ``GET  /api/conversations/<cid>/messages``      — read the full history.

All access is session-scoped; a conversation reached through another session's
paper returns 404.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..controllers import conversation as conversation_controller
from ..controllers import paper as paper_controller
from ..models import Message
from ..schemas.conversation import ChatRequest, ConversationDTO, MessageDTO
from ..services.session import current_session_id
from ..services.tutor import TutorError

chat_bp = Blueprint('chat', __name__)


def _message_dto(message: Message) -> MessageDTO:
    return MessageDTO(
        id=message.id,
        role=message.role,
        content=message.content,
        cited_chunk_ids=list(message.cited_chunk_ids or []),
        comprehension_score=message.comprehension_score,
        score_rationale=message.score_rationale,
    )


@chat_bp.route('/api/papers/<int:paper_id>/conversation', methods=['POST'])
def start_conversation(paper_id: int):  # type: ignore[no-untyped-def]
    """Start or fetch the conversation for a paper."""
    session_id = current_session_id()
    try:
        conversation = conversation_controller.get_or_create_conversation(
            paper_id, session_id
        )
    except paper_controller.PaperNotFoundError:
        return jsonify({'error': 'Paper not found.'}), 404

    payload = ConversationDTO(
        id=conversation.id,
        paper_id=conversation.paper_id,
        messages=[_message_dto(m) for m in conversation.messages],
    )
    return jsonify(payload.model_dump()), 200


@chat_bp.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
def send_message(conversation_id: int):  # type: ignore[no-untyped-def]
    """Send a user turn and return the user + assistant messages."""
    session_id = current_session_id()
    body = request.get_json(silent=True) or {}
    try:
        chat_request = ChatRequest.model_validate(body)
    except Exception:  # noqa: BLE001 - validation error -> 400
        return jsonify({'error': 'A non-empty "message" is required.'}), 400

    try:
        user_row, assistant_row = conversation_controller.append_turn(
            conversation_id, session_id, chat_request.message
        )
    except conversation_controller.ConversationNotFoundError:
        return jsonify({'error': 'Conversation not found.'}), 404
    except TutorError as exc:
        return jsonify({'error': f'Tutor failed: {exc}'}), 502

    return (
        jsonify(
            {
                'user': _message_dto(user_row).model_dump(),
                'assistant': _message_dto(assistant_row).model_dump(),
            }
        ),
        201,
    )


@chat_bp.route('/api/conversations/<int:conversation_id>/messages', methods=['GET'])
def list_messages(conversation_id: int):  # type: ignore[no-untyped-def]
    """Return the full message history for a conversation."""
    session_id = current_session_id()
    try:
        messages = conversation_controller.get_messages(
            conversation_id, session_id
        )
    except conversation_controller.ConversationNotFoundError:
        return jsonify({'error': 'Conversation not found.'}), 404

    return jsonify({'messages': [_message_dto(m).model_dump() for m in messages]})

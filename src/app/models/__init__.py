"""Database models package.

Exports all models for easy importing throughout the application. Importing the
modules here also ensures every model is registered on ``db.metadata`` before
``db.create_all()`` / Alembic autogenerate run.
"""
from .base import db
from .paper import EMBEDDING_DIMS, Paper, PaperAnalysis, PaperChunk
from .conversation import Conversation, Message

__all__ = [
    'db',
    'Paper',
    'PaperChunk',
    'PaperAnalysis',
    'Conversation',
    'Message',
    'EMBEDDING_DIMS',
]

"""enable pgvector and create paper + conversation tables

Replaces the Space Invaders era (no tables) with the Paper Comprehension Tutor
schema. This migration:

* Enables the PostgreSQL ``vector`` extension (pgvector) so chunk embeddings can
  be stored and searched with cosine distance in the database.
* Creates the ``paper``, ``paper_chunk``, ``paper_analysis``, ``conversation``,
  and ``message`` tables, all scoped by an anonymous ``session_id``.
* Adds an IVFFlat cosine index on ``paper_chunk.embedding`` for fast retrieval.

The ``embedding`` column dimensionality (1536) matches
``text-embedding-3-small``; swapping the embedding model means changing
``EMBEDDING_DIMS`` in config and adding a follow-up migration that alters the
column type.

This migration targets PostgreSQL (the production/dev database). The unit-test
suite runs on SQLite via ``db.create_all()`` and does not apply Alembic
migrations, so the pgvector-specific statements here never run under SQLite.

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-09 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None

EMBEDDING_DIMS = 1536


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table(
        'paper',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('num_pages', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_paper_session_id', 'paper', ['session_id'])

    op.create_table(
        'paper_chunk',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(length=256), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(EMBEDDING_DIMS), nullable=True),
        sa.ForeignKeyConstraint(['paper_id'], ['paper.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_paper_chunk_paper_id', 'paper_chunk', ['paper_id'])
    # IVFFlat cosine index for approximate nearest-neighbour retrieval.
    op.execute(
        'CREATE INDEX ix_paper_chunk_embedding_cosine ON paper_chunk '
        'USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
    )

    op.create_table(
        'paper_analysis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['paper.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('paper_id'),
    )

    op.create_table(
        'conversation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['paper.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversation_paper_id', 'conversation', ['paper_id'])
    op.create_index('ix_conversation_session_id', 'conversation', ['session_id'])

    op.create_table(
        'message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('cited_chunk_ids', sa.JSON(), nullable=False),
        sa.Column('comprehension_score', sa.Integer(), nullable=True),
        sa.Column('score_rationale', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['conversation_id'], ['conversation.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_message_conversation_id', 'message', ['conversation_id'])


def downgrade() -> None:
    op.drop_index('ix_message_conversation_id', table_name='message')
    op.drop_table('message')
    op.drop_index('ix_conversation_session_id', table_name='conversation')
    op.drop_index('ix_conversation_paper_id', table_name='conversation')
    op.drop_table('conversation')
    op.drop_table('paper_analysis')
    op.execute('DROP INDEX IF EXISTS ix_paper_chunk_embedding_cosine')
    op.drop_index('ix_paper_chunk_paper_id', table_name='paper_chunk')
    op.drop_table('paper_chunk')
    op.drop_index('ix_paper_session_id', table_name='paper')
    op.drop_table('paper')

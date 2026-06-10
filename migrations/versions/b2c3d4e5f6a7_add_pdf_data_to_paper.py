"""add pdf_data column to paper for inline PDF preview

Stores the raw uploaded PDF bytes on the ``paper`` row so the workspace can
serve an inline preview of the original document (``GET /papers/<id>/pdf``)
next to the tutor conversation. Nullable so any pre-existing rows uploaded
before this column existed remain valid (they simply have no preview).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-09 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'paper',
        sa.Column('pdf_data', sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('paper', 'pdf_data')

"""add chat session document ids json

Revision ID: f2c4e8a9d1b3
Revises: b4e7d5f8c2a1
Create Date: 2026-03-24 00:00:02.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2c4e8a9d1b3"
down_revision: Union[str, Sequence[str], None] = "b4e7d5f8c2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("document_ids_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "document_ids_json")

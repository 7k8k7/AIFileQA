"""add chat message sources

Revision ID: 9d3b6b4a2f11
Revises: c8fc7452a3bb
Create Date: 2026-03-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3b6b4a2f11"
down_revision: Union[str, Sequence[str], None] = "c8fc7452a3bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("sources_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "sources_json")

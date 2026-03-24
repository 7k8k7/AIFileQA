"""add provider embedding fields

Revision ID: a6e84f6d9c12
Revises: f2c4e8a9d1b3
Create Date: 2026-03-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6e84f6d9c12"
down_revision: str | Sequence[str] | None = "f2c4e8a9d1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("provider_configs") as batch_op:
        batch_op.add_column(
            sa.Column("embedding_model", sa.String(length=128), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("enable_embedding", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("provider_configs") as batch_op:
        batch_op.drop_column("enable_embedding")
        batch_op.drop_column("embedding_model")

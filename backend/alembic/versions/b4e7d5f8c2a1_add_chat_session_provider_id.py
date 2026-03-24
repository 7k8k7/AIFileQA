"""add chat session provider id

Revision ID: b4e7d5f8c2a1
Revises: 9d3b6b4a2f11
Create Date: 2026-03-24 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4e7d5f8c2a1"
down_revision: Union[str, Sequence[str], None] = "9d3b6b4a2f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("chat_sessions")}

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("chat_sessions", recreate="always") as batch_op:
            if "provider_id" not in columns:
                batch_op.add_column(sa.Column("provider_id", sa.String(length=32), nullable=True))
            if "fk_chat_sessions_provider_id" not in foreign_keys:
                batch_op.create_foreign_key(
                    "fk_chat_sessions_provider_id",
                    "provider_configs",
                    ["provider_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        return

    if "provider_id" not in columns:
        op.add_column(
            "chat_sessions",
            sa.Column("provider_id", sa.String(length=32), nullable=True),
        )
    if "fk_chat_sessions_provider_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_chat_sessions_provider_id",
            "chat_sessions",
            "provider_configs",
            ["provider_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("chat_sessions")}

    if bind.dialect.name == "sqlite":
        if "provider_id" not in columns:
            return
        with op.batch_alter_table("chat_sessions", recreate="always") as batch_op:
            if "fk_chat_sessions_provider_id" in foreign_keys:
                batch_op.drop_constraint("fk_chat_sessions_provider_id", type_="foreignkey")
            batch_op.drop_column("provider_id")
        return

    if "fk_chat_sessions_provider_id" in foreign_keys:
        op.drop_constraint("fk_chat_sessions_provider_id", "chat_sessions", type_="foreignkey")
    if "provider_id" in columns:
        op.drop_column("chat_sessions", "provider_id")

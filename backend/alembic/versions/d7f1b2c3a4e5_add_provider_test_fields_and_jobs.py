"""add provider test fields and jobs

Revision ID: d7f1b2c3a4e5
Revises: a6e84f6d9c12
Create Date: 2026-03-24 00:00:03.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7f1b2c3a4e5"
down_revision: Union[str, Sequence[str], None] = "a6e84f6d9c12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("provider_configs") as batch_op:
        batch_op.add_column(
            sa.Column("last_test_success", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("last_test_message", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_ext", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)
    op.create_index("ix_jobs_document_id", "jobs", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_document_id", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")

    with op.batch_alter_table("provider_configs") as batch_op:
        batch_op.drop_column("last_test_at")
        batch_op.drop_column("last_test_message")
        batch_op.drop_column("last_test_success")

"""functions, function_versions, function_aliases, function_secrets, function_runs (Functions: Lambda 형 실행)

Revision ID: za1b2c3d4e5f
Revises: z9a1b2c3d4e5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "za1b2c3d4e5f"
down_revision: Union[str, None] = "z9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LongText = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")


def upgrade() -> None:
    op.create_table(
        "functions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("runtime", sa.String(20), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("disabled_reason", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_key", sa.String(36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "name", "deleted_key", name="uq_functions_name"),
    )
    op.create_table(
        "function_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("function_id", sa.String(36), sa.ForeignKey("functions.id"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tar_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("unpacked_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="drive"),
        sa.Column("source_ref", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("function_id", "version", name="uq_function_versions"),
    )
    op.create_table(
        "function_aliases",
        sa.Column("function_id", sa.String(36), sa.ForeignKey("functions.id"), primary_key=True),
        sa.Column("alias", sa.String(40), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "function_secrets",
        sa.Column("function_id", sa.String(36), sa.ForeignKey("functions.id"), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value_enc", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "function_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("function_id", sa.String(36), sa.ForeignKey("functions.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("input", LongText, nullable=True),
        sa.Column("result", LongText, nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("log", LongText, nullable=True),
        sa.Column("log_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cold_start_ms", sa.Integer(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_run_id", sa.String(36), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("idempotency_key", sa.String(80), nullable=True),
        sa.Column("worker_id", sa.String(80), nullable=True),
    )
    op.create_index("ix_function_runs_user_queued", "function_runs", ["user_id", "queued_at"])
    op.create_index("ix_function_runs_function_queued", "function_runs", ["function_id", "queued_at"])
    op.create_index("ix_function_runs_status", "function_runs", ["status"])
    op.create_table(
        "function_triggers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("function_id", sa.String(36), sa.ForeignKey("functions.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default=""),
        sa.Column("ref", sa.String(40), nullable=False, server_default="latest"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("schedule_type", sa.String(20), nullable=True),
        sa.Column("schedule_time", sa.String(5), nullable=True),
        sa.Column("weekdays", sa.JSON(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("interval_hours", sa.Integer(), nullable=True),
        sa.Column("run_at", sa.DateTime(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_id", sa.String(36), nullable=True),
        sa.Column("last_status", sa.String(120), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("last_called_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_function_triggers_due", "function_triggers", ["kind", "enabled", "next_run_at"])


def downgrade() -> None:
    for t in ("function_triggers", "function_runs", "function_secrets", "function_aliases", "function_versions", "functions"):
        op.drop_table(t)

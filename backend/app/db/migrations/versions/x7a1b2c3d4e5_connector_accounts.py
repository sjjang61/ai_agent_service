"""connector_accounts (Google Workspace 커넥터 OAuth 연결)

Revision ID: x7a1b2c3d4e5
Revises: w6a1b2c3d4e5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x7a1b2c3d4e5"
down_revision: Union[str, None] = "w6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connector_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("connectors", sa.JSON(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "provider", name="uq_connector_accounts_user_provider"),
    )


def downgrade() -> None:
    op.drop_table("connector_accounts")

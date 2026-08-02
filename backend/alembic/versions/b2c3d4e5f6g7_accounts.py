"""accounts: app_user, api_key, credit_ledger

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-01

Adds the monetization vertical slice tables (docs/13-COMPETITIVE-STRATEGY.md
section 5, docs/10-AUTH-AND-ACCOUNTS.md):
- APP_USER: named accounts (email + argon2id hash, role, subscription/credits)
- API_KEY: long-lived hashed keys (raw shown once at creation)
- CREDIT_LEDGER: append-only credit movements (1 credit = 1 comparison)
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="consumer"),
        sa.Column("subscription_active", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("credit_balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"])

    op.create_table(
        "api_key",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("user_id", sa.CHAR(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("key_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_api_key_user_id", "api_key", ["user_id"])
    op.create_index("ix_api_key_key_hash", "api_key", ["key_hash"])

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("user_id", sa.CHAR(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("delta", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])


def downgrade() -> None:
    op.drop_table("credit_ledger")
    op.drop_table("api_key")
    op.drop_table("app_user")

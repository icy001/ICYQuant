"""create account / position snapshot tables (Commit 015 §8)

    account
       ├── account_balance_snapshot
       └── position_snapshot
               └── position_snapshot_item

Revision ID: 003
Revises: 002
"""
from alembic import op

import sqlalchemy as sa


revision = "003"
down_revision = "002"


_MONEY = sa.Numeric(20, 4)
_QUANTITY = sa.Numeric(20, 6)
_RATE = sa.Numeric(12, 6)


def _timestamps() -> list:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "account",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False, server_default=""),
        sa.Column("broker", sa.String(64), nullable=False, server_default=""),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="OFFLINE"
        ),
        *_timestamps(),
    )
    op.create_index("ix_account_account_id", "account", ["account_id"])

    op.create_table(
        "account_balance_snapshot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.String(96), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("cash", _MONEY, nullable=False, server_default="0"),
        sa.Column("available_cash", _MONEY, nullable=False, server_default="0"),
        sa.Column("frozen_cash", _MONEY, nullable=False, server_default="0"),
        sa.Column("market_value", _MONEY, nullable=False, server_default="0"),
        sa.Column("total_asset", _MONEY, nullable=False, server_default="0"),
        sa.Column("buying_power", _MONEY, nullable=False, server_default="0"),
        sa.Column("broker_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_timestamp", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("sync_latency_ms", sa.Numeric(14, 3), nullable=True),
        sa.Column(
            "source", sa.String(16), nullable=False, server_default="BROKER"
        ),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.account_id"],
            name="fk_account_balance_snapshot_account",
        ),
        sa.UniqueConstraint(
            "snapshot_id", name="uq_account_balance_snapshot_id"
        ),
    )
    op.create_index(
        "ix_account_balance_snapshot_account_time",
        "account_balance_snapshot",
        ["account_id", "broker_timestamp"],
    )

    op.create_table(
        "position_snapshot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.String(96), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "position_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="SYNCED"
        ),
        sa.Column(
            "source", sa.String(16), nullable=False, server_default="BROKER"
        ),
        sa.Column("broker_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_timestamp", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("sync_latency_ms", sa.Numeric(14, 3), nullable=True),
        sa.Column("reconciliation_status", sa.String(24), nullable=True),
        sa.Column("reconciliation_outcome", sa.String(8), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.account_id"],
            name="fk_position_snapshot_account",
        ),
        sa.UniqueConstraint("snapshot_id", name="uq_position_snapshot_id"),
    )
    op.create_index(
        "ix_position_snapshot_account_time",
        "position_snapshot",
        ["account_id", "broker_timestamp"],
    )

    op.create_table(
        "position_snapshot_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.String(96), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(8), nullable=False, server_default=""),
        sa.Column("quantity", _QUANTITY, nullable=False, server_default="0"),
        sa.Column(
            "available_quantity", _QUANTITY, nullable=False, server_default="0"
        ),
        sa.Column(
            "frozen_quantity", _QUANTITY, nullable=False, server_default="0"
        ),
        sa.Column("average_cost", _MONEY, nullable=False, server_default="0"),
        sa.Column("market_price", _MONEY, nullable=True),
        sa.Column("market_value", _MONEY, nullable=True),
        sa.Column("unrealized_pnl", _MONEY, nullable=True),
        sa.Column("unrealized_pnl_pct", _RATE, nullable=True),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="VALID"
        ),
        sa.Column("broker_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_timestamp", sa.DateTime(timezone=True), nullable=True
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["position_snapshot.snapshot_id"],
            name="fk_position_snapshot_item_snapshot",
        ),
    )
    op.create_index(
        "ix_position_snapshot_item_account_symbol",
        "position_snapshot_item",
        ["account_id", "symbol"],
    )


def downgrade():
    op.drop_index(
        "ix_position_snapshot_item_account_symbol",
        table_name="position_snapshot_item",
    )
    op.drop_table("position_snapshot_item")
    op.drop_index(
        "ix_position_snapshot_account_time", table_name="position_snapshot"
    )
    op.drop_table("position_snapshot")
    op.drop_index(
        "ix_account_balance_snapshot_account_time",
        table_name="account_balance_snapshot",
    )
    op.drop_table("account_balance_snapshot")
    op.drop_index("ix_account_account_id", table_name="account")
    op.drop_table("account")

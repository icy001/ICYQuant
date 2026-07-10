"""
create ledger events table

Revision ID: 001
"""

from alembic import op

import sqlalchemy as sa


revision = "001"
down_revision = None


def upgrade():
    op.create_table(
        "ledger_events",
        sa.Column(
            "id",
            sa.String(),
            primary_key=True
        ),
        sa.Column(
            "event_type",
            sa.Text(),
            nullable=False
        ),
        sa.Column(
            "payload",
            sa.Text(),
            nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        )
    )


def downgrade():
    op.drop_table(
        "ledger_events"
    )
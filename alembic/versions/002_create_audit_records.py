"""
create audit records table
"""

from alembic import op

import sqlalchemy as sa


revision = "002"
down_revision = "001"


def upgrade():
    op.create_table(
        "audit_records",
        sa.Column(
            "id",
            sa.String(),
            primary_key=True
        ),
        sa.Column(
            "action",
            sa.Text(),
            nullable=False
        ),
        sa.Column(
            "reason",
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
        "audit_records"
    )
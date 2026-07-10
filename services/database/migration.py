"""
Database migration helper.
"""

from __future__ import annotations

import subprocess


def upgrade_database():
    """
    Apply latest migrations.
    """
    subprocess.run(
        [
            "alembic",
            "upgrade",
            "head"
        ],
        check=True
    )


def downgrade_database():
    """
    Rollback last migration.
    """
    subprocess.run(
        [
            "alembic",
            "downgrade",
            "-1"
        ],
        check=True
    )
"""
Alembic migration manager.

Manages database schema migrations
through the Alembic migration toolchain.
"""

from __future__ import annotations


class MigrationManager:
    """
    Alembic migration manager.

    Provides a programmatic interface to
    Alembic upgrade/downgrade/history commands.

    Alembic is lazily imported on first
    method call to allow this module to be
    imported even when alembic is not
    installed in the current environment.
    """

    def __init__(
        self,
        config_file: str = "alembic.ini",
    ) -> None:

        self._config_file = config_file

        self._config = None

    @property
    def config(
        self,
    ):
        """
        Return the Alembic config object.

        Creates it lazily on first access.
        """

        if self._config is None:
            from alembic.config import Config

            self._config = Config(
                self._config_file
            )

        return self._config

    def _get_command(self):
        """Lazily import alembic command module."""
        from alembic import command
        return command

    def upgrade(
        self,
        revision: str = "head",
    ) -> None:
        """
        Upgrade database schema to revision.

        Args:
            revision: Target revision or "head"
                for the latest.
        """

        command = self._get_command()

        command.upgrade(
            self.config,
            revision,
        )

    def downgrade(
        self,
        revision: str,
    ) -> None:
        """
        Downgrade database schema to revision.

        Args:
            revision: Target revision.
        """

        command = self._get_command()

        command.downgrade(
            self.config,
            revision,
        )

    def current(
        self,
    ) -> None:
        """
        Show current database revision.
        """

        command = self._get_command()

        command.current(
            self.config
        )

    def history(
        self,
    ) -> None:
        """
        Show migration history.
        """

        command = self._get_command()

        command.history(
            self.config
        )
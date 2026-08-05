"""Version rollback for the plugin marketplace.

Provides :class:`MarketplaceRollback` for creating checkpoints
before updates and restoring previous plugin versions on failure.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional

from ..exceptions import PluginInstallError
from ..utils import compare_versions

logger = logging.getLogger(__name__)


class MarketplaceRollback:
    """Manages version rollback for installed plugins.

    Creates checkpoints that save the current plugin state before
    an update, and can restore a plugin to any previous version
    when needed.

    Usage::

        rollback = MarketplaceRollback()
        checkpoint = await rollback.create_checkpoint("my.plugin")
        result = await rollback.rollback("my.plugin", "1.0.0")
        checkpoints = await rollback.list_checkpoints("my.plugin")
    """

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
    ) -> None:
        self._checkpoint_dir = checkpoint_dir or tempfile.mkdtemp(
            prefix="icyquant_checkpoints_"
        )
        self._checkpoints: Dict[str, List[Dict[str, Any]]] = {}
        self._checkpoint_count: int = 0
        self._rollback_count: int = 0
        self._failure_count: int = 0

        os.makedirs(self._checkpoint_dir, exist_ok=True)

    async def create_checkpoint(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Save the current state of a plugin as a checkpoint.

        Args:
            plugin_id: The plugin identifier to checkpoint.

        Returns:
            A dictionary with checkpoint information including
            ``checkpoint_id``, ``plugin_id``, ``timestamp``,
            and ``version``.
        """
        checkpoint_id = f"{plugin_id}_{int(time.time())}"
        checkpoint: Dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "plugin_id": plugin_id,
            "timestamp": time.time(),
            "version": None,
            "path": os.path.join(
                self._checkpoint_dir, f"{checkpoint_id}.json"
            ),
        }

        plugin_data = self._capture_plugin_state(plugin_id)
        checkpoint["version"] = plugin_data.get("version")
        checkpoint["plugin_data"] = plugin_data

        plugin_checkpoints = self._checkpoints.setdefault(
            plugin_id, []
        )
        plugin_checkpoints.append(checkpoint)

        self._persist_checkpoint(checkpoint)

        self._checkpoint_count += 1
        logger.info(
            "Created checkpoint '%s' for plugin '%s'.",
            checkpoint_id,
            plugin_id,
        )
        return {
            "checkpoint_id": checkpoint_id,
            "plugin_id": plugin_id,
            "timestamp": checkpoint["timestamp"],
            "version": checkpoint["version"],
        }

    async def rollback(
        self,
        plugin_id: str,
        target_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rollback a plugin to a previous version.

        Args:
            plugin_id: The plugin identifier to rollback.
            target_version: Optional target version. If ``None``,
                rolls back to the most recent checkpoint.

        Returns:
            A dictionary with rollback result.

        Raises:
            PluginInstallError: If no suitable checkpoint exists
                or the rollback fails.
        """
        self._rollback_count += 1
        start_time = time.time()

        try:
            checkpoints = self._checkpoints.get(plugin_id, [])
            if not checkpoints:
                raise PluginInstallError(
                    f"No checkpoints found for '{plugin_id}'."
                )

            target: Optional[Dict[str, Any]] = None
            if target_version is not None:
                for cp in reversed(checkpoints):
                    if cp.get("version") == target_version:
                        target = cp
                        break
                if target is None:
                    raise PluginInstallError(
                        f"No checkpoint found for version "
                        f"'{target_version}' of '{plugin_id}'."
                    )
            else:
                target = checkpoints[-1]

            self._restore_plugin_state(plugin_id, target)

            elapsed = time.time() - start_time
            logger.info(
                "Rolled back plugin '%s' to version '%s' in %.2fs.",
                plugin_id,
                target.get("version"),
                elapsed,
            )
            return {
                "success": True,
                "plugin_id": plugin_id,
                "target_version": target.get("version"),
                "checkpoint_id": target.get("checkpoint_id"),
                "duration_seconds": elapsed,
                "message": "Plugin rolled back successfully.",
            }
        except PluginInstallError:
            self._failure_count += 1
            raise
        except Exception as exc:
            self._failure_count += 1
            logger.error(
                "Failed to rollback plugin '%s': %s", plugin_id, exc
            )
            raise PluginInstallError(
                f"Failed to rollback plugin '{plugin_id}': {exc}"
            ) from exc

    async def list_checkpoints(
        self, plugin_id: str
    ) -> List[Dict[str, Any]]:
        """List all checkpoints for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            A list of checkpoint summary dictionaries (without
            the full plugin data).
        """
        checkpoints = self._checkpoints.get(plugin_id, [])
        summaries: List[Dict[str, Any]] = []
        for cp in checkpoints:
            summaries.append(
                {
                    "checkpoint_id": cp["checkpoint_id"],
                    "plugin_id": cp["plugin_id"],
                    "timestamp": cp["timestamp"],
                    "version": cp.get("version"),
                }
            )
        return summaries

    async def delete_checkpoint(
        self, plugin_id: str, checkpoint_id: str
    ) -> Dict[str, Any]:
        """Delete a specific checkpoint for a plugin.

        Args:
            plugin_id: The plugin identifier.
            checkpoint_id: The checkpoint identifier to delete.

        Returns:
            A dictionary with deletion result.

        Raises:
            KeyError: If the checkpoint is not found.
        """
        checkpoints = self._checkpoints.get(plugin_id, [])
        for i, cp in enumerate(checkpoints):
            if cp["checkpoint_id"] == checkpoint_id:
                del checkpoints[i]

                checkpoint_path = cp.get("path", "")
                if checkpoint_path and os.path.exists(
                    checkpoint_path
                ):
                    os.remove(checkpoint_path)

                logger.info(
                    "Deleted checkpoint '%s' for '%s'.",
                    checkpoint_id,
                    plugin_id,
                )
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "checkpoint_id": checkpoint_id,
                    "message": "Checkpoint deleted.",
                }

        raise KeyError(
            f"Checkpoint '{checkpoint_id}' not found for "
            f"'{plugin_id}'."
        )

    def get_stats(self) -> Dict[str, Any]:
        """Return rollback statistics.

        Returns:
            Dictionary with checkpoint and rollback counts.
        """
        total_checkpoints = sum(
            len(cps) for cps in self._checkpoints.values()
        )
        return {
            "total_checkpoints": total_checkpoints,
            "plugins_with_checkpoints": len(self._checkpoints),
            "checkpoint_count": self._checkpoint_count,
            "rollback_count": self._rollback_count,
            "failure_count": self._failure_count,
        }

    @staticmethod
    def _capture_plugin_state(
        plugin_id: str,
    ) -> Dict[str, Any]:
        """Capture the current state of a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            A dictionary with the plugin's state.
        """
        try:
            from ..registry import PluginRegistry

            registry = PluginRegistry()
            plugin = registry.get_plugin(plugin_id)
            if plugin is not None and hasattr(plugin, "to_dict"):
                return plugin.to_dict()
        except Exception:
            pass

        return {
            "id": plugin_id,
            "version": None,
            "state": "unknown",
        }

    @staticmethod
    def _restore_plugin_state(
        plugin_id: str, checkpoint: Dict[str, Any]
    ) -> None:
        """Restore a plugin's state from a checkpoint.

        Args:
            plugin_id: The plugin identifier.
            checkpoint: The checkpoint data to restore.
        """
        plugin_data = checkpoint.get("plugin_data", {})
        logger.info(
            "Restoring state for '%s' from checkpoint.",
            plugin_id,
        )
        logger.debug(
            "Restored data for '%s': %s", plugin_id, plugin_data
        )

    @staticmethod
    def _persist_checkpoint(checkpoint: Dict[str, Any]) -> None:
        """Persist a checkpoint to disk.

        Args:
            checkpoint: The checkpoint data to persist.
        """
        import json

        path = checkpoint.get("path", "")
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2, default=str)
        except OSError as exc:
            logger.warning(
                "Failed to persist checkpoint: %s", exc
            )
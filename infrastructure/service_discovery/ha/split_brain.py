"""Split-brain detection and resolution for ICYQuant HA.

Provides ``SplitBrainDetector`` for detecting network
partitions, leader conflicts, and registry splits, and
resolving them via majority voting and epoch versioning.

Detection: Leader Conflict, Registry Conflict, Network Partition
Resolution: Majority Voting, Epoch Version, Conflict Resolution
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SplitBrainDetector:
    """Detects and resolves split-brain scenarios.

    Uses epoch versioning and quorum-based detection to
    identify network partitions and leader conflicts, then
    resolves them through majority voting.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._epoch = 0
        self._detection_count = 0
        self._resolution_count = 0
        self._split_brain_detected = 0
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    def detect(
        self, nodes: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect split-brain across cluster nodes.

        Args:
            nodes: List of node state dictionaries. Each node
                should have at minimum: ``node_id``, ``role``,
                and ``epoch``.

        Returns:
            A dictionary describing the split-brain scenario if
            detected, or None.
        """
        with self._lock:
            self._detection_count += 1

        if not nodes:
            return None

        leaders: List[Dict[str, Any]] = []
        for node in nodes:
            if node.get("role") in ("leader", "primary"):
                leaders.append(node)

        if len(leaders) > 1:
            result: Dict[str, Any] = {
                "detected": True,
                "type": "leader_conflict",
                "description": "Multiple leaders detected.",
                "leaders": [
                    {
                        "node_id": l.get("node_id", "unknown"),
                        "epoch": l.get("epoch", 0),
                        "term": l.get("term", 0),
                    }
                    for l in leaders
                ],
                "node_count": len(nodes),
                "timestamp": self._now_iso(),
            }
            with self._lock:
                self._split_brain_detected += 1
                self._record_history("detect", result)
            logger.warning(
                "Split-brain detected: leader conflict (%d leaders).",
                len(leaders),
            )
            return result

        registry_versions: Dict[str, List[Dict[str, Any]]] = {}
        for node in nodes:
            reg_version = node.get("registry_version", 0)
            key = str(reg_version)
            registry_versions.setdefault(key, []).append(node)

        if len(registry_versions) > 1:
            max_count = max(len(v) for v in registry_versions.values())
            if max_count < len(nodes):
                result = {
                    "detected": True,
                    "type": "registry_conflict",
                    "description": (
                        "Nodes have inconsistent registry versions."
                    ),
                    "version_groups": {
                        k: [
                            n.get("node_id", "unknown")
                            for n in v
                        ]
                        for k, v in registry_versions.items()
                    },
                    "node_count": len(nodes),
                    "timestamp": self._now_iso(),
                }
                with self._lock:
                    self._split_brain_detected += 1
                    self._record_history("detect", result)
                logger.warning(
                    "Split-brain detected: registry conflict (%d "
                    "versions).",
                    len(registry_versions),
                )
                return result

        if len(leaders) == 0 and len(nodes) >= 2:
            epochs = {n.get("epoch", 0) for n in nodes}
            if len(epochs) > 1:
                result = {
                    "detected": True,
                    "type": "network_partition",
                    "description": (
                        "No leader and divergent epochs; "
                        "possible network partition."
                    ),
                    "epochs": sorted(epochs),
                    "node_count": len(nodes),
                    "timestamp": self._now_iso(),
                }
                with self._lock:
                    self._split_brain_detected += 1
                    self._record_history("detect", result)
                logger.warning(
                    "Split-brain detected: network partition."
                )
                return result

        return None

    def check_quorum(
        self, node_count: int, quorum_size: Optional[int] = None
    ) -> bool:
        """Check whether a quorum is satisfied.

        Args:
            node_count: Number of available nodes.
            quorum_size: Required quorum size. Defaults to
                ``(node_count // 2) + 1``.

        Returns:
            True if quorum is met.
        """
        if node_count <= 0:
            return False
        if quorum_size is None:
            quorum_size = (node_count // 2) + 1
        return node_count >= quorum_size

    async def resolve(
        self,
        node_a_data: Dict[str, Any],
        node_b_data: Dict[str, Any],
        strategy: str = "majority",
    ) -> Dict[str, Any]:
        """Resolve a split-brain conflict between two nodes.

        Args:
            node_a_data: State data from node A.
            node_b_data: State data from node B.
            strategy: Resolution strategy (majority, epoch,
                force).

        Returns:
            A dictionary describing the resolution outcome.
        """
        with self._lock:
            self._resolution_count += 1

        strategy = (strategy or "majority").lower()

        if strategy == "majority":
            result = self._resolve_by_majority(
                node_a_data, node_b_data
            )
        elif strategy == "epoch":
            result = self._resolve_by_epoch(
                node_a_data, node_b_data
            )
        elif strategy == "force":
            result = self._resolve_by_force(
                node_a_data, node_b_data
            )
        else:
            result = self._resolve_by_majority(
                node_a_data, node_b_data
            )

        self.increment_epoch()

        with self._lock:
            self._record_history("resolve", result)

        logger.info(
            "Split-brain resolved via '%s': winner=%s.",
            strategy,
            result.get("winner", "unknown"),
        )
        return result

    def get_epoch(self) -> int:
        """Return the current epoch number.

        Returns:
            The current epoch value.
        """
        with self._lock:
            return self._epoch

    def increment_epoch(self) -> int:
        """Increment the epoch and return the new value.

        Returns:
            The new epoch value.
        """
        with self._lock:
            self._epoch += 1
            return self._epoch

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the detector."""
        with self._lock:
            return {
                "epoch": self._epoch,
                "detection_count": self._detection_count,
                "resolution_count": self._resolution_count,
                "split_brain_detected": self._split_brain_detected,
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    # ── Resolution strategies ──

    @staticmethod
    def _resolve_by_majority(
        node_a: Dict[str, Any],
        node_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        votes_a = int(node_a.get("votes", node_a.get("node_count", 0)))
        votes_b = int(node_b.get("votes", node_b.get("node_count", 0)))

        if votes_a > votes_b:
            winner = node_a.get("node_id", "node_a")
            loser = node_b.get("node_id", "node_b")
        elif votes_b > votes_a:
            winner = node_b.get("node_id", "node_b")
            loser = node_a.get("node_id", "node_a")
        else:
            epoch_a = int(node_a.get("epoch", 0))
            epoch_b = int(node_b.get("epoch", 0))
            if epoch_a >= epoch_b:
                winner = node_a.get("node_id", "node_a")
                loser = node_b.get("node_id", "node_b")
            else:
                winner = node_b.get("node_id", "node_b")
                loser = node_a.get("node_id", "node_a")

        return {
            "strategy": "majority_voting",
            "winner": winner,
            "loser": loser,
            "votes_a": votes_a,
            "votes_b": votes_b,
            "resolved": True,
            "timestamp": SplitBrainDetector._now_iso(),
        }

    @staticmethod
    def _resolve_by_epoch(
        node_a: Dict[str, Any],
        node_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        epoch_a = int(node_a.get("epoch", 0))
        epoch_b = int(node_b.get("epoch", 0))

        if epoch_a >= epoch_b:
            winner = node_a.get("node_id", "node_a")
            loser = node_b.get("node_id", "node_b")
        else:
            winner = node_b.get("node_id", "node_b")
            loser = node_a.get("node_id", "node_a")

        return {
            "strategy": "epoch_version",
            "winner": winner,
            "loser": loser,
            "epoch_a": epoch_a,
            "epoch_b": epoch_b,
            "resolved": True,
            "timestamp": SplitBrainDetector._now_iso(),
        }

    @staticmethod
    def _resolve_by_force(
        node_a: Dict[str, Any],
        node_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        winner = node_a.get("node_id", "node_a")
        loser = node_b.get("node_id", "node_b")

        return {
            "strategy": "force",
            "winner": winner,
            "loser": loser,
            "resolved": True,
            "timestamp": SplitBrainDetector._now_iso(),
        }

    # ── Internal ──

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"SplitBrainDetector(epoch={self._epoch}, "
                f"detected={self._split_brain_detected})"
            )
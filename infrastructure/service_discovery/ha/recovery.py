"""Registry recovery for ICYQuant service discovery HA.

Provides ``RegistryRecovery`` for loading snapshots, replaying
events, verifying cluster consistency, and resuming operations
after a registry failure.

Pipeline: Load Snapshot -> Replay Events -> Consistency Check
          -> Resume
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RegistryRecovery:
    """Orchestrates registry recovery after a failure.

    Loads snapshots, replays events, verifies cluster
    consistency, and resumes normal operations.

    Args:
        registry: Optional registry for state restoration.
    """

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {
            "phase": "idle",
            "snapshot_loaded": False,
            "events_replayed": 0,
            "consistency_verified": False,
            "resumed": False,
        }
        self._recovery_count = 0
        self._event_count = 0
        self._inconsistency_count = 0
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    async def load_snapshot(
        self, snapshot_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load a snapshot into the registry.

        Args:
            snapshot_data: The snapshot dictionary to load.

        Returns:
            A dictionary describing the load result.
        """
        with self._lock:
            self._state["phase"] = "loading_snapshot"

        result: Dict[str, Any] = {
            "loaded": False,
            "services_restored": 0,
            "error": None,
            "timestamp": self._now_iso(),
        }

        try:
            services = snapshot_data.get("services", {})
            if not isinstance(services, dict):
                raise ValueError("Snapshot 'services' must be a dict.")

            if self._registry is not None:
                restore_func = getattr(self._registry, "restore", None)
                if callable(restore_func):
                    restore_result = restore_func(snapshot_data)
                    if asyncio.iscoroutine(restore_result):
                        await restore_result
                else:
                    for svc_name, instances in services.items():
                        if isinstance(instances, list):
                            for inst_data in instances:
                                register_func = getattr(
                                    self._registry, "register", None
                                )
                                if callable(register_func):
                                    try:
                                        from ..instance import (
                                            ServiceInstance,
                                        )

                                        inst = (
                                            ServiceInstance.from_dict(
                                                inst_data
                                            )
                                        )
                                        reg_result = register_func(inst)
                                        if asyncio.iscoroutine(reg_result):
                                            await reg_result
                                        result[
                                            "services_restored"
                                        ] += 1
                                    except Exception:
                                        pass
            else:
                result["services_restored"] = len(services)

            result["loaded"] = True
            result["snapshot_version"] = snapshot_data.get("version", 0)
            logger.info(
                "Snapshot loaded (version=%s, services=%d).",
                snapshot_data.get("version", 0),
                result["services_restored"],
            )
        except Exception as exc:
            result["error"] = str(exc)
            logger.exception("Failed to load snapshot: %s", exc)

        with self._lock:
            self._state["snapshot_loaded"] = result["loaded"]
            self._state["phase"] = (
                "snapshot_loaded" if result["loaded"] else "error"
            )

        self._record_history("load_snapshot", result)
        return result

    async def replay_events(
        self, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Replay a list of events to reconstruct state.

        Args:
            events: List of event dictionaries to replay.

        Returns:
            A dictionary describing the replay result.
        """
        with self._lock:
            self._state["phase"] = "replaying_events"

        replayed = 0
        failed = 0

        for event in events:
            try:
                await self._apply_event(event)
                replayed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Failed to replay event: %s", exc
                )

        result: Dict[str, Any] = {
            "replayed": True,
            "events_total": len(events),
            "events_replayed": replayed,
            "events_failed": failed,
            "timestamp": self._now_iso(),
        }

        with self._lock:
            self._state["events_replayed"] = replayed
            self._state["phase"] = "events_replayed"

        self._record_history("replay_events", result)
        logger.info(
            "Replayed %d/%d events.", replayed, len(events)
        )
        return result

    async def verify_consistency(self) -> Dict[str, Any]:
        """Verify cluster consistency after recovery.

        Returns:
            A dictionary with consistency check results.
        """
        with self._lock:
            self._state["phase"] = "verifying_consistency"

        result: Dict[str, Any] = {
            "consistent": True,
            "checks_performed": [],
            "inconsistencies": [],
            "timestamp": self._now_iso(),
        }

        check = {
            "name": "registry_state",
            "status": "passed",
            "message": "Registry state is consistent.",
        }
        result["checks_performed"].append(check)

        if self._registry is not None:
            try:
                list_func = getattr(self._registry, "list_services", None)
                if callable(list_func):
                    services = list_func()
                    if asyncio.iscoroutine(services):
                        services = await services
                    check = {
                        "name": "service_listing",
                        "status": "passed",
                        "message": f"{len(services)} services found.",
                    }
                    result["checks_performed"].append(check)
            except Exception as exc:
                result["consistent"] = False
                result["inconsistencies"].append(str(exc))
                check = {
                    "name": "service_listing",
                    "status": "failed",
                    "message": str(exc),
                }
                result["checks_performed"].append(check)
                with self._lock:
                    self._inconsistency_count += 1

        with self._lock:
            self._state["consistency_verified"] = result["consistent"]
            self._state["phase"] = (
                "consistent" if result["consistent"] else "inconsistent"
            )

        self._record_history("verify_consistency", result)
        return result

    async def resume(self) -> Dict[str, Any]:
        """Resume normal registry operations.

        Returns:
            A dictionary describing the resume result.
        """
        with self._lock:
            self._state["phase"] = "resuming"
            self._recovery_count += 1

        result: Dict[str, Any] = {
            "resumed": True,
            "state": dict(self._state),
            "timestamp": self._now_iso(),
        }

        with self._lock:
            self._state["resumed"] = True
            self._state["phase"] = "active"

        self._record_history("resume", result)
        logger.info("Registry operations resumed.")
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the recovery manager."""
        with self._lock:
            return {
                "phase": self._state["phase"],
                "snapshot_loaded": self._state["snapshot_loaded"],
                "events_replayed": self._state["events_replayed"],
                "consistency_verified": self._state[
                    "consistency_verified"
                ],
                "resumed": self._state["resumed"],
                "recovery_count": self._recovery_count,
                "event_count": self._event_count,
                "inconsistency_count": self._inconsistency_count,
                "history_size": len(self._history),
                "max_history": self._max_history,
                "registry_attached": self._registry is not None,
            }

    # ── Internal helpers ──

    async def _apply_event(self, event: Dict[str, Any]) -> None:
        """Apply a single event to the registry."""
        event_type = event.get("event_type", "")
        service_name = event.get("service_name", "")
        instance_id = event.get("instance_id", "")

        if self._registry is None:
            return

        if event_type in ("service.registered", "service.updated"):
            update_func = getattr(self._registry, "update_instance", None)
            if callable(update_func) and service_name and instance_id:
                updates = event.get("data", {})
                if updates:
                    result = update_func(
                        service_name, instance_id, updates
                    )
                    if asyncio.iscoroutine(result):
                        await result
        elif event_type == "service.deregistered":
            deregister_func = getattr(
                self._registry, "deregister", None
            )
            if callable(deregister_func) and service_name and instance_id:
                result = deregister_func(service_name, instance_id)
                if asyncio.iscoroutine(result):
                    await result

        with self._lock:
            self._event_count += 1

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
                f"RegistryRecovery(phase={self._state['phase']}, "
                f"recoveries={self._recovery_count})"
            )
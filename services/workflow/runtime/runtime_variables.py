"""Runtime Variables — variable store with scoping for workflow execution.

Supports variable scopes:
* **Input** — variables passed into the workflow
* **Output** — variables produced by the workflow
* **Global** — shared across all nodes
* **Temporary** — scoped to a single node execution
* **Secret Reference** — references to external secret stores
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VariableScope(str, Enum):
    """Scope categories for workflow variables."""

    INPUT = "input"
    OUTPUT = "output"
    GLOBAL = "global"
    TEMPORARY = "temporary"
    SECRET_REF = "secret_ref"


class RuntimeVariables:
    """Scoped variable store for workflow execution.

    Variables are organized by scope. Global variables are accessible to all
    nodes; temporary variables are node-scoped and automatically cleaned up.
    Secret references are resolved at runtime from an external secret store.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stores: Dict[VariableScope, Dict[str, Any]] = {
            scope: {} for scope in VariableScope
        }

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def get(self, key: str, scope: VariableScope = VariableScope.GLOBAL, default: Any = None) -> Any:
        with self._lock:
            return self._stores[scope].get(key, default)

    def set(self, key: str, value: Any, scope: VariableScope = VariableScope.GLOBAL) -> None:
        with self._lock:
            self._stores[scope][key] = value

    def delete(self, key: str, scope: VariableScope = VariableScope.GLOBAL) -> bool:
        with self._lock:
            if key in self._stores[scope]:
                del self._stores[scope][key]
                return True
            return False

    def has(self, key: str, scope: VariableScope = VariableScope.GLOBAL) -> bool:
        with self._lock:
            return key in self._stores[scope]

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def get_all(self, scope: VariableScope = VariableScope.GLOBAL) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stores[scope])

    def update(self, variables: Dict[str, Any], scope: VariableScope = VariableScope.GLOBAL) -> None:
        with self._lock:
            self._stores[scope].update(variables)

    def clear_scope(self, scope: VariableScope) -> None:
        with self._lock:
            self._stores[scope].clear()

    def clear_all(self) -> None:
        with self._lock:
            for scope in VariableScope:
                self._stores[scope].clear()

    # ------------------------------------------------------------------
    # Input / Output helpers
    # ------------------------------------------------------------------

    def set_inputs(self, inputs: Dict[str, Any]) -> None:
        self.update(inputs, VariableScope.INPUT)

    def get_inputs(self) -> Dict[str, Any]:
        return self.get_all(VariableScope.INPUT)

    def set_outputs(self, outputs: Dict[str, Any]) -> None:
        self.update(outputs, VariableScope.OUTPUT)

    def get_outputs(self) -> Dict[str, Any]:
        return self.get_all(VariableScope.OUTPUT)

    # ------------------------------------------------------------------
    # Temporary scope (per-node)
    # ------------------------------------------------------------------

    def set_temporary(self, node_id: str, key: str, value: Any) -> None:
        with self._lock:
            if node_id not in self._stores[VariableScope.TEMPORARY]:
                self._stores[VariableScope.TEMPORARY][node_id] = {}
            self._stores[VariableScope.TEMPORARY][node_id][key] = value

    def get_temporary(self, node_id: str, key: str, default: Any = None) -> Any:
        with self._lock:
            node_vars = self._stores[VariableScope.TEMPORARY].get(node_id, {})
            return node_vars.get(key, default)

    def clear_temporary(self, node_id: str) -> None:
        with self._lock:
            self._stores[VariableScope.TEMPORARY].pop(node_id, None)

    # ------------------------------------------------------------------
    # Secret references
    # ------------------------------------------------------------------

    def set_secret_ref(self, key: str, secret_path: str) -> None:
        self.set(key, {"ref": secret_path}, VariableScope.SECRET_REF)

    def get_secret_ref(self, key: str) -> Optional[str]:
        ref = self.get(key, scope=VariableScope.SECRET_REF)
        if isinstance(ref, dict):
            return ref.get("ref")
        return None

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all variables by scope."""
        with self._lock:
            return {
                scope.value: dict(store)
                for scope, store in self._stores.items()
                if store
            }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Restore variables from a snapshot."""
        with self._lock:
            self.clear_all()
            for scope_name, variables in snapshot.items():
                try:
                    scope = VariableScope(scope_name)
                    self._stores[scope] = dict(variables)
                except ValueError:
                    logger.warning("RuntimeVariables: unknown scope %s in snapshot", scope_name)

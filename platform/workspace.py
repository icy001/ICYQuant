"""
ICYQuant Platform - Workspace Manager

Manages multiple workspace lifecycles: Create → Load Config → Attach Modules
→ Run Strategy → Save Snapshot. Supports parallel workspace execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging
import uuid
import json

logger = logging.getLogger(__name__)


class WorkspaceStatus(str, Enum):
    CREATED = "created"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    SNAPSHOT = "snapshot"


@dataclass
class Workspace:
    name: str
    workspace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: WorkspaceStatus = WorkspaceStatus.CREATED
    config: Dict[str, Any] = field(default_factory=dict)
    attached_modules: List[str] = field(default_factory=list)
    running_strategies: List[str] = field(default_factory=list)
    snapshots: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error_message: str = ""

    def attach_module(self, module_name: str):
        if module_name not in self.attached_modules:
            self.attached_modules.append(module_name)

    def detach_module(self, module_name: str):
        if module_name in self.attached_modules:
            self.attached_modules.remove(module_name)

    def start_strategy(self, strategy_id: str):
        if strategy_id not in self.running_strategies:
            self.running_strategies.append(strategy_id)

    def stop_strategy(self, strategy_id: str):
        if strategy_id in self.running_strategies:
            self.running_strategies.remove(strategy_id)

    def save_snapshot(self, data: Dict[str, Any]):
        self.snapshots.append({
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "runningStrategies": list(self.running_strategies),
            "status": self.status.value,
        })

    def to_dict(self) -> Dict:
        return {
            "id": self.workspace_id,
            "name": self.name,
            "status": self.status.value,
            "config": self.config,
            "attachedModules": self.attached_modules,
            "runningStrategies": self.running_strategies,
            "snapshotCount": len(self.snapshots),
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "error": self.error_message,
        }


class WorkspaceManager:
    """
    Manages multiple workspace lifecycles.

    Supports parallel workspace execution with independent
    configurations, module attachments, and strategy runs.
    """

    def __init__(self):
        self._workspaces: Dict[str, Workspace] = {}
        self._name_index: Dict[str, str] = {}
        self._templates: Dict[str, Dict[str, Any]] = {}

    def create_workspace(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        template: Optional[str] = None,
    ) -> Workspace:
        if name in self._name_index:
            raise ValueError(f"Workspace '{name}' already exists")

        ws_config = config or {}
        if template and template in self._templates:
            ws_config.update(self._templates[template])

        workspace = Workspace(
            name=name,
            config=ws_config,
            status=WorkspaceStatus.LOADING,
        )

        self._workspaces[workspace.workspace_id] = workspace
        self._name_index[name] = workspace.workspace_id

        workspace.status = WorkspaceStatus.READY
        workspace.updated_at = datetime.now()

        logger.info(f"Workspace created: {name}")
        return workspace

    def load_workspace(self, workspace_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.status = WorkspaceStatus.LOADING
        ws.status = WorkspaceStatus.READY
        ws.updated_at = datetime.now()
        return True

    def run_workspace(self, workspace_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws or ws.status not in (WorkspaceStatus.READY, WorkspaceStatus.PAUSED):
            return False
        ws.status = WorkspaceStatus.RUNNING
        ws.updated_at = datetime.now()
        logger.info(f"Workspace running: {ws.name}")
        return True

    def pause_workspace(self, workspace_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws or ws.status != WorkspaceStatus.RUNNING:
            return False
        ws.status = WorkspaceStatus.PAUSED
        ws.updated_at = datetime.now()
        return True

    def resume_workspace(self, workspace_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws or ws.status != WorkspaceStatus.PAUSED:
            return False
        ws.status = WorkspaceStatus.RUNNING
        ws.updated_at = datetime.now()
        return True

    def stop_workspace(self, workspace_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.status = WorkspaceStatus.COMPLETED
        ws.running_strategies.clear()
        ws.updated_at = datetime.now()
        return True

    def delete_workspace(self, workspace_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        if ws.name in self._name_index:
            del self._name_index[ws.name]
        del self._workspaces[workspace_id]
        logger.info(f"Workspace deleted: {ws.name}")
        return True

    def attach_module(self, workspace_id: str, module_name: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.attach_module(module_name)
        ws.updated_at = datetime.now()
        return True

    def detach_module(self, workspace_id: str, module_name: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.detach_module(module_name)
        ws.updated_at = datetime.now()
        return True

    def start_strategy(self, workspace_id: str, strategy_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws or ws.status != WorkspaceStatus.RUNNING:
            return False
        ws.start_strategy(strategy_id)
        ws.updated_at = datetime.now()
        return True

    def stop_strategy(self, workspace_id: str, strategy_id: str) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.stop_strategy(strategy_id)
        ws.updated_at = datetime.now()
        return True

    def save_snapshot(self, workspace_id: str, data: Optional[Dict[str, Any]] = None) -> bool:
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False
        ws.save_snapshot(data or {})
        ws.status = WorkspaceStatus.SNAPSHOT
        ws.updated_at = datetime.now()
        return True

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        return self._workspaces.get(workspace_id)

    def get_by_name(self, name: str) -> Optional[Workspace]:
        wid = self._name_index.get(name)
        return self._workspaces.get(wid) if wid else None

    def list_workspaces(self, status: Optional[WorkspaceStatus] = None) -> List[Workspace]:
        workspaces = list(self._workspaces.values())
        if status:
            workspaces = [ws for ws in workspaces if ws.status == status]
        return workspaces

    def register_template(self, name: str, config: Dict[str, Any]):
        self._templates[name] = config

    def list_templates(self) -> List[str]:
        return list(self._templates.keys())

    def get_status(self) -> Dict:
        all_ws = list(self._workspaces.values())
        by_status = {}
        for ws in all_ws:
            s = ws.status.value
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total": len(all_ws),
            "byStatus": by_status,
            "running": sum(1 for ws in all_ws if ws.status == WorkspaceStatus.RUNNING),
            "templates": len(self._templates),
        }

    def to_dict(self) -> Dict:
        return self.get_status()

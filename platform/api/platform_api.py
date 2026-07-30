"""
ICYQuant Platform API - Platform Status Endpoints

REST API endpoints for platform operations:
- GET /api/v1/platform/status
- GET /api/v1/platform/modules
- POST /api/v1/platform/workflow
- POST /api/v1/platform/plugin
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PlatformAPI:
    """
    Platform REST API handler.

    Provides endpoints for:
    - Platform status
    - Module listing
    - Workflow management
    - Plugin management
    - Control plane operations
    """

    def __init__(self, platform_service=None):
        self._platform = platform_service
        self._request_log: List[Dict] = []

    def get_status(self) -> Dict[str, Any]:
        """GET /api/v1/platform/status"""
        if self._platform:
            return self._platform.get_status()
        return {
            "platform": "running",
            "modules": 42,
            "healthy": 42,
            "timestamp": datetime.now().isoformat(),
        }

    def list_modules(self, module_type: Optional[str] = None) -> List[Dict]:
        """GET /api/v1/platform/modules"""
        if self._platform:
            from ..module_registry import ModuleType
            mtype = None
            if module_type:
                try:
                    mtype = ModuleType(module_type)
                except ValueError:
                    pass
            modules = self._platform.get_modules(mtype)
            return modules
        return [
            {"name": "market", "type": "data", "state": "running"},
            {"name": "risk", "type": "risk", "state": "running"},
            {"name": "portfolio", "type": "portfolio", "state": "running"},
            {"name": "ai", "type": "ai", "state": "running"},
            {"name": "research", "type": "research", "state": "running"},
        ]

    def get_module(self, name: str) -> Optional[Dict]:
        """GET /api/v1/platform/modules/{name}"""
        if self._platform:
            for m in self._platform.get_modules():
                if m.get("name") == name:
                    return m
        return None

    def start_workflow(self, workflow_name: str, template: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v1/platform/workflow"""
        if self._platform:
            wf_id = self._platform.run_workflow(workflow_name, template=template)
            return {"workflowId": wf_id, "status": "started"}
        return {
            "workflow": workflow_name,
            "status": "started",
        }

    def list_workflows(self) -> List[Dict]:
        """GET /api/v1/platform/workflows"""
        if self._platform:
            return []
        return []

    def load_plugin(self, plugin_name: str, plugin_type: str = "extension") -> Dict[str, Any]:
        """POST /api/v1/platform/plugin"""
        if self._platform:
            from ..plugin_manager import PluginType
            try:
                pt = PluginType(plugin_type)
            except ValueError:
                pt = PluginType.UTILITY
            success = self._platform.load_plugin(plugin_name, pt)
            return {"plugin": plugin_name, "loaded": success}
        return {"plugin": plugin_name, "loaded": True}

    def list_plugins(self) -> List[Dict]:
        """GET /api/v1/platform/plugins"""
        if self._platform:
            return []
        return []

    def control_trading(self, action: str, reason: str = "") -> Dict[str, Any]:
        """POST /api/v1/platform/control/trading"""
        if self._platform:
            if action == "pause":
                return self._platform.pause_trading(reason)
            elif action == "resume":
                return self._platform.resume_trading(reason)
            elif action == "emergency_halt":
                return self._platform.emergency_halt(reason)
        return {"action": action, "status": "completed"}

    def restart_module(self, name: str) -> Dict[str, Any]:
        """POST /api/v1/platform/modules/{name}/restart"""
        if self._platform:
            success = self._platform.restart_module(name)
            return {"module": name, "restarted": success}
        return {"module": name, "restarted": True}

    def health_check(self) -> Dict[str, Any]:
        """GET /api/v1/platform/health"""
        status = self.get_status()
        return {
            "healthy": True,
            "status": "ok",
            "details": status,
        }

    def get_routes(self) -> List[Dict[str, str]]:
        """Return all available API routes."""
        return [
            {"method": "GET", "path": "/api/v1/platform/status", "description": "Platform status"},
            {"method": "GET", "path": "/api/v1/platform/modules", "description": "List modules"},
            {"method": "GET", "path": "/api/v1/platform/modules/{name}", "description": "Get module details"},
            {"method": "POST", "path": "/api/v1/platform/workflow", "description": "Start workflow"},
            {"method": "GET", "path": "/api/v1/platform/workflows", "description": "List workflows"},
            {"method": "POST", "path": "/api/v1/platform/plugin", "description": "Load plugin"},
            {"method": "GET", "path": "/api/v1/platform/plugins", "description": "List plugins"},
            {"method": "POST", "path": "/api/v1/platform/control/trading", "description": "Control trading"},
            {"method": "POST", "path": "/api/v1/platform/modules/{name}/restart", "description": "Restart module"},
            {"method": "GET", "path": "/api/v1/platform/health", "description": "Health check"},
        ]

    def get_status(self) -> Dict[str, Any]:
        if self._platform:
            return self._platform.get_status()
        return {
            "platform": "running",
            "modules": 42,
            "healthy": 42,
            "timestamp": datetime.now().isoformat(),
        }

    def to_dict(self) -> Dict:
        return {
            "routes": self.get_routes(),
            "status": self.get_status(),
        }

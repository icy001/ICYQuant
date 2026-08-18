"""
ICYQuant Platform - Platform Bootstrap

Startup flow: Load Config → Initialize Logger → Load Registry → Load Plugins
→ Connect Infrastructure → Start Services → Health Check → Ready
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import yaml
import os

logger = logging.getLogger(__name__)


class PlatformBootstrap:
    """
    Platform bootstrap manager.

    Manages the startup sequence ensuring all modules initialize
    in the correct dependency order.
    """

    def __init__(
        self,
        config_dir: str = "configs/platform",
        registry=None,
        runtime=None,
        lifecycle=None,
    ):
        self._config_dir = config_dir
        self._registry = registry
        self._runtime = runtime
        self._lifecycle = lifecycle
        self._bootstrap_status: Dict[str, Any] = {
            "phase": "init",
            "progress": 0,
            "steps": [],
            "errors": [],
            "started_at": None,
            "completed_at": None,
        }
        self._configs: Dict[str, Any] = {}

    def bootstrap(self) -> bool:
        """Execute the full bootstrap sequence."""
        self._bootstrap_status["started_at"] = datetime.now().isoformat()
        phases = [
            ("config", self._load_config),
            ("logger", self._init_logger),
            ("registry", self._load_registry),
            ("plugins", self._load_plugins),
            ("infrastructure", self._connect_infrastructure),
            ("services", self._start_services),
            ("health_check", self._run_health_check),
            ("ready", self._mark_ready),
        ]

        total = len(phases)
        for i, (phase_name, phase_fn) in enumerate(phases):
            self._bootstrap_status["phase"] = phase_name
            self._bootstrap_status["progress"] = int((i / total) * 100)

            try:
                phase_fn()
                self._bootstrap_status["steps"].append({
                    "phase": phase_name,
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info(f"Bootstrap phase '{phase_name}' completed")
            except Exception as e:
                self._bootstrap_status["steps"].append({
                    "phase": phase_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
                self._bootstrap_status["errors"].append({
                    "phase": phase_name,
                    "error": str(e),
                })
                logger.error(f"Bootstrap phase '{phase_name}' failed: {e}")
                self._bootstrap_status["phase"] = "error"
                return False

        self._bootstrap_status["progress"] = 100
        self._bootstrap_status["phase"] = "ready"
        self._bootstrap_status["completed_at"] = datetime.now().isoformat()
        logger.info("Platform bootstrap completed successfully")
        return True

    def _load_config(self):
        """Load all platform configuration files."""
        config_files = [
            "bootstrap.yaml",
            "modules.yaml",
            "plugins.yaml",
            "workflow.yaml",
            "runtime.yaml",
        ]
        for config_name in config_files:
            path = os.path.join(self._config_dir, config_name)
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        self._configs[config_name] = yaml.safe_load(f) or {}
                except Exception as e:
                    logger.warning(f"Failed to load config '{config_name}': {e}")
                    self._configs[config_name] = {}
            else:
                self._configs[config_name] = {}
        logger.info(f"Loaded {len(self._configs)} config files")

    def _init_logger(self):
        """Initialize platform logging configuration."""
        config = self._configs.get("bootstrap.yaml", {})
        log_level = config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

    def _load_registry(self):
        """Load module registry from config."""
        if not self._registry:
            return
        modules_config = self._configs.get("modules.yaml", {})
        if not modules_config:
            return

        modules = modules_config.get("modules", [])
        for mod_config in modules:
            name = mod_config.get("name", "")
            mod_type = mod_config.get("type", "unknown")
            version = mod_config.get("version", "1.0.0")
            self._registry.register(
                name=name,
                module_type=self._parse_module_type(mod_type),
                version=version,
                description=mod_config.get("description", ""),
                dependencies=mod_config.get("dependencies", []),
            )

    def _load_plugins(self):
        """Load plugins from config."""
        plugins_config = self._configs.get("plugins.yaml", {})
        plugins = plugins_config.get("plugins", [])
        logger.info(f"Processing {len(plugins)} plugins")

    def _connect_infrastructure(self):
        """Connect infrastructure services (DB, cache, message queue)."""
        logger.info("Connecting infrastructure services")

    def _start_services(self):
        """Start all registered services in dependency order."""
        if not self._registry or not self._runtime:
            return

        order = self._registry.ordered_by_dependencies()
        startup_order = [m.name for m in order]
        logger.info(f"Starting {len(startup_order)} modules in order: {startup_order}")

        for name in startup_order:
            rt = self._runtime.register_module(name)
            self._runtime.startup_module(name)

        if self._lifecycle:
            for name in startup_order:
                self._lifecycle.register_module(name)
                self._lifecycle.start(name)

    def _run_health_check(self):
        """Run health checks on all modules."""
        if not self._runtime:
            return
        results = self._runtime.run_health_checks()
        failed = [name for name, healthy in results.items() if not healthy]
        if failed:
            logger.warning(f"Health check failed for: {failed}")
        else:
            logger.info("All module health checks passed")

    def _mark_ready(self):
        """Mark the platform as ready."""
        self._bootstrap_status["phase"] = "ready"
        self._bootstrap_status["progress"] = 100

    def _parse_module_type(self, type_str: str):
        from .module_registry import ModuleType
        try:
            return ModuleType(type_str)
        except ValueError:
            return ModuleType.EXTENSION

    def get_config(self, name: str) -> Dict[str, Any]:
        return self._configs.get(name, {})

    def get_all_configs(self) -> Dict[str, Any]:
        return dict(self._configs)

    def get_bootstrap_status(self) -> Dict[str, Any]:
        return dict(self._bootstrap_status)

    def get_status(self) -> Dict:
        return self.get_bootstrap_status()

    def to_dict(self) -> Dict:
        return self.get_status()

"""Research Registry — central type registry for the research platform.

Maintains mappings of experiment types, dataset types, and runtime
configurations that can be dynamically registered and discovered.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class ResearchRegistry:
    """Central type registry for research platform components.

    Registers:
    * Experiment types → factory callables
    * Dataset types → loader callables
    * Runtime backends → executor callables
    * Artifact types → serializer callables
    """

    def __init__(self) -> None:
        self._experiment_types: Dict[str, Type] = {}
        self._experiment_factories: Dict[str, Callable] = {}
        self._dataset_types: Dict[str, Type] = {}
        self._dataset_loaders: Dict[str, Callable] = {}
        self._runtime_backends: Dict[str, Callable] = {}
        self._artifact_serializers: Dict[str, Callable] = {}
        self._report_generators: Dict[str, Callable] = {}

    # ── experiment registry ───────────────────────────────────────────────

    def register_experiment_type(
        self, name: str, cls: Type, factory: Optional[Callable] = None
    ) -> None:
        """Register an experiment type and optional factory."""
        self._experiment_types[name] = cls
        if factory:
            self._experiment_factories[name] = factory
        logger.debug("Registered experiment type: %s", name)

    def get_experiment_type(self, name: str) -> Optional[Type]:
        return self._experiment_types.get(name)

    def create_experiment(self, name: str, **kwargs) -> Any:
        factory = self._experiment_factories.get(name)
        if factory is None:
            raise ValueError(f"No factory registered for experiment type: {name}")
        return factory(**kwargs)

    def list_experiment_types(self) -> List[str]:
        return list(self._experiment_types.keys())

    # ── dataset registry ──────────────────────────────────────────────────

    def register_dataset_type(
        self, name: str, cls: Type, loader: Optional[Callable] = None
    ) -> None:
        """Register a dataset type and optional loader."""
        self._dataset_types[name] = cls
        if loader:
            self._dataset_loaders[name] = loader
        logger.debug("Registered dataset type: %s", name)

    def get_dataset_type(self, name: str) -> Optional[Type]:
        return self._dataset_types.get(name)

    def load_dataset(self, name: str, **kwargs) -> Any:
        loader = self._dataset_loaders.get(name)
        if loader is None:
            raise ValueError(f"No loader registered for dataset type: {name}")
        return loader(**kwargs)

    def list_dataset_types(self) -> List[str]:
        return list(self._dataset_types.keys())

    # ── runtime registry ──────────────────────────────────────────────────

    def register_runtime_backend(self, name: str, executor: Callable) -> None:
        """Register a runtime execution backend."""
        self._runtime_backends[name] = executor
        logger.debug("Registered runtime backend: %s", name)

    def get_runtime_backend(self, name: str) -> Optional[Callable]:
        return self._runtime_backends.get(name)

    def list_runtime_backends(self) -> List[str]:
        return list(self._runtime_backends.keys())

    # ── artifact registry ─────────────────────────────────────────────────

    def register_artifact_serializer(
        self, artifact_type: str, serializer: Callable
    ) -> None:
        """Register an artifact serializer."""
        self._artifact_serializers[artifact_type] = serializer
        logger.debug("Registered artifact serializer: %s", artifact_type)

    def get_artifact_serializer(self, artifact_type: str) -> Optional[Callable]:
        return self._artifact_serializers.get(artifact_type)

    def list_artifact_types(self) -> List[str]:
        return list(self._artifact_serializers.keys())

    # ── report registry ───────────────────────────────────────────────────

    def register_report_generator(
        self, report_type: str, generator: Callable
    ) -> None:
        """Register a report generator."""
        self._report_generators[report_type] = generator
        logger.debug("Registered report generator: %s", report_type)

    def get_report_generator(self, report_type: str) -> Optional[Callable]:
        return self._report_generators.get(report_type)

    # ── bulk operations ───────────────────────────────────────────────────

    def clear(self) -> None:
        """Clear all registrations."""
        self._experiment_types.clear()
        self._experiment_factories.clear()
        self._dataset_types.clear()
        self._dataset_loaders.clear()
        self._runtime_backends.clear()
        self._artifact_serializers.clear()
        self._report_generators.clear()

    def summary(self) -> Dict[str, Any]:
        return {
            "experiment_types": len(self._experiment_types),
            "dataset_types": len(self._dataset_types),
            "runtime_backends": len(self._runtime_backends),
            "artifact_types": len(self._artifact_serializers),
            "report_types": len(self._report_generators),
        }

    def __repr__(self) -> str:
        s = self.summary()
        return (
            f"ResearchRegistry(experiments={s['experiment_types']}, "
            f"datasets={s['dataset_types']}, runtimes={s['runtime_backends']})"
        )

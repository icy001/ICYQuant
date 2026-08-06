"""Workflow Loader — deserializes workflow definitions from various sources.

Supports loading from:
* YAML files
* JSON files
* Python dictionaries
* Database records (via WorkflowRepository)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from .workflow_definition import WorkflowDefinition
from .workflow_builder import WorkflowBuilder

logger = logging.getLogger(__name__)


class WorkflowLoader:
    """Loads workflow definitions from files, dicts, and databases.

    The loader normalizes all sources into :class:`WorkflowDefinition`
    instances.
    """

    # ------------------------------------------------------------------
    # File-based loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_yaml(path: Union[str, Path]) -> WorkflowDefinition:
        """Load a workflow definition from a YAML file.

        Raises:
            FileNotFoundError: if the file does not exist.
            yaml.YAMLError: if the YAML is malformed.
            ValueError: if the definition is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        logger.info("Loading workflow from YAML: %s", path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid workflow YAML: expected a dict, got {type(data)}")

        return WorkflowBuilder.from_dict(data)

    @staticmethod
    def load_json(path: Union[str, Path]) -> WorkflowDefinition:
        """Load a workflow definition from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        logger.info("Loading workflow from JSON: %s", path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid workflow JSON: expected a dict, got {type(data)}")

        return WorkflowBuilder.from_dict(data)

    @staticmethod
    def load_file(path: Union[str, Path]) -> WorkflowDefinition:
        """Auto-detect format (.yaml/.yml or .json) and load."""
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            return WorkflowLoader.load_yaml(path)
        elif suffix == ".json":
            return WorkflowLoader.load_json(path)
        else:
            raise ValueError(f"Unsupported workflow file format: {suffix}")

    # ------------------------------------------------------------------
    # Directory loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_directory(
        directory: Union[str, Path],
        *,
        recursive: bool = False,
    ) -> Dict[str, WorkflowDefinition]:
        """Load all workflow definitions from a directory.

        Returns a dict mapping workflow name → definition.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        pattern = "**/*.yaml" if recursive else "*.yaml"
        workflows: Dict[str, WorkflowDefinition] = {}

        for file_path in directory.glob(pattern):
            try:
                wf = WorkflowLoader.load_yaml(file_path)
                workflows[wf.name] = wf
                logger.debug("Loaded workflow %s from %s", wf.name, file_path)
            except Exception as exc:
                logger.warning("Failed to load workflow from %s: %s", file_path, exc)

        # Also try JSON files
        json_pattern = "**/*.json" if recursive else "*.json"
        for file_path in directory.glob(json_pattern):
            try:
                wf = WorkflowLoader.load_json(file_path)
                if wf.name not in workflows:
                    workflows[wf.name] = wf
                    logger.debug("Loaded workflow %s from %s", wf.name, file_path)
            except Exception as exc:
                logger.warning("Failed to load workflow from %s: %s", file_path, exc)

        logger.info("Loaded %d workflows from directory %s", len(workflows), directory)
        return workflows

    # ------------------------------------------------------------------
    # Dict-based loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_dict(data: Dict[str, Any]) -> WorkflowDefinition:
        """Load a workflow definition from a dictionary."""
        return WorkflowBuilder.from_dict(data)

    # ------------------------------------------------------------------
    # Database loading (via repository)
    # ------------------------------------------------------------------

    @staticmethod
    async def load_from_repository(
        workflow_id: str,
        repository: Any,
        *,
        version: Optional[str] = None,
    ) -> Optional[WorkflowDefinition]:
        """Load a workflow definition from a repository.

        Args:
            workflow_id: The workflow name/identifier.
            repository: A WorkflowRepository-compatible instance.
            version: Optional specific version to load.
        """
        # Delegate to the repository's load method
        if hasattr(repository, "load_definition"):
            return await repository.load_definition(workflow_id, version=version)
        logger.warning("Repository does not support load_definition")
        return None

    # ------------------------------------------------------------------
    # Batch loading
    # ------------------------------------------------------------------

    @staticmethod
    async def load_and_register_all(
        directory: Union[str, Path],
        registry: Any,
        *,
        recursive: bool = False,
    ) -> int:
        """Load all workflows from a directory and register them.

        Args:
            directory: Path to the directory containing workflow files.
            registry: A WorkflowRegistry-compatible instance.
            recursive: Whether to search subdirectories.

        Returns:
            The number of workflows successfully loaded and registered.
        """
        workflows = WorkflowLoader.load_directory(directory, recursive=recursive)
        count = 0
        for wf in workflows.values():
            try:
                if hasattr(registry, "register"):
                    await registry.register(wf)
                    count += 1
            except Exception as exc:
                logger.error("Failed to register workflow %s: %s", wf.name, exc)
        logger.info("Registered %d workflows from %s", count, directory)
        return count

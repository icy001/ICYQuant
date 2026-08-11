"""
ICYQuant Notebook Manager — Jupyter notebook integration for research workflows.

Manages notebook creation, versioning, execution tracking, and
integration with the research pipeline for reproducible research.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NotebookStatus(str, Enum):
    DRAFT = "draft"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class Notebook:
    """A research notebook entry."""
    notebook_id: str
    title: str
    session_id: str = ""
    status: NotebookStatus = NotebookStatus.DRAFT
    cells: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class NotebookManager:
    """Jupyter notebook management for research workflows.

    Responsibilities:
        - Create and manage research notebooks
        - Track cell execution and outputs
        - Version notebooks for reproducibility
        - Link notebooks to research sessions
        - Export notebooks in various formats
    """

    def __init__(self) -> None:
        self._notebooks: dict[str, Notebook] = {}
        self._total_created = 0

    def create(
        self,
        title: str,
        session_id: str = "",
        tags: Optional[list[str]] = None,
    ) -> Notebook:
        """Create a new research notebook."""
        import uuid
        notebook = Notebook(
            notebook_id=str(uuid.uuid4()),
            title=title,
            session_id=session_id,
            tags=tags or [],
        )
        self._notebooks[notebook.notebook_id] = notebook
        self._total_created += 1
        logger.info("Created notebook: %s", notebook.notebook_id)
        return notebook

    def add_cell(
        self,
        notebook_id: str,
        cell_type: str = "code",
        source: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Add a cell to a notebook."""
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            return None

        cell = {
            "cell_type": cell_type,
            "source": source,
            "metadata": metadata or {},
            "outputs": [],
            "execution_count": None,
            "executed_at": None,
        }
        notebook.cells.append(cell)
        notebook.updated_at = datetime.now(timezone.utc)
        return cell

    def record_output(
        self,
        notebook_id: str,
        cell_index: int,
        output: dict[str, Any],
    ) -> bool:
        """Record the output of a cell execution."""
        notebook = self._notebooks.get(notebook_id)
        if notebook is None or cell_index >= len(notebook.cells):
            return False

        notebook.cells[cell_index]["outputs"].append(output)
        notebook.cells[cell_index]["executed_at"] = datetime.now(timezone.utc).isoformat()
        notebook.updated_at = datetime.now(timezone.utc)
        return True

    def get_notebook(self, notebook_id: str) -> Optional[Notebook]:
        return self._notebooks.get(notebook_id)

    def list_by_session(self, session_id: str) -> list[Notebook]:
        """List notebooks for a research session."""
        return [n for n in self._notebooks.values() if n.session_id == session_id]

    def list_by_tag(self, tag: str) -> list[Notebook]:
        """List notebooks by tag."""
        return [n for n in self._notebooks.values() if tag in n.tags]

    def export(self, notebook_id: str) -> Optional[dict[str, Any]]:
        """Export notebook as a serializable dict."""
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            return None

        return {
            "notebook_id": notebook.notebook_id,
            "title": notebook.title,
            "session_id": notebook.session_id,
            "status": notebook.status.value,
            "cells": notebook.cells,
            "tags": notebook.tags,
            "version": notebook.version,
            "created_at": notebook.created_at.isoformat(),
            "updated_at": notebook.updated_at.isoformat(),
            "metadata": notebook.metadata,
        }

    def archive(self, notebook_id: str) -> bool:
        """Archive a notebook."""
        notebook = self._notebooks.get(notebook_id)
        if notebook:
            notebook.status = NotebookStatus.ARCHIVED
            notebook.updated_at = datetime.now(timezone.utc)
            return True
        return False

    @property
    def notebook_count(self) -> int:
        return len(self._notebooks)

    @property
    def total_created(self) -> int:
        return self._total_created

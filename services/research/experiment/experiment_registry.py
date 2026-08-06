"""Experiment Registry — stores and indexes experiments for fast retrieval.

Provides in-memory indexing with tag-based and status-based lookups.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from .experiment import Experiment

logger = logging.getLogger(__name__)


class ExperimentRegistry:
    """In-memory experiment index with multi-dimensional lookups.

    Indexes:
    * By ID (primary)
    * By status
    * By tags
    * By dataset
    * By experiment type
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Experiment] = {}
        self._by_status: Dict[str, Set[str]] = {}
        self._by_tag: Dict[str, Set[str]] = {}
        self._by_dataset: Dict[str, Set[str]] = {}
        self._by_type: Dict[str, Set[str]] = {}

    # ── registration ──────────────────────────────────────────────────────

    def register(self, experiment: Experiment) -> None:
        """Register an experiment in all indexes."""
        eid = experiment.id

        # Remove from old indexes if already registered
        if eid in self._by_id:
            self._unregister_indexes(eid, self._by_id[eid])

        self._by_id[eid] = experiment
        self._index_status(eid, experiment.status.value)
        for tag in experiment.tags:
            self._index_tag(eid, tag)
        if experiment.dataset:
            self._index_dataset(eid, experiment.dataset)
        self._index_type(eid, experiment.experiment_type)

        logger.debug("Registered experiment: %s", eid)

    def unregister(self, experiment_id: str) -> Optional[Experiment]:
        """Remove an experiment from all indexes."""
        experiment = self._by_id.pop(experiment_id, None)
        if experiment is None:
            return None
        self._unregister_indexes(experiment_id, experiment)
        return experiment

    # ── retrieval ─────────────────────────────────────────────────────────

    def get(self, experiment_id: str) -> Optional[Experiment]:
        return self._by_id.get(experiment_id)

    def list_all(self) -> List[Experiment]:
        return list(self._by_id.values())

    def list_by_status(self, status: str) -> List[Experiment]:
        ids = self._by_status.get(status, set())
        return [self._by_id[eid] for eid in ids if eid in self._by_id]

    def list_by_tag(self, tag: str) -> List[Experiment]:
        ids = self._by_tag.get(tag, set())
        return [self._by_id[eid] for eid in ids if eid in self._by_id]

    def list_by_tags(self, tags: List[str]) -> List[Experiment]:
        """List experiments matching ALL given tags."""
        if not tags:
            return []
        result_ids = self._by_tag.get(tags[0], set()).copy()
        for tag in tags[1:]:
            result_ids &= self._by_tag.get(tag, set())
        return [self._by_id[eid] for eid in result_ids if eid in self._by_id]

    def list_by_dataset(self, dataset: str) -> List[Experiment]:
        ids = self._by_dataset.get(dataset, set())
        return [self._by_id[eid] for eid in ids if eid in self._by_id]

    def list_by_type(self, experiment_type: str) -> List[Experiment]:
        ids = self._by_type.get(experiment_type, set())
        return [self._by_id[eid] for eid in ids if eid in self._by_id]

    # ── stats ─────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._by_id)

    def summary(self) -> Dict[str, Any]:
        return {
            "total": self.count,
            "by_status": {k: len(v) for k, v in self._by_status.items()},
            "by_tag": {k: len(v) for k, v in self._by_tag.items()},
            "by_dataset": {k: len(v) for k, v in self._by_dataset.items()},
            "by_type": {k: len(v) for k, v in self._by_type.items()},
        }

    # ── internal ──────────────────────────────────────────────────────────

    def _index_status(self, eid: str, status: str) -> None:
        self._by_status.setdefault(status, set()).add(eid)

    def _index_tag(self, eid: str, tag: str) -> None:
        self._by_tag.setdefault(tag, set()).add(eid)

    def _index_dataset(self, eid: str, dataset: str) -> None:
        self._by_dataset.setdefault(dataset, set()).add(eid)

    def _index_type(self, eid: str, experiment_type: str) -> None:
        self._by_type.setdefault(experiment_type, set()).add(eid)

    def _unregister_indexes(self, eid: str, experiment: Experiment) -> None:
        self._by_status.get(experiment.status.value, set()).discard(eid)
        for tag in experiment.tags:
            self._by_tag.get(tag, set()).discard(eid)
        if experiment.dataset:
            self._by_dataset.get(experiment.dataset, set()).discard(eid)
        self._by_type.get(experiment.experiment_type, set()).discard(eid)

    def __repr__(self) -> str:
        return f"ExperimentRegistry(experiments={self.count})"

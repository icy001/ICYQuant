"""Model Audit Engine – records model/parameter/prompt versions for full audit trail."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AuditRecord:
    model: str
    status: str = "RECORDED"
    model_version: str = "1.0.0"
    parameter_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    feature_version: str = "1.0.0"
    decision_version: str = "1.0.0"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelAuditEngine:
    """Records full model lineage for every AI decision."""

    def __init__(self) -> None:
        self._records: List[AuditRecord] = []

    def record(
        self,
        model: str,
        model_version: str = "1.0.0",
        parameter_version: str = "1.0.0",
        prompt_version: str = "1.0.0",
        feature_version: str = "1.0.0",
        decision_version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Record a model decision for audit purposes.

        Args:
            model: model name / identifier.
            model_version: version of the model.
            parameter_version: version of parameters used.
            prompt_version: version of the prompt (if LLM-based).
            feature_version: version of feature set.
            decision_version: version of the decision logic.
            metadata: additional context.

        Returns:
            The created AuditRecord.
        """
        record = AuditRecord(
            model=model,
            model_version=model_version,
            parameter_version=parameter_version,
            prompt_version=prompt_version,
            feature_version=feature_version,
            decision_version=decision_version,
            metadata=metadata or {},
        )
        self._records.append(record)
        return record

    def query_by_model(self, model: str) -> List[AuditRecord]:
        """Retrieve all audit records for a given model."""
        return [r for r in self._records if r.model == model]

    def query_by_timerange(self, start: datetime, end: datetime) -> List[AuditRecord]:
        """Retrieve audit records within a time window."""
        return [r for r in self._records if start <= r.timestamp <= end]

    @property
    def record_count(self) -> int:
        return len(self._records)

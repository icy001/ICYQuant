"""Evolution Memory – persist strategy evolution history and knowledge."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvolutionRecord:
    """A single record in the evolution memory."""

    record_id: str = ""
    event_type: str = ""  # "generation", "mutation", "crossover", "cull", "deploy"
    genome_name: str = ""
    generation: int = 0
    timestamp: str = ""

    # Details
    description: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    parent_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Outcome
    success: bool = True
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "event_type": self.event_type,
            "genome_name": self.genome_name,
            "generation": self.generation,
            "timestamp": self.timestamp,
            "description": self.description,
            "metrics": self.metrics,
            "parent_ids": self.parent_ids,
            "tags": self.tags,
            "success": self.success,
            "notes": self.notes,
        }


class EvolutionMemory:
    """Persistent memory for the strategy evolution process.

    Stores:
    - Strategy history (lineage, generations)
    - Mutation results (what mutations worked)
    - Crossover results (what combinations succeeded)
    - Failed experiments (to avoid repeating mistakes)
    - Successful patterns (to reinforce good mutations)
    - Evolution knowledge base
    """

    def __init__(self):
        self._history: List[EvolutionRecord] = []
        self._id_counter: int = 0

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def save(self, item: dict) -> EvolutionRecord:
        """Save an evolution event (legacy interface). Accepts a dict."""
        record = EvolutionRecord(
            record_id=self._next_id(),
            event_type=item.get("event_type", "unknown"),
            genome_name=item.get("genome_name", ""),
            generation=item.get("generation", 0),
            description=item.get("description", ""),
            metrics=item.get("metrics", {}),
            parent_ids=item.get("parent_ids", []),
            tags=item.get("tags", []),
            success=item.get("success", True),
            notes=item.get("notes", ""),
        )
        self._history.append(record)
        return record

    def save_record(self, record: EvolutionRecord) -> EvolutionRecord:
        """Save an evolution record."""
        if not record.record_id:
            record.record_id = self._next_id()
        self._history.append(record)
        return record

    def record_generation(self, generation: int, population_size: int,
                          elite: List[str], culled: int, stats: dict) -> EvolutionRecord:
        """Record a generation evolution event."""
        return self.save_record(EvolutionRecord(
            record_id=self._next_id(),
            event_type="generation",
            generation=generation,
            description=f"Generation {generation}: {population_size} strategies, "
                        f"{len(elite)} elite, {culled} culled",
            metrics={"population_size": population_size, "elite": elite,
                     "culled": culled, "stats": stats},
            tags=["generation"],
        ))

    def record_mutation(self, parent_name: str, child_name: str,
                        mutation_type: str, generation: int) -> EvolutionRecord:
        """Record a mutation event."""
        return self.save_record(EvolutionRecord(
            record_id=self._next_id(),
            event_type="mutation",
            genome_name=child_name,
            generation=generation,
            description=f"Mutated {parent_name} → {child_name} [{mutation_type}]",
            parent_ids=[parent_name],
            tags=["mutation", mutation_type],
        ))

    def record_crossover(self, parent_a: str, parent_b: str,
                         child_name: str, crossover_type: str,
                         generation: int) -> EvolutionRecord:
        """Record a crossover event."""
        return self.save_record(EvolutionRecord(
            record_id=self._next_id(),
            event_type="crossover",
            genome_name=child_name,
            generation=generation,
            description=f"Crossover {parent_a} × {parent_b} → {child_name} [{crossover_type}]",
            parent_ids=[parent_a, parent_b],
            tags=["crossover", crossover_type],
        ))

    def record_failure(self, genome_name: str, reason: str,
                       generation: int) -> EvolutionRecord:
        """Record a failed experiment to avoid repeating it."""
        return self.save_record(EvolutionRecord(
            record_id=self._next_id(),
            event_type="failure",
            genome_name=genome_name,
            generation=generation,
            description=f"Failed: {genome_name} – {reason}",
            success=False,
            notes=reason,
            tags=["failure"],
        ))

    def record_deployment(self, genome_name: str, generation: int,
                          score: float) -> EvolutionRecord:
        """Record a strategy deployment event."""
        return self.save_record(EvolutionRecord(
            record_id=self._next_id(),
            event_type="deploy",
            genome_name=genome_name,
            generation=generation,
            description=f"Deployed {genome_name} (score: {score:.1f})",
            metrics={"score": score},
            tags=["deployment"],
        ))

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_history(self) -> List[dict]:
        """Get all history records as dicts."""
        return [r.to_dict() for r in self._history]

    def get_records(self) -> List[EvolutionRecord]:
        """Get all evolution records."""
        return list(self._history)

    def get_by_type(self, event_type: str) -> List[EvolutionRecord]:
        """Query records by event type."""
        return [r for r in self._history if r.event_type == event_type]

    def get_by_genome(self, genome_name: str) -> List[EvolutionRecord]:
        """Query records for a specific genome."""
        return [r for r in self._history if r.genome_name == genome_name]

    def get_by_generation(self, generation: int) -> List[EvolutionRecord]:
        """Query records for a specific generation."""
        return [r for r in self._history if r.generation == generation]

    def get_by_tag(self, tag: str) -> List[EvolutionRecord]:
        """Query records by tag."""
        return [r for r in self._history if tag in r.tags]

    def get_successful_mutations(self) -> List[EvolutionRecord]:
        """Get successful mutation records."""
        return [r for r in self._history
                if r.event_type == "mutation" and r.success]

    def get_failed_experiments(self) -> List[EvolutionRecord]:
        """Get failed experiment records."""
        return [r for r in self._history
                if r.event_type == "failure" or
                (r.event_type == "mutation" and not r.success)]

    def get_deployments(self) -> List[EvolutionRecord]:
        """Get deployment records."""
        return self.get_by_type("deploy")

    # ------------------------------------------------------------------
    # Knowledge extraction
    # ------------------------------------------------------------------

    def get_successful_patterns(self) -> List[dict]:
        """Extract successful mutation/crossover patterns."""
        patterns = []
        for r in self._history:
            if r.success and r.event_type in ("mutation", "crossover"):
                patterns.append({
                    "type": r.event_type,
                    "description": r.description,
                    "tags": r.tags,
                })
        return patterns

    def get_failed_patterns(self) -> List[dict]:
        """Extract failed patterns to avoid."""
        patterns = []
        for r in self._history:
            if not r.success:
                patterns.append({
                    "reason": r.notes,
                    "genome_name": r.genome_name,
                })
        return patterns

    def summary(self) -> dict:
        """Get a summary of the evolution memory."""
        total = len(self._history)
        if total == 0:
            return {"total_records": 0}

        types = {}
        for r in self._history:
            types[r.event_type] = types.get(r.event_type, 0) + 1

        successes = sum(1 for r in self._history if r.success)
        failures = sum(1 for r in self._history if not r.success)
        max_gen = max((r.generation for r in self._history), default=0)

        return {
            "total_records": total,
            "event_types": types,
            "successful": successes,
            "failed": failures,
            "max_generation": max_gen,
        }

    def reset(self) -> None:
        """Clear all memory."""
        self._history.clear()
        self._id_counter = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"EVO-{self._id_counter:06d}"

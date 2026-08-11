"""
Genome — Encoded genetic representation of a factor or alpha.

The Genome is the core data structure that captures the full expression
of a factor or alpha in a form suitable for mutation, crossover, and
expression evaluation. It consists of a tree of Gene nodes.

Structure:
    Genome
    ├── genome_type: "factor" or "alpha"
    ├── root_gene: top-level Gene node
    ├── parameters: global parameters
    └── metadata: version, lineage info
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.alpha_evolution.gene import Gene


class GenomeType(Enum):
    FACTOR = "factor"
    ALPHA = "alpha"


class ExpressionType(Enum):
    """Types of factor/alpha expressions."""

    RAW = "raw"
    ZSCORE = "zscore"
    RANK = "rank"
    PERCENTILE = "percentile"
    WINSORIZE = "winsorize"
    NEUTRALIZE = "neutralize"
    LOG = "log"
    SQRT = "sqrt"
    POWER = "power"
    DELTA = "delta"
    PCT_CHANGE = "pct_change"
    ROLLING_MEAN = "rolling_mean"
    ROLLING_STD = "rolling_std"
    ROLLING_MIN = "rolling_min"
    ROLLING_MAX = "rolling_max"
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"
    COMPOSITE = "composite"
    CONDITIONAL = "conditional"


@dataclass
class Genome:
    """
    Encoded genetic representation of a factor or alpha expression.

    The genome can be serialized, cloned, mutated, and combined via crossover.
    It supports expression evaluation to produce the actual factor/alpha values.
    """

    genome_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    genome_type: GenomeType = GenomeType.FACTOR
    name: str = ""
    root_gene: Optional[Gene] = None
    expression_type: ExpressionType = ExpressionType.RAW
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    neutralization: Optional[Dict[str, Any]] = None
    version: int = 1
    parent_ids: List[str] = field(default_factory=list)
    creation_method: str = "seed"  # "seed", "mutation", "crossover"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Clone / Copy ───────────────────────────────────────

    def clone(self) -> Genome:
        """Deep copy the genome."""
        new_genome = copy.deepcopy(self)
        new_genome.genome_id = uuid.uuid4().hex[:12]
        new_genome.parent_ids = [self.genome_id]
        new_genome.version = 1
        new_genome.creation_method = "clone"
        new_genome.created_at = datetime.now(timezone.utc)
        return new_genome

    def copy_for_mutation(self) -> Genome:
        """Create a copy intended for mutation."""
        new_genome = self.clone()
        new_genome.creation_method = "mutation"
        new_genome.parent_ids = [self.genome_id]
        return new_genome

    def copy_for_crossover(self, other: Genome) -> Genome:
        """Create a copy intended as crossover offspring."""
        new_genome = self.clone()
        new_genome.creation_method = "crossover"
        new_genome.parent_ids = [self.genome_id, other.genome_id]
        return new_genome

    # ── Mutation Helpers ───────────────────────────────────

    def mutate_parameter(
        self, param_name: str, new_value: Any
    ) -> None:
        """Mutate a parameter value."""
        self.parameters[param_name] = new_value
        self.version += 1
        self.touch()

    def mutate_window(
        self, window_name: str, new_window: int
    ) -> None:
        """Mutate a look-back window size."""
        self.parameters[window_name] = new_window
        self.version += 1
        self.touch()

    def mutate_expression_type(
        self, new_type: ExpressionType
    ) -> None:
        """Change the expression type (e.g., raw → zscore)."""
        self.expression_type = new_type
        self.version += 1
        self.touch()

    def mutate_gene(
        self, gene_path: List[int], new_gene: Gene
    ) -> None:
        """Replace a gene at a given path in the gene tree."""
        if not self.root_gene or not gene_path:
            self.root_gene = new_gene
            self.version += 1
            self.touch()
            return

        current = self.root_gene
        for idx in gene_path[:-1]:
            if idx < len(current.children):
                current = current.children[idx]
            else:
                return

        last_idx = gene_path[-1]
        if last_idx < len(current.children):
            current.children[last_idx] = new_gene
            self.version += 1
            self.touch()

    # ── Crossover Helpers ──────────────────────────────────

    def get_all_genes(self) -> List[Gene]:
        """Flatten the gene tree into a list."""
        if not self.root_gene:
            return []
        return self.root_gene.flatten()

    def swap_subtree(
        self, gene_index: int, other_genome: Genome
    ) -> Optional[Gene]:
        """Swap a subtree with another genome (for crossover)."""
        my_genes = self.get_all_genes()
        other_genes = other_genome.get_all_genes()
        if gene_index >= len(my_genes) or gene_index >= len(other_genes):
            return None
        return other_genes[gene_index]

    # ── Expression ─────────────────────────────────────────

    def to_expression_string(self) -> str:
        """Convert genome to human-readable expression string."""
        if not self.root_gene:
            return "EMPTY"
        parts = []
        self._build_expression(self.root_gene, parts)
        expr = " ".join(parts)
        if self.expression_type == ExpressionType.ZSCORE:
            expr = f"zscore({expr})"
        elif self.expression_type == ExpressionType.RANK:
            expr = f"rank({expr})"
        elif self.expression_type == ExpressionType.PERCENTILE:
            expr = f"percentile({expr})"
        elif self.expression_type == ExpressionType.WINSORIZE:
            expr = f"winsorize({expr})"
        return expr

    def _build_expression(
        self, gene: Gene, parts: List[str]
    ) -> None:
        """Recursively build expression string from gene tree."""
        if gene.type == "operand":
            parts.append(str(gene.value))
            if gene.parameters:
                parts.append(f"({', '.join(f'{k}={v}' for k, v in gene.parameters.items())})")
        elif gene.type in ("operator", "function"):
            if not gene.children:
                parts.append(gene.value)
            elif len(gene.children) == 1:
                parts.append(gene.value)
                parts.append("(")
                self._build_expression(gene.children[0], parts)
                parts.append(")")
            else:
                parts.append("(")
                for i, child in enumerate(gene.children):
                    if i > 0:
                        parts.append(f" {gene.value} ")
                    self._build_expression(child, parts)
                parts.append(")")

    # ── Hashing ────────────────────────────────────────────

    def content_hash(self) -> str:
        """Compute a content hash for redundancy detection."""
        expr = self.to_expression_string()
        params = json.dumps(self.parameters, sort_keys=True)
        content = f"{self.genome_type.value}:{expr}:{params}"
        return hashlib.md5(content.encode()).hexdigest()

    def is_similar_to(
        self, other: Genome, correlation_threshold: float = 0.85
    ) -> bool:
        """Quick similarity check via expression hashing."""
        return self.content_hash() == other.content_hash()

    # ── Serialization ──────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "genome_type": self.genome_type.value,
            "name": self.name,
            "root_gene": self.root_gene.to_dict() if self.root_gene else None,
            "expression_type": self.expression_type.value,
            "parameters": self.parameters,
            "constraints": self.constraints,
            "neutralization": self.neutralization,
            "version": self.version,
            "parent_ids": self.parent_ids,
            "creation_method": self.creation_method,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Genome:
        genome = cls(
            genome_id=data.get("genome_id", ""),
            genome_type=GenomeType(data.get("genome_type", "factor")),
            name=data.get("name", ""),
            expression_type=ExpressionType(data.get("expression_type", "raw")),
            parameters=data.get("parameters", {}),
            constraints=data.get("constraints", {}),
            neutralization=data.get("neutralization"),
            version=data.get("version", 1),
            parent_ids=data.get("parent_ids", []),
            creation_method=data.get("creation_method", "seed"),
            metadata=data.get("metadata", {}),
        )
        if data.get("root_gene"):
            genome.root_gene = Gene.from_dict(data["root_gene"])
        return genome

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"Genome(id={self.genome_id}, type={self.genome_type.value}, "
            f"expr={self.to_expression_string()[:40]}..., v={self.version})"
        )

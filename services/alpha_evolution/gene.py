"""
Gene — Atomic unit of a Genome tree.

A Gene is a node in the expression tree that represents:
    - An operand (feature, constant)
    - An operator (+, -, *, /, etc.)
    - A function (momentum, volatility, zscore, rank, etc.)

Genes form a tree structure where:
    - Leaf nodes are operands (input features/constants)
    - Internal nodes are operators or functions
    - The tree encodes a mathematical/computational expression
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class GeneType:
    """Gene type constants."""

    OPERAND = "operand"    # Input feature or constant
    OPERATOR = "operator"  # Mathematical operator
    FUNCTION = "function"  # Transformation function
    CONDITION = "condition"  # Conditional node
    AGGREGATOR = "aggregator"  # Aggregation node


class GeneOperator:
    """Common operators used in factor expressions."""

    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    POW = "^"
    AND = "&"
    OR = "|"
    GT = ">"
    LT = "<"
    EQ = "=="
    NEQ = "!="


class GeneFunction:
    """Common functions used in factor expressions."""

    # Transformations
    ZSCORE = "zscore"
    RANK = "rank"
    PERCENTILE = "percentile"
    WINSORIZE = "winsorize"
    NEUTRALIZE = "neutralize"
    LOG = "log"
    SQRT = "sqrt"
    ABS = "abs"
    SIGN = "sign"

    # Rolling / Window
    MEAN = "mean"
    STD = "std"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    PROD = "prod"
    MEDIAN = "median"
    SKEW = "skew"
    KURTOSIS = "kurtosis"

    # Momentum / Trend
    MOMENTUM = "momentum"
    ROC = "roc"  # Rate of change
    EMA = "ema"
    SMA = "sma"

    # Volatility
    VOLATILITY = "volatility"
    ATR = "atr"

    # Volume
    VOLUME_RATIO = "volume_ratio"
    VWAP = "vwap"

    # Cross-sectional
    CROSS_SECTIONAL_RANK = "cs_rank"
    CROSS_SECTIONAL_ZSCORE = "cs_zscore"
    GROUP_MEAN = "group_mean"
    GROUP_MEDIAN = "group_median"

    # Conditional
    IF_ELSE = "if_else"
    CLIP = "clip"

    # Decay / Time
    DECAY_LINEAR = "decay_linear"
    DECAY_EXP = "decay_exp"


@dataclass
class Gene:
    """
    A node in the genome expression tree.

    Attributes:
        type: Gene type (operand, operator, function, etc.)
        value: The specific value/name
        parameters: Key-value parameters for functions
        children: Child genes (for operators and functions)
        weight: Optional weight for weighted combinations
        description: Human-readable description
        metadata: Arbitrary metadata
    """

    type: str = GeneType.OPERAND
    value: Any = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    children: List[Gene] = field(default_factory=list)
    weight: float = 1.0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ────────────────────────────────────

    @classmethod
    def operand(cls, value: Any, **params) -> Gene:
        """Create an operand (feature/constant) gene."""
        return cls(
            type=GeneType.OPERAND,
            value=value,
            parameters=params,
        )

    @classmethod
    def operator(
        cls, op: str, *children: Gene, **params
    ) -> Gene:
        """Create an operator gene."""
        return cls(
            type=GeneType.OPERATOR,
            value=op,
            children=list(children),
            parameters=params,
        )

    @classmethod
    def function(
        cls, func_name: str, *children: Gene, **params
    ) -> Gene:
        """Create a function gene."""
        return cls(
            type=GeneType.FUNCTION,
            value=func_name,
            children=list(children),
            parameters=params,
        )

    @classmethod
    def momentum(cls, feature: str, window: int = 20) -> Gene:
        """Create a momentum gene."""
        return cls.function(
            GeneFunction.MOMENTUM,
            cls.operand(feature),
            window=window,
        )

    @classmethod
    def zscore(cls, child: Gene, window: int = 252) -> Gene:
        """Create a z-score normalization gene."""
        return cls.function(
            GeneFunction.ZSCORE,
            child,
            window=window,
        )

    @classmethod
    def rank(cls, child: Gene) -> Gene:
        """Create a cross-sectional rank gene."""
        return cls.function(GeneFunction.RANK, child)

    @classmethod
    def volatility(cls, feature: str, window: int = 20) -> Gene:
        """Create a volatility gene."""
        return cls.function(
            GeneFunction.VOLATILITY,
            cls.operand(feature),
            window=window,
        )

    @classmethod
    def composite(
        cls, *genes_with_weights: tuple[Gene, float]
    ) -> Gene:
        """Create a weighted composite gene."""
        children = []
        weights = []
        for gene, weight in genes_with_weights:
            child = gene
            child.weight = weight
            children.append(child)
            weights.append(weight)
        return cls(
            type=GeneType.FUNCTION,
            value=GeneFunction.MEAN,
            children=children,
            parameters={"weights": weights},
        )

    @classmethod
    def conditional(
        cls, condition: Gene, true_branch: Gene, false_branch: Gene
    ) -> Gene:
        """Create a conditional (if-else) gene."""
        return cls.function(
            GeneFunction.IF_ELSE,
            condition,
            true_branch,
            false_branch,
        )

    # ── Tree Operations ────────────────────────────────────

    def flatten(self) -> List[Gene]:
        """Flatten the gene tree into a list (pre-order)."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def get_leaf_operands(self) -> List[Gene]:
        """Get all leaf operand genes (features/constants)."""
        leaves = []
        for gene in self.flatten():
            if gene.type == GeneType.OPERAND and not gene.children:
                leaves.append(gene)
        return leaves

    def depth(self) -> int:
        """Get the maximum depth of the gene tree."""
        if not self.children:
            return 1
        return 1 + max(child.depth() for child in self.children)

    def size(self) -> int:
        """Get the total number of genes in the tree."""
        return len(self.flatten())

    def replace_child(self, index: int, new_gene: Gene) -> None:
        """Replace a child gene at a given index."""
        if 0 <= index < len(self.children):
            self.children[index] = new_gene

    def add_child(self, child: Gene) -> None:
        """Add a child gene."""
        self.children.append(child)

    def insert_child(self, index: int, child: Gene) -> None:
        """Insert a child gene at a specific index."""
        self.children.insert(index, child)

    def remove_child(self, index: int) -> Optional[Gene]:
        """Remove and return a child gene at index."""
        if 0 <= index < len(self.children):
            return self.children.pop(index)
        return None

    def get_operators(self) -> List[Gene]:
        """Get all operator genes in the tree."""
        return [g for g in self.flatten() if g.type == GeneType.OPERATOR]

    def get_functions(self) -> List[Gene]:
        """Get all function genes in the tree."""
        return [g for g in self.flatten() if g.type == GeneType.FUNCTION]

    # ── Mutation Helpers ───────────────────────────────────

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def is_operator(self) -> bool:
        return self.type == GeneType.OPERATOR

    @property
    def is_function(self) -> bool:
        return self.type == GeneType.FUNCTION

    @property
    def is_operand(self) -> bool:
        return self.type == GeneType.OPERAND

    def clone(self) -> Gene:
        """Deep copy the gene tree."""
        from copy import deepcopy
        return deepcopy(self)

    # ── Serialization ──────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value,
            "parameters": self.parameters,
            "children": [c.to_dict() for c in self.children],
            "weight": self.weight,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Gene:
        gene = cls(
            type=data.get("type", GeneType.OPERAND),
            value=data.get("value"),
            parameters=data.get("parameters", {}),
            weight=data.get("weight", 1.0),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )
        gene.children = [
            cls.from_dict(c) for c in data.get("children", [])
        ]
        return gene

    def __repr__(self) -> str:
        return (
            f"Gene(type={self.type}, value={self.value}, "
            f"children={len(self.children)}, params={list(self.parameters.keys())})"
        )

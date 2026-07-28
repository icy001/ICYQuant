"""Decision Collector – collects decisions from all Intelligence Engines into Decision Packages."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DecisionPackage:
    """A single decision from an intelligence engine."""

    source: str
    signal: str
    confidence: float
    payload: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionCollector:
    """Collects DecisionPackages from all upstream intelligence engines.

    Acts as the unified ingestion point for the Decision Center.
    """

    def __init__(self) -> None:
        self._packages: List[DecisionPackage] = []

    def collect(
        self,
        source: str,
        signal: str,
        confidence: float,
        payload: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionPackage:
        package = DecisionPackage(
            source=source,
            signal=signal,
            confidence=confidence,
            payload=payload,
            metadata=metadata or {},
        )
        self._packages.append(package)
        return package

    def flush(self) -> List[DecisionPackage]:
        packages = list(self._packages)
        self._packages.clear()
        return packages

    @property
    def package_count(self) -> int:
        return len(self._packages)

    def by_source(self, source: str) -> List[DecisionPackage]:
        return [p for p in self._packages if p.source == source]

    def by_signal(self, signal: str) -> List[DecisionPackage]:
        return [p for p in self._packages if p.signal == signal]

"""Candidate Generator for Strategy Discovery Lab v1.

Generates exactly ``spec.candidates_total`` (300) reproducible candidates from
the sealed parameter grids with the fixed family distribution:

    Trend 100 / Momentum 60 / Breakout 60 / Mean Reversion 50 / Hybrid 30

No free-form random strategy authoring — every candidate is an instantiation of
a whitelisted structure with whitelisted parameter values.  Families whose grid
pool exceeds the family target are sampled deterministically with a fixed seed,
so the generated set is bit-for-bit reproducible across runs.

Candidates are *strategy templates* (``asset="ALL"``); the engine expands each
template across the 9-asset universe as per-asset candidate instances.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .candidate import Candidate, CandidateManifest
from .spec import DISCOVERY_SPEC_V1, FAMILY_NAMES, DiscoverySpec


@dataclass
class CandidateGenerator:
    """Deterministic generator of the v1 candidate set."""

    spec: DiscoverySpec = field(default_factory=lambda: DISCOVERY_SPEC_V1)
    seed: int = 42
    candidate_timeframe: str = "1H"

    # ------------------------------------------------------------------ #
    def _family_pool(self, family: str) -> list[tuple[str, dict[str, Any]]]:
        """All (structure_id, params) combinations for a family, in structure
        order, using only the whitelisted parameter grids."""
        pool: list[tuple[str, dict[str, Any]]] = []
        for sid, struct in self.spec.structures.items():
            if struct["family"] != family:
                continue
            for params in self.spec.parameter_spaces.get(sid, []):
                pool.append((sid, dict(params)))
        return pool

    # ------------------------------------------------------------------ #
    def generate(self) -> list[Candidate]:
        """Generate the full candidate set (300) in family order."""
        rng = random.Random(self.seed)
        structure_order = {sid: i for i, sid in enumerate(self.spec.structures)}
        candidates: list[Candidate] = []

        for family in FAMILY_NAMES:
            target = int(self.spec.family_target[family])
            if target <= 0:
                continue  # family excluded from this experiment
            pool = self._family_pool(family)
            if len(pool) < target:
                raise ValueError(
                    f"Family '{family}': grid pool {len(pool)} < target {target}. "
                    "Expand PARAMETER_SPACES in spec.py."
                )
            chosen = pool if len(pool) == target else rng.sample(pool, target)
            # stable ordering: structure order, then parameters
            chosen.sort(key=lambda item: (
                structure_order[item[0]],
                json.dumps(item[1], sort_keys=True),
            ))
            for structure_id, params in chosen:
                cid = f"C{len(candidates) + 1:04d}"
                candidates.append(Candidate.build(
                    candidate_id=cid,
                    structure_id=structure_id,
                    parameters=params,
                    asset="ALL",
                    timeframe=self.candidate_timeframe,
                ))

        if len(candidates) != self.spec.candidates_total:
            raise RuntimeError(
                f"Generated {len(candidates)} candidates, expected "
                f"{self.spec.candidates_total}."
            )
        return candidates

    # ------------------------------------------------------------------ #
    def generate_manifest(self, candidates: Optional[list[Candidate]] = None,
                          generated_at: Optional[str] = None) -> CandidateManifest:
        """Snapshot of the spec + candidates (fully reproducible)."""
        return CandidateManifest(
            spec=self.spec.to_dict(),
            generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
            candidates=candidates if candidates is not None else self.generate(),
        )

    # ------------------------------------------------------------------ #
    def family_counts(self, candidates: list[Candidate]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in candidates:
            counts[c.family] = counts.get(c.family, 0) + 1
        return counts

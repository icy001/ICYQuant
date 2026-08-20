"""Command-line entry point for Strategy Discovery Lab v1 experiments.

Examples
--------
    # Discovery Experiment #001 (9 assets x 1H, Trend/Momentum/Breakout)
    python -m research.discovery.run --experiment-id exp-001 \
        --families Trend Momentum Breakout --jobs 4

    # full sealed spec (300 candidates across all five families)
    python -m research.discovery.run --experiment-id exp-full --jobs 4

    # fast smoke test (2 candidates x 1 asset)
    python -m research.discovery.run --experiment-id smoke --limit 2 \
        --assets NVDA --jobs 1
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .engine import DiscoveryEngine
from .report import DiscoveryReport
from .spec import DISCOVERY_SPEC_V1


def _default_experiment_id() -> str:
    return "discovery-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.discovery.run",
        description="Run a Strategy Discovery Lab v1 experiment.",
    )
    parser.add_argument("--experiment-id", default=None,
                        help="Unique experiment id (default: timestamp).")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Number of worker processes (default: 1).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit the number of candidates (smoke tests).")
    parser.add_argument("--assets", nargs="+", default=None,
                        help="Restrict the universe (e.g. --assets NVDA SPY).")
    parser.add_argument("--families", nargs="+", default=None,
                        help="Restrict strategy families "
                             "(e.g. --families Trend Momentum Breakout).")
    parser.add_argument("--data-root", type=Path, default=None,
                        help="Path to the processed CSV data directory.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Report output directory.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Generator seed (default: 42).")
    args = parser.parse_args(argv)

    experiment_id = args.experiment_id or _default_experiment_id()
    print(f"[discovery] experiment_id={experiment_id} jobs={args.jobs} "
          f"limit={args.limit} assets={args.assets} "
          f"families={args.families} seed={args.seed}")

    spec = DISCOVERY_SPEC_V1
    if args.families:
        spec = _families_restricted_spec(spec, args.families)
    if args.assets:
        spec = replace(spec, universe=tuple(args.assets))

    engine = DiscoveryEngine(
        spec=spec,
        data_root=args.data_root,
        jobs=args.jobs,
        seed=args.seed,
    )

    result = engine.run_experiment(experiment_id, limit=args.limit)

    # candidate manifest (reproducibility artifact)
    manifest = engine.generator.generate_manifest(candidates=engine.candidates)
    report = DiscoveryReport(output_dir=args.output_dir, spec=engine.spec)
    json_path, md_path = report.save(report.build(result, engine.candidates),
                                     result.experiment_id)
    manifest_dir = json_path.parent
    manifest_path = manifest_dir / "candidate_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _print_summary(result)
    print(f"[discovery] report:  {md_path}")
    print(f"[discovery] json:    {json_path}")
    print(f"[discovery] manifest:{manifest_path}")
    return 0


def _families_restricted_spec(spec, families: list[str]):
    """Return a copy of the spec restricted to the given strategy families.

    Excluded families get a target of 0; ``candidates_total`` is recomputed
    from the remaining targets. All other sealed settings are untouched.
    """
    unknown = [f for f in families if f not in spec.family_target]
    if unknown:
        valid = ", ".join(sorted(spec.family_target))
        raise SystemExit(f"unknown families: {unknown}. Valid families: {valid}")
    target = {f: (n if f in families else 0) for f, n in spec.family_target.items()}
    return replace(spec, family_target=target,
                   candidates_total=sum(target.values()))


def _print_summary(result) -> None:
    f = result.to_dict()["funnel"]
    print()
    print("=" * 68)
    print("Discovery Gate v1 Funnel")
    print("=" * 68)
    for k, v in f.items():
        print(f"  {k:24s} {v}")
    print("-" * 68)
    for r in result.top_candidates:
        print(f"  {r['candidate_id']} {r['family']:14s} "
              f"assets={len(r['assets_passed'])} "
              f"score={r['total_score']:.4f}")
    print("=" * 68)


if __name__ == "__main__":
    sys.exit(main())

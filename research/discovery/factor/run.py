"""Command-line entry point for the Factor Discovery Track (Alpha101).

Examples
--------
    # full sealed experiment: 101 alphas x 9 assets
    python -m research.discovery.factor.run --experiment-id factor-v1 --jobs 4

    # fast smoke test (5 alphas x 1 asset)
    python -m research.discovery.factor.run --experiment-id factor-smoke \
        --limit-alphas 5 --assets NVDA --jobs 1

    # real daily data validation (data/real/d1)
    python -m research.discovery.factor.run --experiment-id factor-real-d1 \
        --spec factor-discovery-real-d1 --data-root data/real/d1 --jobs 4

    # converge with a specific strategy experiment
    python -m research.discovery.factor.run --experiment-id factor-v1 \
        --strategy-report research/discovery/output/lab-v1/report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .factor_engine import FactorDiscoveryEngine
from .factor_report import FactorReport
from .factor_spec import FACTOR_SPEC_REAL_D1, FACTOR_SPEC_V1

# registry of runnable specs (sealed configurations only)
SPECS = {
    FACTOR_SPEC_V1.version: FACTOR_SPEC_V1,
    FACTOR_SPEC_REAL_D1.version: FACTOR_SPEC_REAL_D1,
}


def _default_experiment_id() -> str:
    return "factor-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.discovery.factor.run",
        description="Run an Alpha101 Factor Discovery experiment.",
    )
    parser.add_argument("--experiment-id", default=None,
                        help="Unique experiment id (default: timestamp).")
    parser.add_argument("--spec", default=FACTOR_SPEC_V1.version,
                        choices=sorted(SPECS),
                        help="Sealed spec version to run (default: "
                             "factor-discovery-v1 on synthetic 1H data).")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Number of worker processes (default: 1).")
    parser.add_argument("--limit-alphas", type=int, default=None,
                        help="Limit the number of alphas (smoke tests).")
    parser.add_argument("--assets", nargs="+", default=None,
                        help="Restrict the universe (e.g. --assets NVDA SPY).")
    parser.add_argument("--data-root", type=Path, default=None,
                        help="Path to the processed CSV data directory.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Report output directory.")
    parser.add_argument("--strategy-report", type=Path, default=None,
                        help="Strategy discovery report.json used for the "
                             "convergence table (default: output/lab-v1).")
    args = parser.parse_args(argv)

    experiment_id = args.experiment_id or _default_experiment_id()
    spec = SPECS[args.spec]
    print(f"[factor] experiment_id={experiment_id} spec={spec.version} "
          f"jobs={args.jobs} limit_alphas={args.limit_alphas} "
          f"assets={args.assets}")

    engine = FactorDiscoveryEngine(
        spec=spec,
        data_root=args.data_root,
        jobs=args.jobs,
    )

    result = engine.run_experiment(
        experiment_id,
        limit_alphas=args.limit_alphas,
        assets=args.assets,
    )

    report = FactorReport(output_dir=args.output_dir, spec=engine.spec)
    json_path, md_path = report.save(
        report.build(result, strategy_report_path=args.strategy_report),
        result.experiment_id)

    _print_summary(result)
    print(f"[factor] report: {md_path}")
    print(f"[factor] json:   {json_path}")
    return 0


def _print_summary(result) -> None:
    f = result.to_dict()["funnel"]
    print()
    print("=" * 68)
    print("Factor Discovery Gate v1 Funnel")
    print("=" * 68)
    for k, v in f.items():
        print(f"  {k:24s} {v}")
    print("-" * 68)
    for r in result.ranked_pairs[:10]:
        print(f"  {r['alpha_id']} {r['asset']:10s} "
              f"score={r['score']:.4f} icir={r['oos_icir']}")
    print("=" * 68)


if __name__ == "__main__":
    sys.exit(main())

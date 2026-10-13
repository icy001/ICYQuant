#!/usr/bin/env python3
"""v9 Script 3: Final Verification.

Cross-script interface check, snapshot consistency re-check, acceptance
re-evaluation, final PASS/FAIL report. Read-only with respect to source data
(may write only to artifacts/histdata_v9/verify/).

Inputs:
  --output-dir DIR     artifacts dir (default: artifacts/histdata_v9)
  --repo-root DIR      Git repo root (default: discover by walking up from out_dir)

Outputs:
  verify/interface_check.json     inter-script paths and hash format check
  verify/coverage_audit.json      14-item coverage re-audit
  verify/final_report.json        overall PASS/FAIL with component breakdown

Exit codes:
  0  Overall PASS
  1  Output dir missing
  7  Overall FAIL
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_OUTPUT_DIR = "artifacts/histdata_v9"


def emit(ev: dict) -> None:
    print(json.dumps(ev, ensure_ascii=False, sort_keys=True), flush=True)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_any(p: Path) -> Any:
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    # Strip leading '#'-only comment lines.
    lines = text.splitlines()
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    text = "\n".join(lines)
    # Try JSON first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to YAML if PyYAML is available.
    if HAS_YAML:
        return yaml.safe_load(text)
    return None


def discover_repo_root(start: Path) -> str:
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / ".git").exists():
            return str(cur)
        cur = cur.parent
    return str(start)


def check_interfaces(out_dir: Path) -> dict:
    """Verify inter-script paths resolve and hash formats are valid."""
    manifest = load_any(out_dir / "manifest.yaml")
    if manifest is None:
        return {"ok": False, "reason": "manifest_missing", "issues": []}
    issues: list[dict] = []

    for category, paths in manifest.get("outputs", {}).items():
        # Script 3 produces the 'verify/' category; skip it here to avoid
        # self-reference false-positive on the first run.
        if category == "verify":
            continue
        for p in paths:
            if not Path(p).exists():
                issues.append({"kind": "missing_output", "category": category,
                               "path": p})

    csv_hashes = load_any(out_dir / "snapshot" / "csv_hashes.json") or {}
    for p, h in csv_hashes.items():
        if not (isinstance(h, str) and len(h) == 64
                and all(c in "0123456789abcdef" for c in h)):
            issues.append({"kind": "bad_hash_format", "path": p, "hash": h})

    schema = load_any(out_dir / "schema.json")
    if not schema or "Bar" not in schema.get("definitions", {}):
        issues.append({"kind": "missing_schema_def", "def": "Bar"})
    if not schema or "ErrorRecord" not in schema.get("definitions", {}):
        issues.append({"kind": "missing_schema_def", "def": "ErrorRecord"})

    ledger = load_any(out_dir / "ledger.json")
    n_entries = len(ledger.get("entries", [])) if ledger else 0
    if n_entries != 4:
        issues.append({"kind": "bad_ledger_entry_count",
                       "expected": 4, "actual": n_entries})

    quality = load_any(out_dir / "quality_contract.yaml") or load_any(
        out_dir / "quality_contract.json")
    if not quality or quality.get("denominator") != 14:
        issues.append({"kind": "bad_quality_denominator",
                       "expected": 14,
                       "actual": (quality or {}).get("denominator")})
    elif len(quality.get("acceptance_items", [])) != 14:
        issues.append({"kind": "bad_quality_item_count",
                       "expected": 14,
                       "actual": len(quality.get("acceptance_items", []))})

    return {
        "ok": not issues,
        "issues": issues,
        "checked_paths": sum(len(v) for v in manifest.get("outputs", {}).values()),
        "checked_hashes": len(csv_hashes),
    }


def check_snapshot_consistency(out_dir: Path, repo_root: str) -> dict:
    snap = load_any(out_dir / "snapshot" / "baseline.json")
    csv_hashes = load_any(out_dir / "snapshot" / "csv_hashes.json") or {}
    if not snap or not csv_hashes:
        return {"ok": False, "reason": "snapshot_missing"}
    actual = {p: sha256_file(Path(repo_root) / p) for p in csv_hashes}
    diffs = {p: {"expected": csv_hashes[p], "actual": actual[p]}
             for p in csv_hashes if actual[p] != csv_hashes[p]}

    proc = subprocess.run(["git", "rev-parse", "HEAD"],
                          cwd=repo_root, capture_output=True, text=True)
    head_now = proc.stdout.strip() if proc.returncode == 0 else None
    head_snap = snap.get("git", {}).get("commit")
    head_drift = head_now != head_snap

    return {
        "ok": not diffs and not head_drift,
        "csv_diffs": diffs,
        "git_head_snap": head_snap,
        "git_head_now": head_now,
        "head_drift": head_drift,
    }


def recheck_acceptance(out_dir: Path) -> dict:
    acc = load_any(out_dir / "acceptance" / "run_acceptance.json")
    if not acc:
        return {"ok": False, "reason": "acceptance_missing"}
    items = acc.get("items", [])
    expected = {f"G{i:02d}" for i in range(1, 11)} | {f"K{i:02d}" for i in range(1, 5)}
    found = {it.get("id") for it in items}
    missing = sorted(expected - found)
    return {
        "ok": not missing and acc.get("denominator") == 14,
        "denominator_claimed": acc.get("denominator"),
        "denominator_actual": len(items),
        "missing": missing,
        "pass_count": acc.get("pass_count"),
        "fail_count": acc.get("fail_count"),
        "overall_claimed": acc.get("overall"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v9 Script 3: Verify")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--repo-root", default=None)
    args = parser.parse_args(argv)

    emit({"event": "start", "script": "03_verify",
          "ts": datetime.now(timezone.utc).isoformat()})

    out_dir = Path(args.output_dir)
    if not out_dir.exists():
        emit({"event": "fatal", "code": "output_dir_missing",
              "path": str(out_dir)})
        return 1
    (out_dir / "verify").mkdir(parents=True, exist_ok=True)

    # 1) Interface check
    iface = check_interfaces(out_dir)
    emit({"event": "interface_check_done", "ok": iface["ok"],
          "issues": iface.get("issues", []),
          "checked_paths": iface.get("checked_paths", 0),
          "checked_hashes": iface.get("checked_hashes", 0)})
    (out_dir / "verify" / "interface_check.json").write_text(
        json.dumps(iface, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )

    # 2) Snapshot consistency
    repo_root = args.repo_root or discover_repo_root(out_dir)
    snap = check_snapshot_consistency(out_dir, repo_root)
    emit({"event": "snapshot_check_done", "ok": snap["ok"],
          "csv_diffs": snap.get("csv_diffs", {}),
          "head_drift": snap.get("head_drift", False)})

    # 3) Re-check acceptance
    acc = recheck_acceptance(out_dir)
    emit({"event": "acceptance_recheck", "ok": acc["ok"],
          "denominator_claimed": acc.get("denominator_claimed"),
          "denominator_actual": acc.get("denominator_actual"),
          "missing": acc.get("missing", []),
          "overall_claimed": acc.get("overall_claimed")})

    # 4) Coverage audit
    cov = load_any(out_dir / "acceptance" / "coverage_audit.json") or {}
    emit({"event": "coverage_audit", "complete": cov.get("complete", False),
          "missing": cov.get("missing", [])})
    (out_dir / "verify" / "coverage_audit.json").write_text(
        json.dumps(cov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )

    # 5) Final report
    overall = (iface["ok"] and snap["ok"] and acc["ok"]
               and cov.get("complete", False))
    final = {
        "schema_version": "histdata_v9_final_report_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": "PASS" if overall else "FAIL",
        "components": {
            "interfaces": iface["ok"],
            "snapshot": snap["ok"],
            "acceptance": acc["ok"],
            "coverage": cov.get("complete", False),
        },
        "details": {
            "interfaces": iface,
            "snapshot": snap,
            "acceptance": acc,
            "coverage": cov,
        },
    }
    final_path = out_dir / "verify" / "final_report.json"
    final_path.write_text(
        json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    emit({"event": "end", "ok": overall, "exit_code": 0 if overall else 7,
          "overall": final["overall"]})
    return 0 if overall else 7


if __name__ == "__main__":
    sys.exit(main())

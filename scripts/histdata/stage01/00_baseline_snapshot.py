#!/usr/bin/env python3
"""v9 Script 0: Baseline Snapshot.

Captures pre-execution state for reproducibility and downstream verification.
Hard-gates on the 3 baseline CSVs being TRACKED in git
(`git ls-files --error-unmatch`); aborts with exit 2 if any is NOT_TRACKED.

Inputs:
  --input-dir DIR         Raw histdata M1 dir (default: data/real/histdata/XAUUSD_M1)
  --output-dir DIR        Snapshot output dir (default: artifacts/histdata_v9/snapshot)
  --baseline PATH [PATH]  Baseline CSVs to lock (default: 3 factor discovery outputs)
  --repo-root DIR         Git repo root (default: discover from CWD)

Outputs:
  <output-dir>/baseline.json      git head, branch, dirty, baselines status, etc.
  <output-dir>/csv_hashes.json    {path: sha256} for each TRACKED baseline CSV
  <output-dir>/env.json           python version + tracked package versions

Streaming stats (stdout, JSON Lines):
  {"event": "start"|"git_head"|"csv_check"|"csv_hashed"|"env_captured"|"fatal"|"end", ...}

Exit codes:
  0  Success
  2  One or more baseline CSVs NOT_TRACKED (or missing on disk)
  4  Git unavailable / no .git found
  5  Output dir not writable
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Default 3 baseline CSVs (research/discovery outputs that must NOT be perturbed).
# These are the gates Script 0 enforces; if any is NOT_TRACKED, the whole v9 aborts.
DEFAULT_BASELINES = [
    "research/discovery/output/factor-paper-d1/summary.csv",
    "research/discovery/output/factor-v1/csv/alpha_ranking.csv",
    "research/discovery/output/factor-v1/csv/convergence.csv",
]
DEFAULT_INPUT_DIR = "data/real/histdata/XAUUSD_M1"
DEFAULT_OUTPUT_DIR = "artifacts/histdata_v9/snapshot"
TRACKED_PACKAGES = ["pandas", "numpy", "pyarrow", "pyyaml", "jsonschema"]


def emit(event: dict) -> None:
    """Print a JSON Lines event to stdout (streaming stats CLI contract)."""
    print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)


def run_git(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def is_tracked(path: str, repo_root: str) -> bool:
    """True iff `git ls-files --error-unmatch <path>` exits 0."""
    rc, _, _ = run_git(["ls-files", "--error-unmatch", "--", path], cwd=repo_root)
    return rc == 0


def get_git_head(repo_root: str) -> dict:
    rc, out, _ = run_git(["rev-parse", "HEAD"], cwd=repo_root)
    if rc != 0:
        raise RuntimeError(f"git rev-parse HEAD failed in {repo_root}")
    commit = out.strip()
    rc, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    branch = out.strip() if rc == 0 else "DETACHED"
    rc, out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    dirty = bool(out.strip())
    return {"commit": commit, "branch": branch, "dirty": dirty}


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_env() -> dict:
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "packages": {},
    }
    # pip package name -> importable module name
    import_names = {"pandas": "pandas", "numpy": "numpy", "pyarrow": "pyarrow",
                    "pyyaml": "yaml", "jsonschema": "jsonschema"}
    for pkg in TRACKED_PACKAGES:
        try:
            mod = __import__(import_names.get(pkg, pkg))
            env["packages"][pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            env["packages"][pkg] = "missing"
    return env


def discover_repo_root(start: str) -> str:
    p = Path(start).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return str(cand)
    raise RuntimeError(f"No .git found above {start}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v9 Script 0: Baseline Snapshot")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--baseline", nargs="*", default=DEFAULT_BASELINES)
    parser.add_argument("--repo-root", default=None)
    args = parser.parse_args(argv)

    emit({"event": "start", "script": "00_baseline_snapshot",
          "ts": datetime.now(timezone.utc).isoformat(),
          "input_dir": args.input_dir, "output_dir": args.output_dir,
          "baselines": args.baseline})

    in_dir = Path(args.input_dir)
    if not in_dir.exists():
        emit({"event": "warn", "code": "input_dir_missing", "path": str(in_dir)})
    else:
        n_csv = sum(1 for _ in in_dir.rglob("*.csv"))
        emit({"event": "input_scanned", "path": str(in_dir), "csv_count": n_csv})

    try:
        repo_root = args.repo_root or discover_repo_root(os.getcwd())
    except RuntimeError as e:
        emit({"event": "fatal", "code": "no_git_repo", "msg": str(e)})
        return 4
    emit({"event": "repo_root", "path": repo_root})

    try:
        head = get_git_head(repo_root)
        emit({"event": "git_head", **head})
    except RuntimeError as e:
        emit({"event": "fatal", "code": "git_head_failed", "msg": str(e)})
        return 4

    # HARD gate: every baseline CSV must be TRACKED.
    tracked_status: dict[str, str] = {}
    any_untracked = False
    for csv_path in args.baseline:
        tracked = is_tracked(csv_path, repo_root)
        tracked_status[csv_path] = "TRACKED" if tracked else "NOT_TRACKED"
        emit({"event": "csv_check", "path": csv_path,
              "status": tracked_status[csv_path]})
        if not tracked:
            any_untracked = True

    if any_untracked:
        emit({"event": "fatal", "code": "baseline_not_tracked",
              "msg": "One or more baseline CSVs are NOT_TRACKED; v9 aborts.",
              "details": tracked_status})
        return 2

    # Hash only after TRACKED gate passes.
    csv_hashes: dict[str, str] = {}
    for csv_path in args.baseline:
        full = Path(repo_root) / csv_path
        if not full.exists():
            emit({"event": "fatal", "code": "baseline_missing_on_disk",
                  "path": csv_path, "msg": "TRACKED but file missing on disk."})
            return 2
        h = hash_file(full)
        csv_hashes[csv_path] = h
        emit({"event": "csv_hashed", "path": csv_path, "sha256": h})

    env = capture_env()
    emit({"event": "env_captured",
          "python": env["python"],
          "packages": env["packages"]})

    out_dir = Path(args.output_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        emit({"event": "fatal", "code": "output_dir_unwritable",
              "path": str(out_dir), "msg": str(e)})
        return 5

    baseline_record = {
        "schema_version": "histdata_v9_baseline_v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git": head,
        "baselines": tracked_status,
        "input_dir": str(in_dir),
        "input_dir_exists": in_dir.exists(),
        "repo_root": repo_root,
    }
    (out_dir / "baseline.json").write_text(
        json.dumps(baseline_record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "csv_hashes.json").write_text(
        json.dumps(csv_hashes, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "env.json").write_text(
        json.dumps(env, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    emit({"event": "end", "ok": True, "exit_code": 0,
          "outputs": ["baseline.json", "csv_hashes.json", "env.json"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())

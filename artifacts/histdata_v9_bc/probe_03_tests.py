#!/usr/bin/env python3
"""Drift probes for scripts/histdata/tests/test_verify_crossref.py (B+C step 2).

Copies scripts/histdata into a temp tree, injects one defect into 03_verify.py,
and re-runs the new test file there. A probe is CAUGHT when the suite fails in
the copy; a probe that still passes means the test is decorative.

Usage: python3 artifacts/histdata_v9_bc/probe_03_tests.py
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SUITE = "test_verify_crossref.py"

PARSED_REF_OUTSIDE = '    else:\n        return None, "parsed_ref_outside_parsed_dir"'

# label -> tuple of (anchor, replacement) applied to 03_verify.py
PROBES = (
    ("traversal accepted (dot-dot guard removed)", (
        ('if any(segment in (".", "..") for segment in segments):', "if False:"),
    )),
    ("wrong prefix accepted (string comparison instead of a walk)", (
        (PARSED_REF_OUTSIDE,
         '    else:\n        relative = token'),
        ("    if segments[0] != PARSED_DIR_SEGMENT:", "    if False:"),
    )),
    ("audit unwired from check_interfaces", (
        ('    issues.extend(refs["issues"])', "    pass"),
    )),
    ("scan limited to a known field instead of the whole document", (
        ("        for pointer, text in iter_strings(document):",
         "        for pointer, text in iter_strings(document.get("
         "\"entries\", []) if isinstance(document, dict) else []):"),
    )),
    ("missing target folded into a pass", (
        ("                elif key not in declared:", "                elif False:"),
    )),
    ("empty-token reason folded into outside-parsed-dir", (
        ('    if not token:\n        return None, "parsed_ref_empty"\n', ""),
    )),
)


def run(cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover",
         "-s", "scripts/histdata/tests", "-t", "scripts/histdata/tests",
         "-p", SUITE],
        cwd=cwd, capture_output=True, text=True)


def main() -> int:
    missed = 0
    for label, edits in PROBES:
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            shutil.copytree(ROOT / "scripts" / "histdata",
                            tmp / "scripts" / "histdata",
                            ignore=shutil.ignore_patterns("__pycache__"))
            target = tmp / "scripts" / "histdata" / "stage01" / "03_verify.py"
            source = target.read_text(encoding="utf-8")
            missing = [old for old, _ in edits if old not in source]
            if missing:
                print(f"SKIP   {label}: anchor not found: {missing[0]!r}")
                missed += 1
                continue
            for old, new in edits:
                source = source.replace(old, new, 1)
            target.write_text(source, encoding="utf-8")
            result = run(tmp)
            tail = (result.stderr.strip().splitlines() or ["<no output>"])[-1]
            caught = result.returncode != 0
            print(f"{'CAUGHT' if caught else 'MISSED'} {label} -> {tail}")
            if not caught:
                missed += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    control = run(ROOT)
    control_ok = control.returncode == 0
    print(f"{'OK' if control_ok else 'BROKEN'} control (unmutated tree) -> "
          f"{(control.stderr.strip().splitlines() or ['<no output>'])[-1]}")
    if not control_ok:
        missed += 1
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())

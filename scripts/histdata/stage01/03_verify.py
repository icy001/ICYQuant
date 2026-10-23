#!/usr/bin/env python3
"""v9 Script 3: Final Verification.

Cross-script interface check, snapshot consistency re-check, acceptance
re-evaluation, final PASS/FAIL report. Read-only with respect to source data
(may write only to artifacts/histdata_v9/verify/).

The interface check carries a second, INDEPENDENT claim: every `parsed/...`
reference in ledger.json and validation_gates.yaml must resolve to a parsed
output that manifest.yaml declares. Script 1 checks that relation too, but
Script 1 is the producer of those documents -- a document edited after the fact,
or written by some other process, satisfies Script 1 just as well. This script
re-derives the authority set from manifest.yaml and does NOT import Script 1's
crossref_report(): one implementation shared by producer and verifier would
share its blind spots and let the same defect pass both.

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
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

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


# ---------------------------------------------------------------------------
# Independent parsed-reference audit.
#
# The documents address parsed outputs relative to the artifacts dir
# ("parsed/<pair>_<year>_bars.parquet") while manifest.yaml declares them
# relative to the repository root ("artifacts/histdata_v9/parsed/..."). Both
# forms are accepted, but only after lexical normalization that refuses to leave
# the artifacts dir: a token such as "parsed/../../secrets.json" must not be
# waved through by a string-prefix test, and a token that merely looks like a
# parsed path ("backup/parsed/x.parquet") must not resolve either.
# ---------------------------------------------------------------------------

PARSED_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\\-]+")
PARSED_DIR_SEGMENT = "parsed"


def iter_strings(obj: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    """Yield (json_pointer, text) for every string in a loaded document.

    The audit walks the whole document instead of a list of known fields: a
    reference tucked into a field nobody thought to scan is still a reference.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from iter_strings(value, f"{pointer}/{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from iter_strings(value, f"{pointer}/{index}")
    elif isinstance(obj, str):
        yield pointer, obj


def parsed_reference_tokens(text: str) -> list[str]:
    """The parsed references in one string, in order of appearance.

    A candidate is a path-like token with `parsed` as a DIRECTORY segment, i.e.
    something is named below it. The bare word `parsed` -- as in the gate text
    "manifest.yaml has outputs.{snapshot,contract,parsed,acceptance,verify}" --
    names no file and is therefore not a reference.

    Both separators count when deciding what looks like a reference, so a
    backslash path is seen and then refused by resolve_parsed_reference() as
    non-canonical instead of slipping past unnoticed.
    """
    return [token for token in PARSED_PATH_TOKEN_RE.findall(text)
            if PARSED_DIR_SEGMENT in token.replace("\\", "/").split("/")[:-1]]


def declared_parsed_refs(manifest: dict, out_dir: str) -> set[str]:
    """The parsed references manifest.yaml authorises, as artifacts-dir-relative
    keys -- the form the ledger and the gates use.

    A manifest path inside the artifacts dir is keyed by what follows that dir; a
    path outside it is keyed by its tail from the `parsed` segment, so an
    absolute --output-dir and a relative one still describe the same files.
    """
    root = out_dir.strip("/")
    prefix = f"{root}/" if root else ""
    declared: set[str] = set()
    for raw in (manifest.get("outputs") or {}).get(PARSED_DIR_SEGMENT) or []:
        token = str(raw).strip()
        if prefix and token.startswith(prefix):
            declared.add(token[len(prefix):])
            continue
        segments = token.split("/")
        if PARSED_DIR_SEGMENT in segments[:-1]:
            declared.add("/".join(segments[segments.index(PARSED_DIR_SEGMENT):]))
    return declared


def resolve_parsed_reference(raw: str, out_dir: str) -> tuple[str | None, str | None]:
    """Resolve one parsed reference into its artifacts-dir-relative key.

    Returns (key, None) when the reference is canonical, and (None, reason) when
    it is not. The reason codes are stable and end up verbatim in
    verify/interface_check.json.
    """
    token = raw.strip()
    if not token:
        return None, "parsed_ref_empty"
    if "\\" in token:
        # Only forward slashes are canonical; no platform-dependent reading.
        return None, "parsed_ref_not_canonical"
    if token.startswith("/") or (len(token) > 1 and token[1] == ":"):
        return None, "parsed_ref_absolute"

    root = out_dir.strip("/")
    root_parts = [part for part in root.split("/") if part not in ("", ".")]
    prefix = f"{root}/" if root else ""
    if prefix and token.startswith(prefix):
        relative = token[len(prefix):]
    elif token.startswith(f"{PARSED_DIR_SEGMENT}/"):
        relative = token
    else:
        return None, "parsed_ref_outside_parsed_dir"

    segments = relative.split("/")
    if segments[0] != PARSED_DIR_SEGMENT:
        # A path with the parsed dir somewhere in the middle is not a parsed
        # reference: it points at something else and only looks similar.
        return None, "parsed_ref_outside_parsed_dir"
    if any(segment == "" for segment in segments):
        return None, "parsed_ref_not_canonical"
    if any(segment in (".", "..") for segment in segments):
        # `.`/`..` never appear in a canonical reference, and a detour is judged
        # by walking the path, not by comparing prefixes: a reference that
        # climbs out of the artifacts dir is an escape, one that stays inside is
        # still not canonical. Neither is accepted.
        depth = len(root_parts)
        for segment in segments:
            depth += -1 if segment == ".." else (0 if segment == "." else 1)
            if depth < len(root_parts):
                return None, "parsed_ref_escapes_root"
        return None, "parsed_ref_not_canonical"
    return relative, None


def audit_parsed_references(manifest: dict, documents: dict, out_dir: str) -> dict:
    """Every parsed reference in `documents` must resolve to a manifest output.

    Pure function over loaded documents, so the tests can feed it the documents
    Script 1 really emits as well as deliberately tampered ones. `documents` maps
    a display name (the file name as the operator sees it) to the loaded object.
    """
    declared = declared_parsed_refs(manifest, out_dir)
    issues: list[dict] = []
    counts: dict[tuple[str, str], int] = {}
    for name, document in documents.items():
        cited = 0
        for pointer, text in iter_strings(document):
            for raw in parsed_reference_tokens(text):
                cited += 1
                counts[(name, raw)] = counts.get((name, raw), 0) + 1
                key, reason = resolve_parsed_reference(raw, out_dir)
                if reason is not None:
                    issues.append({"kind": reason, "file": name,
                                   "pointer": pointer, "reference": raw,
                                   "missing_target": None})
                elif key not in declared:
                    # Well formed, but it names a file this run never declared:
                    # another run's output, or a stale name.
                    issues.append({"kind": "parsed_ref_missing_target",
                                   "file": name, "pointer": pointer,
                                   "reference": raw, "missing_target": key})
        if not cited:
            # Deleting the reference must not be a way to pass the check.
            issues.append({"kind": "parsed_refs_absent", "file": name,
                           "pointer": "", "reference": None,
                           "missing_target": None})
    duplicates = sorted(f"{name}:{ref}" for (name, ref), count in counts.items()
                        if count > 1)
    return {
        "ok": not issues,
        "issues": issues,
        "declared": sorted(declared),
        "references": sorted({ref for _, ref in counts}),
        "duplicates": duplicates,
    }


def check_interfaces(out_dir: Path) -> dict:
    """Verify inter-script paths resolve, hash formats are valid, and every
    parsed reference in the ledger and the gates is one the manifest declares."""
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

    # Independent parsed-reference audit. Documents that did not load are left to
    # the manifest check above, which already reports every declared output that
    # is missing from disk.
    gates = load_any(out_dir / "validation_gates.yaml") or load_any(
        out_dir / "validation_gates.json")
    documents = {name: doc for name, doc in
                 (("ledger.json", ledger), ("validation_gates.yaml", gates))
                 if doc is not None}
    refs = audit_parsed_references(manifest, documents, str(out_dir))
    issues.extend(refs["issues"])

    return {
        "ok": not issues,
        "issues": issues,
        "checked_paths": sum(len(v) for v in manifest.get("outputs", {}).values()),
        "checked_hashes": len(csv_hashes),
        "parsed_refs": {
            "declared": refs["declared"],
            "references": refs["references"],
            "duplicates": refs["duplicates"],
        },
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
    refs = iface.get("parsed_refs", {})
    emit({"event": "interface_check_done", "ok": iface["ok"],
          "issues": iface.get("issues", []),
          "checked_paths": iface.get("checked_paths", 0),
          "checked_hashes": iface.get("checked_hashes", 0),
          "parsed_refs_declared": len(refs.get("declared", [])),
          "parsed_refs_cited": refs.get("references", []),
          "parsed_ref_duplicates": refs.get("duplicates", [])})
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

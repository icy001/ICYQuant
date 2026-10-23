#!/usr/bin/env python3
"""v9 Script 1: Generate Artifacts.

Pure configuration generation. Reads Script 0's baseline.json and produces the
contract layer that Scripts 2 and 3 read:
  - manifest.yaml            file inventory (inputs, outputs, scripts, baselines)
  - schema.json              JSON Schema for Bar and ErrorRecord
  - ledger.json              operational ledger (who-did-what-when)
  - quality_contract.yaml    14 acceptance items (G01-G10, K01-K04)
  - validation_gates.yaml    pre/post conditions for each script

Everything Scripts 2/3 can cross-check is DERIVED from one authority, never
retyped here:

  ACCEPTANCE_ITEMS       -> item ids, denominator, pass_rule wording
  SCRIPTS                -> ledger entries, gate targets, gate counts
  --pair / --year        -> manifest.outputs.parsed, ledger produces, gate post
  baseline["baselines"]  -> snapshot csv count, gate baseline-count wording
  CONTRACT_VERSION       -> quality_contract.version (shared freeze, 9.1)

A change of parameters therefore cannot leave "xauusd_2024" or "14" behind in a
document that describes another run, and crossref_report() fails the run when two
of the four documents disagree about a reference or a count.

After assembling the contract, 01 re-validates that object with the shared
guards (`contract_guard` / `contract_items_guard`). Per the frozen reachability
contract those call sites cannot fire here -- the version is the one 01 just
wrote and the denominator is derived from the item list -- so a failure means the
builder itself is broken. Such an id is deliberately absent from EXIT_MAP_01, so
the shared wrapper reports E_EXIT_MAP_MISSING and falls back to 4.

Inputs:
  --baseline PATH      Path to Script 0's baseline.json
  --output-dir DIR     Contract output dir (default: artifacts/histdata_v9)
  --pair LABEL         Pair label for parsed output filenames (default: xauusd)
  --year LABEL         Year label for parsed output filenames (default: 2024)
  --repo-root DIR      Root the output dir must stay inside (default: nearest .git)

Exit codes (unchanged by this work):
  0  Success
  1  Baseline missing or malformed
  4  Output dir outside the repo, self-check failure, or cross-reference broken
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# `_g11_common` is standard-library-only by policy, so importing it cannot add a
# pandas / pyarrow / PyYAML dependency here. It is the authority for the contract
# version, and the tests assert the emitted document carries exactly that value.
_STAGE_DIR = str(Path(__file__).resolve().parent)
if _STAGE_DIR not in sys.path:
    sys.path.insert(0, _STAGE_DIR)
from _g11_common import (  # noqa: E402
    CONTRACT_VERSION,
    ContractError,
    contract_guard,
    contract_items_guard,
    fatal_from_error,
    repo_relative,
)

DEFAULT_BASELINE = "artifacts/histdata_v9/snapshot/baseline.json"
DEFAULT_OUTPUT_DIR = "artifacts/histdata_v9"

SCRIPTS = [
    {"id": "00", "name": "00_baseline_snapshot.py", "role": "snapshot", "stage": "01"},
    {"id": "01", "name": "01_generate_artifacts.py", "role": "generate", "stage": "01"},
    {"id": "02", "name": "02_execute.py", "role": "execute", "stage": "01"},
    {"id": "03", "name": "03_verify.py", "role": "verify", "stage": "01"},
]

# ---------------------------------------------------------------------------
# Derived authorities. Every count and reference in the four emitted documents
# comes from here, so the documents cannot disagree with each other or with the
# parameters of the run that produced them.
# ---------------------------------------------------------------------------

# Script file name -> stem ("02_execute.py" -> "02_execute"). Ledger entries and
# gate targets are keyed by the stem.
SCRIPT_STEMS: tuple[str, ...] = tuple(Path(s["name"]).stem for s in SCRIPTS)
LEDGER_ENTRY_COUNT: int = len(SCRIPTS)   # one ledger entry per script
GATE_COUNT: int = len(SCRIPTS)           # one validation gate per script

# Key into `_g11_common`'s per-script exit maps, and the contract keys Scripts 2/3
# read -- the self-check enforces them on the object 01 just assembled.
SCRIPT_NAME = "01_generate_artifacts"
QUALITY_CONTRACT_REQUIRED_KEYS = ("acceptance_items", "denominator", "version")


def discover_repo_root(start: Path) -> Path:
    """Nearest ancestor holding .git, else `start` itself, so the boundary check
    always compares against something concrete instead of guessing."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current

# The 14 acceptance items, single source of truth across Scripts 1/2/3.
ACCEPTANCE_ITEMS = [
    {"id": "G01", "kind": "data",
     "name": "raw_file_integrity",
     "desc": "Raw histdata CSV files are readable, non-empty.",
     "tolerance": {"min_files": 1}},
    {"id": "G02", "kind": "data",
     "name": "parsed_row_count",
     "desc": "rows_emitted + errors_emitted == total_lines (per file).",
     "tolerance": {"max_skipped_pct": 1.0}},
    {"id": "G03", "kind": "data",
     "name": "naive_timestamp_semantics",
     "desc": "Timestamps are naive (no tzinfo), ISO 8601, UTC-anchored.",
     "tolerance": {}},
    {"id": "G04", "kind": "data",
     "name": "no_future_timestamps",
     "desc": "max(ts) <= now_utc + 1 day (grace for clock skew).",
     "tolerance": {"future_grace_days": 1}},
    {"id": "G05", "kind": "data",
     "name": "monotonic_time_order",
     "desc": "Within each file, timestamps are non-decreasing.",
     "tolerance": {"allow_equal": True}},
    {"id": "G06", "kind": "data",
     "name": "ohlc_integrity",
     "desc": "H >= max(O,C) and L <= min(O,C) for every bar.",
     "tolerance": {"max_violation_pct": 0.0}},
    {"id": "G07", "kind": "data",
     "name": "non_negative_volume",
     "desc": "Volume >= 0 for every bar.",
     "tolerance": {"max_negative_pct": 0.0}},
    {"id": "G08", "kind": "data",
     "name": "no_duplicate_timestamps",
     "desc": "No two rows share the same (ts) within a file.",
     "tolerance": {"max_dup_pct": 0.0}},
    {"id": "G09", "kind": "data",
     "name": "error_record_emitted",
     "desc": "Malformed rows produce ErrorRecord with {file, line, code, raw_excerpt}.",
     "tolerance": {}},
    {"id": "G10", "kind": "data",
     "name": "parquet_roundtrip",
     "desc": "Read-back parquet matches in-memory bars (rows + required columns).",
     "tolerance": {"dtypes_strict": False}},
    {"id": "K01", "kind": "process",
     "name": "streaming_stats_cli",
     "desc": "Script 02 emits per-file JSON Lines to stdout as it processes.",
     "tolerance": {"min_events_per_file": 2}},
    {"id": "K02", "kind": "process",
     "name": "quality_contract_bounds",
     "desc": "Error rate <= 0.01 AND completeness >= 0.99.",
     "tolerance": {"max_error_rate": 0.01, "min_completeness": 0.99}},
    {"id": "K03", "kind": "process",
     "name": "snapshot_csv_immutability",
     "desc": "Baseline CSVs SHA-256 match Script 0's csv_hashes.json.",
     "tolerance": {"hash_algorithm": "sha256", "strict": True}},
    {"id": "K04", "kind": "process",
     "name": "manifest_path_resolution",
     "desc": "Every path in manifest.yaml exists or has explicit 'generated_by' parent.",
     "tolerance": {"allow_generated_by": True}},
]

# Derived from the list above, never retyped. The order is part of the contract,
# so the ids stay a tuple and are compared element-wise.
ACCEPTANCE_ITEM_IDS: tuple[str, ...] = tuple(item["id"] for item in ACCEPTANCE_ITEMS)
ACCEPTANCE_DENOMINATOR: int = len(ACCEPTANCE_ITEMS)

# Cross-document reference scanners. The gate pre/post fields are prose for a
# human reader, so the only way to prove they still speak about THIS run is to
# read the references and counts back out of them and compare against the
# objects that were actually built.
REF_PARSED_RE = re.compile(r"parsed/([A-Za-z0-9_.\-]+)")
REF_COUNT_RE = re.compile(r"(\S+) has (\d+) (entries|items|gates|results)")
REF_RATIO_RE = re.compile(r"(\d+)/(\d+) items re-evaluated")
REF_BASELINE_COUNT_RE = re.compile(r"all (\d+) baseline CSVs TRACKED")


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)


def fatal(err: ContractError) -> int:
    """Emit the wrapper's fatal event and return its mapped exit code.

    `fatal_from_error` is the shared wrapper tail: it maps a semantic id onto a
    code this script ALREADY used before this work, and when the id has no entry
    -- the deliberate case for 01's self-check ids -- it reports
    E_EXIT_MAP_MISSING and falls back to the script's contract-error code. Never 0.
    """
    event, code = fatal_from_error(SCRIPT_NAME, err)
    emit(event)
    return code


def build_manifest(baseline: dict, output_dir: str, pair: str = "xauusd",
                   year: str = "2024") -> dict:
    return {
        "schema_version": "histdata_v9_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": baseline.get("git", {}),
        "scripts": SCRIPTS,
        "inputs": [
            {"path": baseline.get("input_dir", ""),
             "kind": "raw_histdata_m1_dir",
             "glob": "**/*.csv",
             "required": False,
             "note": "May be absent if not yet downloaded; Script 02 will warn."},
        ],
        "baselines": [
            {"path": p, "kind": "research_discovery_output", "required_tracked": True}
            for p in baseline.get("baselines", {}).keys()
        ],
        "outputs": {
            "snapshot": [
                f"{output_dir}/snapshot/baseline.json",
                f"{output_dir}/snapshot/csv_hashes.json",
                f"{output_dir}/snapshot/env.json",
            ],
            "contract": [
                f"{output_dir}/manifest.yaml",
                f"{output_dir}/schema.json",
                f"{output_dir}/ledger.json",
                f"{output_dir}/quality_contract.yaml",
                f"{output_dir}/validation_gates.yaml",
            ],
            "parsed": [
                f"{output_dir}/parsed/{pair}_{year}_bars.parquet",
                f"{output_dir}/parsed/{pair}_{year}_errors.jsonl",
                f"{output_dir}/parsed/parse_stats.json",
            ],
            "acceptance": [
                f"{output_dir}/acceptance/run_acceptance.json",
                f"{output_dir}/acceptance/coverage_audit.json",
            ],
            "verify": [
                f"{output_dir}/verify/final_report.json",
                f"{output_dir}/verify/interface_check.json",
                f"{output_dir}/verify/coverage_audit.json",
            ],
        },
    }


def build_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "histdata_v9_bar_v1",
        "title": "HistData v9 Bar and ErrorRecord",
        "definitions": {
            "Bar": {
                "type": "object",
                "required": ["ts", "open", "high", "low", "close", "volume"],
                "properties": {
                    "ts": {"type": "string", "format": "date-time",
                           "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",
                           "description": "Naive UTC ISO 8601 (no tz suffix)."},
                    "open": {"type": "number", "exclusiveMinimum": 0},
                    "high": {"type": "number", "exclusiveMinimum": 0},
                    "low": {"type": "number", "exclusiveMinimum": 0},
                    "close": {"type": "number", "exclusiveMinimum": 0},
                    "volume": {"type": "number", "minimum": 0},
                    "source_file": {"type": "string"},
                    "source_line": {"type": "integer", "minimum": 1},
                },
            },
            "ErrorRecord": {
                "type": "object",
                "required": ["file", "line", "code", "raw_excerpt"],
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},
                    "code": {"type": "string", "enum": [
                        "BAD_FIELD_COUNT", "BAD_TIMESTAMP", "BAD_OHLC",
                        "BAD_VOLUME", "NEGATIVE_PRICE", "DUPLICATE_TS",
                        "OUT_OF_RANGE_PRICE", "ENCODING_ERROR",
                    ]},
                    "raw_excerpt": {"type": "string", "maxLength": 1024},
                    "detail": {"type": "string"},
                },
            },
        },
    }


def build_ledger(baseline: dict, pair: str, year: str) -> dict:
    """Operational ledger. Script names come from SCRIPTS (indices follow that
    order) and the parsed paths carry THIS run's --pair/--year, so a ledger can
    no longer describe another run's files."""
    return {
        "schema_version": "histdata_v9_ledger_v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git": baseline.get("git", {}),
        "entries": [
            {"seq": 0, "script": SCRIPT_STEMS[0], "action": "snapshot",
             "target": "git_head + env + baseline_csv_hashes",
             "precondition": "repo has .git",
             "produces": ["snapshot/baseline.json", "snapshot/csv_hashes.json",
                          "snapshot/env.json"]},
            {"seq": 1, "script": SCRIPT_STEMS[1], "action": "generate_contracts",
             "target": "manifest + schema + ledger + quality_contract + validation_gates",
             "precondition": "snapshot/baseline.json exists",
             "produces": ["manifest.yaml", "schema.json", "ledger.json",
                          "quality_contract.yaml", "validation_gates.yaml"]},
            {"seq": 2, "script": SCRIPT_STEMS[2], "action": "parse_validate_accept",
             "target": "raw histdata -> bars.parquet + errors.jsonl + acceptance",
             "precondition": "contracts exist; raw dir present (warn-only if absent)",
             "produces": [f"parsed/{pair}_{year}_bars.parquet",
                          f"parsed/{pair}_{year}_errors.jsonl",
                          "parsed/parse_stats.json",
                          "acceptance/run_acceptance.json",
                          "acceptance/coverage_audit.json"]},
            {"seq": 3, "script": SCRIPT_STEMS[3], "action": "cross_check_finalize",
             "target": "all artifacts + interfaces + re-run acceptance",
             "precondition": "Scripts 00,01,02 completed",
             "produces": ["verify/final_report.json",
                          "verify/interface_check.json",
                          "verify/coverage_audit.json"]},
        ],
    }


def build_quality_contract() -> dict:
    """The quality contract. `version` carries the shared freeze from
    `_g11_common`; the item list and the denominator are the same authority, so
    they cannot drift apart. Scripts 2/3 keep reading `denominator` only, which
    is why adding `version` does not change their behaviour."""
    return {
        "schema_version": "histdata_v9_quality_contract_v1",
        "version": CONTRACT_VERSION,
        "acceptance_items": ACCEPTANCE_ITEMS,
        "denominator": ACCEPTANCE_DENOMINATOR,
        "pass_rule": (f"all {ACCEPTANCE_DENOMINATOR} items pass; "
                      f"any FAIL -> overall FAIL"),
    }


def build_validation_gates(baseline: dict, pair: str, year: str) -> dict:
    """Pre/post conditions per script. Every count and every parsed path in the
    post lists is derived, so another --pair/--year or another baseline set
    rewrites the prose instead of leaving a stale literal behind."""
    n_baselines = len(baseline.get("baselines", {}))
    bars = f"parsed/{pair}_{year}_bars.parquet"
    errors = f"parsed/{pair}_{year}_errors.jsonl"
    return {
        "schema_version": "histdata_v9_validation_gates_v1",
        "gates": [
            {"id": "G00_baseline_tracked", "applies_to": SCRIPT_STEMS[0],
             "pre": ["repo has .git", "raw input dir OR warn-only"],
             "post": [f"all {n_baselines} baseline CSVs TRACKED",
                      "snapshot/baseline.json exists",
                      f"snapshot/csv_hashes.json has {n_baselines} entries"],
             "failure_codes": {2: "baseline_not_tracked", 4: "git_unavailable"}},
            {"id": "G01_contracts_generated", "applies_to": SCRIPT_STEMS[1],
             "pre": ["snapshot/baseline.json exists"],
             "post": ["manifest.yaml has outputs.{snapshot,contract,parsed,acceptance,verify}",
                      "schema.json defines Bar + ErrorRecord",
                      f"ledger.json has {LEDGER_ENTRY_COUNT} entries",
                      f"quality_contract.yaml has {ACCEPTANCE_DENOMINATOR} items",
                      f"validation_gates.yaml has {GATE_COUNT} gates"],
             "failure_codes": {1: "baseline_missing"}},
            {"id": "G02_executed", "applies_to": SCRIPT_STEMS[2],
             "pre": ["manifest.yaml", "schema.json", "quality_contract.yaml exist"],
             "post": [f"{bars} non-empty (if raw available)",
                      f"{errors} exists",
                      "parsed/parse_stats.json has per-file stats",
                      f"acceptance/run_acceptance.json has {ACCEPTANCE_DENOMINATOR} results"],
             "failure_codes": {}},
            {"id": "G03_verified", "applies_to": SCRIPT_STEMS[3],
             "pre": ["all prior scripts' outputs present"],
             "post": ["verify/final_report.json: overall PASS/FAIL",
                      "verify/interface_check.json: all inter-script paths resolve",
                      f"verify/coverage_audit.json: {ACCEPTANCE_DENOMINATOR}/"
                      f"{ACCEPTANCE_DENOMINATOR} items re-evaluated"],
             "failure_codes": {}},
        ],
    }


def crossref_report(manifest: dict, schema: dict, ledger: dict, quality: dict,
                    gates: dict, n_baselines: int) -> dict:
    """Cross-check the four documents against each other and against the run's
    parameters. Pure function, so the tests can call it for both parameter sets
    and the checks cannot rot inside main().

    The gate pre/post fields are prose, so the references and counts are read
    back out of the text and compared with the objects that were actually built.
    Anything that cannot be found is a failure: a reference that disappeared must
    not pass as "nothing to check".
    """
    manifest_parsed = {Path(p).name for p in manifest["outputs"]["parsed"]}
    ledger_parsed = {Path(p).name for entry in ledger["entries"]
                     for p in entry["produces"] if p.startswith("parsed/")}

    gate_texts = [text for gate in gates["gates"]
                  for text in list(gate["pre"]) + list(gate["post"])]
    gate_parsed = {m for text in gate_texts for m in REF_PARSED_RE.findall(text)}
    gate_counts = {(target, unit): int(n) for text in gate_texts
                   for target, n, unit in REF_COUNT_RE.findall(text)}
    gate_baseline_counts = {int(n) for text in gate_texts
                            for n in REF_BASELINE_COUNT_RE.findall(text)}
    gate_ratios = {(int(a), int(b)) for text in gate_texts
                   for a, b in REF_RATIO_RE.findall(text)}

    item_ids = [item["id"] for item in quality["acceptance_items"]]
    checks = {
        # manifest / schema shape
        "manifest_outputs_in_subdirs": all(
            key in manifest["outputs"] for key in
            ("snapshot", "contract", "parsed", "acceptance", "verify")),
        "schema_defines_bar": "Bar" in schema["definitions"],
        "schema_defines_error_record": "ErrorRecord" in schema["definitions"],
        # quality contract: version frozen, items and denominator one authority
        "quality_version_is_frozen_version":
            quality.get("version") == CONTRACT_VERSION,
        "quality_item_ids_match_authority":
            item_ids == list(ACCEPTANCE_ITEM_IDS),
        "quality_denominator_matches_items":
            quality.get("denominator") == len(item_ids),
        "quality_pass_rule_names_denominator":
            str(len(item_ids)) in str(quality.get("pass_rule", "")),
        # ledger / gates enumerate exactly the scripts we know
        "ledger_scripts_match_scripts":
            [e["script"] for e in ledger["entries"]] == list(SCRIPT_STEMS),
        "gate_targets_match_scripts":
            [g["applies_to"] for g in gates["gates"]] == list(SCRIPT_STEMS),
        "ledger_entry_count_matches_scripts":
            len(ledger["entries"]) == LEDGER_ENTRY_COUNT,
        "gate_count_matches_scripts": len(gates["gates"]) == GATE_COUNT,
        # references spanning the documents
        "ledger_parsed_refs_resolve_to_manifest":
            bool(ledger_parsed) and ledger_parsed <= manifest_parsed,
        "gate_parsed_refs_resolve_to_manifest":
            bool(gate_parsed) and gate_parsed <= manifest_parsed,
        "gate_count_refs_match_objects":
            gate_counts.get(("ledger.json", "entries")) == len(ledger["entries"])
            and gate_counts.get(("quality_contract.yaml", "items")) == len(item_ids)
            and gate_counts.get(("validation_gates.yaml", "gates")) == len(gates["gates"])
            and gate_counts.get(("acceptance/run_acceptance.json", "results")) == len(item_ids)
            and gate_counts.get(("snapshot/csv_hashes.json", "entries")) == n_baselines,
        "gate_baseline_count_refs_match": gate_baseline_counts == {n_baselines},
        "gate_ratio_refs_match_items":
            gate_ratios == {(len(item_ids), len(item_ids))},
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "quality_version": quality.get("version"),
        "quality_denominator": quality.get("denominator"),
        "quality_item_ids": item_ids,
        "manifest_parsed": sorted(manifest_parsed),
        "ledger_parsed_refs": sorted(ledger_parsed),
        "gate_parsed_refs": sorted(gate_parsed),
        "ledger_entry_count": len(ledger["entries"]),
        "validation_gate_count": len(gates["gates"]),
        "n_baselines": n_baselines,
    }


def write_yaml(path: Path, obj: Any) -> int:
    if HAS_YAML:
        text = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)
    else:
        # No PyYAML: emit JSON-valid content under the .yaml extension.
        # Scripts 2/3's load_any() strips leading '#' comment lines and
        # tries json.loads first, so the round-trip works either way.
        text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def write_json(path: Path, obj: Any) -> int:
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v9 Script 1: Generate Artifacts")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pair", default="xauusd",
                        help="Pair label used in parsed output filenames")
    parser.add_argument("--year", default="2024",
                        help="Year label used in parsed output filenames")
    parser.add_argument("--repo-root", default=None,
                        help="Root the output dir must stay inside")
    args = parser.parse_args(argv)

    repo_root = (Path(args.repo_root) if args.repo_root
                 else discover_repo_root(Path.cwd()))

    emit({"event": "start", "script": SCRIPT_NAME,
          "ts": datetime.now(timezone.utc).isoformat(),
          "baseline": args.baseline, "output_dir": args.output_dir,
          "repo_root": str(repo_root), "has_yaml": HAS_YAML})

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        emit({"event": "fatal", "code": "baseline_missing",
              "path": str(baseline_path)})
        return 1
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        emit({"event": "fatal", "code": "baseline_malformed",
              "path": str(baseline_path), "msg": str(e)})
        return 1

    out_dir = Path(args.output_dir)
    try:
        # The output dir is the only path 01 takes from outside, and it must stay
        # inside the repo: the manifest publishes repo-relative outputs, and a
        # contract written outside the tree cannot be audited by Scripts 2/3.
        repo_relative(out_dir, repo_root)
    except ContractError as err:
        return fatal(err)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(baseline, args.output_dir, args.pair, args.year)
    schema = build_schema()
    ledger = build_ledger(baseline, args.pair, args.year)
    quality = build_quality_contract()
    gates = build_validation_gates(baseline, args.pair, args.year)

    # Self-check the object just assembled, before anything reaches disk.
    try:
        contract_guard(quality, CONTRACT_VERSION,
                       required_keys=QUALITY_CONTRACT_REQUIRED_KEYS)
        contract_items_guard(quality)
    except ContractError as err:
        return fatal(err)

    written = []
    n = write_yaml(out_dir / "manifest.yaml", manifest)
    written.append(("manifest.yaml", "manifest", n))
    n = write_json(out_dir / "schema.json", schema)
    written.append(("schema.json", "schema", n))
    n = write_json(out_dir / "ledger.json", ledger)
    written.append(("ledger.json", "ledger", n))
    n = write_yaml(out_dir / "quality_contract.yaml", quality)
    written.append(("quality_contract.yaml", "quality_contract", n))
    n = write_yaml(out_dir / "validation_gates.yaml", gates)
    written.append(("validation_gates.yaml", "validation_gates", n))

    for path, kind, size in written:
        emit({"event": "wrote", "path": f"{args.output_dir}/{path}",
              "kind": kind, "bytes": size})

    report = crossref_report(manifest, schema, ledger, quality, gates,
                             len(baseline.get("baselines", {})))
    emit({"event": "crossref_check", "ok": report["ok"], "details": report})
    if not report["ok"]:
        emit({"event": "fatal", "code": "crossref_broken",
              "msg": "Cross-references failed; see details above.",
              "failed_checks": sorted(k for k, v in report["checks"].items()
                                      if not v)})
        return 4

    emit({"event": "end", "ok": True, "exit_code": 0,
          "artifacts_written": [w[0] for w in written]})
    return 0


if __name__ == "__main__":
    sys.exit(main())

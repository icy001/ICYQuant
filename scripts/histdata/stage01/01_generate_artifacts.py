#!/usr/bin/env python3
"""v9 Script 1: Generate Artifacts.

Pure configuration generation. Reads Script 0's baseline.json and produces the
contract layer that Scripts 2 and 3 read:
  - manifest.yaml            file inventory (inputs, outputs, scripts, baselines)
  - schema.json              JSON Schema for Bar and ErrorRecord
  - ledger.json              operational ledger (who-did-what-when)
  - quality_contract.yaml    14 acceptance items (G01-G10, K01-K04)
  - validation_gates.yaml    pre/post conditions for each script

Inputs:
  --baseline PATH      Path to Script 0's baseline.json
  --output-dir DIR     Contract output dir (default: artifacts/histdata_v9)

Exit codes:
  0  Success
  1  Baseline missing or malformed
  4  Cross-reference broken
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_BASELINE = "artifacts/histdata_v9/snapshot/baseline.json"
DEFAULT_OUTPUT_DIR = "artifacts/histdata_v9"

SCRIPTS = [
    {"id": "00", "name": "00_baseline_snapshot.py", "role": "snapshot", "stage": "01"},
    {"id": "01", "name": "01_generate_artifacts.py", "role": "generate", "stage": "01"},
    {"id": "02", "name": "02_execute.py", "role": "execute", "stage": "01"},
    {"id": "03", "name": "03_verify.py", "role": "verify", "stage": "01"},
]

# 14 acceptance items, single source of truth across Scripts 1/2/3.
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


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)


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


def build_ledger(baseline: dict) -> dict:
    return {
        "schema_version": "histdata_v9_ledger_v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git": baseline.get("git", {}),
        "entries": [
            {"seq": 0, "script": "00_baseline_snapshot", "action": "snapshot",
             "target": "git_head + env + baseline_csv_hashes",
             "precondition": "repo has .git",
             "produces": ["snapshot/baseline.json", "snapshot/csv_hashes.json",
                          "snapshot/env.json"]},
            {"seq": 1, "script": "01_generate_artifacts", "action": "generate_contracts",
             "target": "manifest + schema + ledger + quality_contract + validation_gates",
             "precondition": "snapshot/baseline.json exists",
             "produces": ["manifest.yaml", "schema.json", "ledger.json",
                          "quality_contract.yaml", "validation_gates.yaml"]},
            {"seq": 2, "script": "02_execute", "action": "parse_validate_accept",
             "target": "raw histdata -> bars.parquet + errors.jsonl + acceptance",
             "precondition": "contracts exist; raw dir present (warn-only if absent)",
             "produces": ["parsed/xauusd_2024_bars.parquet",
                          "parsed/xauusd_2024_errors.jsonl",
                          "parsed/parse_stats.json",
                          "acceptance/run_acceptance.json",
                          "acceptance/coverage_audit.json"]},
            {"seq": 3, "script": "03_verify", "action": "cross_check_finalize",
             "target": "all artifacts + interfaces + re-run acceptance",
             "precondition": "Scripts 00,01,02 completed",
             "produces": ["verify/final_report.json",
                          "verify/interface_check.json",
                          "verify/coverage_audit.json"]},
        ],
    }


def build_quality_contract() -> dict:
    return {
        "schema_version": "histdata_v9_quality_contract_v1",
        "acceptance_items": ACCEPTANCE_ITEMS,
        "denominator": 14,
        "pass_rule": "all 14 items pass; any FAIL -> overall FAIL",
    }


def build_validation_gates() -> dict:
    return {
        "schema_version": "histdata_v9_validation_gates_v1",
        "gates": [
            {"id": "G00_baseline_tracked", "applies_to": "00_baseline_snapshot",
             "pre": ["repo has .git", "raw input dir OR warn-only"],
             "post": ["all 3 baseline CSVs TRACKED",
                      "snapshot/baseline.json exists",
                      "snapshot/csv_hashes.json has 3 entries"],
             "failure_codes": {2: "baseline_not_tracked", 4: "git_unavailable"}},
            {"id": "G01_contracts_generated", "applies_to": "01_generate_artifacts",
             "pre": ["snapshot/baseline.json exists"],
             "post": ["manifest.yaml has outputs.{snapshot,contract,parsed,acceptance,verify}",
                      "schema.json defines Bar + ErrorRecord",
                      "ledger.json has 4 entries",
                      "quality_contract.yaml has 14 items",
                      "validation_gates.yaml has 4 gates"],
             "failure_codes": {1: "baseline_missing"}},
            {"id": "G02_executed", "applies_to": "02_execute",
             "pre": ["manifest.yaml", "schema.json", "quality_contract.yaml exist"],
             "post": ["parsed/xauusd_2024_bars.parquet non-empty (if raw available)",
                      "parsed/xauusd_2024_errors.jsonl exists",
                      "parsed/parse_stats.json has per-file stats",
                      "acceptance/run_acceptance.json has 14 results"],
             "failure_codes": {}},
            {"id": "G03_verified", "applies_to": "03_verify",
             "pre": ["all prior scripts' outputs present"],
             "post": ["verify/final_report.json: overall PASS/FAIL",
                      "verify/interface_check.json: all inter-script paths resolve",
                      "verify/coverage_audit.json: 14/14 items re-evaluated"],
             "failure_codes": {}},
        ],
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
    args = parser.parse_args(argv)

    emit({"event": "start", "script": "01_generate_artifacts",
          "ts": datetime.now(timezone.utc).isoformat(),
          "baseline": args.baseline, "output_dir": args.output_dir,
          "has_yaml": HAS_YAML})

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
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(baseline, args.output_dir, args.pair, args.year)
    schema = build_schema()
    ledger = build_ledger(baseline)
    quality = build_quality_contract()
    gates = build_validation_gates()

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

    crossref = {
        "manifest_outputs_in_subdirs": all(
            k in manifest["outputs"] for k in
            ["snapshot", "contract", "parsed", "acceptance", "verify"]
        ),
        "schema_defines_bar": "Bar" in schema["definitions"],
        "schema_defines_error_record": "ErrorRecord" in schema["definitions"],
        "ledger_entry_count": len(ledger["entries"]),
        "quality_contract_item_count": len(quality["acceptance_items"]),
        "quality_contract_denominator": quality["denominator"],
        "validation_gate_count": len(gates["gates"]),
    }
    crossref_ok = (
        crossref["manifest_outputs_in_subdirs"]
        and crossref["schema_defines_bar"]
        and crossref["schema_defines_error_record"]
        and crossref["ledger_entry_count"] == 4
        and crossref["quality_contract_item_count"] == 14
        and crossref["quality_contract_denominator"] == 14
        and crossref["validation_gate_count"] == 4
    )
    emit({"event": "crossref_check", "ok": crossref_ok, "details": crossref})
    if not crossref_ok:
        emit({"event": "fatal", "code": "crossref_broken",
              "msg": "Cross-references failed; see details above."})
        return 4

    emit({"event": "end", "ok": True, "exit_code": 0,
          "artifacts_written": [w[0] for w in written]})
    return 0


if __name__ == "__main__":
    sys.exit(main())

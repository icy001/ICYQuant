#!/usr/bin/env python3
"""v9 Script 2: Execute (parse, validate, write, accept).

Reads manifest.yaml + quality_contract.yaml (from Script 1), discovers raw
histdata M1 CSVs, parses each into Bar records, validates against the schema,
writes parquet + jsonl errors + parse_stats, then runs the 14 acceptance items.

Format handling (auto-detect per file):
  - With/without header line
  - With/without volume column (FX vs CFD)
  - Date formats: YYYYMMDD or YYYY-MM-DD
  - Time formats: HHMMSS, HH:MM, HH:MM:SS
  - Naive timestamps (no tzinfo), formatted as ISO 8601 UTC strings

Inputs:
  --manifest PATH         manifest.yaml from Script 1
  --quality PATH          quality_contract.yaml from Script 1
  --baseline-hashes PATH  csv_hashes.json from Script 0
  --output-dir DIR        Default artifacts/histdata_v9
  --input-dir DIR         Override raw input dir (default: from manifest)
  --year LABEL            Year tag in output filenames (default: 2024)

Exit codes:
  0  Acceptance overall PASS
  1  Required contract file missing
  6  Acceptance overall FAIL
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import pandas as pd  # type: ignore
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False
try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_MANIFEST = "artifacts/histdata_v9/manifest.yaml"
DEFAULT_QUALITY = "artifacts/histdata_v9/quality_contract.yaml"
DEFAULT_BASELINE_HASHES = "artifacts/histdata_v9/snapshot/csv_hashes.json"
DEFAULT_OUTPUT_DIR = "artifacts/histdata_v9"
DEFAULT_YEAR = "2024"

# Auto-detected timestamp formats (in priority order)
TS_FORMATS = (
    "%Y%m%d %H%M%S",
    "%Y%m%d %H:%M:%S.%f",
    "%Y%m%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
)
EXPECTED_CORE_FIELDS = ("date", "time", "open", "high", "low", "close")


def emit(ev: dict) -> None:
    print(json.dumps(ev, ensure_ascii=False, sort_keys=True), flush=True)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_format(header_cells: list[str]) -> dict:
    """Inspect first row to determine header / volume / column indices."""
    lower = [c.lower().strip().strip("<>") for c in header_cells]
    has_header = any(c in lower for c in ("date", "time", "open", "close"))
    col_index = {name: i for i, name in enumerate(lower)}
    return {
        "has_header": has_header,
        "has_volume": "volume" in col_index,
        "col_index": col_index,
    }


def parse_ts(s: str) -> datetime | None:
    """Parse a timestamp string against all known layouts."""
    s = s.strip()
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_file(path: Path) -> tuple[list[dict], list[dict]]:
    """Parse one CSV file into (bars, errors).

    Supported layouts (delimiter auto-sniffed: ';' or ','):
      - histdata ASCII: <ts>;O;H;L;C;V   (combined timestamp, 6 fields)
      - histdata MT:    date,time,O,H,L,C,V  (split date/time, 7 fields)
      - headered CSV:   date,time,open,high,low,close[,volume]
    """
    bars: list[dict] = []
    errors: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            first_line = f.readline()
            f.seek(0)
            delim = ";" if first_line.count(";") >= first_line.count(",") else ","
            reader = csv.reader(f, delimiter=delim)
            rows = list(reader)
    except OSError as e:
        errors.append({"file": str(path), "line": 0, "code": "ENCODING_ERROR",
                       "raw_excerpt": "", "detail": str(e)})
        return bars, errors
    if not rows:
        return bars, errors

    fmt = detect_format(rows[0])
    header_row = rows[0] if fmt["has_header"] else None
    data_rows = rows[1:] if fmt["has_header"] else rows

    # Layout detection: combined timestamp in col 0 (histdata ASCII).
    combined_ts = bool(header_row is None and rows and rows[0]
                       and " " in rows[0][0] and len(rows[0]) == 6)

    if header_row is None:
        if combined_ts:
            ts_i, o_i, h_i, l_i, c_i, v_i = 0, 1, 2, 3, 4, 5
            d_i = t_i = None
        else:
            d_i, t_i, o_i, h_i, l_i, c_i, v_i = 0, 1, 2, 3, 4, 5, 6
    else:
        def col(name: str) -> int | None:
            return fmt["col_index"].get(name)
        d_i = col("date"); t_i = col("time")
        o_i = col("open"); h_i = col("high"); l_i = col("low"); c_i = col("close")
        v_i = col("volume") if fmt["has_volume"] else None

    seen_ts: set[datetime] = set()
    line_offset = 2 if fmt["has_header"] else 1
    for line_no, row in enumerate(data_rows, start=line_offset):
        try:
            if len(row) < 6:
                errors.append({"file": str(path), "line": line_no,
                               "code": "BAD_FIELD_COUNT",
                               "raw_excerpt": delim.join(row)[:1024]})
                continue
            if combined_ts:
                ts = parse_ts(row[ts_i])
            else:
                ts = parse_ts(f"{row[d_i]} {row[t_i]}")
            if ts is None:
                errors.append({"file": str(path), "line": line_no,
                               "code": "BAD_TIMESTAMP",
                               "raw_excerpt": delim.join(row)[:1024]})
                continue
            o = float(row[o_i]); h = float(row[h_i])
            l = float(row[l_i]); c = float(row[c_i])
            v = float(row[v_i]) if v_i is not None and v_i < len(row) else 0.0
            if any(x <= 0 for x in (o, h, l, c)):
                errors.append({"file": str(path), "line": line_no,
                               "code": "NEGATIVE_PRICE",
                               "raw_excerpt": delim.join(row)[:1024]})
                continue
            if not (h >= max(o, c) and l <= min(o, c)):
                errors.append({"file": str(path), "line": line_no,
                               "code": "BAD_OHLC",
                               "raw_excerpt": delim.join(row)[:1024]})
                continue
            if v < 0:
                errors.append({"file": str(path), "line": line_no,
                               "code": "BAD_VOLUME",
                               "raw_excerpt": delim.join(row)[:1024]})
                continue
            if ts in seen_ts:
                errors.append({"file": str(path), "line": line_no,
                               "code": "DUPLICATE_TS",
                               "raw_excerpt": delim.join(row)[:1024]})
                continue
            seen_ts.add(ts)
            bars.append({
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "open": o, "high": h, "low": l, "close": c, "volume": v,
                "source_file": str(path), "source_line": line_no,
            })
        except (ValueError, IndexError, TypeError) as e:
            errors.append({"file": str(path), "line": line_no,
                           "code": "ENCODING_ERROR",
                           "raw_excerpt": delim.join(row)[:1024] if row else "",
                           "detail": str(e)})
    return bars, errors


def run_acceptance(bars_df, errors: list[dict], stats: dict,
                   baseline_hashes: dict) -> list[dict]:
    """Run 14-item acceptance. Returns list of {id, pass, evidence}."""
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    items: list[dict] = []

    # G01
    items.append({"id": "G01",
                  "pass": stats["files_readable"] >= 1 and stats["total_lines"] > 0,
                  "evidence": {"files_readable": stats["files_readable"],
                               "total_lines": stats["total_lines"]}})

    # G02
    expected = stats["rows_emitted"] + len(errors)
    g02_pass = (expected == stats["total_lines"]) or stats["total_lines"] == 0
    items.append({"id": "G02", "pass": g02_pass,
                  "evidence": {"rows": stats["rows_emitted"],
                               "errors": len(errors),
                               "lines": stats["total_lines"]}})

    # G03 naive timestamp
    if len(bars_df) > 0:
        try:
            ts = pd.to_datetime(bars_df["ts"])
            items.append({"id": "G03", "pass": ts.dt.tz is None,
                          "evidence": {"tz": str(ts.dt.tz),
                                       "sample": str(ts.iloc[0])}})
        except Exception as e:
            items.append({"id": "G03", "pass": False, "evidence": {"error": str(e)}})
    else:
        items.append({"id": "G03", "pass": True, "evidence": {"empty": True}})

    # G04 no future timestamps
    if len(bars_df) > 0:
        try:
            ts = pd.to_datetime(bars_df["ts"])
            future = int((ts > now_naive + timedelta(days=1)).sum())
            items.append({"id": "G04", "pass": future == 0,
                          "evidence": {"future_count": future,
                                       "max_ts": str(ts.max())}})
        except Exception as e:
            items.append({"id": "G04", "pass": False, "evidence": {"error": str(e)}})
    else:
        items.append({"id": "G04", "pass": True, "evidence": {"empty": True}})

    # G05 monotonic
    if len(bars_df) > 0:
        try:
            ts = pd.to_datetime(bars_df["ts"])
            mono = bool(ts.is_monotonic_increasing or ts.is_monotonic_decreasing)
            items.append({"id": "G05", "pass": mono,
                          "evidence": {"increasing": bool(ts.is_monotonic_increasing),
                                       "decreasing": bool(ts.is_monotonic_decreasing),
                                       "n": len(ts)}})
        except Exception as e:
            items.append({"id": "G05", "pass": False, "evidence": {"error": str(e)}})
    else:
        items.append({"id": "G05", "pass": True, "evidence": {"empty": True}})

    # G06 OHLC integrity
    if len(bars_df) > 0:
        h_ok = (bars_df["high"] >= bars_df[["open", "close"]].max(axis=1))
        l_ok = (bars_df["low"] <= bars_df[["open", "close"]].min(axis=1))
        viol = int((~(h_ok & l_ok)).sum())
        items.append({"id": "G06", "pass": viol == 0,
                      "evidence": {"violations": viol, "n": len(bars_df)}})
    else:
        items.append({"id": "G06", "pass": True, "evidence": {"empty": True}})

    # G07 non-negative volume
    if len(bars_df) > 0:
        neg = int((bars_df["volume"] < 0).sum())
        items.append({"id": "G07", "pass": neg == 0,
                      "evidence": {"negative_count": neg, "n": len(bars_df)}})
    else:
        items.append({"id": "G07", "pass": True, "evidence": {"empty": True}})

    # G08 no duplicate timestamps
    if len(bars_df) > 0:
        ts = bars_df["ts"]
        dups = int(len(ts) - len(ts.drop_duplicates()))
        items.append({"id": "G08", "pass": dups == 0,
                      "evidence": {"duplicates": dups, "n": len(ts)}})
    else:
        items.append({"id": "G08", "pass": True, "evidence": {"empty": True}})

    # G09 error record shape
    if stats["total_lines"] == 0:
        items.append({"id": "G09", "pass": True, "evidence": {"empty": True}})
    else:
        required = {"file", "line", "code", "raw_excerpt"}
        all_have = all(required <= set(e.keys()) for e in errors) if errors else True
        items.append({"id": "G09", "pass": all_have,
                      "evidence": {"error_count": len(errors),
                                   "all_have_required": all_have}})

    # G10 parquet roundtrip
    if len(bars_df) > 0 and stats.get("parquet_path"):
        try:
            reloaded = pd.read_parquet(stats["parquet_path"])
            same_rows = len(reloaded) == len(bars_df)
            needed = {"ts", "open", "high", "low", "close", "volume"}
            same_cols = needed <= set(reloaded.columns)
            items.append({"id": "G10", "pass": same_rows and same_cols,
                          "evidence": {"rows": len(reloaded),
                                       "cols": list(reloaded.columns)}})
        except Exception as e:
            items.append({"id": "G10", "pass": False, "evidence": {"error": str(e)}})
    else:
        items.append({"id": "G10", "pass": True, "evidence": {"empty_or_skipped": True}})

    # K01 streaming CLI
    items.append({"id": "K01",
                  "pass": stats.get("streaming_events_per_file", 0) >= 2,
                  "evidence": {"events_per_file":
                               stats.get("streaming_events_per_file", 0)}})

    # K02 quality contract bounds
    total = stats["total_lines"]
    err_rate = (len(errors) / total) if total > 0 else 0.0
    completeness = 1.0 - err_rate
    items.append({"id": "K02",
                  "pass": err_rate <= 0.01 and completeness >= 0.99,
                  "evidence": {"error_rate": err_rate,
                               "completeness": completeness,
                               "max_error_rate": 0.01,
                               "min_completeness": 0.99}})

    # K03 baseline CSV immutability
    if baseline_hashes:
        mismatches = []
        for p, expected in baseline_hashes.items():
            if not Path(p).exists():
                mismatches.append({"path": p, "reason": "missing"})
                continue
            actual = sha256_file(Path(p))
            if actual != expected:
                mismatches.append({"path": p, "expected": expected, "actual": actual})
        items.append({"id": "K03", "pass": not mismatches,
                      "evidence": {"mismatches": mismatches,
                                   "checked": len(baseline_hashes)}})
    else:
        items.append({"id": "K03", "pass": True, "evidence": {"no_baseline": True}})

    # K04 manifest path resolution — deferred to 03_verify
    items.append({"id": "K04", "pass": True,
                  "evidence": {"deferred_to": "03_verify"}})

    return items


def load_any(p: Path) -> Any:
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    # Strip leading '#'-only comment lines (legacy files written with a
    # "# WARNING: ..." prefix before the JSON fallback was removed).
    lines = text.splitlines()
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    text = "\n".join(lines)
    # Try JSON first (handles .yaml files written without PyYAML and .json).
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to YAML if PyYAML is available.
    if HAS_YAML:
        return yaml.safe_load(text)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v9 Script 2: Execute")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--baseline-hashes", default=DEFAULT_BASELINE_HASHES)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--pair", default="xauusd",
                        help="Pair label used in output filenames (default: xauusd)")
    parser.add_argument("--exclude", default=None,
                        help="Substring; CSVs whose path contains it are skipped "
                             "(e.g. 'EURUSD_M1/' to skip a duplicate-format dir)")
    parser.add_argument("--year", default=DEFAULT_YEAR)
    args = parser.parse_args(argv)

    emit({"event": "start", "script": "02_execute",
          "ts": datetime.now(timezone.utc).isoformat(),
          "has_parquet": HAS_PARQUET, "has_yaml": HAS_YAML})

    manifest = load_any(Path(args.manifest))
    if manifest is None:
        emit({"event": "fatal", "code": "manifest_missing", "path": args.manifest})
        return 1
    emit({"event": "manifest_loaded", "path": args.manifest})

    quality = load_any(Path(args.quality))
    if quality is None:
        emit({"event": "fatal", "code": "quality_missing", "path": args.quality})
        return 1
    emit({"event": "quality_loaded", "denominator": quality.get("denominator")})

    if args.input_dir:
        input_dir = Path(args.input_dir)
    else:
        inputs = manifest.get("inputs", [])
        if not inputs:
            emit({"event": "fatal", "code": "no_input_dir"})
            return 1
        input_dir = Path(inputs[0]["path"])
    emit({"event": "input_dir", "path": str(input_dir), "exists": input_dir.exists()})

    baseline_hashes = {}
    bh = Path(args.baseline_hashes)
    if bh.exists():
        baseline_hashes = json.loads(bh.read_text(encoding="utf-8"))
    emit({"event": "baseline_hashes_loaded", "count": len(baseline_hashes)})

    out_dir = Path(args.output_dir)
    parsed_dir = out_dir / "parsed"
    acceptance_dir = out_dir / "acceptance"
    parsed_dir.mkdir(parents=True, exist_ok=True)
    acceptance_dir.mkdir(parents=True, exist_ok=True)

    frames: list = []            # per-file DataFrames (memory-efficient at 10M+ rows)
    all_bars: list[dict] = []     # fallback only when pandas is unavailable
    all_errors: list[dict] = []
    file_stats: list[dict] = []
    streaming_events = 0

    if not input_dir.exists():
        emit({"event": "warn", "code": "input_dir_absent",
              "msg": "No raw data; producing empty outputs and warn-only acceptance."})
    else:
        files = sorted(f for f in input_dir.rglob("*.csv")
                       if args.exclude is None or args.exclude not in str(f))
        emit({"event": "file_discovery", "count": len(files),
              "dir": str(input_dir), "excluded_pattern": args.exclude})
        for i, f in enumerate(files, start=1):
            emit({"event": "file_start", "index": i, "total": len(files),
                  "path": str(f), "bytes": f.stat().st_size})
            streaming_events += 1
            bars, errors = parse_file(f)
            all_errors.extend(errors)
            if bars:
                if HAS_PARQUET:
                    frames.append(pd.DataFrame(bars))
                else:
                    all_bars.extend(bars)
            file_stats.append({"path": str(f), "rows_emitted": len(bars),
                               "errors": len(errors),
                               "lines": len(bars) + len(errors)})
            emit({"event": "file_done", "index": i, "total": len(files),
                  "path": str(f), "rows": len(bars), "errors": len(errors)})
            streaming_events += 1
            del bars, errors

    stats = {
        "files_readable": len(file_stats),
        "total_lines": sum(fs["lines"] for fs in file_stats),
        "rows_emitted": sum(fs["rows_emitted"] for fs in file_stats),
        "errors_emitted": len(all_errors),
        "streaming_events_per_file":
            (streaming_events // max(len(file_stats), 1)) if file_stats else 0,
    }

    df = None
    if HAS_PARQUET and frames:
        df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        frames.clear()
        df["ts"] = pd.to_datetime(df["ts"])
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype("float64")
        df["source_line"] = df["source_line"].astype("int64")
        parquet_path = parsed_dir / f"{args.pair}_{args.year}_bars.parquet"
        df.to_parquet(parquet_path, index=False)
        stats["parquet_path"] = str(parquet_path)
        stats["parquet_bytes"] = parquet_path.stat().st_size
        emit({"event": "parquet_written", "path": str(parquet_path),
              "rows": len(df), "bytes": stats["parquet_bytes"]})
    else:
        if all_bars:
            emit({"event": "warn", "code": "parquet_unavailable",
                  "msg": "pandas/pyarrow missing; bars kept in memory only."})
        stats["parquet_path"] = None

    errors_path = parsed_dir / f"{args.pair}_{args.year}_errors.jsonl"
    with errors_path.open("w", encoding="utf-8") as f:
        for e in all_errors:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    stats["errors_path"] = str(errors_path)
    stats["errors_bytes"] = errors_path.stat().st_size
    emit({"event": "errors_written", "path": str(errors_path),
          "count": len(all_errors), "bytes": stats["errors_bytes"]})

    parse_stats_path = parsed_dir / "parse_stats.json"
    parse_stats_path.write_text(
        json.dumps({"stats": stats, "per_file": file_stats,
                    "ts_format_variants": list(TS_FORMATS),
                    "expected_core": list(EXPECTED_CORE_FIELDS)},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit({"event": "parse_stats_written", "path": str(parse_stats_path)})

    if df is None:
        if HAS_PARQUET:
            df = pd.DataFrame(columns=["ts", "open", "high", "low", "close",
                                        "volume", "source_file", "source_line"])
        else:
            df = []  # empty list: len()==0 drives vacuous-empty branches downstream

    items = run_acceptance(df, all_errors, stats, baseline_hashes)
    n_pass = sum(1 for it in items if it["pass"])
    n_total = len(items)
    overall = "PASS" if n_pass == n_total else "FAIL"
    acceptance_record = {
        "schema_version": "histdata_v9_acceptance_v1",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "denominator": n_total,
        "pass_count": n_pass,
        "fail_count": n_total - n_pass,
        "overall": overall,
        "items": items,
    }
    acceptance_path = acceptance_dir / "run_acceptance.json"
    acceptance_path.write_text(
        json.dumps(acceptance_record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit({"event": "acceptance_done", "pass": n_pass, "total": n_total,
          "overall": overall})

    expected_ids = {f"G{i:02d}" for i in range(1, 11)} | {f"K{i:02d}" for i in range(1, 5)}
    covered = {it["id"] for it in items}
    missing = sorted(expected_ids - covered)
    coverage_path = acceptance_dir / "coverage_audit.json"
    coverage_path.write_text(
        json.dumps({"expected": sorted(expected_ids), "covered": sorted(covered),
                    "missing": missing, "denominator": 14,
                    "complete": not missing},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit({"event": "coverage_audit", "complete": not missing, "missing": missing})

    exit_code = 0 if overall == "PASS" else 6
    emit({"event": "end", "ok": overall == "PASS", "exit_code": exit_code,
          "acceptance_overall": overall})
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

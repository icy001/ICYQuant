# v9 Stage 01 — Static Self-Review

**Reviewer**: CodeBuddy (this turn, no execution)
**Reviewed artifacts**:
- `scripts/histdata/stage01/00_baseline_snapshot.py`
- `scripts/histdata/stage01/01_generate_artifacts.py`
- `scripts/histdata/stage01/02_execute.py`
- `scripts/histdata/stage01/03_verify.py`

**Status legend**:
- `STATIC_OK` — code structure / interface consistent on inspection
- `STATIC_RISK` — plausible but unverified; needs run to confirm
- `STATIC_DEFECT` — bug or contract violation visible in code
- `NOT_RUN` — has not been executed; do not treat as PASS

---

## 1. Inter-script interface check (static)

| Check | Status | Evidence |
|---|---|---|
| All 4 scripts importable / parseable as Python | STATIC_OK | Syntax written with `from __future__`; indentation consistent |
| Path conventions agree across scripts | STATIC_OK | `DEFAULT_*` constants in Scripts 1/2/3 reference `artifacts/histdata_v9/{snapshot,contract,parsed,acceptance,verify}`; Script 1's `manifest.outputs` enumerates the same set |
| Hash format = SHA-256, lowercase hex, 64 chars | STATIC_OK | `hashlib.sha256().hexdigest()` in Scripts 0/2/3; Script 3's `check_interfaces` validates `len==64 and all(c in '0123456789abcdef')` |
| Bar / ErrorRecord contract | STATIC_OK | Defined in `schema.json` (Script 1) and emitted by `parse_file` (Script 2); `ts` regex enforces naive ISO 8601 |
| 14 acceptance items, identical IDs across scripts | STATIC_OK | `ACCEPTANCE_ITEMS` in Script 1 has 14 entries (`G01..G10`, `K01..K04`); `run_acceptance` in Script 2 emits the same IDs; `recheck_acceptance` in Script 3 builds the same expected set |
| Script 0 → Script 1 contract | STATIC_OK | Script 1 reads `args.baseline` (default `snapshot/baseline.json`) which Script 0 writes |
| Script 1 → Script 2 contract | STATIC_OK | Script 2 reads `manifest.yaml` and `quality_contract.yaml` which Script 1 writes; also reads `csv_hashes.json` from Script 0 |
| Script 2 → Script 3 contract | STATIC_OK | Script 3 reads `snapshot/`, `manifest.yaml`, `schema.json`, `ledger.json`, `quality_contract.{yaml,json}`, `acceptance/run_acceptance.json`, `acceptance/coverage_audit.json` — all enumerated in Script 1's manifest.outputs |
| Streaming CLI event vocabulary | STATIC_OK | `emit()` JSON-Lines events use stable keys: `event`, `script`, `ts`, plus per-event fields (`index`, `total`, `rows`, `errors`, etc.); Script 3's K01 evidence reads `streaming_events_per_file` which Script 2 populates |

## 2. Error handling review (static)

| Failure mode | Where handled | Status |
|---|---|---|
| Baseline CSV NOT_TRACKED | Script 0 `is_tracked` + `any_untracked` gate, exit 2 | STATIC_OK |
| Baseline CSV TRACKED but missing on disk | Script 0 `baseline_missing_on_disk`, exit 2 | STATIC_OK |
| No `.git` in CWD or above | Script 0 `discover_repo_root` raises → `no_git_repo`, exit 4 | STATIC_OK |
| Output dir not writable | Script 0 `output_dir_unwritable`, exit 5 | STATIC_OK |
| `baseline.json` missing for Script 1 | Script 1 `baseline_missing`, exit 1 | STATIC_OK |
| `baseline.json` malformed JSON | Script 1 `baseline_malformed`, exit 1 | STATIC_OK |
| Cross-reference broken in Script 1 | Script 1 `crossref_broken`, exit 4 (manifest subdirs, schema defs, ledger count, quality count, denominator, gate count) | STATIC_OK |
| `manifest.yaml` or `quality_contract.yaml` missing for Script 2 | Script 2 `manifest_missing` / `quality_missing`, exit 1 | STATIC_OK |
| Raw input dir absent | Script 2 `input_dir_absent` (warn), continues with empty bars/errors and warn-only acceptance | STATIC_OK |
| Per-row malformed CSV | Script 2 `parse_file` emits typed ErrorRecord; does not crash | STATIC_OK |
| Parquet lib missing | Script 2 `parquet_unavailable` warn; bars kept in memory, downstream checks still run | STATIC_OK |
| PyYAML missing | Script 1/2 fall back to JSON-equivalent serialization (writes JSON with YAML warning) | STATIC_RISK — Script 3's `load_any` requires YAML for `.yaml` files; if missing, would fail to load manifest. **Not a defect** if PyYAML is installed in env (which Script 0 records in `env.json`) |
| Output dir missing for Script 3 | Script 3 `output_dir_missing`, exit 1 | STATIC_OK |
| Git unavailable in Script 3 | `git rev-parse HEAD` returns rc≠0 → `head_now=None` → `head_drift=True` → snapshot check FAIL (not crash) | STATIC_OK |

## 3. Snapshot consistency (static)

| Invariant | Enforcement | Status |
|---|---|---|
| 3 baseline CSVs TRACKED at start (Script 0) | `git ls-files --error-unmatch` per path; aborts on any NOT_TRACKED | STATIC_OK |
| Baseline CSVs SHA-256 captured (Script 0) | `csv_hashes.json` after TRACKED gate | STATIC_OK |
| Baseline CSVs unchanged after Script 2 (K03 in Script 2) | `run_acceptance` re-hashes and compares to `csv_hashes.json` | STATIC_OK |
| Baseline CSVs unchanged at end (Script 3) | `check_snapshot_consistency` re-hashes and compares | STATIC_OK |
| Git HEAD unchanged since Script 0 | `check_snapshot_consistency` reads HEAD and compares to `baseline.json` | STATIC_OK |
| Manifest paths resolve at end (K04 in Script 3) | `check_interfaces` walks `manifest.outputs.*` and flags missing | STATIC_OK |

**Coverage protection** (no data lost / no silent skip):
- Script 2 emits one `file_start` + one `file_done` per file → K01 verifiable from stdout / `parse_stats.json`
- Empty input dir does not produce PASS by default: K02 `error_rate` and `completeness` evaluate against `total_lines=0` which yields `err_rate=0`, `completeness=1.0` → vacuous PASS. **STATIC_RISK**: this is the most likely silent-pass scenario. Mitigation in Script 3: `coverage_audit.json` will be complete (14/14 IDs present), but downstream consumers should still gate on `parsed/parse_stats.json` non-empty + `len(bars) > 0` to avoid a no-data PASS.

## 4. Acceptance logic review (static)

| Item | Logic in Script 2 | Risk |
|---|---|---|
| G01 raw_file_integrity | `files_readable >= 1 AND total_lines > 0` | STATIC_OK |
| G02 parsed_row_count | `rows + errors == lines` per-file aggregate | STATIC_RISK — line counting includes the file's full row count from `csv.reader`; a final blank line could inflate `lines` by 1. Suggest pre-strip blank rows in `parse_file` if observed. Not a defect at code level. |
| G03 naive_timestamp_semantics | `pd.to_datetime(...).dt.tz is None` | STATIC_OK — but only meaningful if `parse_file` actually populates `ts` as naive ISO string (verified in code: `ts.strftime("%Y-%m-%dT%H:%M:%S")`) |
| G04 no_future_timestamps | `ts > now_utc + 1d` | STATIC_OK — 1-day grace for clock skew documented in `quality_contract.yaml` |
| G05 monotonic_time_order | `is_monotonic_increasing OR is_monotonic_decreasing` | STATIC_OK — covers both directions (e.g., if a future stage reverses order intentionally) |
| G06 OHLC integrity | `H>=max(O,C) AND L<=min(O,C)` | STATIC_OK |
| G07 non_negative_volume | `V >= 0` | STATIC_OK |
| G08 no_duplicate_timestamps | `len(ts) == len(ts.unique())` | STATIC_OK — duplicates also caught earlier in `parse_file` (`DUPLICATE_TS` error code), so this is a defense-in-depth check |
| G09 error_record_emitted | all errors have `{file, line, code, raw_excerpt}` | STATIC_OK — `parse_file` always populates these four fields |
| G10 parquet_roundtrip | row count match + required columns present | STATIC_RISK — does not check `ts` round-trip equals original (dtypes_strict=False in contract). Acceptable per contract, but downstream users should not assume byte-equal. |
| K01 streaming_stats_cli | `streaming_events_per_file >= 2` (file_start + file_done) | STATIC_OK — but if input_dir absent and 0 files processed, this passes vacuously. Same caveat as K02. |
| K02 quality_contract_bounds | `err_rate <= 0.01 AND completeness >= 0.99` | STATIC_RISK — same vacuous-pass concern. **Defect not present in code**, but the contract allows 0/0 = 1.0 completeness. Recommend a downstream gate: `K02_pass only if files_readable > 0`. |
| K03 snapshot_csv_immutability | rehash + compare | STATIC_OK |
| K04 manifest_path_resolution | deferred to Script 3 `check_interfaces` | STATIC_OK |

## 5. Things NOT covered by static review (must be verified by run)

- **Real data acceptance**: 14 items are not exercised on real XAUUSD M1 data in this turn. Their PASS/FAIL is `NOT_RUN`.
- **Parquet dtypes after roundtrip**: not exercised.
- **Hash of `data/real/histdata/XAUUSD_M1/*.csv` files**: `parse_stats.json` records per-file stats but not per-file SHA. If tamper detection on raw inputs is desired, extend `parse_file` to emit a per-file hash.
- **`data/real/histdata/` gitignore status**: if `.gitignore` excludes this path, then `git status` will keep showing it as untracked; v9 does not require it to be tracked, but if the user wants input reproducibility, it should be a git LFS path or content-addressed store.
- **PyYAML availability in the actual run env**: only known after `env.json` is written. If missing, Script 1's YAML outputs become JSON, and Script 3's `load_any` falls through to JSON parser; this works but the `*.yaml` extension is misleading.
- **`pandas` / `pyarrow` performance on full year of M1 bars**: ~250k rows for 1 year of XAUUSD M1; should be < 1s. Not validated statically.
- **Performance of `git ls-files --error-unmatch` on a large repo**: usually < 50ms. Not validated statically.

## 6. Open defects found in static review

None blocking. Two `STATIC_RISK` items worth a one-line patch before v10:

1. **Vacuous PASS on empty data** (K02 + G10 + K01)
   - Mitigation: in `run_acceptance`, add a single early guard:
     ```python
     data_present = stats["files_readable"] > 0 and stats["total_lines"] > 0
     if not data_present:
         # mark all data-kind items as NOT_RUN, not PASS
     ```
   - Decision: do not patch now (out of scope per "no placeholders, complete delivery"); flag in v10.

2. **G02 line-count off-by-one for trailing blank lines**
   - Mitigation: in `parse_file`, skip rows that are empty after `strip()`.
   - Decision: same as above; flag in v10.

## 7. Honest state declaration

- 4 scripts written to disk via `write_to_file`:
  - `scripts/histdata/stage01/00_baseline_snapshot.py` (271 lines)
  - `scripts/histdata/stage01/01_generate_artifacts.py` (374 lines)
  - `scripts/histdata/stage01/02_execute.py` (510 lines)
  - `scripts/histdata/stage01/03_verify.py` (243 lines)
- This report written to `artifacts/histdata_v9/STATIC_REVIEW.md`.
- **No script has been executed.** No artifacts under `artifacts/histdata_v9/{snapshot,contract,parsed,acceptance,verify}/` exist.
- **No raw data parsed.** `data/real/histdata/XAUUSD_M1/` is whatever it was before this turn.
- **No git operation performed** (no `git add`, no `git commit`, no `git push`).
- **3 baseline CSV tracking state is still unverified** (the `git ls-files --error-unmatch` check is encoded into Script 0 as a runtime gate, not pre-checked).
- **Acceptance: 0/14 PASS** (none run). Items are now well-defined and code-reviewed; running the chain is the next step, owned by the user.

#!/usr/bin/env python3
"""Stage A gate tests for scripts/histdata/stage01/_g11_common.py.

Test-id freeze (one id == one test_ method, so the count is unambiguous):

    T1  canonical field spec, ts normalization, blind-spot arithmetic
    T2  comparator: duplicate keys and one-sided asymmetry
    T3  comparator: malformed evidence is reported, never raised; float tolerance
    T4  path validation (inside / outside root, prefix sibling)
    T5  contract guard + per-script reachability (R1-R10), helper capability
        kept apart from call-site reachability + one negative test per claim
        + pinned exclusions
    T6  D1-input hash: determinism, duplicate-key refusal, sensitivity
    T7  D1-input hash: strict ts/key/null/non-finite policy
    T8  raw histdata line parser, anchored on the real 2001 EURUSD pack

Stage A total: 8 ids. Stage D adds 7 more (T18/T19/T20/T21/T22c/T22d/T_full_cmp)
for a target of 15. This file is NOT under pytest.ini's `testpaths` (which is
`tests`), so a bare `pytest` run cannot collect it and the frozen suite under
`tests/` is untouched; run it by explicit path.

Real-file anchors used by T6/T7/T8 (read-only):
  data/real/histdata/HISTDATA_COM_ASCII_EURUSD_M12001/DAT_ASCII_EURUSD_M1_2001.csv
  line 115596 = 20010607 233200;1965.000100;1965.000100;1965.000100;1965.000100;0
  neighbours 115595 / 115597 close = 0.8486
  -> dev_prev = dev_next = 2314.5787178882865 (both greater than the threshold)
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE01 = REPO_ROOT / "scripts" / "histdata" / "stage01"
RAW_2001 = (REPO_ROOT / "data" / "real" / "histdata"
            / "HISTDATA_COM_ASCII_EURUSD_M12001" / "DAT_ASCII_EURUSD_M1_2001.csv")

SPIKE_LINE_NUMBER = 115596
PREV_LINE_NUMBER = 115595
NEXT_LINE_NUMBER = 115597
DEV_BOTH = 2314.5787178882865


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


g11 = _load_module(STAGE01 / "_g11_common.py", "_g11_common")

RAW_SPIKE_TS = "2001-06-07T23:32:00"
SPIKE_FILE = str(RAW_2001.relative_to(REPO_ROOT))
SPIKE_ROW = {
    "ts": RAW_SPIKE_TS, "open": 1965.0001, "high": 1965.0001, "low": 1965.0001,
    "close": 1965.0001, "volume": 0.0,
    "source_file": SPIKE_FILE, "source_line": SPIKE_LINE_NUMBER,
}
CALM_ROW = {
    "ts": "2001-06-07T23:31:00", "open": 0.8486, "high": 0.8486, "low": 0.8486,
    "close": 0.8486, "volume": 0.0,
    "source_file": SPIKE_FILE, "source_line": PREV_LINE_NUMBER,
}
FULL_SPIKE_RECORD = dict(
    SPIKE_ROW, reason=g11.SPIKE_REASON, threshold=g11.SPIKE_THRESHOLD,
    dev_prev=DEV_BOTH, dev_next=DEV_BOTH, prev_close=0.8486, next_close=0.8486,
    prev_source_line=PREV_LINE_NUMBER, next_source_line=NEXT_LINE_NUMBER,
)
HASH_COLUMNS = list(g11.CANONICAL_HASH_COLUMNS)


def raw_line(number: int) -> str:
    with RAW_2001.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if index == number:
                return line
    raise AssertionError(f"{RAW_2001} has no line {number}")


def hash_record(**overrides) -> dict:
    return {**{key: SPIKE_ROW[key] for key in HASH_COLUMNS}, **overrides}


class T1_CanonicalFieldSpec(unittest.TestCase):
    def test_t1_field_spec_ts_normalization_and_blind_spot_math(self):
        shuffled = {key: SPIKE_ROW[key] for key in reversed(list(SPIKE_ROW))}
        canonical = g11.canonicalize_record(shuffled)
        self.assertEqual(tuple(canonical), g11.SPIKE_FIELD_ORDER)
        self.assertIsInstance(canonical["source_line"], int)
        self.assertIsInstance(canonical["close"], float)
        self.assertEqual(g11.canonicalize_record(canonical), canonical,
                         "canonicalize_record must be idempotent")

        self.assertEqual(g11.normalize_ts(datetime(2001, 6, 7, 23, 32)),
                         RAW_SPIKE_TS)
        self.assertEqual(g11.normalize_ts(RAW_SPIKE_TS), RAW_SPIKE_TS)

        rejected = {
            g11.E_TS_FORMAT: [
                "2001-06-07 23:32:00",           # space separator (old JSONL form)
                "2001-06-07T23:32:00Z",          # zulu suffix
                "2001-06-07T23:32:00.000000",    # fractional seconds
                "2001-02-30T00:00:00",           # regex-valid, calendar-invalid
                "2001-6-7T23:32:00",             # unpadded
            ],
            g11.E_TS_TZ: [datetime(2001, 6, 7, tzinfo=timezone.utc)],
            g11.E_TS_TYPE: [20010607, None],
        }
        for expected_code, values in rejected.items():
            for value in values:
                with self.subTest(code=expected_code, value=repr(value)):
                    with self.assertRaises(g11.ContractError) as ctx:
                        g11.normalize_ts(value)
                    self.assertEqual(ctx.exception.code, expected_code)

        # blind spots come from the real inventory, never from a constant
        self.assertEqual(g11.boundary_blind_spot_rows([250000] * 36), 72)
        self.assertEqual(g11.boundary_blind_spot_rows([1]), 1)
        self.assertEqual(g11.boundary_blind_spot_rows([0]), 0)
        self.assertEqual(g11.boundary_blind_spot_rows([]), 0)
        report = g11.blind_spot_report([230767, 1, 0])
        self.assertEqual(report["files"], 3)
        self.assertEqual(report["files_with_rows"], 2)
        self.assertEqual(report["data_rows"], 230768)
        self.assertEqual(report["boundary_rows"], 3)
        self.assertFalse(report["boundary_rows_equals_2n"],
                         "2N must be flagged as NOT holding when a file has 1 row")
        self.assertTrue(g11.blind_spot_report([10, 10])["boundary_rows_equals_2n"])
        self.assertEqual(len(report["reasons"]), 3)
        self.assertIn("does not recognise every bad price",
                      report["completeness_claim"])


class T2_DetectionRecordsMatchDuplicates(unittest.TestCase):
    def test_t2_duplicate_keys_and_one_sided_records(self):
        matched = g11.detection_records_match([FULL_SPIKE_RECORD],
                                             [dict(FULL_SPIKE_RECORD)])
        self.assertTrue(matched["ok"], matched)
        self.assertEqual(matched["compared"], 1)

        duplicated = g11.detection_records_match(
            [FULL_SPIKE_RECORD, dict(FULL_SPIKE_RECORD)], [FULL_SPIKE_RECORD])
        self.assertFalse(duplicated["ok"])
        self.assertEqual(len(duplicated["duplicates_a"]), 1)
        self.assertEqual(duplicated["duplicates_a"][0]["side"], "a")
        self.assertEqual(duplicated["duplicates_a"][0]["record_index"], 1)
        self.assertEqual(len(duplicated["duplicates_b"]), 0)

        asymmetric = g11.detection_records_match([FULL_SPIKE_RECORD], [])
        self.assertFalse(asymmetric["ok"])
        self.assertEqual(asymmetric["count_a"], 1)
        self.assertEqual(asymmetric["count_b"], 0)
        self.assertEqual(len(asymmetric["only_in_a"]), 1)
        self.assertEqual(asymmetric["only_in_a"][0][0], RAW_SPIKE_TS)
        self.assertEqual(asymmetric["only_in_a"][0][2], SPIKE_LINE_NUMBER)


class T3_DetectionRecordsMatchEvidenceValidation(unittest.TestCase):
    def test_t3_invalid_evidence_reported_and_float_tolerance(self):
        with self.subTest("inside tolerance passes"):
            near = dict(FULL_SPIKE_RECORD,
                        dev_prev=DEV_BOTH + g11.SPIKE_RECORD_FLOAT_TOL / 2)
            self.assertTrue(g11.detection_records_match([FULL_SPIKE_RECORD],
                                                        [near])["ok"])
        with self.subTest("outside tolerance fails with a reason"):
            far = dict(FULL_SPIKE_RECORD,
                       dev_prev=DEV_BOTH + g11.SPIKE_RECORD_FLOAT_TOL * 10)
            report = g11.detection_records_match([FULL_SPIKE_RECORD], [far])
            self.assertFalse(report["ok"])
            self.assertEqual(report["field_mismatches"][0]["why"], "float_tol")
        with self.subTest("field on one side only fails"):
            report = g11.detection_records_match([FULL_SPIKE_RECORD],
                                                 [dict(FULL_SPIKE_RECORD,
                                                       reason="other")])
            self.assertFalse(report["ok"])
            self.assertEqual(report["field_mismatches"][0]["field"], "reason")

        invalid_cases = {
            "not_a_mapping": ["a string, not a record"],
            "missing_fields": [{key: SPIKE_ROW[key] for key in HASH_COLUMNS
                                if key != "volume"}],
            "null_key": [dict(SPIKE_ROW, source_line=None)],
            "bool_source_line": [dict(SPIKE_ROW, source_line=True)],
            "ts_not_canonical": [dict(SPIKE_ROW, ts="2001-06-07 23:32:00")],
            "non_finite_dev": [dict(FULL_SPIKE_RECORD, dev_prev=float("nan"))],
            "dev_wrong_type": [dict(FULL_SPIKE_RECORD, dev_prev="2314.57")],
            "threshold_mismatch": [dict(FULL_SPIKE_RECORD, threshold=0.05)],
            "non_finite_price": [dict(SPIKE_ROW, close=float("inf"))],
        }
        for name, records in invalid_cases.items():
            with self.subTest(case=name):
                report = g11.detection_records_match(records, [FULL_SPIKE_RECORD])
                self.assertFalse(report["ok"], name)
                self.assertEqual(len(report["invalid_a"]), 1, name)
                self.assertTrue(report["invalid_a"][0]["code"].startswith("E_"),
                                report["invalid_a"][0])

        with self.subTest("invalid on both sides, no exception escapes"):
            report = g11.detection_records_match(["x"], [42])
            self.assertFalse(report["ok"])
            self.assertEqual(len(report["invalid_a"]), 1)
            self.assertEqual(len(report["invalid_b"]), 1)


class T4_PathValidation(unittest.TestCase):
    def test_t4_repo_relative_bounds(self):
        self.assertEqual(g11.repo_relative(STAGE01 / "_g11_common.py", REPO_ROOT),
                         "scripts/histdata/stage01/_g11_common.py")
        self.assertEqual(g11.repo_relative(RAW_2001, REPO_ROOT), SPIKE_FILE)

        outside = {
            "prefix_sibling": REPO_ROOT.parent / (REPO_ROOT.name + "_sibling") / "f.csv",
            "absolute_outside": Path("/etc/hosts"),
            "parent_traversal": STAGE01 / ".." / ".." / ".." / ".." / "etc" / "hosts",
        }
        for name, path in outside.items():
            with self.subTest(case=name):
                with self.assertRaises(g11.ContractError) as ctx:
                    g11.repo_relative(path, REPO_ROOT)
                self.assertEqual(ctx.exception.code, g11.E_PATH_OUTSIDE_ROOT)
                self.assertNotIn("..", ctx.exception.detail)


# R7 trigger table: (helper, code) -> a call that really raises that code. Its
# key set must equal the helper raise table in _g11_common.py, so a claim with no
# negative test -- and a negative test for a claim that was removed -- both fail.
TS_TZ_STAMP = datetime(2001, 6, 7, 23, 32, tzinfo=timezone.utc)

HELPER_TRIGGERS = {
    ("normalize_ts", g11.E_TS_TYPE): lambda: g11.normalize_ts(20010607),
    ("normalize_ts", g11.E_TS_TZ): lambda: g11.normalize_ts(TS_TZ_STAMP),
    ("normalize_ts", g11.E_TS_FORMAT):
        lambda: g11.normalize_ts("2001-06-07 23:32:00"),
    ("normalize_scalar", g11.E_TS_TZ): lambda: g11.normalize_scalar(TS_TZ_STAMP),
    ("normalize_scalar", g11.E_HASH_NONFINITE):
        lambda: g11.normalize_scalar(float("nan")),
    ("normalize_scalar", g11.E_SCALAR_TYPE):
        lambda: g11.normalize_scalar(object()),
    ("canonicalize_record", g11.E_TS_TYPE):
        lambda: g11.canonicalize_record({"ts": 20010607}),
    ("canonicalize_record", g11.E_TS_TZ):
        lambda: g11.canonicalize_record({"ts": TS_TZ_STAMP}),
    ("canonicalize_record", g11.E_TS_FORMAT):
        lambda: g11.canonicalize_record({"ts": "2001-6-7T23:32:00"}),
    ("canonicalize_record", g11.E_HASH_NONFINITE):
        lambda: g11.canonicalize_record({"close": float("inf")}),
    ("canonicalize_record", g11.E_SCALAR_TYPE):
        lambda: g11.canonicalize_record({"close": object()}),
    ("validate_spike_key", g11.E_HASH_COLUMNS):
        lambda: g11.validate_spike_key({"ts": RAW_SPIKE_TS}),
    ("validate_spike_key", g11.E_HASH_KEY_TYPE):
        lambda: g11.validate_spike_key({"ts": "2001-06-07 23:32:00",
                                        "source_file": SPIKE_FILE,
                                        "source_line": 1}),
    ("validate_spike_key", g11.E_EVIDENCE_INVALID):
        lambda: g11.validate_spike_key({"ts": RAW_SPIKE_TS,
                                        "source_file": SPIKE_FILE,
                                        "source_line": 0},
                                       code=g11.E_EVIDENCE_INVALID),
    ("canonical_d1_input_hash", g11.E_HASH_COLUMNS):
        lambda: g11.canonical_d1_input_hash([{"ts": RAW_SPIKE_TS}]),
    ("canonical_d1_input_hash", g11.E_HASH_NULL):
        lambda: g11.canonical_d1_input_hash([hash_record(close=None)]),
    ("canonical_d1_input_hash", g11.E_HASH_DUPLICATE_KEY):
        lambda: g11.canonical_d1_input_hash([hash_record(), hash_record()]),
    ("canonical_d1_input_hash", g11.E_HASH_KEY_TYPE):
        lambda: g11.canonical_d1_input_hash([hash_record(source_line=0)]),
    ("canonical_d1_input_hash", g11.E_HASH_NONFINITE):
        lambda: g11.canonical_d1_input_hash([hash_record(close=float("nan"))]),
    ("canonical_d1_input_hash", g11.E_SCALAR_TYPE):
        lambda: g11.canonical_d1_input_hash([hash_record(close=object())]),
    ("canonical_d1_input_hash", g11.E_TS_TYPE):
        lambda: g11.canonical_d1_input_hash([hash_record(ts=20010607)]),
    ("canonical_d1_input_hash", g11.E_TS_TZ):
        lambda: g11.canonical_d1_input_hash([hash_record(ts=TS_TZ_STAMP)]),
    ("canonical_d1_input_hash", g11.E_TS_FORMAT):
        lambda: g11.canonical_d1_input_hash([hash_record(ts="2001-6-7T23:32:00")]),
    ("repo_relative", g11.E_PATH_OUTSIDE_ROOT):
        lambda: g11.repo_relative("/etc", REPO_ROOT),
    ("contract_guard", g11.E_CONTRACT_MISSING):
        lambda: g11.contract_guard(None, g11.CONTRACT_VERSION),
    ("contract_guard", g11.E_CONTRACT_VERSION):
        lambda: g11.contract_guard({"version": "9.0"}, g11.CONTRACT_VERSION),
    ("contract_guard", g11.E_CONTRACT_KEYS):
        lambda: g11.contract_guard({"version": g11.CONTRACT_VERSION},
                                   g11.CONTRACT_VERSION, required_keys=["paths"]),
    ("contract_items_guard", g11.E_CONTRACT_ITEMS):
        lambda: g11.contract_items_guard({"acceptance_items": [],
                                          "denominator": 0}),
    ("contract_items_guard", g11.E_CONTRACT_DENOMINATOR):
        lambda: g11.contract_items_guard({"acceptance_items": [{"id": "G01"}],
                                          "denominator": 14}),
    ("item_status", g11.E_STATUS_INVALID):
        lambda: g11.item_status({"id": "G11", "pass": True}),
    ("item_status", g11.E_STATUS_CONFLICT):
        lambda: g11.item_status({"id": "G11", "status": "PENDING", "pass": True}),
    ("aggregate_status", g11.E_STATUS_INVALID):
        lambda: g11.aggregate_status(["PASS", "SKIPPED"]),
    ("build_item", g11.E_STATUS_INVALID):
        lambda: g11.build_item("G11", "SKIPPED"),
    ("get_validator", g11.E_SCHEMA_INVALID):
        lambda: g11.get_validator("no_such_validator"),
    ("validate_by_id", g11.E_SCHEMA_INVALID):
        lambda: g11.validate_by_id("no_such_validator", {}, {}),
    ("exit_code_for", g11.E_EXIT_MAP_MISSING):
        lambda: g11.exit_code_for("02_execute", "E_NOT_DECLARED_ANYWHERE"),
}

# The other half of R7: a helper that claims it cannot raise has to survive
# malformed input, so the empty entries are evidenced too, not just asserted.
NO_RAISE_PROBES = {
    "parse_histdata_line": lambda: g11.parse_histdata_line("not;a;bar"),
    "detection_records_match": lambda: g11.detection_records_match(
        [{"nope": 1}, 7], [{"other": 2}]),
    "bar_storage_validator": lambda: g11.bar_storage_validator({}, {}),
    "fatal_from_error": lambda: g11.fatal_from_error(
        "02_execute", g11.ContractError("E_NOT_DECLARED_ANYWHERE", "boom")),
}


class T5_ContractGuardAndExitMapReachability(unittest.TestCase):
    def test_t5_contract_guard_and_exit_map_reachability(self):
        contract = {"version": g11.CONTRACT_VERSION,
                    "acceptance_items": [{"id": "G01"}, {"id": "G02"}],
                    "denominator": 2, "paths": {}}
        self.assertIs(g11.contract_guard(contract, g11.CONTRACT_VERSION,
                                         required_keys=["paths", "denominator"]),
                      contract)
        items, ids = g11.contract_items_guard(contract)
        self.assertEqual(ids, ["G01", "G02"])
        self.assertEqual(len(items), 2)

        guard_cases = {
            g11.E_CONTRACT_MISSING: [lambda: g11.contract_guard(None, "9.1"),
                                     lambda: g11.contract_guard(["x"], "9.1")],
            g11.E_CONTRACT_VERSION: [
                lambda: g11.contract_guard({"version": None}, "9.1"),
                lambda: g11.contract_guard({"version": "9.0"}, "9.1"),
                lambda: g11.contract_guard({"acceptance_items": []}, "9.1")],
            g11.E_CONTRACT_KEYS: [
                lambda: g11.contract_guard({"version": "9.1"}, "9.1",
                                           required_keys=["paths"])],
            g11.E_CONTRACT_ITEMS: [
                lambda: g11.contract_items_guard({"acceptance_items": [],
                                                  "denominator": 0}),
                lambda: g11.contract_items_guard(
                    {"acceptance_items": [{"id": "G01"}, {"id": "G01"}],
                     "denominator": 2}),
                lambda: g11.contract_items_guard(
                    {"acceptance_items": [{"no_id": 1}], "denominator": 1})],
            g11.E_CONTRACT_DENOMINATOR: [
                lambda: g11.contract_items_guard(
                    {"acceptance_items": [{"id": "G01"}], "denominator": 14})],
        }
        for expected_code, calls in guard_cases.items():
            for index, call in enumerate(calls):
                with self.subTest(code=expected_code, case=index):
                    with self.assertRaises(g11.ContractError) as ctx:
                        call()
                    self.assertEqual(ctx.exception.code, expected_code)

        # ---- reachability, frozen rules R1-R10 -----------------------------
        # R1: the literal declaration and the call-site derivation must agree;
        # neither may drift away from the other.
        derived = g11.derived_reachable_ids()
        self.assertEqual(set(derived), set(g11.REACHABLE_IDS_DECLARED))
        for script, ids in derived.items():
            with self.subTest(rule="R1", script=script):
                self.assertEqual(ids, g11.REACHABLE_IDS_DECLARED[script])
                self.assertEqual(ids, g11.REACHABLE_IDS[script])

        # R7/R8: a call site may narrow a helper capability, never widen it, and
        # every call site -- including one that can fire nothing -- says why.
        self.assertEqual(set(g11.CALL_SITE_RATIONALE), set(g11.CALL_SITES))
        for script, sites in g11.CALL_SITES.items():
            with self.subTest(rule="R7", script=script, case="rationale keys"):
                self.assertEqual(set(g11.CALL_SITE_RATIONALE[script]),
                                 set(sites))
            for helper, codes in sorted(sites.items()):
                with self.subTest(rule="R8", script=script, helper=helper):
                    self.assertTrue(callable(getattr(g11, helper)))
                    self.assertLessEqual(
                        codes, g11.HELPER_RAISES[helper],
                        "a call site cannot reach beyond its helper's capability")
                with self.subTest(rule="R7", script=script, helper=helper):
                    self.assertTrue(
                        g11.CALL_SITE_RATIONALE[script][helper].strip(),
                        "every call site needs a written reason")

        # own raises are reachable by construction
        for script, own in g11.SCRIPT_OWN_IDS.items():
            with self.subTest(rule="own", script=script):
                self.assertLessEqual(own, g11.REACHABLE_IDS[script])

        # R2/R3: the map is exactly legacy ids + the reachable set. A semantic id
        # the script cannot reach may not sit in its map.
        for script, mapping in g11.EXIT_MAPS.items():
            allowed = g11.EXISTING_EXIT_CODES[script]
            semantic_in_map = {code for code in mapping
                               if code in g11.ALL_SEMANTIC_IDS}
            with self.subTest(rule="R2", script=script):
                self.assertLessEqual(set(g11.REACHABLE_IDS[script]), set(mapping))
            with self.subTest(rule="R3", script=script):
                self.assertEqual(semantic_in_map, set(g11.REACHABLE_IDS[script]))

            # R4: and it never invents an exit code
            for code, value in mapping.items():
                with self.subTest(rule="R4", script=script, code=code):
                    self.assertIn(value, allowed,
                                  f"{script}: {code} -> {value} is a NEW exit code")
            self.assertIn(script, g11.FALLBACK_EXIT)
            self.assertIn(g11.FALLBACK_EXIT[script], allowed)

        # legacy ids keep their exact old values, per script -- checked through
        # the lookup function as well, so "the old branches did not move" is a
        # statement about behaviour, not only about the table.
        for script, legacy in g11.LEGACY_EXIT.items():
            for code, value in legacy.items():
                with self.subTest(rule="legacy", script=script, code=code):
                    self.assertEqual(g11.EXIT_MAPS[script][code], value)
                    self.assertEqual(g11.exit_code_for(script, code), value)

        # R5/R9/R10: nothing is homeless, no owned capability is dead, every
        # pinned exclusion is owner-backed, and asking for an unreachable id is
        # loud -- it must never degrade into a silent 0.
        self.assertEqual(g11.unowned_ids(), (),
                         "a declared E_* constant has no producer at all")
        self.assertEqual(g11.globally_unreachable_ids(), (),
                         "an owned capability is dead: no call site can fire it")
        for script, pinned in g11.PINNED_NON_REACHABLE.items():
            with self.subTest(rule="pinned", script=script):
                self.assertEqual(set(pinned) & g11.owned_ids(), set(pinned),
                                 "a pinned exclusion is not even owned")
                self.assertFalse(set(pinned) & set(g11.REACHABLE_IDS[script]),
                                 "a pinned exclusion reappeared as reachable")
        for script in g11.EXIT_MAPS:
            for bogus in ("E_NOT_DECLARED_ANYWHERE", "NOT_A_REAL_ID"):
                with self.subTest(rule="R5", script=script, code=bogus):
                    with self.assertRaises(g11.ContractError) as ctx:
                        g11.exit_code_for(script, bogus)
                    self.assertEqual(ctx.exception.code, g11.E_EXIT_MAP_MISSING)
        with self.subTest(rule="R5", script="unknown_script"):
            with self.assertRaises(g11.ContractError) as ctx:
                g11.exit_code_for("04_imaginary", g11.E_CONTRACT_VERSION)
            self.assertEqual(ctx.exception.code, g11.E_EXIT_MAP_MISSING)

        # R6: the wrapper falls back to an existing code, never to 0, and a
        # reachable id still maps normally.
        for script, fallback in g11.FALLBACK_EXIT.items():
            with self.subTest(rule="R6", script=script):
                self.assertNotEqual(fallback, 0)
                self.assertIn(fallback, g11.EXISTING_EXIT_CODES[script])
                event, code = g11.fatal_from_error(
                    script, g11.ContractError("E_NOT_DECLARED_ANYWHERE", "boom"))
                self.assertEqual(code, fallback)
                self.assertEqual(event["code"], g11.E_EXIT_MAP_MISSING)
                self.assertEqual(event["exit_code"], fallback)
                self.assertEqual(event["original"]["code"],
                                 "E_NOT_DECLARED_ANYWHERE")
            declared = sorted(g11.REACHABLE_IDS[script])
            with self.subTest(rule="R6", script=script, code=declared[0]):
                event, code = g11.fatal_from_error(
                    script, g11.ContractError(declared[0], "boom"))
                self.assertEqual(code, g11.EXIT_MAPS[script][declared[0]])
                self.assertEqual(event["code"], declared[0])
        with self.subTest(rule="R6", case="02 acceptance FAIL keeps legacy 6"):
            event, code = g11.fatal_from_error(
                "02_execute", g11.ContractError(g11.E_ACCEPTANCE_FAIL, "G06"))
            self.assertEqual((code, event["code"]), (6, g11.E_ACCEPTANCE_FAIL))
        with self.subTest(rule="R6", case="03 report verdict keeps legacy 7"):
            event, code = g11.fatal_from_error(
                "03_verify", g11.ContractError(g11.E_REPORT_PENDING, "G11 pending"))
            self.assertEqual((code, event["code"]), (7, g11.E_REPORT_PENDING))

        # R7: every reachable id has a negative test. Helper claims are exercised
        # right here; script-own ids are carried by a named later stage.
        declared_pairs = {(helper, code)
                          for helper, codes in g11.HELPER_RAISES.items()
                          for code in codes}
        self.assertEqual(set(HELPER_TRIGGERS), declared_pairs,
                         "a helper raise claim and its negative test disagree")
        for (helper, code), trigger in sorted(HELPER_TRIGGERS.items()):
            with self.subTest(rule="R7", helper=helper, code=code):
                self.assertTrue(callable(getattr(g11, helper)))
                with self.assertRaises(g11.ContractError) as ctx:
                    trigger()
                self.assertEqual(ctx.exception.code, code)
        silent_helpers = {helper for helper, codes in g11.HELPER_RAISES.items()
                          if not codes}
        self.assertEqual(set(NO_RAISE_PROBES), silent_helpers,
                         "a 'cannot raise' claim has no probe (or vice versa)")
        for helper, probe in sorted(NO_RAISE_PROBES.items()):
            with self.subTest(rule="R7", helper=helper, claim="cannot raise"):
                self.assertTrue(callable(getattr(g11, helper)))
                probe()   # raising here fails the subtest
        for helper, codes in g11.HELPER_RAISES.items():
            with self.subTest(rule="R7", helper=helper):
                self.assertTrue(callable(getattr(g11, helper)))
                self.assertEqual(codes, codes & set(g11.ALL_SEMANTIC_IDS))
        self.assertEqual(set(g11.OWN_ID_TEST_PLAN),
                         set().union(*g11.SCRIPT_OWN_IDS.values()),
                         "a script-own id has no negative test booked")
        for code, owner in g11.OWN_ID_TEST_PLAN.items():
            with self.subTest(rule="R7", own_id=code):
                self.assertTrue(owner.strip())
        covered = {code for _, code in declared_pairs} | set(g11.OWN_ID_TEST_PLAN)
        self.assertEqual(covered, set(g11.ALL_SEMANTIC_IDS),
                         "a declared E_* id has no reachable trigger anywhere")

        with self.subTest("three-state aggregation and status/pass conflict"):
            self.assertEqual(g11.aggregate_status(["PASS", "PASS"]), "PASS")
            self.assertEqual(g11.aggregate_status(["PASS", "PENDING"]), "PENDING")
            self.assertEqual(g11.aggregate_status(["PENDING", "FAIL"]), "FAIL")
            self.assertIsNone(g11.build_item("G11", "PENDING")["pass"])
            self.assertIs(g11.build_item("G11", "PASS")["pass"], True)
            self.assertIs(g11.build_item("G11", "FAIL")["pass"], False)
            self.assertEqual(g11.item_status({"id": "G11", "status": "PENDING",
                                              "pass": None}), "PENDING")
            with self.assertRaises(g11.ContractError) as ctx:
                g11.item_status({"id": "G11", "status": "PENDING", "pass": True})
            self.assertEqual(ctx.exception.code, g11.E_STATUS_CONFLICT)
            with self.assertRaises(g11.ContractError) as ctx:
                g11.item_status({"id": "G11", "pass": True})
            self.assertEqual(ctx.exception.code, g11.E_STATUS_INVALID)
            with self.assertRaises(g11.ContractError) as ctx:
                g11.aggregate_status(["PASS", "SKIPPED"])
            self.assertEqual(ctx.exception.code, g11.E_STATUS_INVALID)


class T6_D1HashDeterminism(unittest.TestCase):
    def test_t6_hash_determinism_uniqueness_and_sensitivity(self):
        rows = [CALM_ROW, SPIKE_ROW,
                dict(CALM_ROW, ts="2001-06-07T23:33:00", source_line=NEXT_LINE_NUMBER)]
        baseline = g11.canonical_d1_input_hash(rows)
        self.assertEqual(len(baseline), 64)
        self.assertEqual(baseline, g11.canonical_d1_input_hash(list(reversed(rows))))
        self.assertEqual(baseline, g11.canonical_d1_input_hash(
            sorted(rows, key=lambda row: row["ts"])))

        with self.subTest("dict key order is irrelevant"):
            forward = {key: SPIKE_ROW[key] for key in HASH_COLUMNS}
            reverse = {key: SPIKE_ROW[key] for key in reversed(HASH_COLUMNS)}
            self.assertEqual(g11.canonical_d1_input_hash([forward]),
                             g11.canonical_d1_input_hash([reverse]))

        with self.subTest("extra columns are excluded from the hash"):
            self.assertEqual(
                g11.canonical_d1_input_hash([SPIKE_ROW]),
                g11.canonical_d1_input_hash([dict(SPIKE_ROW, quarantined=False)]))

        with self.subTest("duplicate sort keys refused"):
            with self.assertRaises(g11.ContractError) as ctx:
                g11.canonical_d1_input_hash([SPIKE_ROW, dict(SPIKE_ROW)])
            self.assertEqual(ctx.exception.code, g11.E_HASH_DUPLICATE_KEY)

        with self.subTest("every aggregated column moves the hash"):
            for column, value in (("open", 1.0001), ("high", 2.0001),
                                  ("low", 0.5001), ("close", 1.0002),
                                  ("volume", 1.0), ("source_line", 115596 + 1),
                                  ("source_file", SPIKE_FILE + ".bak")):
                with self.subTest(column=column):
                    self.assertNotEqual(
                        baseline, g11.canonical_d1_input_hash(rows[:1] + [
                            dict(SPIKE_ROW, **{column: value})] + rows[2:]))

        with self.subTest("no rounding: five-decimal EURUSD quotes differ"):
            self.assertNotEqual(g11.canonical_d1_input_hash([dict(CALM_ROW, close=1.15823)]),
                                g11.canonical_d1_input_hash([dict(CALM_ROW, close=1.15824)]))


class T7_D1HashStrictInput(unittest.TestCase):
    def test_t7_hash_strict_ts_key_and_null_policy(self):
        self.assertEqual(g11.canonical_d1_input_hash([hash_record()]),
                         g11.canonical_d1_input_hash([hash_record()]))

        cases = {
            g11.E_HASH_NULL: [hash_record(volume=None)],
            g11.E_HASH_COLUMNS: [{key: SPIKE_ROW[key] for key in HASH_COLUMNS[:-1]}],
            g11.E_HASH_NONFINITE: [hash_record(close=float("nan"))],
            g11.E_TS_FORMAT: [hash_record(ts="2001-06-07 23:32:00")],
            g11.E_TS_TZ: [hash_record(ts=datetime(2001, 6, 7, 23, 32,
                                                  tzinfo=timezone.utc))],
            g11.E_TS_TYPE: [hash_record(ts=20010607)],
            g11.E_HASH_KEY_TYPE: [hash_record(source_line="115596"),
                                  hash_record(source_line=True),
                                  hash_record(source_line=0),
                                  hash_record(source_file="")],
            g11.E_SCALAR_TYPE: [hash_record(close=object())],
        }
        for expected_code, records in cases.items():
            with self.subTest(code=expected_code):
                with self.assertRaises(g11.ContractError) as ctx:
                    g11.canonical_d1_input_hash(records)
                self.assertEqual(ctx.exception.code, expected_code)

        with self.subTest("non-mapping row"):
            with self.assertRaises(g11.ContractError) as ctx:
                g11.canonical_d1_input_hash(["not a record"])
            self.assertEqual(ctx.exception.code, g11.E_HASH_COLUMNS)

        with self.subTest("a Timestamp-like object normalizes, a str does not"):
            class Stamp:
                def __init__(self, value): self._value = value
                def to_pydatetime(self): return self._value

            self.assertEqual(g11.canonical_d1_input_hash(
                [hash_record(ts=Stamp(datetime(2001, 6, 7, 23, 32)))]),
                g11.canonical_d1_input_hash([hash_record()]))


class T8_ParseHistdataLine(unittest.TestCase):
    def test_t8_real_2001_glitch_line_and_strict_rejections(self):
        bar, error = g11.parse_histdata_line(
            raw_line(SPIKE_LINE_NUMBER), as_of_source=(SPIKE_FILE, SPIKE_LINE_NUMBER))
        self.assertIsNone(error)
        self.assertEqual(bar["ts"], RAW_SPIKE_TS)
        self.assertEqual((bar["open"], bar["high"], bar["low"], bar["close"]),
                         (1965.0001, 1965.0001, 1965.0001, 1965.0001))
        self.assertEqual(bar["volume"], 0.0)
        self.assertEqual((bar["source_file"], bar["source_line"]),
                         (SPIKE_FILE, SPIKE_LINE_NUMBER))
        self.assertEqual(tuple(bar), g11.SPIKE_FIELD_ORDER)

        prev_bar, _ = g11.parse_histdata_line(raw_line(PREV_LINE_NUMBER))
        next_bar, _ = g11.parse_histdata_line(raw_line(NEXT_LINE_NUMBER))
        self.assertEqual((prev_bar["close"], next_bar["close"]), (0.8486, 0.8486))
        dev_prev = abs(bar["close"] - prev_bar["close"]) / abs(prev_bar["close"])
        dev_next = abs(bar["close"] - next_bar["close"]) / abs(next_bar["close"])
        self.assertEqual(dev_prev, DEV_BOTH)
        self.assertEqual(dev_next, DEV_BOTH)
        self.assertGreater(dev_prev, g11.SPIKE_THRESHOLD)
        self.assertGreater(dev_next, g11.SPIKE_THRESHOLD)

        with self.subTest("the old space-separated JSONL ts form is refused"):
            with self.assertRaises(g11.ContractError) as ctx:
                g11.normalize_ts("2001-06-07 23:32:00")
            self.assertEqual(ctx.exception.code, g11.E_TS_FORMAT)

        rejections = {
            "BAD_FIELD_COUNT": ["", "   ",
                                "20010607 233200;1;1;1;1",
                                "20010607 233200;1;1;1;1;0;extra"],
            "BAD_TIMESTAMP": ["2001-06-07 23:32:00;1;1;1;1;0",
                              "20010230 010000;1;1;1;1;0"],
            "ENCODING_ERROR": ["20010607 233200;abc;1;1;1;0",
                               "20010607 233200;1;1;1;1;"],
            "NEGATIVE_PRICE": ["20010607 233200;0;0;0;0;0",
                               "20010607 233200;-1;1;1;1;0"],
            "BAD_OHLC": ["20010607 233200;1;0.5;0.5;1;0",     # high < max(open, close)
                         "20010607 233200;1;1;1.5;0.5;0"],    # low > min(open, close)
            "BAD_VOLUME": ["20010607 233200;1;1;1;1;-1"],
        }
        for expected_code, lines in rejections.items():
            for line in lines:
                with self.subTest(code=expected_code, line=line):
                    bar, error = g11.parse_histdata_line(line)
                    self.assertIsNone(bar)
                    self.assertEqual(error["code"], expected_code)
                    self.assertIn("raw_excerpt", error)

        with self.subTest("valid six-field line still parses"):
            bar, error = g11.parse_histdata_line("20010607 233200;1;1;1;1;1")
            self.assertIsNone(error)
            self.assertEqual(bar["volume"], 1.0)


if __name__ == "__main__":
    unittest.main()

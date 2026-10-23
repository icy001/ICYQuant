#!/usr/bin/env python3
"""T-B+C: the artifact contract Script 01 emits.

Stage A (test_g11_common.py) freezes the error-id reachability R1-R10. This file
freezes the other half, because the two can drift apart independently:

  * the contract version is 9.1 and comes from the shared freeze, not a literal
  * the denominator is the item count, and the 14 item ids keep their order
  * every count and every parsed path in the four documents follows the run's
    --pair/--year and the baseline set, so no document describes another run
  * crossref_report() fires on each kind of drift (it is not a rubber stamp)
  * the entry point keeps its old exit codes: 0 / 1 (baseline) / 4 (crossref)

Nothing here runs Scripts 02/03: the claim is about what 01 writes, which is
exactly what they read.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
STAGE_DIR = TESTS_DIR.parent / "stage01"
if str(STAGE_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE_DIR))

import _g11_common as g11  # noqa: E402
from _g11_common import CONTRACT_VERSION  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "g11_generate_artifacts", STAGE_DIR / "01_generate_artifacts.py")
art = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(art)

if art.HAS_YAML:
    import yaml  # type: ignore

# Frozen by Stage A/B+C: the ids and their order are part of the contract.
EXPECTED_ITEM_IDS = (
    "G01", "G02", "G03", "G04", "G05", "G06", "G07", "G08", "G09", "G10",
    "K01", "K02", "K03", "K04",
)

PARAM_SETS = (("xauusd", "2024"), ("eurusd", "2000-2026"))

BASELINE = {
    "schema_version": "histdata_v9_baseline_v1",
    "git": {"commit": "0" * 40, "branch": "test", "dirty": False},
    "input_dir": "data/real/histdata",
    "baselines": {"research/a.csv": {}, "research/b.csv": {}, "research/c.csv": {}},
}


def build(pair: str, year: str, baseline: dict | None = None,
          output_dir: str = "artifacts/unused") -> tuple:
    """Build the five documents the way main() does, without touching disk."""
    baseline = BASELINE if baseline is None else baseline
    return (
        art.build_manifest(baseline, output_dir, pair, year),
        art.build_schema(),
        art.build_ledger(baseline, pair, year),
        art.build_quality_contract(),
        art.build_validation_gates(baseline, pair, year),
    )


def report_for(pair: str, year: str, baseline: dict | None = None) -> dict:
    baseline = BASELINE if baseline is None else baseline
    return art.crossref_report(*build(pair, year, baseline),
                               len(baseline["baselines"]))


def load_doc(path: Path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text) if art.HAS_YAML else json.loads(text)


class ArtifactContractTest(unittest.TestCase):
    """T-B+C: version, denominator, params, cross-document references."""

    def test_version_is_the_shared_freeze(self) -> None:
        quality = art.build_quality_contract()
        self.assertEqual(CONTRACT_VERSION, "9.1")
        self.assertEqual(quality["version"], CONTRACT_VERSION,
                         "the emitted version must be the frozen constant")

    def test_denominator_is_item_count_and_ids_keep_order(self) -> None:
        quality = art.build_quality_contract()
        ids = tuple(item["id"] for item in quality["acceptance_items"])
        self.assertEqual(ids, EXPECTED_ITEM_IDS)
        self.assertEqual(quality["denominator"], len(quality["acceptance_items"]))
        self.assertEqual(quality["denominator"], len(EXPECTED_ITEM_IDS))
        self.assertIn(str(quality["denominator"]), quality["pass_rule"])
        # the module-level derivations must agree with the document
        self.assertEqual(art.ACCEPTANCE_ITEM_IDS, EXPECTED_ITEM_IDS)
        self.assertEqual(art.ACCEPTANCE_DENOMINATOR, len(EXPECTED_ITEM_IDS))

    def test_crossref_passes_for_both_parameter_sets(self) -> None:
        for pair, year in PARAM_SETS:
            with self.subTest(pair=pair, year=year):
                report = report_for(pair, year)
                failed = sorted(k for k, v in report["checks"].items() if not v)
                self.assertEqual(failed, [], f"crossref failed: {failed}")
                self.assertTrue(report["ok"])
                self.assertEqual(report["quality_version"], CONTRACT_VERSION)
                self.assertEqual(report["quality_denominator"],
                                 len(EXPECTED_ITEM_IDS))
                self.assertEqual(report["quality_item_ids"],
                                 list(EXPECTED_ITEM_IDS))

    def test_paths_follow_pair_year_across_documents(self) -> None:
        for pair, year in PARAM_SETS:
            stem = f"{pair}_{year}"
            manifest, _, ledger, _, gates = build(pair, year)
            manifest_names = [Path(p).name for p in manifest["outputs"]["parsed"]]
            ledger_names = [Path(p).name for entry in ledger["entries"]
                            for p in entry["produces"] if p.startswith("parsed/")]
            gate_names = {m for gate in gates["gates"] for text in gate["post"]
                          for m in art.REF_PARSED_RE.findall(text)}
            expected = [f"{stem}_bars.parquet", f"{stem}_errors.jsonl",
                        "parse_stats.json"]
            with self.subTest(pair=pair, year=year):
                self.assertEqual(manifest_names, expected)
                self.assertEqual(ledger_names, expected,
                                 "ledger must describe THIS run's parsed files")
                self.assertEqual(sorted(gate_names), sorted(expected),
                                 "gate post text must describe THIS run's parsed files")

    def test_documents_do_not_carry_another_runs_parameters(self) -> None:
        for pair, year in PARAM_SETS:
            other_pair = "xauusd" if pair != "xauusd" else "eurusd"
            other_year = "2024" if year != "2024" else "2000-2026"
            manifest, _, ledger, quality, gates = build(pair, year)
            blob = json.dumps([manifest, ledger, quality, gates])
            with self.subTest(pair=pair, year=year):
                self.assertNotIn(other_pair, blob)
                self.assertNotIn(other_year, blob)

    def test_crossref_fires_on_each_kind_of_drift(self) -> None:
        cases = {
            "ledger_paths": "ledger_parsed_refs_resolve_to_manifest",
            "gate_paths": "gate_parsed_refs_resolve_to_manifest",
            "gate_counts": "gate_count_refs_match_objects",
            "gate_ratio": "gate_ratio_refs_match_items",
            "baseline_count": "gate_baseline_count_refs_match",
            "version": "quality_version_is_frozen_version",
            "denominator": "quality_denominator_matches_items",
            "item_order": "quality_item_ids_match_authority",
            "ledger_entries": "ledger_entry_count_matches_scripts",
            "gate_targets": "gate_targets_match_scripts",
        }
        for kind, expected_check in sorted(cases.items()):
            manifest, schema, ledger, quality, gates = build("eurusd", "2000-2026")
            if kind == "ledger_paths":
                ledger["entries"][2]["produces"][0] = "parsed/xauusd_2024_bars.parquet"
            elif kind == "gate_paths":
                gates["gates"][2]["post"][0] = "parsed/xauusd_2024_bars.parquet non-empty"
            elif kind == "gate_counts":
                gates["gates"][1]["post"][2] = "ledger.json has 5 entries"
            elif kind == "gate_ratio":
                gates["gates"][3]["post"][2] = ("verify/coverage_audit.json: "
                                                "13/14 items re-evaluated")
            elif kind == "baseline_count":
                gates["gates"][0]["post"][0] = "all 4 baseline CSVs TRACKED"
            elif kind == "version":
                quality["version"] = "9.0"
            elif kind == "denominator":
                quality["denominator"] = 13
            elif kind == "item_order":
                quality["acceptance_items"] = list(
                    reversed(quality["acceptance_items"]))
            elif kind == "ledger_entries":
                ledger["entries"] = ledger["entries"][:3]
            elif kind == "gate_targets":
                gates["gates"][0]["applies_to"] = "00_something_else"
            report = art.crossref_report(manifest, schema, ledger, quality,
                                         gates, 3)
            with self.subTest(drift=kind):
                self.assertFalse(report["checks"][expected_check],
                                 f"{kind} was not caught by {expected_check}")
                self.assertFalse(report["ok"])

    def test_entry_point_keeps_its_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            out = tmpdir / "out"

            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = art.main(["--baseline", str(tmpdir / "absent.json"),
                               "--output-dir", str(out)])
            self.assertEqual(rc, 1)
            self.assertIn("baseline_missing", buf.getvalue())

            bad = tmpdir / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = art.main(["--baseline", str(bad), "--output-dir", str(out)])
            self.assertEqual(rc, 1)
            self.assertIn("baseline_malformed", buf.getvalue())

            good = tmpdir / "baseline.json"
            good.write_text(json.dumps(BASELINE), encoding="utf-8")
            argv = ["--baseline", str(good), "--output-dir", str(out),
                    "--repo-root", str(tmpdir),
                    "--pair", "eurusd", "--year", "2000-2026"]
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = art.main(argv)
            self.assertEqual(rc, 0)
            self.assertIn('"ok": true', buf.getvalue())

            # the old crossref failure path: non-zero, same error id, and the
            # failing check named so the operator does not have to guess
            original = art.build_ledger

            def broken_ledger(baseline: dict, pair: str, year: str) -> dict:
                ledger = original(baseline, pair, year)
                ledger["entries"][2]["produces"][0] = "parsed/xauusd_2024_bars.parquet"
                return ledger

            art.build_ledger = broken_ledger
            try:
                with contextlib.redirect_stdout(io.StringIO()) as buf:
                    rc = art.main(argv)
            finally:
                art.build_ledger = original
            self.assertEqual(rc, 4)
            self.assertIn("crossref_broken", buf.getvalue())
            self.assertIn("ledger_parsed_refs_resolve_to_manifest",
                          buf.getvalue())

    def test_written_documents_are_self_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            baseline_path = tmpdir / "baseline.json"
            baseline_path.write_text(json.dumps(BASELINE), encoding="utf-8")
            out = tmpdir / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = art.main(["--baseline", str(baseline_path),
                               "--output-dir", str(out),
                               "--repo-root", str(tmpdir),
                               "--pair", "eurusd", "--year", "2000-2026"])
            self.assertEqual(rc, 0)

            docs = [load_doc(out / name) for name in
                    ("manifest.yaml", "schema.json", "ledger.json",
                     "quality_contract.yaml", "validation_gates.yaml")]
            report = art.crossref_report(*docs, len(BASELINE["baselines"]))
            self.assertTrue(report["ok"], report["checks"])
            self.assertEqual(docs[3]["version"], CONTRACT_VERSION)
            self.assertEqual(docs[3]["denominator"], len(EXPECTED_ITEM_IDS))

    def test_01_really_calls_the_declared_call_sites(self) -> None:
        """The frozen contract names 01's call sites, so the source must contain
        them: an entry describing code that does not exist would make the
        reachability table fiction and quietly invalidate R1-R10.

        `exit_code_for` is reached through `fatal_from_error` (the shared wrapper
        tail calls it), so the direct-call check covers the other four.
        """
        source = (STAGE_DIR / "01_generate_artifacts.py").read_text(encoding="utf-8")
        called = {node.func.id for node in ast.walk(ast.parse(source))
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        declared = set(g11.CALL_SITES["01_generate_artifacts"])
        self.assertEqual(declared, {"contract_guard", "contract_items_guard",
                                    "repo_relative", "exit_code_for",
                                    "fatal_from_error"})
        for helper in sorted(declared - {"exit_code_for"}):
            with self.subTest(helper=helper):
                self.assertIn(helper, called,
                              f"{helper} is declared for 01 but never called")
        self.assertIn("fatal_from_error", called)
        # and every id those call sites can fire is declared reachable for 01
        self.assertLessEqual(
            g11.CALL_SITES["01_generate_artifacts"]["repo_relative"],
            g11.REACHABLE_IDS["01_generate_artifacts"])

    def test_output_dir_outside_the_repo_is_rejected(self) -> None:
        """The one path 01 takes from outside must stay inside the repo.

        This is 01's only directly reachable semantic id per the frozen contract,
        so it needs its negative test like every other reachable id.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            baseline_path = tmpdir / "baseline.json"
            baseline_path.write_text(json.dumps(BASELINE), encoding="utf-8")
            outside = tmpdir / "outside"
            # no --repo-root: the boundary is the real repository, and a temp dir
            # is outside it
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = art.main(["--baseline", str(baseline_path),
                               "--output-dir", str(outside)])
            self.assertEqual(rc, 4)
            self.assertIn("E_PATH_OUTSIDE_ROOT", buf.getvalue())
            self.assertFalse(outside.exists(), "nothing is written outside the repo")

    def test_self_check_failure_is_loud_and_falls_back(self) -> None:
        """01 re-validates the contract it just assembled.

        Those call sites cannot fire in a healthy build (the frozen contract says
        so), so this test breaks the builder on purpose. Each failure must be
        reported, and because the ids are deliberately absent from EXIT_MAP_01 the
        wrapper must say E_EXIT_MAP_MISSING and fall back to 4 -- never 0, and
        never a silent pass.
        """
        broken = {
            "version mismatch": ({"version": "0.0"}, "E_CONTRACT_VERSION"),
            "missing required key": ({"acceptance_items": None}, "E_CONTRACT_KEYS"),
            "denominator mismatch": ({"denominator": len(EXPECTED_ITEM_IDS) + 1},
                                     "E_CONTRACT_DENOMINATOR"),
        }
        original = art.build_quality_contract
        for label, (patch, expected_code) in sorted(broken.items()):
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = Path(tmp)
                baseline_path = tmpdir / "baseline.json"
                baseline_path.write_text(json.dumps(BASELINE), encoding="utf-8")
                out = tmpdir / "out"

                def broken_contract(patch=patch):
                    contract = dict(original())
                    for key, value in patch.items():
                        if value is None:
                            contract.pop(key, None)
                        else:
                            contract[key] = value
                    return contract

                art.build_quality_contract = broken_contract
                try:
                    with contextlib.redirect_stdout(io.StringIO()) as buf:
                        rc = art.main(["--baseline", str(baseline_path),
                                       "--output-dir", str(out),
                                       "--repo-root", str(tmpdir)])
                finally:
                    art.build_quality_contract = original
                text = buf.getvalue()
                with self.subTest(case=label, code=expected_code):
                    self.assertEqual(rc, 4)
                    self.assertIn("E_EXIT_MAP_MISSING", text)
                    self.assertIn(expected_code, text)
                    self.assertFalse((out / "quality_contract.yaml").exists(),
                                     "nothing is written after a failed self-check")


if __name__ == "__main__":
    unittest.main()

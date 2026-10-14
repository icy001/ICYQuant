#!/usr/bin/env python3
"""B+C step 2: Script 03's INDEPENDENT parsed-reference audit.

Script 01 cross-checks the four documents while it writes them. Script 03 has to
reach the same conclusion on its own, because 01 is the producer: a document
edited after the fact, or written by some other process, satisfies 01 just as
well. These tests freeze that second implementation.

    T09  authority set derived from manifest.yaml; both documented reference
         forms (artifacts-dir-relative and the manifest's own path) resolve
    T10  a wrong directory prefix is reported, not waved through
    T11  a well-formed reference to an undeclared file names the missing target
    T12  traversal, `.`/`..` detours, empty segments, backslashes and absolute
         paths are never accepted -- and a string-prefix test would have taken
         the first four
    T13  a duplicate citation is surfaced without failing; dropping the
         references entirely fails
    T14  the scan covers the whole document, not a list of known fields
    T15  end to end: intact artifacts PASS (0), a tampered ledger/gates FAIL (7)
         with file/pointer/reference recorded, restoring them PASSes again, the
         pre-existing checks keep firing on their own kinds, and the pre-existing
         exit codes (1 missing dir, 7 missing manifest) hold
    T16  03 does not import or reuse 01's crossref_report() -- one shared
         implementation would share its blind spots
    T17  resolve_parsed_reference()'s own contract: the reason codes reached by
         direct call, including the one the document scan cannot produce

Nothing here runs Scripts 00/02; T15 builds its own artifact tree.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
STAGE_DIR = TESTS_DIR.parent / "stage01"
if str(STAGE_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE_DIR))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY_SOURCE = STAGE_DIR / "03_verify.py"
verify = _load_module(VERIFY_SOURCE, "g11_verify")
art = _load_module(STAGE_DIR / "01_generate_artifacts.py", "g11_generate_artifacts")

OUT_DIR = "artifacts/histdata_v9"

# The three parsed outputs of the run described by MANIFEST below. Written out
# rather than imported from 01: the verifier's expectation must not be built by
# the code it verifies.
DECLARED = ("parsed/eurusd_2000-2026_bars.parquet",
            "parsed/eurusd_2000-2026_errors.jsonl",
            "parsed/parse_stats.json")

MANIFEST = {
    "schema_version": "histdata_v9_manifest_v1",
    "outputs": {
        "snapshot": [f"{OUT_DIR}/snapshot/baseline.json"],
        "contract": [f"{OUT_DIR}/manifest.yaml", f"{OUT_DIR}/validation_gates.yaml"],
        "parsed": [f"{OUT_DIR}/{ref}" for ref in DECLARED],
        "acceptance": [f"{OUT_DIR}/acceptance/run_acceptance.json"],
        "verify": [f"{OUT_DIR}/verify/final_report.json"],
    },
}

# The 14 acceptance ids, restated here so T15's fixture is not built by the code
# under test.
ACCEPTANCE_IDS = ("G01", "G02", "G03", "G04", "G05", "G06", "G07", "G08", "G09",
                  "G10", "K01", "K02", "K03", "K04")


def ledger_doc(parsed_refs=None, extra_field=None):
    entry = {"seq": 2, "script": "02_execute", "action": "parse_validate_accept",
             "produces": list(DECLARED if parsed_refs is None else parsed_refs)}
    if extra_field:
        entry.update(extra_field)
    return {"schema_version": "histdata_v9_ledger_v1", "entries": [
        {"seq": 0, "script": "00_baseline_snapshot",
         "produces": ["snapshot/baseline.json", "snapshot/csv_hashes.json"]},
        entry,
    ]}


def gates_doc(parsed_refs=None):
    refs = DECLARED if parsed_refs is None else parsed_refs
    return {"schema_version": "histdata_v9_validation_gates_v1", "gates": [
        {"id": "G02_executed", "applies_to": "02_execute",
         "pre": ["manifest.yaml", "schema.json"],
         "post": [f"{ref} exists" for ref in refs]},
    ]}


def audit(ledger=None, gates=None, manifest=None, out_dir=OUT_DIR):
    return verify.audit_parsed_references(
        MANIFEST if manifest is None else manifest,
        {"ledger.json": ledger_doc() if ledger is None else ledger,
         "validation_gates.yaml": gates_doc() if gates is None else gates},
        out_dir)


def issues_of(report, kind):
    return [i for i in report["issues"] if i["kind"] == kind]


class T09_DeclaredAuthorityAndReferenceForms(unittest.TestCase):
    def test_t09_authority_set_and_both_reference_forms(self):
        report = audit()
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["declared"], sorted(DECLARED))
        self.assertEqual(report["references"], sorted(DECLARED))
        self.assertEqual(report["duplicates"], [])

        # the manifest's own path form names the same file
        qualified = f"{OUT_DIR}/{DECLARED[2]}"
        with self.subTest(form="manifest_path"):
            report = audit(ledger=ledger_doc([DECLARED[2]]),
                           gates=gates_doc([qualified]))
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(report["references"],
                             sorted([DECLARED[2], qualified]))

        # an absolute --output-dir keys the same files as a relative one
        absolute_manifest = {"outputs": {
            "parsed": [f"/repo/{OUT_DIR}/{ref}" for ref in DECLARED]}}
        with self.subTest(form="absolute_output_dir"):
            report = audit(manifest=absolute_manifest)
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(report["declared"], sorted(DECLARED))


class T10_WrongDirectoryPrefix(unittest.TestCase):
    def test_t10_wrong_prefix_is_reported(self):
        cases = (
            ("ledger.json", f"backup/{DECLARED[2]}"),
            ("ledger.json", f"{OUT_DIR}_old/{DECLARED[2]}"),
            ("validation_gates.yaml", f"backup/old/{DECLARED[2]}"),
        )
        for file, reference in cases:
            report = (audit(ledger=ledger_doc([reference]))
                      if file == "ledger.json"
                      else audit(gates=gates_doc([reference])))
            with self.subTest(file=file, reference=reference):
                found = [i for i in report["issues"]
                         if i["reference"] == reference]
                self.assertEqual(len(found), 1, report["issues"])
                self.assertEqual(found[0]["kind"], "parsed_ref_outside_parsed_dir")
                self.assertEqual(found[0]["file"], file)
                self.assertIsNone(found[0]["missing_target"])
                self.assertFalse(report["ok"])


class T11_MissingTarget(unittest.TestCase):
    def test_t11_undeclared_target_is_named(self):
        stale = "parsed/xauusd_2024_bars.parquet"
        report = audit(ledger=ledger_doc([stale] + list(DECLARED)))
        found = issues_of(report, "parsed_ref_missing_target")
        self.assertEqual(len(found), 1, report["issues"])
        self.assertEqual(found[0]["file"], "ledger.json")
        self.assertEqual(found[0]["reference"], stale)
        self.assertEqual(found[0]["missing_target"], stale)
        self.assertTrue(found[0]["pointer"].startswith("/entries/"),
                        found[0]["pointer"])
        self.assertFalse(report["ok"])


class T12_TraversalIsNeverAccepted(unittest.TestCase):
    def test_t12_traversal_detour_and_absolute_paths(self):
        cases = (
            ("parsed/../../etc/passwd", "parsed_ref_escapes_root"),
            (f"{OUT_DIR}/parsed/../../../etc/passwd", "parsed_ref_escapes_root"),
            ("parsed/../parsed/parse_stats.json", "parsed_ref_not_canonical"),
            ("parsed/./parse_stats.json", "parsed_ref_not_canonical"),
            ("parsed//parse_stats.json", "parsed_ref_not_canonical"),
            ("parsed\\parse_stats.json", "parsed_ref_not_canonical"),
            ("/etc/histdata/parsed/parse_stats.json", "parsed_ref_absolute"),
        )
        for reference, kind in cases:
            report = audit(gates=gates_doc([reference]))
            with self.subTest(reference=reference):
                found = [i for i in report["issues"]
                         if i["reference"] == reference]
                self.assertEqual(len(found), 1, report["issues"])
                self.assertEqual(found[0]["kind"], kind)
                self.assertFalse(report["ok"])

        # the point of walking the path instead of comparing prefixes: every one
        # of these satisfies a starts-with test and is refused anyway
        prefix_would_accept = ("parsed/../../etc/passwd",
                               "parsed/../parsed/parse_stats.json",
                               "parsed/./parse_stats.json",
                               "parsed//parse_stats.json")
        for reference in prefix_would_accept:
            with self.subTest(prefix_test=reference):
                self.assertTrue(reference.startswith("parsed/"))
                self.assertFalse(audit(gates=gates_doc([reference]))["ok"])


class T13_DuplicatesAndAbsentReferences(unittest.TestCase):
    def test_t13_duplicates_surfaced_and_absence_fails(self):
        duplicate = list(DECLARED) + [DECLARED[2]]
        report = audit(ledger=ledger_doc(duplicate))
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["duplicates"], [f"ledger.json:{DECLARED[2]}"])
        self.assertEqual(report["references"], sorted(DECLARED))

        # the same file cited by two documents is normal, not a duplicate
        report = audit(ledger=ledger_doc([DECLARED[2]]),
                       gates=gates_doc([DECLARED[2]]))
        self.assertEqual(report["duplicates"], [])
        self.assertTrue(report["ok"], report["issues"])

        # removing the references must not be a way to pass
        report = audit(ledger=ledger_doc(["snapshot/csv_hashes.json"]))
        found = issues_of(report, "parsed_refs_absent")
        self.assertEqual([i["file"] for i in found], ["ledger.json"])
        self.assertFalse(report["ok"])

        report = audit(gates=gates_doc([]))
        self.assertEqual([i["kind"] for i in report["issues"]],
                         ["parsed_refs_absent"])
        self.assertEqual(report["issues"][0]["file"], "validation_gates.yaml")


class T14_WholeDocumentScan(unittest.TestCase):
    def test_t14_reference_outside_the_known_fields_is_found(self):
        stale = "parsed/xauusd_2024_bars.parquet"
        report = audit(ledger=ledger_doc(extra_field={"precondition": stale}))
        found = issues_of(report, "parsed_ref_missing_target")
        self.assertEqual(len(found), 1, report["issues"])
        self.assertEqual(found[0]["pointer"], "/entries/1/precondition")
        self.assertEqual(found[0]["reference"], stale)
        self.assertFalse(report["ok"])

        # gate `pre` lists are scanned too, and the pointer names the exact spot
        gates = {"schema_version": "histdata_v9_validation_gates_v1", "gates": [
            {"id": "G02_executed", "applies_to": "02_execute",
             "pre": [f"{stale} exists"],
             "post": [f"{ref} exists" for ref in DECLARED]}]}
        report = audit(gates=gates)
        found = issues_of(report, "parsed_ref_missing_target")
        self.assertEqual([i["pointer"] for i in found], ["/gates/0/pre/0"])
        self.assertFalse(report["ok"])


class T15_EndToEndTamperProbesAndExitCodes(unittest.TestCase):
    """The CLI-level claim: intact artifacts pass, edited artifacts do not."""

    def _build_tree(self, tmpdir: Path) -> Path:
        """Let Script 1 write the five contract documents, then supply the
        outputs Scripts 0/2 would have written, so 03 can run for real."""
        baseline_path = tmpdir / "baseline.json"
        baseline_path.write_text(json.dumps({
            "schema_version": "histdata_v9_baseline_v1",
            "git": {"commit": None, "branch": "test", "dirty": False},
            "input_dir": "data/real/histdata",
            "baselines": {"research/a.csv": {}, "research/b.csv": {},
                          "research/c.csv": {}},
        }), encoding="utf-8")

        out = tmpdir / "out"
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = art.main(["--baseline", str(baseline_path),
                           "--output-dir", str(out), "--repo-root", str(tmpdir),
                           "--pair", "eurusd", "--year", "2000-2026"])
        self.assertEqual(rc, 0, buf.getvalue())

        manifest = verify.load_any(out / "manifest.yaml")
        for category, paths in manifest["outputs"].items():
            if category in ("contract", "verify"):
                continue
            for raw in paths:
                target = Path(raw)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_text("", encoding="utf-8")

        # Script 0's snapshot: one tracked file whose hash matches, and a
        # baseline whose commit is compared against this temp dir (not a git
        # repo -> `git rev-parse` fails -> both sides are None), so no drift.
        tracked = tmpdir / "data" / "a.csv"
        tracked.parent.mkdir(parents=True, exist_ok=True)
        tracked.write_text("ts,open\n", encoding="utf-8")
        (out / "snapshot" / "csv_hashes.json").write_text(
            json.dumps({"data/a.csv": verify.sha256_file(tracked)}),
            encoding="utf-8")
        (out / "snapshot" / "baseline.json").write_text(
            json.dumps({"git": {"commit": None}}), encoding="utf-8")
        (out / "acceptance" / "run_acceptance.json").write_text(json.dumps({
            "denominator": len(ACCEPTANCE_IDS),
            "items": [{"id": i, "status": "PASS"} for i in ACCEPTANCE_IDS],
            "pass_count": len(ACCEPTANCE_IDS), "fail_count": 0,
            "overall": "PASS"}), encoding="utf-8")
        (out / "acceptance" / "coverage_audit.json").write_text(
            json.dumps({"complete": True, "missing": []}), encoding="utf-8")
        return out

    def _run(self, out: Path, tmpdir: Path) -> tuple:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = verify.main(["--output-dir", str(out), "--repo-root", str(tmpdir)])
        report = json.loads((out / "verify" / "interface_check.json").read_text(
            encoding="utf-8"))
        return rc, report

    def test_t15_end_to_end_tamper_probes_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            out = self._build_tree(tmpdir)

            rc, report = self._run(out, tmpdir)
            self.assertEqual(rc, 0, report["issues"])
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(report["parsed_refs"]["declared"], sorted(DECLARED))
            self.assertEqual(report["parsed_refs"]["references"],
                             sorted(DECLARED))

            probes = (
                ("ledger.json", "parsed/parse_stats.json",
                 "parsed/xauusd_2024_parse_stats.json",
                 "parsed_ref_missing_target"),
                ("validation_gates.yaml", "parsed/parse_stats.json",
                 "backup/parsed/parse_stats.json",
                 "parsed_ref_outside_parsed_dir"),
                ("validation_gates.yaml", "parsed/parse_stats.json",
                 "parsed/../../parse_stats.json",
                 "parsed_ref_escapes_root"),
                ("ledger.json", "parsed/parse_stats.json",
                 "parsed/../parsed/parse_stats.json",
                 "parsed_ref_not_canonical"),
            )
            for name, old, new, kind in probes:
                path = out / name
                original = path.read_text(encoding="utf-8")
                self.assertIn(old, original, f"{name} does not cite {old}")
                path.write_text(original.replace(old, new), encoding="utf-8")

                rc, report = self._run(out, tmpdir)
                with self.subTest(file=name, reference=new):
                    self.assertEqual(rc, 7)
                    self.assertFalse(report["ok"])
                    found = [i for i in report["issues"]
                             if i["kind"] == kind and i["file"] == name]
                    self.assertEqual(len(found), 1, report["issues"])
                    self.assertEqual(found[0]["reference"], new)
                    self.assertTrue(found[0]["pointer"], found[0])
                    if kind == "parsed_ref_missing_target":
                        self.assertEqual(found[0]["missing_target"], new)
                    else:
                        self.assertIsNone(found[0]["missing_target"])

                path.write_text(original, encoding="utf-8")
                rc, report = self._run(out, tmpdir)
                self.assertEqual(rc, 0, report["issues"])

            # a duplicate citation is recorded but is not, by itself, a failure
            path = out / "ledger.json"
            original = path.read_text(encoding="utf-8")
            needle = f'"{DECLARED[2]}",'
            self.assertIn(needle, original)
            path.write_text(original.replace(
                needle, f"{needle}\n        \"{DECLARED[2]}\",", 1), encoding="utf-8")
            rc, report = self._run(out, tmpdir)
            self.assertEqual(rc, 0, report["issues"])
            self.assertEqual(report["parsed_refs"]["duplicates"],
                             [f"ledger.json:{DECLARED[2]}"])
            path.write_text(original, encoding="utf-8")
            self.assertEqual(self._run(out, tmpdir)[0], 0)

            # check_interfaces really consults the audit: patching it changes
            # the verdict, so a defined-but-unwired helper cannot hide here
            sentinel = {"ok": False, "issues": [{"kind": "sentinel"}],
                        "declared": [], "references": [], "duplicates": []}
            original_audit = verify.audit_parsed_references
            verify.audit_parsed_references = lambda *a, **kw: sentinel
            try:
                direct = verify.check_interfaces(out)
            finally:
                verify.audit_parsed_references = original_audit
            self.assertFalse(direct["ok"])
            self.assertIn({"kind": "sentinel"}, direct["issues"])

            # the pre-existing independent checks still fire on their own kinds
            quality = out / "quality_contract.yaml"
            original = quality.read_text(encoding="utf-8")
            self.assertIn("denominator", original)
            quality.write_text(re.sub(r'denominator(["\']?\s*:\s*)14',
                                     r"denominator\g<1>13", original),
                               encoding="utf-8")
            with self.subTest(legacy="bad_quality_denominator"):
                direct = verify.check_interfaces(out)
                self.assertFalse(direct["ok"])
                self.assertIn("bad_quality_denominator",
                              [i["kind"] for i in direct["issues"]])
            quality.write_text(original, encoding="utf-8")

            hashes_path = out / "snapshot" / "csv_hashes.json"
            hashes_text = hashes_path.read_text(encoding="utf-8")
            hashes = json.loads(hashes_text)
            hashes["data/a.csv"] = "deadbeef"
            hashes_path.write_text(json.dumps(hashes), encoding="utf-8")
            with self.subTest(legacy="bad_hash_format"):
                direct = verify.check_interfaces(out)
                self.assertFalse(direct["ok"])
                self.assertIn("bad_hash_format",
                              [i["kind"] for i in direct["issues"]])

            # every tamper undone: the intact tree is clean again
            hashes_path.write_text(hashes_text, encoding="utf-8")
            self.assertTrue(verify.check_interfaces(out)["ok"])

            # pre-existing exit codes: 1 for a missing output dir, 7 for a
            # directory that exists but holds no manifest
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = verify.main(["--output-dir", str(tmpdir / "absent")])
            self.assertEqual(rc, 1)
            self.assertIn("output_dir_missing", buf.getvalue())

            empty = tmpdir / "empty"
            empty.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                rc = verify.main(["--output-dir", str(empty),
                                  "--repo-root", str(tmpdir)])
            self.assertEqual(rc, 7)
            final = json.loads((empty / "verify" / "final_report.json").read_text(
                encoding="utf-8"))
            self.assertEqual(final["overall"], "FAIL")
            self.assertEqual(final["details"]["interfaces"]["reason"],
                             "manifest_missing")


class T16_IndependentImplementation(unittest.TestCase):
    def test_t16_03_does_not_reuse_01_crossref(self):
        tree = ast.parse(VERIFY_SOURCE.read_text(encoding="utf-8"))

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        with self.subTest(check="imports"):
            self.assertEqual(
                imported & {"_g11_common", "01_generate_artifacts",
                            "g11_generate_artifacts"}, set())

        names = {node.id for node in ast.walk(tree)
                 if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        names |= {node.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)}
        with self.subTest(check="no shared implementation"):
            self.assertNotIn("crossref_report", names)
        self.assertFalse(hasattr(verify, "crossref_report"))

        # its authority is the manifest it read: a manifest that declares
        # nothing authorises nothing, so every citation in both documents loses
        # its target instead of passing by default
        report = audit(manifest={"outputs": {"parsed": []}})
        self.assertFalse(report["ok"])
        self.assertEqual(report["declared"], [])
        self.assertEqual(len(issues_of(report, "parsed_ref_missing_target")),
                         2 * len(DECLARED))


class T17_ResolverHelperContract(unittest.TestCase):
    """The reason codes resolve_parsed_reference() returns, by direct call.

    `parsed_ref_empty` cannot arise from the document scan -- a scanned token
    always has at least one character -- so it is covered here, as the helper's
    own contract, instead of being left as a branch nobody can reach: the same
    split Stage A froze between a helper's capability and a call site's
    reachability.
    """

    def test_t17_empty_tokens_and_the_not_a_reference_rule(self):
        for raw in ("", "   ", "\t"):
            with self.subTest(raw=raw):
                self.assertEqual(verify.resolve_parsed_reference(raw, OUT_DIR),
                                 (None, "parsed_ref_empty"))

        # the parsed dir with nothing under it names no file
        self.assertEqual(verify.resolve_parsed_reference("parsed/", OUT_DIR),
                         (None, "parsed_ref_not_canonical"))

        # the real gate text mentions `parsed` without referencing a file
        gate_text = ("manifest.yaml has outputs."
                     "{snapshot,contract,parsed,acceptance,verify}")
        self.assertEqual(verify.parsed_reference_tokens(gate_text), [])
        self.assertEqual(verify.parsed_reference_tokens("parsed/x.json"),
                         ["parsed/x.json"])
        self.assertEqual(verify.parsed_reference_tokens(
            "then parsed/../x.json next"), ["parsed/../x.json"])


if __name__ == "__main__":
    unittest.main()

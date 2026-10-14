#!/usr/bin/env python3
"""Shared pure helpers for the v9 histdata G11 spike-quarantine work.

Scope rule
----------
The spike *detector* is deliberately NOT here. `02_execute.py`
(`self_detect_spikes`), `03_verify.py` (`independent_detect_spikes`) and the
tests each implement detection separately, so that a mistake in one cannot mask
a mistake in another. This module holds only what two or more of them must
agree on bit-for-bit:

  - the threshold and the spike record field order
  - the canonical D1-input hash spec
  - the raw-line parser used for source tracing
  - the record-comparison helper (a *comparator*, never a detector)
  - the contract guard and the explicit semantic-id -> exit-code maps
  - the three-state (PASS / FAIL / PENDING) aggregator
  - the Bar_Storage schema validator and the blind-spot arithmetic

Import policy
-------------
Standard library only. This module must stay importable where pandas / pyarrow
/ PyYAML are absent, because `00_baseline_snapshot.py` records those packages as
optional.

Exit codes
----------
Nothing here exits and nothing here returns an exit code. `contract_guard()`
raises `ContractError` carrying a stable semantic id (``E_*``). Each script's
entry point catches it and translates it with ITS OWN map from this module:

    EXIT_MAP_00 / EXIT_MAP_01 / EXIT_MAP_02 / EXIT_MAP_03 / EXIT_MAP_F

The maps are data, not behaviour, so a test can assert that (a) every value is
one of the codes that script already used before this change, and (b) each map
carries exactly the ids that script can really reach -- see ``REACHABLE_IDS`` and
the frozen rules R1-R10 in the reachability block below. Covering the whole
``E_*`` namespace in every map was rejected: an entry that can never fire cannot
be told apart from a wrong one. What a helper *can* raise (``HELPER_RAISES``) is
kept apart from what a script *does* reach (``CALL_SITES``): calling a guard is
not the same as being able to fail it, which is why the contract layer's producer
carries no contract ids. An id no script reaches raises ``E_EXIT_MAP_MISSING`` on
lookup and the wrapper falls back to that script's contract-error code -- never
to 0. Legacy error ids (``manifest_missing``, ``crossref_broken``, ...) are
carried unchanged: renaming them would itself be a behaviour change.

Contract versioning
-------------------
`CONTRACT_VERSION` is 9.1 and `contract_guard()` has NO default for
`expected_version`, so a caller cannot drift into "validate nothing" by
omission. The check is fail-closed: an unversioned contract is a hard error,
never a silent pass. **Ordering consequence**: `01_generate_artifacts.py` must
emit ``version: "9.1"`` before any script calls `contract_guard()` at runtime.
Stage B+C landed that: 01 imports `CONTRACT_VERSION` from here, so the emitted
document carries this value by construction and cannot be retyped locally. No
other script imports this module yet, so their behaviour is unchanged.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Stable semantic ids. Never renumber, never rename, never recycle.
# ---------------------------------------------------------------------------
E_CONTRACT_MISSING = "E_CONTRACT_MISSING"
E_CONTRACT_VERSION = "E_CONTRACT_VERSION"
E_CONTRACT_KEYS = "E_CONTRACT_KEYS"
E_CONTRACT_ITEMS = "E_CONTRACT_ITEMS"
E_CONTRACT_DENOMINATOR = "E_CONTRACT_DENOMINATOR"
E_EXIT_MAP_MISSING = "E_EXIT_MAP_MISSING"
E_STATUS_INVALID = "E_STATUS_INVALID"
E_STATUS_CONFLICT = "E_STATUS_CONFLICT"
E_SCHEMA_INVALID = "E_SCHEMA_INVALID"
E_PATH_OUTSIDE_ROOT = "E_PATH_OUTSIDE_ROOT"
E_TS_TYPE = "E_TS_TYPE"
E_TS_TZ = "E_TS_TZ"
E_TS_FORMAT = "E_TS_FORMAT"
E_SCALAR_TYPE = "E_SCALAR_TYPE"
E_HASH_COLUMNS = "E_HASH_COLUMNS"
E_HASH_NULL = "E_HASH_NULL"
E_HASH_NONFINITE = "E_HASH_NONFINITE"
E_HASH_KEY_TYPE = "E_HASH_KEY_TYPE"
E_HASH_DUPLICATE_KEY = "E_HASH_DUPLICATE_KEY"
E_EVIDENCE_INVALID = "E_EVIDENCE_INVALID"
E_INPUT_MISSING = "E_INPUT_MISSING"
E_QUARANTINE_MARKING_MISSING = "E_QUARANTINE_MARKING_MISSING"
E_ACCEPTANCE_FAIL = "E_ACCEPTANCE_FAIL"
E_REPORT_FAIL = "E_REPORT_FAIL"
E_REPORT_PENDING = "E_REPORT_PENDING"

ALL_SEMANTIC_IDS = tuple(sorted(
    name for name, value in globals().items()
    if name.startswith("E_") and isinstance(value, str)
))

CONTRACT_VERSION = "9.1"

# ---------------------------------------------------------------------------
# Exit-code inventory: the codes each script ALREADY uses, before this work.
# Evidence: script docstrings + repo-wide audit (no in-repo caller exists).
# This tuple is what the maps are allowed to map onto; growing it is a
# compatibility decision, not a refactor.
# ---------------------------------------------------------------------------
EXISTING_EXIT_CODES: dict[str, tuple[int, ...]] = {
    "00_baseline_snapshot": (0, 2, 4, 5),
    "01_generate_artifacts": (0, 1, 4),
    "02_execute": (0, 1, 6),
    "03_verify": (0, 1, 7),
    "stage02_01_resample_d1": (0, 5, 6, 7),
}

# ---------------------------------------------------------------------------
# Reachability freeze (Stage A gate): three notions, kept apart on purpose
# ---------------------------------------------------------------------------
#   (A) HELPER CAPABILITY -- HELPER_RAISES[helper] is what that helper can raise
#       under ITS OWN contract, for any input a caller could hand it. It is the
#       theory layer and says nothing about any script.
#   (B) CALL-SITE REACHABILITY -- CALL_SITES[script][helper] is the subset of
#       (A) that the script can really produce AT THAT CALL SITE, given the
#       arguments it passes and the branches around it. Charging a whole helper
#       capability to a script that cannot exercise it is the mistake this split
#       exists to stop: a call site that can fire nothing declares the empty set
#       and says why in CALL_SITE_RATIONALE.
#   (C) OWNERSHIP -- owned_ids() lists every E_* constant with a named producer,
#       helper capability or script-own raise. Ownership is NOT reachability:
#       "no constant is homeless" (unowned_ids) and "no owned capability is
#       dead" (globally_unreachable_ids) are separate claims, separately checked.
#
# Frozen rules:
#   R1  REACHABLE_IDS[script] derives from CALL_SITES + SCRIPT_OWN_IDS and is
#       cross-checked against the literal REACHABLE_IDS_DECLARED.
#   R2  REACHABLE_IDS[script] <= EXIT_MAP[script]
#   R3  set(EXIT_MAP[script]) & ALL_SEMANTIC_IDS == REACHABLE_IDS[script]
#       (a semantic id the script cannot reach may not sit in its map)
#   R4  every mapped value is in EXISTING_EXIT_CODES[script]
#   R5  an id no script reaches sits in no map, and exit_code_for() raises
#       E_EXIT_MAP_MISSING for it -- never a silent 0
#   R6  the entry wrapper falls back to FALLBACK_EXIT[script] (never 0)
#   R7  every reachable id has a negative test, every call site has a written
#       rationale, and every "cannot raise" claim is probed
#   R8  CALL_SITES[script][helper] <= HELPER_RAISES[helper]: a call site may
#       narrow a capability, never widen it
#   R9  unowned_ids() == ()             (no E_* constant is homeless)
#   R10 globally_unreachable_ids() == ()   (no owned capability is dead)
#
# PINNED_NON_REACHABLE turns the deliberate exclusions -- "01 writes the
# contract, so it is not the script that reports a missing or mismatched one" --
# into an executable claim rather than a comment.
#
# Widening reachability is a contract change: add the call site, state why, add
# the id to the tables and its negative test in the same change.
# ---------------------------------------------------------------------------

# What each shared helper can raise, and only that. Every non-empty entry is
# exercised directly by tests/test_g11_common.py; an empty entry is a promise the
# tests check by feeding the helper malformed input.
HELPER_RAISES: dict[str, frozenset[str]] = {
    "normalize_ts": frozenset({E_TS_TYPE, E_TS_TZ, E_TS_FORMAT}),
    # A datetime is the only thing normalize_scalar forwards to normalize_ts, so
    # E_TS_TYPE / E_TS_FORMAT -- which normalize_ts only raises for non-datetime
    # input -- are NOT reachable through this helper.
    "normalize_scalar": frozenset({E_TS_TZ, E_HASH_NONFINITE, E_SCALAR_TYPE}),
    "canonicalize_record": frozenset({E_TS_TYPE, E_TS_TZ, E_TS_FORMAT,
                                      E_HASH_NONFINITE, E_SCALAR_TYPE}),
    "validate_spike_key": frozenset({E_HASH_COLUMNS, E_HASH_KEY_TYPE,
                                     E_EVIDENCE_INVALID}),
    "canonical_d1_input_hash": frozenset({
        E_HASH_COLUMNS, E_HASH_NULL, E_HASH_DUPLICATE_KEY, E_HASH_KEY_TYPE,
        E_HASH_NONFINITE, E_SCALAR_TYPE, E_TS_TYPE, E_TS_TZ, E_TS_FORMAT}),
    "repo_relative": frozenset({E_PATH_OUTSIDE_ROOT}),
    "contract_guard": frozenset({E_CONTRACT_MISSING, E_CONTRACT_VERSION,
                                 E_CONTRACT_KEYS}),
    "contract_items_guard": frozenset({E_CONTRACT_ITEMS, E_CONTRACT_DENOMINATOR}),
    "item_status": frozenset({E_STATUS_INVALID, E_STATUS_CONFLICT}),
    "aggregate_status": frozenset({E_STATUS_INVALID}),
    "build_item": frozenset({E_STATUS_INVALID}),
    "get_validator": frozenset({E_SCHEMA_INVALID}),
    "validate_by_id": frozenset({E_SCHEMA_INVALID}),
    "exit_code_for": frozenset({E_EXIT_MAP_MISSING}),
    # Declared unable to raise. Not a claim taken on trust: the tests feed each
    # of these malformed input and assert that it reports instead of raising.
    "parse_histdata_line": frozenset(),
    "detection_records_match": frozenset(),
    "bar_storage_validator": frozenset(),
    "fatal_from_error": frozenset(),
}

# (B) Per-script call sites, with the ids that call site can really produce
# THERE. An empty value means "this script does call this helper, and at this
# call site nothing can fire" -- a claim R7 demands a rationale for. Every entry
# path ends in the same wrapper: `exit_code_for` maps whatever code reached it,
# `fatal_from_error` reports at most.
CALL_SITES: dict[str, dict[str, frozenset[str]]] = {
    # 00 is a git/env snapshot: no contract read, no record hashing, no parquet
    # validation, so no helper beyond the wrapper can fire on its path.
    "00_baseline_snapshot": {
        "exit_code_for": frozenset({E_EXIT_MAP_MISSING}),
        "fatal_from_error": frozenset(),
    },
    # 01 WRITES the contract layer. It calls the guards to self-check the object
    # it just assembled, so none of the contract ids can fire here (see the
    # rationale). Only the CLI-supplied output path can.
    "01_generate_artifacts": {
        "contract_guard": frozenset(),
        "contract_items_guard": frozenset(),
        "repo_relative": frozenset({E_PATH_OUTSIDE_ROOT}),
        "exit_code_for": frozenset({E_EXIT_MAP_MISSING}),
        "fatal_from_error": frozenset(),
    },
    # 02 and 03 CONSUME the contract, the schema and the raw input: every
    # contract/path/ts/hash id is driven by data they did not author.
    "02_execute": {
        "contract_guard": frozenset({E_CONTRACT_MISSING, E_CONTRACT_VERSION,
                                     E_CONTRACT_KEYS}),
        "contract_items_guard": frozenset({E_CONTRACT_ITEMS,
                                           E_CONTRACT_DENOMINATOR}),
        "validate_by_id": frozenset({E_SCHEMA_INVALID}),
        "repo_relative": frozenset({E_PATH_OUTSIDE_ROOT}),
        "canonical_d1_input_hash": frozenset({
            E_HASH_COLUMNS, E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE,
            E_HASH_DUPLICATE_KEY, E_SCALAR_TYPE, E_TS_TYPE, E_TS_TZ,
            E_TS_FORMAT}),
        "item_status": frozenset({E_STATUS_INVALID, E_STATUS_CONFLICT}),
        "aggregate_status": frozenset({E_STATUS_INVALID}),
        # build_item is handed 02's own status literals: nothing external.
        "build_item": frozenset(),
        "parse_histdata_line": frozenset(),
        "exit_code_for": frozenset({E_EXIT_MAP_MISSING}),
        "fatal_from_error": frozenset(),
    },
    "03_verify": {
        "contract_guard": frozenset({E_CONTRACT_MISSING, E_CONTRACT_VERSION,
                                     E_CONTRACT_KEYS}),
        "contract_items_guard": frozenset({E_CONTRACT_ITEMS,
                                           E_CONTRACT_DENOMINATOR}),
        "validate_by_id": frozenset({E_SCHEMA_INVALID}),
        "repo_relative": frozenset({E_PATH_OUTSIDE_ROOT}),
        "canonical_d1_input_hash": frozenset({
            E_HASH_COLUMNS, E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE,
            E_HASH_DUPLICATE_KEY, E_SCALAR_TYPE, E_TS_TYPE, E_TS_TZ,
            E_TS_FORMAT}),
        "item_status": frozenset({E_STATUS_INVALID, E_STATUS_CONFLICT}),
        "aggregate_status": frozenset({E_STATUS_INVALID}),
        "build_item": frozenset(),
        "parse_histdata_line": frozenset(),
        "detection_records_match": frozenset(),
        "exit_code_for": frozenset({E_EXIT_MAP_MISSING}),
        "fatal_from_error": frozenset(),
    },
    # F consumes Stage 01's evidence chain and re-reads its own parquet, so the
    # contract / schema / path / ts / hash ids are live. It reads no
    # run_acceptance item, so the three-state ids are not.
    "stage02_01_resample_d1": {
        "contract_guard": frozenset({E_CONTRACT_MISSING, E_CONTRACT_VERSION,
                                     E_CONTRACT_KEYS}),
        "contract_items_guard": frozenset({E_CONTRACT_ITEMS,
                                           E_CONTRACT_DENOMINATOR}),
        "validate_by_id": frozenset({E_SCHEMA_INVALID}),
        "repo_relative": frozenset({E_PATH_OUTSIDE_ROOT}),
        "canonical_d1_input_hash": frozenset({
            E_HASH_COLUMNS, E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE,
            E_HASH_DUPLICATE_KEY, E_SCALAR_TYPE, E_TS_TYPE, E_TS_TZ,
            E_TS_FORMAT}),
        "parse_histdata_line": frozenset(),
        "detection_records_match": frozenset(),
        "exit_code_for": frozenset({E_EXIT_MAP_MISSING}),
        "fatal_from_error": frozenset(),
    },
}

# R7: one written reason per call site, keyed exactly like CALL_SITES. The point
# is the difference between "the helper can raise X" and "this script, here, can
# put X on the wire".
CALL_SITE_RATIONALE: dict[str, dict[str, str]] = {
    "00_baseline_snapshot": {
        "exit_code_for": "wrapper tail: whichever code reached it, including "
                         "one with no map entry",
        "fatal_from_error": "wrapper tail, reports only",
    },
    "01_generate_artifacts": {
        "contract_guard": "01 assembles the contract from its own constants and "
                          "passes that dict: the object is never absent, the "
                          "version equals the CONTRACT_VERSION it just wrote "
                          "(true by construction) and the keys are the ones it "
                          "emitted -- no branch here can fire",
        "contract_items_guard": "same object: item ids and denominator come from "
                                "01's own ACCEPTANCE_ITEMS, and the denominator "
                                "is derived from that list, so the check is true "
                                "by construction",
        "repo_relative": "output_dir arrives from the CLI, i.e. from outside the "
                         "repo",
        "exit_code_for": "wrapper tail",
        "fatal_from_error": "wrapper tail, reports only",
    },
    "02_execute": {
        "contract_guard": "02 loads manifest / quality_contract / schema from "
                          "disk: the file may be absent, carry another version "
                          "or miss required keys",
        "contract_items_guard": "the loaded contract's items and denominator are "
                                "not authored by 02",
        "validate_by_id": "the schema document is read from disk and may name an "
                          "unknown validator or miss a table",
        "repo_relative": "paths come from the manifest",
        "canonical_d1_input_hash": "the records come from the raw HistData CSVs",
        "item_status": "acceptance items come from the contract and the "
                       "detectors, both outside 02's control",
        "aggregate_status": "same item statuses",
        "build_item": "status literals are 02's own, and 02 does not read an "
                      "unknown state from elsewhere",
        "parse_histdata_line": "reports malformed lines as error records instead "
                               "of raising",
        "exit_code_for": "wrapper tail",
        "fatal_from_error": "wrapper tail, reports only",
    },
    "03_verify": {
        "contract_guard": "03 re-loads the contract from disk independently",
        "contract_items_guard": "same reload",
        "validate_by_id": "schema re-read from disk",
        "repo_relative": "paths come from the manifest",
        "canonical_d1_input_hash": "03 re-hashes the evidence it read back",
        "item_status": "03 aggregates the items it recomputed",
        "aggregate_status": "same",
        "build_item": "status literals are 03's own",
        "parse_histdata_line": "reports instead of raising",
        "detection_records_match": "compares and reports, never raises",
        "exit_code_for": "wrapper tail",
        "fatal_from_error": "wrapper tail, reports only",
    },
    "stage02_01_resample_d1": {
        "contract_guard": "F loads the contract to confirm G11 exists before it "
                          "trusts the evidence chain",
        "contract_items_guard": "same reload",
        "validate_by_id": "F validates the parquet schema it re-read",
        "repo_relative": "evidence paths come from the manifest",
        "canonical_d1_input_hash": "F re-reads its own filtered parquet and "
                                   "hashes it",
        "parse_histdata_line": "reports instead of raising",
        "detection_records_match": "compares and reports, never raises",
        "exit_code_for": "wrapper tail",
        "fatal_from_error": "wrapper tail, reports only",
    },
}

# Ids the script raises itself, outside any shared helper. 00 and 01 raise none:
# 00 cannot detect evidence problems and 01 is the producer of the contract it
# would otherwise check.
SCRIPT_OWN_IDS: dict[str, frozenset[str]] = {
    "00_baseline_snapshot": frozenset(),
    "01_generate_artifacts": frozenset(),
    "02_execute": frozenset({E_INPUT_MISSING, E_QUARANTINE_MARKING_MISSING,
                             E_EVIDENCE_INVALID, E_ACCEPTANCE_FAIL}),
    "03_verify": frozenset({E_INPUT_MISSING, E_QUARANTINE_MARKING_MISSING,
                            E_EVIDENCE_INVALID, E_ACCEPTANCE_FAIL,
                            E_REPORT_FAIL, E_REPORT_PENDING}),
    "stage02_01_resample_d1": frozenset({E_INPUT_MISSING,
                                         E_QUARANTINE_MARKING_MISSING,
                                         E_EVIDENCE_INVALID}),
}

# R7 accounting for the ids a helper cannot produce: the stage that must bring
# the negative test when the call site lands. Stage A freezes the debt; D/F/E
# pay it. A new own-id with no entry here fails the Stage A gate.
OWN_ID_TEST_PLAN: dict[str, str] = {
    E_INPUT_MISSING: "Stage D/F: evidence input absent -> non-zero exit",
    E_QUARANTINE_MARKING_MISSING: "Stage D/F: marker absent or contradicted",
    E_EVIDENCE_INVALID: "Stage D/F: malformed spike evidence is rejected",
    E_ACCEPTANCE_FAIL: "Stage D: acceptance overall FAIL -> 02 exit 6, 03 exit 1",
    E_REPORT_FAIL: "Stage E: final report overall FAIL -> 03 exit 7",
    E_REPORT_PENDING: "Stage E: final report overall PENDING -> 03 exit 7",
}


def derived_reachable_ids() -> dict[str, frozenset[str]]:
    """Script-reachable ids: own raises plus the non-empty call-site subsets.

    Helper capability is NOT inherited. Only what a call site can really fire
    counts, which is why CALL_SITES carries per-site subsets instead of helper
    names.
    """
    derived: dict[str, frozenset[str]] = {}
    for script, sites in CALL_SITES.items():
        ids = set(SCRIPT_OWN_IDS.get(script, frozenset()))
        for codes in sites.values():
            ids |= codes
        derived[script] = frozenset(ids)
    return derived


REACHABLE_IDS: dict[str, frozenset[str]] = derived_reachable_ids()

# The same sets, spelled out. Redundant on purpose: the tests assert this equals
# the derived result, so the declaration cannot drift away from the call sites.
REACHABLE_IDS_DECLARED: dict[str, frozenset[str]] = {
    "00_baseline_snapshot": frozenset({E_EXIT_MAP_MISSING}),
    # 01 writes the contract layer: it is not the script that reports the
    # contract missing, mismatched or incomplete. Only the CLI-supplied output
    # path is external to it. See PINNED_NON_REACHABLE.
    "01_generate_artifacts": frozenset({E_PATH_OUTSIDE_ROOT, E_EXIT_MAP_MISSING}),
    "02_execute": frozenset({
        E_CONTRACT_MISSING, E_CONTRACT_VERSION, E_CONTRACT_KEYS,
        E_CONTRACT_ITEMS, E_CONTRACT_DENOMINATOR, E_SCHEMA_INVALID,
        E_PATH_OUTSIDE_ROOT, E_TS_TYPE, E_TS_TZ, E_TS_FORMAT, E_SCALAR_TYPE,
        E_HASH_COLUMNS, E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE,
        E_HASH_DUPLICATE_KEY, E_STATUS_INVALID, E_STATUS_CONFLICT,
        E_INPUT_MISSING, E_QUARANTINE_MARKING_MISSING, E_EVIDENCE_INVALID,
        E_ACCEPTANCE_FAIL, E_EXIT_MAP_MISSING}),
    "03_verify": frozenset({
        E_CONTRACT_MISSING, E_CONTRACT_VERSION, E_CONTRACT_KEYS,
        E_CONTRACT_ITEMS, E_CONTRACT_DENOMINATOR, E_SCHEMA_INVALID,
        E_PATH_OUTSIDE_ROOT, E_TS_TYPE, E_TS_TZ, E_TS_FORMAT, E_SCALAR_TYPE,
        E_HASH_COLUMNS, E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE,
        E_HASH_DUPLICATE_KEY, E_STATUS_INVALID, E_STATUS_CONFLICT,
        E_INPUT_MISSING, E_QUARANTINE_MARKING_MISSING, E_EVIDENCE_INVALID,
        E_ACCEPTANCE_FAIL, E_REPORT_FAIL, E_REPORT_PENDING,
        E_EXIT_MAP_MISSING}),
    "stage02_01_resample_d1": frozenset({
        E_CONTRACT_MISSING, E_CONTRACT_VERSION, E_CONTRACT_KEYS,
        E_CONTRACT_ITEMS, E_CONTRACT_DENOMINATOR, E_SCHEMA_INVALID,
        E_PATH_OUTSIDE_ROOT, E_TS_TYPE, E_TS_TZ, E_TS_FORMAT, E_SCALAR_TYPE,
        E_HASH_COLUMNS, E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE,
        E_HASH_DUPLICATE_KEY, E_INPUT_MISSING, E_QUARANTINE_MARKING_MISSING,
        E_EVIDENCE_INVALID, E_EXIT_MAP_MISSING}),
}


# Pinned exclusions: ids that stay OUT of a script's reachable set even though
# the helper it calls can raise them elsewhere. This is the executable form of
# the review decisions, so an exclusion cannot be undone without a rationale.
PINNED_NON_REACHABLE: dict[str, frozenset[str]] = {
    "00_baseline_snapshot": frozenset(set(ALL_SEMANTIC_IDS)
                                      - {E_EXIT_MAP_MISSING}),
    "01_generate_artifacts": frozenset({
        E_CONTRACT_MISSING, E_CONTRACT_VERSION, E_CONTRACT_KEYS,
        E_CONTRACT_ITEMS, E_CONTRACT_DENOMINATOR, E_SCHEMA_INVALID,
        E_TS_TYPE, E_TS_TZ, E_TS_FORMAT, E_SCALAR_TYPE, E_HASH_COLUMNS,
        E_HASH_NULL, E_HASH_NONFINITE, E_HASH_KEY_TYPE, E_HASH_DUPLICATE_KEY,
        E_EVIDENCE_INVALID, E_INPUT_MISSING, E_QUARANTINE_MARKING_MISSING,
        E_STATUS_INVALID, E_STATUS_CONFLICT, E_ACCEPTANCE_FAIL, E_REPORT_FAIL,
        E_REPORT_PENDING}),
    "02_execute": frozenset({E_REPORT_FAIL, E_REPORT_PENDING}),
    "03_verify": frozenset(),
    "stage02_01_resample_d1": frozenset({
        E_STATUS_INVALID, E_STATUS_CONFLICT, E_ACCEPTANCE_FAIL, E_REPORT_FAIL,
        E_REPORT_PENDING}),
}


def owned_ids() -> frozenset[str]:
    """Every E_* constant with a named producer: helper capability or own raise.

    Ownership is weaker than reachability. It only says the constant is not
    homeless, never that some script can put it on the wire.
    """
    owned: set[str] = set()
    for codes in HELPER_RAISES.values():
        owned |= codes
    for codes in SCRIPT_OWN_IDS.values():
        owned |= codes
    return frozenset(owned)


def unowned_ids() -> tuple[str, ...]:
    """Constants no producer claims at all. Frozen to empty.

    A new ``E_*`` constant raised from nowhere lands here and fails the gate:
    new semantics must arrive with their producer.
    """
    return tuple(sorted(set(ALL_SEMANTIC_IDS) - owned_ids()))


def globally_unreachable_ids() -> tuple[str, ...]:
    """Owned constants that no script reaches: a capability nobody exercises.

    Frozen to empty, and deliberately not the same question as unowned_ids().
    If a helper grows a code that no call site can ever put on the wire, the gap
    shows up here -- either wire it somewhere or drop the claim.
    """
    reachable: set[str] = set()
    for ids in REACHABLE_IDS.values():
        reachable |= ids
    return tuple(sorted(owned_ids() - reachable))


# Legacy ids keep their exact old spelling and values: renaming or renumbering
# them would itself be a behaviour change.
LEGACY_EXIT: dict[str, dict[str, int]] = {
    "00_baseline_snapshot": {"no_git_repo": 4, "git_head_failed": 4,
                             "baseline_not_tracked": 2,
                             "baseline_missing_on_disk": 2,
                             "output_dir_unwritable": 5},
    "01_generate_artifacts": {"baseline_missing": 1, "baseline_malformed": 1,
                              "crossref_broken": 4},
    "02_execute": {"manifest_missing": 1, "quality_missing": 1,
                   "no_input_dir": 1},
    "03_verify": {"output_dir_missing": 1},
    "stage02_01_resample_d1": {"m1_missing": 5, "d1_invariant_violation": 6,
                               "roundtrip_failed": 7},
}

# The new semantics, one entry per reachable id per script. E_EXIT_MAP_MISSING is
# listed for every script because the wrapper must always be able to report that
# it could not map something.
REACHABLE_EXIT: dict[str, dict[str, int]] = {
    "00_baseline_snapshot": {E_EXIT_MAP_MISSING: 4},
    "01_generate_artifacts": {E_PATH_OUTSIDE_ROOT: 4, E_EXIT_MAP_MISSING: 4},
    "02_execute": {E_CONTRACT_MISSING: 1, E_CONTRACT_VERSION: 1,
                   E_CONTRACT_KEYS: 1, E_CONTRACT_ITEMS: 1,
                   E_CONTRACT_DENOMINATOR: 1, E_SCHEMA_INVALID: 1,
                   E_PATH_OUTSIDE_ROOT: 1, E_TS_TYPE: 1, E_TS_TZ: 1,
                   E_TS_FORMAT: 1, E_SCALAR_TYPE: 1, E_HASH_COLUMNS: 1,
                   E_HASH_NULL: 1, E_HASH_NONFINITE: 1, E_HASH_KEY_TYPE: 1,
                   E_HASH_DUPLICATE_KEY: 1, E_STATUS_INVALID: 1,
                   E_STATUS_CONFLICT: 1, E_INPUT_MISSING: 1,
                   E_QUARANTINE_MARKING_MISSING: 1, E_EVIDENCE_INVALID: 1,
                   E_EXIT_MAP_MISSING: 1,
                   # acceptance outcome (unchanged meaning: FAIL only)
                   E_ACCEPTANCE_FAIL: 6},
    "03_verify": {E_CONTRACT_MISSING: 1, E_CONTRACT_VERSION: 1,
                  E_CONTRACT_KEYS: 1, E_CONTRACT_ITEMS: 1,
                  E_CONTRACT_DENOMINATOR: 1, E_SCHEMA_INVALID: 1,
                  E_PATH_OUTSIDE_ROOT: 1, E_TS_TYPE: 1, E_TS_TZ: 1,
                  E_TS_FORMAT: 1, E_SCALAR_TYPE: 1, E_HASH_COLUMNS: 1,
                  E_HASH_NULL: 1, E_HASH_NONFINITE: 1, E_HASH_KEY_TYPE: 1,
                  E_HASH_DUPLICATE_KEY: 1, E_STATUS_INVALID: 1,
                  E_STATUS_CONFLICT: 1, E_INPUT_MISSING: 1,
                  E_QUARANTINE_MARKING_MISSING: 1, E_EVIDENCE_INVALID: 1,
                  E_EXIT_MAP_MISSING: 1, E_ACCEPTANCE_FAIL: 1,
                  # final judgement: 7 is extended from "Overall FAIL" to
                  # "Overall not PASS" (FAIL or PENDING); the two ids keep them
                  # distinguishable.
                  E_REPORT_FAIL: 7, E_REPORT_PENDING: 7},
    "stage02_01_resample_d1": {E_CONTRACT_MISSING: 5, E_CONTRACT_VERSION: 5,
                               E_CONTRACT_KEYS: 5, E_CONTRACT_ITEMS: 5,
                               E_CONTRACT_DENOMINATOR: 5, E_SCHEMA_INVALID: 5,
                               E_PATH_OUTSIDE_ROOT: 5, E_TS_TYPE: 5,
                               E_TS_TZ: 5, E_TS_FORMAT: 5, E_SCALAR_TYPE: 5,
                               E_HASH_COLUMNS: 5, E_HASH_NULL: 5,
                               E_HASH_NONFINITE: 5, E_HASH_KEY_TYPE: 5,
                               E_HASH_DUPLICATE_KEY: 5, E_INPUT_MISSING: 5,
                               E_QUARANTINE_MARKING_MISSING: 5,
                               E_EVIDENCE_INVALID: 5, E_EXIT_MAP_MISSING: 5},
}

EXIT_MAP_00: dict[str, int] = {
    # 00 is a git/env snapshot: it reads no contract and touches no records, so
    # it reaches exactly one semantic id -- the wrapper's own "cannot map this".
    **LEGACY_EXIT["00_baseline_snapshot"],
    **REACHABLE_EXIT["00_baseline_snapshot"],
}

EXIT_MAP_01: dict[str, int] = {
    # 01 is the PRODUCER of the contract layer, so it is not the script that can
    # report that contract missing / mismatched / incomplete: it passes the dict
    # it just assembled, and every comparison inside the guards is true by
    # construction. Only the CLI-supplied output path is external to it. Calling
    # contract_guard is therefore NOT the same as reaching E_CONTRACT_* -- see
    # CALL_SITES / CALL_SITE_RATIONALE / PINNED_NON_REACHABLE.
    **LEGACY_EXIT["01_generate_artifacts"],
    **REACHABLE_EXIT["01_generate_artifacts"],
}

EXIT_MAP_02: dict[str, int] = {
    # 02 loads the contract, parses raw data and reports acceptance. It reaches
    # the contract/schema/path/hash/ts ids, the quarantine and three-state ids,
    # and E_ACCEPTANCE_FAIL -> 6. It does NOT reach E_REPORT_FAIL /
    # E_REPORT_PENDING: 02 never writes the final report, and its own PENDING
    # outcome is a normal `emit`, not a fatal.
    **LEGACY_EXIT["02_execute"],
    **REACHABLE_EXIT["02_execute"],
}

EXIT_MAP_03: dict[str, int] = {
    # 03 re-computes everything 02 produced, so it reaches the whole set 02
    # reaches, plus the two report ids that carry its own verdict.
    **LEGACY_EXIT["03_verify"],
    **REACHABLE_EXIT["03_verify"],
}

EXIT_MAP_F: dict[str, int] = {
    # F consumes the evidence Stage 01 produced and re-reads its own output to
    # hash it, so it reaches the contract / schema / path / hash / ts ids and
    # the three evidence ids it raises itself. It does NOT reach the three-state
    # ids (it reads the evidence chain, not 02's run_acceptance) nor the report
    # ids (it writes no report).
    **LEGACY_EXIT["stage02_01_resample_d1"],
    **REACHABLE_EXIT["stage02_01_resample_d1"],
}

EXIT_MAPS: dict[str, dict[str, int]] = {
    "00_baseline_snapshot": EXIT_MAP_00,
    "01_generate_artifacts": EXIT_MAP_01,
    "02_execute": EXIT_MAP_02,
    "03_verify": EXIT_MAP_03,
    "stage02_01_resample_d1": EXIT_MAP_F,
}

# Fallback used only when a semantic id somehow has no entry: loud, and it lands
# on the script's existing "contract problem" code rather than on 0.
FALLBACK_EXIT: dict[str, int] = {
    "00_baseline_snapshot": 4,
    "01_generate_artifacts": 4,
    "02_execute": 1,
    "03_verify": 1,
    "stage02_01_resample_d1": 5,
}


def exit_code_for(script: str, code: str) -> int:
    """Map a stable semantic id onto one of `script`'s pre-existing exit codes."""
    if script not in EXIT_MAPS:
        raise ContractError(E_EXIT_MAP_MISSING, f"unknown script {script!r}")
    mapping = EXIT_MAPS[script]
    if code not in mapping:
        raise ContractError(E_EXIT_MAP_MISSING,
                            f"{script} has no exit code for {code!r}",
                            {"script": script, "code": code})
    return mapping[code]


# ---------------------------------------------------------------------------
# G11 spike quarantine
# ---------------------------------------------------------------------------
SPIKE_THRESHOLD = 0.10
SPIKE_REASON = "close_deviation_gt_threshold_vs_both_neighbours"
SPIKE_CONDITION = (
    "close deviates by more than SPIKE_THRESHOLD from BOTH the previous and the "
    "next close **of the same source file**"
)
SPIKE_FIELD_ORDER = ("ts", "open", "high", "low", "close", "volume",
                     "source_file", "source_line")
SPIKE_EVIDENCE_FIELDS = ("reason", "threshold", "dev_prev", "dev_next",
                         "prev_close", "next_close",
                         "prev_source_line", "next_source_line")
SPIKE_FINITE_EVIDENCE_FIELDS = ("dev_prev", "dev_next", "prev_close", "next_close")
SPIKE_RECORD_FLOAT_TOL = 5e-5
SPIKE_KEY_FIELDS = ("ts", "source_file", "source_line")

# Disclosed detection limits. Never claim the detector finds every bad tick.
SPIKE_BLIND_SPOT_REASONS = (
    "file boundary: the first and the last data row of each source file have no "
    "two-sided neighbour, so per-file detection can never mark them",
    "adjacent spikes: two consecutive spiked bars stabilise each other (A's next "
    "is B and B's prev is A), so neither is marked",
    "genuine gap: a real jump larger than the threshold sitting between two "
    "neighbours that are also further than the threshold away is "
    "indistinguishable from a bad tick",
)

# ---------------------------------------------------------------------------
# Canonical D1-input hash
# ---------------------------------------------------------------------------
CANONICAL_HASH_COLUMNS = ("ts", "open", "high", "low", "close", "volume",
                          "source_file", "source_line")
CANONICAL_HASH_SORT_KEYS = ("ts", "source_file", "source_line")
CANONICAL_HASH_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"
CANONICAL_HASH_JSON_KWARGS = {"ensure_ascii": False, "separators": (",", ":"),
                              "allow_nan": False}
CANONICAL_HASH_FLOAT_POLICY = ("exact float64 (json shortest round-trip repr); "
                               "no rounding")
CANONICAL_HASH_NULL_POLICY = "forbidden (fail-closed)"
CANONICAL_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
CANONICAL_TS_RE = re.compile(CANONICAL_TS_PATTERN)

# Physical layout of the evidence parquet written by Stage 02 before aggregation.
M1_EVIDENCE_COLUMNS = ("ts", "open", "high", "low", "close", "volume",
                       "source_file", "source_line", "quarantined")

# ---------------------------------------------------------------------------
# Bar_Storage schema validator
# ---------------------------------------------------------------------------
BAR_STORAGE_VALIDATOR_ID = "bar_storage_v1"

# ---------------------------------------------------------------------------
# Three-state acceptance
# ---------------------------------------------------------------------------
STATE_PASS = "PASS"
STATE_FAIL = "FAIL"
STATE_PENDING = "PENDING"
STATUS_ORDER = (STATE_FAIL, STATE_PENDING, STATE_PASS)   # highest severity first
STATUS_TO_PASS = {STATE_PASS: True, STATE_FAIL: False, STATE_PENDING: None}

_MISSING = object()


class ContractError(Exception):
    """Contract / evidence violation carrying a stable semantic id."""

    def __init__(self, code: str, detail: str = "", context: dict | None = None):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.context = dict(context or {})

    def to_event(self, script: str, exit_code: int | None = None,
                 **extra: Any) -> dict:
        event = {"event": "fatal", "script": script, "code": self.code,
                 "detail": self.detail}
        if self.context:
            event["context"] = self.context
        if exit_code is not None:
            event["exit_code"] = exit_code
        event.update(extra)
        return event


def fatal_from_error(script: str, error: ContractError) -> tuple[dict, int]:
    """(event, exit_code) for a ContractError raised inside `script`.

    An id with no entry in the script's map is itself reported loudly rather than
    being silently mapped to 0.
    """
    try:
        code = exit_code_for(script, error.code)
        return error.to_event(script, exit_code=code), code
    except ContractError:
        code = FALLBACK_EXIT.get(script, 1)
        return ({"event": "fatal", "script": script, "code": E_EXIT_MAP_MISSING,
                 "detail": f"no exit mapping for {error.code!r}",
                 "original": error.to_event(script), "exit_code": code}, code)


# ---------------------------------------------------------------------------
# Timestamp and scalar normalization
# ---------------------------------------------------------------------------
def is_canonical_ts(value: Any) -> bool:
    return isinstance(value, str) and bool(CANONICAL_TS_RE.match(value))


def normalize_ts(value: Any) -> str:
    """Canonical naive timestamp string, or a ContractError.

    Accepts a naive datetime (or pandas Timestamp) and a *canonical* string.
    Everything else is refused: tz-aware instants, space-separated strings,
    fractional seconds, 'Z' suffixes and calendar-invalid dates such as
    2001-02-30 (which would pass the regex).
    """
    convert = getattr(value, "to_pydatetime", None)
    if callable(convert):
        value = convert()
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ContractError(E_TS_TZ, f"timestamp must be naive, got {value!r}")
        return value.strftime(CANONICAL_HASH_TS_FORMAT)
    if isinstance(value, str):
        if not is_canonical_ts(value):
            raise ContractError(
                E_TS_FORMAT,
                f"ts {value!r} does not match {CANONICAL_TS_PATTERN}", {"value": value})
        try:
            parsed = datetime.strptime(value, CANONICAL_HASH_TS_FORMAT)
        except ValueError as exc:
            raise ContractError(E_TS_FORMAT, f"ts {value!r} is not an instant",
                                {"value": value}) from exc
        return parsed.strftime(CANONICAL_HASH_TS_FORMAT)
    raise ContractError(E_TS_TYPE, f"cannot interpret {type(value).__name__} as ts")


def normalize_scalar(value: Any) -> Any:
    """JSON-safe deterministic scalar. numpy / Timestamp-likes are unwrapped."""
    if value is None:
        return None
    convert = getattr(value, "to_pydatetime", None)
    if callable(convert):
        value = convert()
    if isinstance(value, datetime):
        return normalize_ts(value)
    item = getattr(value, "item", None)
    if callable(item) and not isinstance(value, (str, bytes)):
        value = item()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ContractError(E_HASH_NONFINITE, f"non-finite float {value!r}")
        return value
    raise ContractError(E_SCALAR_TYPE, f"unsupported scalar {value!r}")


def canonicalize_record(record: Mapping,
                        field_order: Sequence[str] = SPIKE_FIELD_ORDER,
                        include_extra: bool = True) -> dict:
    """New dict: `field_order` keys first, then the remaining keys.

    Validates/normalizes every ``ts`` field (canonically, see `normalize_ts`)
    and refuses NaN / inf. Insertion order is the only ordering mechanism.

    `include_extra=False` keeps ONLY `field_order`: the canonical D1-input hash
    needs that, because a column that is not part of the pinned spec (for
    example the ``quarantined`` marker) must not be able to move the hash.
    """
    out: dict[str, Any] = {}
    for key in field_order:
        if key in record:
            out[key] = normalize_scalar(record[key])
    if include_extra:
        for key in record:
            if key not in out:
                out[key] = normalize_scalar(record[key])
    if "ts" in out:
        out["ts"] = normalize_ts(out["ts"])
    return out


# ---------------------------------------------------------------------------
# Sort-key validation (shared by the hash and the comparator)
# ---------------------------------------------------------------------------
def validate_spike_key(row: Mapping, *, index: int = 0,
                       code: str = E_HASH_KEY_TYPE) -> tuple:
    """Validate one row's sort/key triple and return it.

    Types are checked explicitly so that a malformed evidence file raises a
    stable ContractError instead of a downstream TypeError, and so that
    ordering cannot depend on whether the caller normalized the row.
    """
    try:
        ts, source_file, source_line = (row[k] for k in CANONICAL_HASH_SORT_KEYS)
    except KeyError as exc:
        raise ContractError(E_HASH_COLUMNS,
                            f"row {index} missing key field {exc}") from exc
    if not is_canonical_ts(ts):
        raise ContractError(code, f"row {index} ts {ts!r} is not canonical",
                            {"row": index, "field": "ts", "value": ts})
    if not isinstance(source_file, str) or not source_file:
        raise ContractError(code,
                            f"row {index} source_file {source_file!r} is not a "
                            f"non-empty string",
                            {"row": index, "field": "source_file"})
    if isinstance(source_line, bool) or not isinstance(source_line, int):
        raise ContractError(code,
                            f"row {index} source_line {source_line!r} is not an int",
                            {"row": index, "field": "source_line"})
    if source_line < 1:
        raise ContractError(code, f"row {index} source_line {source_line} < 1",
                            {"row": index, "field": "source_line"})
    return ts, source_file, source_line


# ---------------------------------------------------------------------------
# Canonical D1-input hash
# ---------------------------------------------------------------------------
def canonical_d1_input_hash(records: Iterable[Mapping],
                           columns: Sequence[str] = CANONICAL_HASH_COLUMNS) -> str:
    """SHA-256 over the exact rows fed to the D1 aggregator.

    Every spec point is enforced inside this function, so no caller can change
    the hash by pre-sorting, re-indexing or reordering columns:

      columns  : `columns`, in that order, nothing else
      ts       : re-normalized to CANONICAL_HASH_TS_FORMAT (non-canonical or
                 tz-aware input is refused, not coerced)
      sort     : CANONICAL_HASH_SORT_KEYS ascending, validated types
      keys     : duplicate (ts, source_file, source_line) triplets are refused
      floats   : exact float64 (no rounding)
      nulls    : forbidden -- null / NaN / inf raise

    `records` must contain every row that is aggregated (never a pre-filtered
    subset) and must come from the re-read evidence parquet.
    """
    rows: list[dict] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ContractError(E_HASH_COLUMNS,
                                f"row {index} is {type(record).__name__}, not a mapping")
        missing = [c for c in columns if c not in record]
        if missing:
            raise ContractError(E_HASH_COLUMNS, f"row {index} missing columns {missing}")
        row = canonicalize_record(record, field_order=columns,
                                  include_extra=False)
        for column in columns:
            if row[column] is None:
                raise ContractError(E_HASH_NULL,
                                    f"row {index} column {column} is null",
                                    {"row": index, "column": column})
        validate_spike_key(row, index=index)
        rows.append(row)

    keys = [tuple(row[k] for k in CANONICAL_HASH_SORT_KEYS) for row in rows]
    if len(set(keys)) != len(keys):
        seen: set = set()
        duplicates = sorted({k for k in keys if k in seen or seen.add(k)})
        raise ContractError(E_HASH_DUPLICATE_KEY,
                            f"{len(keys) - len(set(keys))} duplicate sort keys",
                            {"examples": [list(k) for k in duplicates[:5]]})

    rows.sort(key=lambda row: tuple(row[k] for k in CANONICAL_HASH_SORT_KEYS))
    payload = json.dumps(rows, **CANONICAL_HASH_JSON_KWARGS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Raw histdata line parser (source tracing)
# ---------------------------------------------------------------------------
HISTDATA_DELIM = ";"
HISTDATA_FIELD_COUNT = 6
HISTDATA_TS_FORMAT = "%Y%m%d %H%M%S"


def parse_histdata_line(line: str, delim: str = HISTDATA_DELIM,
                        as_of_source: tuple[str, int] | None = None
                        ) -> tuple[dict | None, dict | None]:
    """Strictly parse one histdata ASCII M1 line -> (bar, error).

    Layout: ``YYYYMMDD HHMMSS;O;H;L;C;V`` (exactly six fields). Returns
    ``(bar, None)`` or ``(None, error)``. The error carries the codes
    schema.json's ErrorRecord already declares, plus ``raw_excerpt``; when
    `as_of_source` is given, ``file`` / ``line`` are filled in so the record
    matches ErrorRecord directly.
    """
    text = line.rstrip("\r\n")
    excerpt = text[:1024]

    def err(code: str, detail: str = "") -> tuple[None, dict]:
        record: dict[str, Any] = {"code": code, "raw_excerpt": excerpt}
        if as_of_source is not None:
            record["file"], record["line"] = as_of_source
        if detail:
            record["detail"] = detail
        return None, record

    if not text.strip():
        return err("BAD_FIELD_COUNT", "empty line")
    fields = text.split(delim)
    if len(fields) != HISTDATA_FIELD_COUNT:
        return err("BAD_FIELD_COUNT",
                   f"expected {HISTDATA_FIELD_COUNT} fields, got {len(fields)}")

    try:
        ts = datetime.strptime(fields[0].strip(), HISTDATA_TS_FORMAT)
    except ValueError:
        return err("BAD_TIMESTAMP", f"unparsed ts {fields[0]!r}")

    try:
        open_, high, low, close, volume = (float(f) for f in fields[1:6])
    except ValueError as exc:
        return err("ENCODING_ERROR", str(exc))

    if any(price <= 0 for price in (open_, high, low, close)):
        return err("NEGATIVE_PRICE")
    if not (high >= max(open_, close) and low <= min(open_, close)):
        return err("BAD_OHLC")
    if volume < 0:
        return err("BAD_VOLUME")

    bar = {"ts": ts.strftime(CANONICAL_HASH_TS_FORMAT),
           "open": open_, "high": high, "low": low, "close": close,
           "volume": volume, "source_file": None, "source_line": None}
    if as_of_source is not None:
        bar["source_file"], bar["source_line"] = as_of_source
    return bar, None


# ---------------------------------------------------------------------------
# Spike-record comparison (a comparator, never a detector)
# ---------------------------------------------------------------------------
def detection_records_match(records_a: Iterable[Mapping],
                            records_b: Iterable[Mapping],
                            float_tol: float = SPIKE_RECORD_FLOAT_TOL,
                            key_fields: Sequence[str] = SPIKE_KEY_FIELDS,
                            required_fields: Sequence[str] = SPIKE_FIELD_ORDER,
                            ) -> dict:
    """Full-field (never count-only) comparison of two spike-record sets.

    Malformed evidence never escapes as an exception and is never accepted as a
    valid record: every problem becomes an entry in ``invalid_a`` / ``invalid_b``
    and forces ``ok`` to False.
    """

    def index(records: Iterable[Mapping], side: str) -> tuple[dict, list, list]:
        indexed: dict[tuple, dict] = {}
        duplicates: list[dict] = []
        invalid: list[dict] = []
        for position, record in enumerate(records):
            try:
                if not isinstance(record, Mapping):
                    raise ContractError(E_EVIDENCE_INVALID,
                                        f"{type(record).__name__} is not a mapping")
                missing = [f for f in required_fields if f not in record]
                if missing:
                    raise ContractError(E_EVIDENCE_INVALID, f"missing fields {missing}")
                canonical = canonicalize_record(record)
                key = tuple(canonical.get(f) for f in key_fields)
                if any(k is None for k in key):
                    raise ContractError(E_EVIDENCE_INVALID,
                                        f"null key field in {list(key)}")
                validate_spike_key(canonical, index=position, code=E_EVIDENCE_INVALID)
                for field in SPIKE_FINITE_EVIDENCE_FIELDS:
                    value = canonical.get(field)
                    if value is None:
                        continue
                    if not isinstance(value, float) or value != value or value in (
                            float("inf"), float("-inf")):
                        raise ContractError(E_EVIDENCE_INVALID,
                                            f"{field}={value!r} is not a finite float")
                threshold = canonical.get("threshold")
                if threshold is not None and threshold != SPIKE_THRESHOLD:
                    raise ContractError(
                        E_EVIDENCE_INVALID,
                        f"record threshold {threshold!r} != SPIKE_THRESHOLD "
                        f"{SPIKE_THRESHOLD}")
            except ContractError as exc:
                invalid.append({"side": side, "record_index": position,
                                "code": exc.code, "detail": exc.detail})
                continue
            if key in indexed:
                duplicates.append({"key": list(key), "side": side,
                                   "record_index": position})
            else:
                indexed[key] = canonical
        return indexed, duplicates, invalid

    index_a, duplicates_a, invalid_a = index(records_a, "a")
    index_b, duplicates_b, invalid_b = index(records_b, "b")

    only_in_a = [list(k) for k in index_a if k not in index_b]
    only_in_b = [list(k) for k in index_b if k not in index_a]
    mismatches: list[dict] = []
    for key in index_a.keys() & index_b.keys():
        row_a, row_b = index_a[key], index_b[key]
        for field in sorted(set(row_a) | set(row_b)):
            value_a = row_a.get(field, _MISSING)
            value_b = row_b.get(field, _MISSING)
            if value_a is _MISSING or value_b is _MISSING:
                mismatches.append({
                    "key": list(key), "field": field,
                    "a": None if value_a is _MISSING else value_a,
                    "b": None if value_b is _MISSING else value_b,
                    "why": "field_present_on_one_side_only"})
            elif isinstance(value_a, float) and isinstance(value_b, float):
                if abs(value_a - value_b) > float_tol:
                    mismatches.append({"key": list(key), "field": field,
                                       "a": value_a, "b": value_b,
                                       "why": "float_tol"})
            elif value_a != value_b:
                mismatches.append({"key": list(key), "field": field,
                                   "a": value_a, "b": value_b, "why": "value"})

    return {
        "ok": not (only_in_a or only_in_b or mismatches or duplicates_a
                   or duplicates_b or invalid_a or invalid_b),
        "compared": len(index_a.keys() & index_b.keys()),
        "count_a": len(index_a), "count_b": len(index_b),
        "only_in_a": only_in_a, "only_in_b": only_in_b,
        "field_mismatches": mismatches,
        "duplicates_a": duplicates_a, "duplicates_b": duplicates_b,
        "invalid_a": invalid_a, "invalid_b": invalid_b,
        "float_tol": float_tol,
        "key_fields": list(key_fields),
        "required_fields": list(required_fields),
    }


# ---------------------------------------------------------------------------
# Blind-spot arithmetic (computed from the real file inventory, never hardcoded)
# ---------------------------------------------------------------------------
def boundary_blind_spot_rows(rows_per_file: Sequence[int]) -> int:
    """Rows that per-file detection can never mark, computed from real counts.

    The first row of a file has no previous row and the last row has no next
    row, so both lack the two-sided neighbour the rule requires. A file with
    exactly one row has no two-sided neighbour at all and contributes 1. For
    every file with >= 2 rows this is 2, so the total equals 2 * n_files_with_rows
    -- but it is derived from the inventory, not from a constant.
    """
    total = 0
    for count in rows_per_file:
        count = int(count)
        if count <= 0:
            continue
        total += 1 if count == 1 else 2
    return total


def blind_spot_report(rows_per_file: Sequence[int],
                      threshold: float = SPIKE_THRESHOLD) -> dict:
    """Disclosure block for the reports: computed counts + stated limits."""
    counts = [int(c) for c in rows_per_file]
    files_with_rows = sum(1 for c in counts if c > 0)
    boundary = boundary_blind_spot_rows(counts)
    return {
        "threshold": threshold,
        "files": len(counts),
        "files_with_rows": files_with_rows,
        "data_rows": sum(counts),
        "boundary_rows": boundary,
        "boundary_formula": ("sum(1 if n == 1 else 2 for n in rows_per_file "
                             "if n > 0)"),
        "boundary_rows_equals_2n": boundary == 2 * files_with_rows,
        "detection_scope": "per source file",
        "reasons": list(SPIKE_BLIND_SPOT_REASONS),
        "completeness_claim": ("the detector does not recognise every bad price; "
                               "the rows above are out of its reach by design"),
    }


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------
def repo_relative(path: Any, repo_root: Any,
                  code: str = E_PATH_OUTSIDE_ROOT) -> str:
    """POSIX path of `path` relative to `repo_root`.

    Uses Path.relative_to -- not str.startswith (which cannot tell /a/bc from
    /a/b) and not os.path.relpath (which happily returns '../..'). A path
    outside the root is an error, never a relative path.
    """
    resolved = Path(path).resolve()
    root = Path(repo_root).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ContractError(code, f"{resolved} is not under {root}") from exc


# ---------------------------------------------------------------------------
# Contract guard
# ---------------------------------------------------------------------------
def contract_guard(contract: Any, expected_version: str,
                   required_keys: Sequence[str] = (),
                   version_key: str = "version") -> Mapping:
    """Validate a loaded contract; raise ContractError, never return a code.

    `expected_version` is positional-required on purpose: there is no default
    that could silently turn version checking off.
    """
    if contract is None:
        raise ContractError(E_CONTRACT_MISSING, "contract could not be loaded")
    if not isinstance(contract, Mapping):
        raise ContractError(E_CONTRACT_MISSING,
                            f"contract is {type(contract).__name__}, not a mapping")
    actual = contract.get(version_key)
    if actual != expected_version:
        raise ContractError(
            E_CONTRACT_VERSION,
            f"{version_key} {actual!r} != {expected_version!r}",
            {"actual": actual, "expected": expected_version})
    missing = [key for key in required_keys if key not in contract]
    if missing:
        raise ContractError(E_CONTRACT_KEYS, f"missing keys {missing}",
                            {"missing": missing})
    return contract


def contract_items_guard(contract: Mapping,
                         item_key: str = "acceptance_items") -> tuple[list, list]:
    """Return (items, ids); enforce id uniqueness and denominator == len(items)."""
    items = contract.get(item_key)
    if not isinstance(items, list) or not items:
        raise ContractError(E_CONTRACT_ITEMS,
                            f"{item_key} is {type(items).__name__} / empty")
    ids = [item.get("id") for item in items]
    if any(not isinstance(i, str) or not i for i in ids):
        raise ContractError(E_CONTRACT_ITEMS, f"{item_key} has an item without an id")
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ContractError(E_CONTRACT_ITEMS, f"duplicate item ids {duplicates}")
    denominator = contract.get("denominator")
    if denominator != len(items):
        raise ContractError(
            E_CONTRACT_DENOMINATOR,
            f"denominator {denominator!r} != {len(items)} items",
            {"denominator": denominator, "items": len(items)})
    return items, ids


# ---------------------------------------------------------------------------
# Three-state acceptance
# ---------------------------------------------------------------------------
def item_status(item: Mapping) -> str:
    """Authoritative status of one acceptance item. `status` wins over `pass`."""
    status = item.get("status")
    if status not in STATUS_TO_PASS:
        raise ContractError(E_STATUS_INVALID,
                            f"item {item.get('id')!r} status {status!r} not in "
                            f"{list(STATUS_TO_PASS)}")
    legacy = item.get("pass", _MISSING)
    if legacy is not _MISSING and legacy != STATUS_TO_PASS[status]:
        raise ContractError(
            E_STATUS_CONFLICT,
            f"item {item.get('id')!r} status={status} contradicts pass={legacy}")
    return status


def aggregate_status(statuses: Iterable[str]) -> str:
    """FAIL > PENDING > PASS. PENDING is never silently promoted to PASS."""
    seen = set(statuses)
    unknown = sorted(seen - set(STATUS_TO_PASS))
    if unknown:
        raise ContractError(E_STATUS_INVALID, f"unknown statuses {unknown}")
    for state in STATUS_ORDER:
        if state in seen:
            return state
    return STATE_PASS


def build_item(item_id: str, status: str, evidence: dict | None = None,
               **extra: Any) -> dict:
    """Item dict with `status` authoritative and `pass` as the compatibility map."""
    if status not in STATUS_TO_PASS:
        raise ContractError(E_STATUS_INVALID, f"{item_id}: bad status {status!r}")
    item: dict[str, Any] = {"id": item_id, "status": status,
                            "pass": STATUS_TO_PASS[status],
                            "evidence": dict(evidence or {})}
    item.update(extra)
    return item


# ---------------------------------------------------------------------------
# Bar_Storage schema validator
# ---------------------------------------------------------------------------
def bar_storage_validator(storage_block: Mapping, arrow_types: Mapping,
                          pandas_dtypes: Mapping | None = None) -> dict:
    """Validate a parquet against schema.json's Bar_Storage block.

    Authority is the Arrow schema (``pyarrow.parquet.read_schema``): it is what
    is physically on disk and it does not drift with the pandas version. The
    pandas dtypes are recorded as non-gating evidence -- under pandas 3.0.x a
    parquet ``large_string`` reads back as pandas ``str``, under 2.x as
    ``object``, so they can never decide pass/fail.
    """
    issues: list[dict] = []
    required = list(storage_block.get("x_required_columns", []))
    present = list(arrow_types)
    missing = [column for column in required if column not in present]
    if missing:
        issues.append({"kind": "missing_columns", "columns": missing})
    if storage_block.get("x_columns_must_be_in_order") and present != required:
        issues.append({"kind": "column_order", "expected": required,
                       "actual": present})
    for column, allowed in (storage_block.get("x_arrow_dtypes") or {}).items():
        if column in arrow_types and arrow_types[column] not in allowed:
            issues.append({"kind": "arrow_dtype", "column": column,
                           "expected": list(allowed),
                           "actual": arrow_types[column]})
    if pandas_dtypes is not None:
        for column, allowed in (storage_block.get("x_pandas_dtype_equivalents")
                                or {}).items():
            if column in pandas_dtypes and pandas_dtypes[column] not in allowed:
                issues.append({"kind": "pandas_dtype", "column": column,
                               "expected": list(allowed),
                               "actual": pandas_dtypes[column]})
    return {"ok": not issues, "validator": BAR_STORAGE_VALIDATOR_ID,
            "arrow_types": dict(arrow_types),
            "pandas_dtypes": dict(pandas_dtypes or {}),
            "issues": issues}


VALIDATORS = {BAR_STORAGE_VALIDATOR_ID: bar_storage_validator}


def get_validator(validator_id: str):
    try:
        return VALIDATORS[validator_id]
    except KeyError as exc:
        raise ContractError(E_SCHEMA_INVALID,
                            f"unknown x_validator_id {validator_id!r}") from exc


def validate_by_id(validator_id: str, *args: Any, **kwargs: Any) -> dict:
    return get_validator(validator_id)(*args, **kwargs)

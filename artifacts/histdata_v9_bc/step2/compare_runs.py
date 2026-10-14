#!/usr/bin/env python3
"""Structural comparison of two histdata_v9 runs (B+C step 2 evidence).

For a before/after pair this reports:

  * the 14 acceptance ids in order and their pass/fail, plus denominator/overall
  * the component verdicts and the interface issues
  * every small document, with volatile fields (generated_at / captured_at)
    dropped, so a timestamp cannot masquerade as a change
  * large binaries by size only

Exit 0 when nothing differs, 1 otherwise. Usage:
  python3 compare_runs.py BEFORE_DIR AFTER_DIR
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

VOLATILE = {"generated_at", "captured_at", "ts", "timestamp", "finished_at",
            "run_at"}
SMALL = 5 << 20
SKIP_HASH = {".parquet"}


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml
        return yaml.safe_load(text)


def strip_volatile(obj, substitutions=()):
    """Drop volatile fields and fold the output dir out of path strings, so two
    runs that differ only in where they were written compare clean.

    `substitutions` is a tuple of (prefix, replacement); the resolved form is
    substituted before the shorter one so the longer match wins.
    """
    if isinstance(obj, dict):
        return {k: strip_volatile(v, substitutions)
                for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [strip_volatile(v, substitutions) for v in obj]
    if isinstance(obj, str):
        for prefix, replacement in substitutions:
            obj = obj.replace(prefix, replacement)
        return obj
    return obj


def acceptance_summary(path: Path):
    doc = load(path)
    return {
        "denominator": doc.get("denominator"),
        "overall": doc.get("overall"),
        "pass_count": doc.get("pass_count"),
        "fail_count": doc.get("fail_count"),
        "items": [(i.get("id"), i.get("pass")) for i in doc.get("items", [])],
    }


def out_dir_of(root: Path) -> str:
    """The artifacts dir a run was written to, read back from its own manifest.

    Needed because a copied 'before' tree still contains the dir it was written
    to, which is not the dir the copy now lives in.
    """
    first = load(root / "manifest.yaml")["outputs"]["parsed"][0]
    return first.split("/parsed/")[0]


def main() -> int:
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    subs = tuple((s, "<OUT>") for s in
                 {out_dir_of(before), out_dir_of(after), str(before.resolve()),
                  str(after.resolve())}
                 if s not in (".", ""))
    problems: list[str] = []

    b_acc = acceptance_summary(before / "acceptance" / "run_acceptance.json")
    a_acc = acceptance_summary(after / "acceptance" / "run_acceptance.json")
    for key in ("denominator", "overall", "pass_count", "fail_count"):
        if b_acc[key] != a_acc[key]:
            problems.append(f"acceptance.{key}: {b_acc[key]} -> {a_acc[key]}")
    if b_acc["items"] != a_acc["items"]:
        changed = [(b, a) for b, a in zip(b_acc["items"], a_acc["items"]) if b != a]
        problems.append(f"acceptance.items differ: {changed}")
    print(f"acceptance ids ({len(a_acc['items'])}): "
          f"{[i for i, _ in a_acc['items']]}")
    failing = [i for i, ok in a_acc["items"] if not ok]
    print(f"acceptance overall: {b_acc['overall']} -> {a_acc['overall']}"
          f" | pass {a_acc['pass_count']}/{a_acc['denominator']}"
          f" | FAIL ids: {failing}")

    b_final = strip_volatile(load(before / "verify" / "final_report.json"), subs)
    a_final = strip_volatile(load(after / "verify" / "final_report.json"), subs)
    if b_final.get("components") != a_final.get("components"):
        problems.append(f"final components: {b_final.get('components')} -> "
                        f"{a_final.get('components')}")
    print(f"components: {a_final.get('components')} | overall {a_final.get('overall')}")
    b_iface = b_final.get("details", {}).get("interfaces", {})
    a_iface = a_final.get("details", {}).get("interfaces", {})
    if b_iface.get("issues") != a_iface.get("issues"):
        problems.append(f"interface issues: {b_iface.get('issues')} -> "
                        f"{a_iface.get('issues')}")
    print(f"interface issues: {a_iface.get('issues')}")

    files = sorted(p for p in after.rglob("*") if p.is_file()
                   and p.relative_to(after).parts[0] != "verify")
    for path in files:
        rel = path.relative_to(after)
        other = before / rel
        if not other.exists():
            print(f"only-after  {rel}")
            continue
        if path.suffix in SKIP_HASH:
            print(f"size-only   {rel} {other.stat().st_size} -> {path.stat().st_size}")
            continue
        if path.stat().st_size > SMALL or other.stat().st_size > SMALL:
            print(f"size-only   {rel} {other.stat().st_size} -> {path.stat().st_size}")
            continue
        if path.suffix in (".json", ".yaml", ".yml"):
            if strip_volatile(load(other), subs) != strip_volatile(load(path), subs):
                problems.append(f"document differs: {rel}")
        else:
            if hashlib.sha256(other.read_bytes()).hexdigest() != \
                    hashlib.sha256(path.read_bytes()).hexdigest():
                problems.append(f"file differs: {rel}")

    # verify/ is 03's own output; compare interface_check.json directly
    b_json = strip_volatile(load(before / "verify" / "interface_check.json"), subs)
    a_json = strip_volatile(load(after / "verify" / "interface_check.json"), subs)
    if b_json.get("issues") != a_json.get("issues"):
        problems.append(f"interface_check issues: {b_json.get('issues')} -> "
                        f"{a_json.get('issues')}")
    elif b_json.get("parsed_refs") != a_json.get("parsed_refs"):
        print(f"parsed_refs: {b_json.get('parsed_refs')} -> {a_json.get('parsed_refs')}")

    print("RESULT:", "IDENTICAL" if not problems else f"DIFFERENCES {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

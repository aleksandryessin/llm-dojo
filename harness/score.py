"""Scorer + reporter for the `tool-calling` suite.

Deterministic only — no LLM judge here. A case passes when the model called exactly the
expected set of tools AND every checked argument matches. For `no_tool` cases, calling any
tool is the failure.

Usage:
    uv run -m harness.score                      # scores the newest run file
    uv run -m harness.score --runs 2026...jsonl  # or a specific one
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"


def norm(value: str) -> str:
    """Normalise names so billing-core / billing_core / Billing Core compare equal."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def check_args(expected: dict, actual: dict) -> tuple[bool, str]:
    """expected: {'equal': {...}} or {'contains': {arg: [substrings]}}"""
    for arg, want in (expected.get("equal") or {}).items():
        got = actual.get(arg)
        if got is None:
            return False, f"missing arg {arg}"
        if norm(got) != norm(want):
            return False, f"{arg}={got!r} != {want!r}"
    for arg, options in (expected.get("contains") or {}).items():
        got = norm(actual.get(arg, ""))
        if not any(norm(opt) in got for opt in options):
            return False, f"{arg}={actual.get(arg)!r} contains none of {options}"
    return True, ""


REFUSAL = "NOT_IN_CORPUS"


def cyrillic_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum("а" <= c.lower() <= "я" or c.lower() == "ё" for c in letters) / len(letters) if letters else 0.0


def language_ok(lang: str, answer: str) -> bool:
    """RU answers must be mostly Cyrillic; EN answers mostly not (tech terms stay Latin)."""
    ratio = cyrillic_ratio(answer)
    return ratio >= 0.3 if lang == "ru" else ratio <= 0.1


def score_rag_record(rec: dict, case: dict) -> dict:
    if rec.get("error"):
        return {**rec, "passed": False, "reason": rec["error"]}
    answer = rec["answer"]
    refused = REFUSAL in answer
    lang_ok = language_ok(case["lang"], answer)
    expect = case.get("expect") or {}

    if case["type"] == "unanswerable":
        passed = refused and lang_ok
        reason = "" if passed else ("answered instead of refusing" if not refused else "wrong language")
        return {**rec, "passed": passed, "reason": reason,
                "refused": refused, "lang_ok": lang_ok, "retrieval_hit": None}

    # answerable
    retrieval_hit = expect["source"] in rec["sources"]
    grounded = any(norm(f) in norm(answer) for f in expect["facts_any"])
    cited = bool(re.search(r"\[\d+\]", answer))
    passed = grounded and not refused and lang_ok
    reason = ("" if passed else
              "refused on an answerable question" if refused else
              f"missing all expected facts {expect['facts_any']}" if not grounded else
              "wrong language")
    return {**rec, "passed": passed, "reason": reason, "refused": refused,
            "lang_ok": lang_ok, "retrieval_hit": retrieval_hit, "cited": cited}


def score_record(rec: dict, case: dict) -> dict:
    expect = case["expect"]
    if rec.get("error"):
        return {**rec, "passed": False, "reason": rec["error"]}

    called = [c["name"] for c in rec["tool_calls"]]
    if set(called) != set(expect["tools"]):
        want = expect["tools"] or ["(no tool)"]
        return {**rec, "passed": False, "reason": f"called {called or ['(no tool)']}, expected {want}"}

    for tool_name, arg_spec in (expect.get("args") or {}).items():
        actual = next(c["args"] for c in rec["tool_calls"] if c["name"] == tool_name)
        ok, why = check_args(arg_spec, actual)
        if not ok:
            return {**rec, "passed": False, "reason": f"{tool_name}: {why}"}

    return {**rec, "passed": True, "reason": ""}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=None, help="run file name; default = newest")
    args = ap.parse_args()

    path = RUNS / args.runs if args.runs else max(RUNS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    suite = records[0]["suite"]
    spec = yaml.safe_load((ROOT / "suites" / suite.replace("-", "_") / "cases.yaml").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in spec["cases"]}

    scorer = score_rag_record if spec.get("kind") == "rag" else score_record
    scored = [scorer(r, cases[r["case_id"]]) for r in records]

    # aggregate: per model per language, plus the EN->RU delta this suite exists for
    agg = defaultdict(lambda: defaultdict(list))
    for s in scored:
        agg[s["model"]][s["lang"]].append(s)

    lines = [f"# Report — suite `{suite}`", "", f"Raw runs: `runs/{path.name}`", ""]
    lines += ["| Model | EN | RU | Δ EN→RU | mean latency |", "|---|---|---|---|---|"]
    for model, by_lang in agg.items():
        en = by_lang.get("en", [])
        ru = by_lang.get("ru", [])
        en_score = sum(s["passed"] for s in en) / len(en) if en else 0
        ru_score = sum(s["passed"] for s in ru) / len(ru) if ru else 0
        lat = [s["latency_s"] for s in en + ru]
        lines.append(
            f"| `{model}` | {en_score:.2f} ({sum(s['passed'] for s in en)}/{len(en)}) "
            f"| {ru_score:.2f} ({sum(s['passed'] for s in ru)}/{len(ru)}) "
            f"| {ru_score - en_score:+.2f} | {sum(lat)/len(lat):.1f}s |"
        )

    lines += ["", "## Failures", ""]
    failures = [s for s in scored if not s["passed"]]
    if failures:
        lines += ["| Model | Case | Type | Why |", "|---|---|---|---|"]
        lines += [
            f"| `{s['model']}` | {s['case_id']} | {s['type']} | {s['reason'].replace('|', '/')} |"
            for s in failures
        ]
    else:
        lines.append("_none_")

    REPORTS.mkdir(exist_ok=True)
    report = REPORTS / f"{suite}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwritten: {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

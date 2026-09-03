"""Deterministic scorer + reporter for harness suite runs.

For tool calling, a case passes when the model called exactly the expected tool multiset and
every checked argument matches. For RAG, grounded facts, citation presence, refusal protocol,
and language adherence are checked without an LLM judge.

Usage:
    uv run -m harness.score                      # scores the newest suite run
    uv run -m harness.score --runs 2026...jsonl  # or a specific one
"""
import argparse
import json
import re
from collections import Counter, defaultdict
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


def read_records(path: Path) -> list[dict]:
    """Read one non-empty JSONL run and fail with a useful CLI error."""
    try:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except FileNotFoundError as exc:
        raise SystemExit(f"run file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSONL in {path}: {exc}") from exc
    if not records:
        raise SystemExit(f"run file is empty: {path}")
    return records


def latest_suite_run(runs_dir: Path = RUNS) -> Path:
    """Return the newest harness suite run, ignoring speed-benchmark JSONL files."""
    candidates = []
    for path in runs_dir.glob("*.jsonl"):
        try:
            first = next(
                line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
            )
            record = json.loads(first)
        except (OSError, StopIteration, json.JSONDecodeError):
            continue
        if record.get("suite"):
            candidates.append(path)
    if not candidates:
        raise SystemExit(f"no suite runs found in {runs_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def resolve_run_path(value: str | None) -> Path:
    """Resolve a CLI path; bare names remain relative to the conventional runs/ folder."""
    if value is None:
        return latest_suite_run()
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path if len(path.parts) > 1 else RUNS / path


def cyrillic_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("а" <= c.lower() <= "я" or c.lower() == "ё" for c in letters) / len(letters)


def language_ok(lang: str, answer: str) -> bool:
    """RU answers must be mostly Cyrillic; EN answers mostly not (tech terms stay Latin)."""
    ratio = cyrillic_ratio(answer)
    return ratio >= 0.3 if lang == "ru" else ratio <= 0.1


def score_rag_record(rec: dict, case: dict) -> dict:
    if rec.get("error"):
        return {**rec, "passed": False, "reason": rec["error"]}
    answer = rec["answer"]
    refused = answer.lstrip().startswith(REFUSAL)
    lang_ok = language_ok(case["lang"], answer)
    expect = case.get("expect") or {}

    if case["type"] == "unanswerable":
        passed = refused and lang_ok
        reason = "" if passed else ("answered instead of refusing" if not refused else "wrong language")
        return {
            **rec,
            "passed": passed,
            "reason": reason,
            "refused": refused,
            "lang_ok": lang_ok,
            "retrieval_hit": None,
        }

    # answerable
    retrieval_hit = expect["source"] in rec["sources"]
    grounded = any(norm(f) in norm(answer) for f in expect["facts_any"])
    cited = bool(re.search(r"\[\d+\]", answer))
    passed = grounded and cited and not refused and lang_ok
    reason = (
        ""
        if passed
        else "refused on an answerable question"
        if refused
        else f"missing all expected facts {expect['facts_any']}"
        if not grounded
        else "missing citation"
        if not cited
        else "wrong language"
    )
    return {
        **rec,
        "passed": passed,
        "reason": reason,
        "refused": refused,
        "lang_ok": lang_ok,
        "retrieval_hit": retrieval_hit,
        "cited": cited,
    }


def score_record(rec: dict, case: dict) -> dict:
    expect = case["expect"]
    if rec.get("error"):
        return {**rec, "passed": False, "reason": rec["error"]}

    called = [c["name"] for c in rec["tool_calls"]]
    if Counter(called) != Counter(expect["tools"]):
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
    ap.add_argument(
        "--runs",
        default=None,
        help="run path, or a file name under runs/; default = newest suite run",
    )
    args = ap.parse_args()

    path = resolve_run_path(args.runs)
    records = read_records(path)
    suite = records[0].get("suite")
    if not suite:
        raise SystemExit(f"not a suite run (missing 'suite' in first record): {path}")
    suite_path = ROOT / "suites" / suite.replace("-", "_") / "cases.yaml"
    if not suite_path.is_file():
        raise SystemExit(f"suite definition not found for {suite!r}: {suite_path}")
    spec = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in spec["cases"]}

    unknown_cases = sorted({record.get("case_id") for record in records} - cases.keys())
    if unknown_cases:
        raise SystemExit(f"run contains cases absent from suite {suite!r}: {unknown_cases}")

    scorer = score_rag_record if spec.get("kind") == "rag" else score_record
    scored = [scorer(r, cases[r["case_id"]]) for r in records]

    # aggregate: per model per language, plus the EN->RU delta this suite exists for
    agg = defaultdict(lambda: defaultdict(list))
    for s in scored:
        agg[s["model"]][s["lang"]].append(s)

    try:
        display_path = path.resolve().relative_to(ROOT)
    except ValueError:
        display_path = path
    lines = [f"# Report — suite `{suite}`", "", f"Raw runs: `{display_path}`", ""]
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

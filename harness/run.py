"""Runner: executes a suite as a model × case matrix and stores RAW results.

Raw runs are never modified afterwards — scoring is a separate pass (harness/score.py),
so fixing a scorer costs a re-score, not a re-run of every model.

Usage:
    uv run -m harness.run --suite tool-calling --models qwen2.5:7b,llama3.2:3b
    uv run -m harness.run --suite tool-calling --models qwen2.5:7b --runtime lmstudio
"""
import argparse
import importlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harness.adapters import get_client

ROOT = Path(__file__).resolve().parents[1]
SUITES = ROOT / "suites"
RUNS = ROOT / "runs"


def load_suite(name: str):
    """A suite = cases.yaml (data) + tools.py (the tool schemas offered to the model)."""
    folder = SUITES / name.replace("-", "_")
    spec = yaml.safe_load((folder / "cases.yaml").read_text(encoding="utf-8"))
    tools = importlib.import_module(f"suites.{folder.name}.tools").TOOLS
    return spec, tools


def run_case(client, model: str, system: str, prompt: str, tools: list) -> dict:
    """One model call. Returns the raw observation: tool calls, text, timing, error."""
    started = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            tools=tools,
            temperature=0,
        )
    except Exception as exc:  # a runtime/model that cannot do tool calling is a result too
        return {"error": f"{type(exc).__name__}: {exc}", "latency_s": time.perf_counter() - started}

    latency = time.perf_counter() - started
    msg = resp.choices[0].message
    calls = []
    for tc in msg.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {"__unparsed__": tc.function.arguments}
        calls.append({"name": tc.function.name, "args": args})
    usage = getattr(resp, "usage", None)
    return {
        "tool_calls": calls,
        "content": msg.content,
        "latency_s": latency,
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "error": None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="tool-calling")
    ap.add_argument("--models", required=True, help="comma-separated model tags")
    ap.add_argument("--runtime", default="ollama", help="ollama | lmstudio | vllm")
    args = ap.parse_args()

    spec, tools = load_suite(args.suite)
    client = get_client(args.runtime)
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    RUNS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RUNS / f"{stamp}-{args.suite}.jsonl"

    with out.open("w", encoding="utf-8") as fh:
        for model in models:
            print(f"\n=== {model} ({args.runtime})")
            for case in spec["cases"]:
                system = spec["system"][case["lang"]]
                result = run_case(client, model, system, case["prompt"], tools)
                record = {
                    "suite": args.suite,
                    "model": model,
                    "runtime": args.runtime,
                    "case_id": case["id"],
                    "pair": case["pair"],
                    "type": case["type"],
                    "lang": case["lang"],
                    **result,
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                fh.flush()
                mark = "ERR" if result.get("error") else ", ".join(
                    c["name"] for c in result["tool_calls"]) or "(no tool)"
                print(f"  {case['id']:24s} {result['latency_s']:5.1f}s  -> {mark}")

    print(f"\nraw runs: {out.relative_to(ROOT)}\nnext: uv run -m harness.score --runs {out.name}")


if __name__ == "__main__":
    main()

import json
import tempfile
import unittest
from pathlib import Path

from harness.score import latest_suite_run, score_rag_record, score_record


class ScoreTests(unittest.TestCase):
    def test_duplicate_tool_call_is_a_failure(self):
        record = {
            "error": None,
            "tool_calls": [
                {"name": "lookup", "args": {}},
                {"name": "lookup", "args": {}},
            ],
        }
        case = {"expect": {"tools": ["lookup"]}}
        self.assertFalse(score_record(record, case)["passed"])

    def test_answerable_rag_requires_a_citation(self):
        record = {
            "error": None,
            "answer": "PagedAttention manages KV memory efficiently.",
            "sources": ["vllm-readme.md"],
        }
        case = {
            "lang": "en",
            "type": "answerable",
            "expect": {"source": "vllm-readme.md", "facts_any": ["PagedAttention"]},
        }
        scored = score_rag_record(record, case)
        self.assertFalse(scored["passed"])
        self.assertEqual(scored["reason"], "missing citation")

    def test_refusal_marker_must_start_the_answer(self):
        record = {
            "error": None,
            "answer": "The answer is missing; use NOT_IN_CORPUS when that happens.",
            "sources": [],
        }
        case = {"lang": "en", "type": "unanswerable", "expect": {}}
        scored = score_rag_record(record, case)
        self.assertFalse(scored["passed"])
        self.assertEqual(scored["reason"], "answered instead of refusing")

    def test_latest_suite_run_skips_speed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = root / "older-suite.jsonl"
            speed = root / "newer-speed.jsonl"
            suite.write_text(json.dumps({"suite": "tool-calling"}) + "\n")
            speed.write_text(json.dumps({"type": "summary"}) + "\n")
            speed.touch()
            self.assertEqual(latest_suite_run(root), suite)


if __name__ == "__main__":
    unittest.main()

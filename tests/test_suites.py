import importlib.util
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class SuiteContractTests(unittest.TestCase):
    def test_env_example_does_not_supply_required_secrets(self):
        env_path = ROOT / "patterns" / "05-serving-vllm" / ".env.example"
        values = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        required_secrets = {
            "NEO4J_PASSWORD",
            "POSTGRES_PASSWORD",
            "LANGFUSE_NEXTAUTH_SECRET",
            "LANGFUSE_SALT",
            "LANGFUSE_ENCRYPTION_KEY",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_USER_PASSWORD",
        }
        self.assertEqual(
            {name: values.get(name) for name in required_secrets},
            dict.fromkeys(required_secrets, ""),
        )

    def test_every_pair_has_one_english_and_one_russian_case(self):
        for suite_path in sorted((ROOT / "suites").glob("*/cases.yaml")):
            spec = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
            ids = [case["id"] for case in spec["cases"]]
            self.assertEqual(len(ids), len(set(ids)), f"duplicate case id in {suite_path}")
            pairs = {}
            for case in spec["cases"]:
                pairs.setdefault(case["pair"], []).append(case["lang"])
            for pair, languages in pairs.items():
                self.assertEqual(sorted(languages), ["en", "ru"], f"{suite_path}: {pair}")

    def test_each_pattern_is_documented_and_runnable(self):
        for pattern in sorted((ROOT / "patterns").iterdir()):
            if not pattern.is_dir():
                continue
            self.assertTrue((pattern / "README.md").is_file(), pattern)
            self.assertTrue(any(pattern.glob("*.py")), pattern)

    def test_default_rag_sources_are_commit_pinned(self):
        path = ROOT / "patterns" / "04-rag-citations" / "fetch_docs.py"
        spec = importlib.util.spec_from_file_location("fetch_docs", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        commit_url = re.compile(r"raw\.githubusercontent\.com/[^/]+/[^/]+/[0-9a-f]{40}/")
        for name, url in module.SOURCES.items():
            self.assertRegex(url, commit_url, name)


if __name__ == "__main__":
    unittest.main()

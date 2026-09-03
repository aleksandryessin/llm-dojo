#!/usr/bin/env python3
"""Fail on artifacts that do not belong in the public repository."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAX_TRACKED_BYTES = 1_000_000
FORBIDDEN_SUFFIXES = {".pdf", ".docx", ".pptx", ".key", ".pem", ".p12", ".pfx"}
REQUIRED_PATHS = {
    "AGENTS.md",
    "STATUS.md",
    ".github/workflows/ci.yml",
    "harness/run.py",
    "harness/score.py",
    "suites/tool_calling/cases.yaml",
    "suites/rag_grounding/cases.yaml",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    # Split the literal so this checker does not flag its own source.
    "absolute macOS home path": re.compile("/" + r"Users/[^/\s]+/"),
}


def tracked_files() -> list[Path]:
    # Include publishable untracked files so the check is useful before the first commit too.
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    return [ROOT / name.decode() for name in output.split(b"\0") if name]


def check_evidence_hashes(errors: list[str]) -> None:
    manifest = yaml.safe_load((ROOT / "runs" / "evidence.yaml").read_text(encoding="utf-8"))
    for group in ("capability", "serving"):
        for item in manifest[group]:
            path = ROOT / item["path"]
            if not path.is_file():
                errors.append(f"evidence file is missing: {item['path']}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != item["sha256"]:
                errors.append(f"evidence hash mismatch: {item['path']}")


def check_local_links(files: list[Path], errors: list[str]) -> None:
    link = re.compile(r"\[[^]]*\]\(([^)]+)\)")
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for target in link.findall(text):
            target = target.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken local link in {path.relative_to(ROOT)}: {target}")


def check_reachable_history(errors: list[str]) -> None:
    """Scan every unique blob reachable from a local ref, not only the current checkout."""
    output = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT)
    seen = set()
    for line in output.decode().splitlines():
        object_id, _, historical_path = line.partition(" ")
        if not historical_path:
            continue
        if Path(historical_path).suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden artifact in reachable history: {historical_path}")
        if object_id in seen:
            continue
        seen.add(object_id)
        blob = subprocess.run(
            ["git", "cat-file", "blob", object_id],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        if blob.returncode or len(blob.stdout) > MAX_TRACKED_BYTES:
            continue
        try:
            text = blob.stdout.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label} in reachable history: {historical_path}")


def main() -> int:
    files = tracked_files()
    tracked_names = {str(path.relative_to(ROOT)) for path in files}
    errors = [f"required public file is missing: {name}" for name in sorted(REQUIRED_PATHS - tracked_names)]

    for path in files:
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            errors.append(f"tracked symlink requires manual publication review: {relative}")
            continue
        if path.name == ".env" or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden tracked artifact: {relative}")
        if path.stat().st_size > MAX_TRACKED_BYTES:
            errors.append(f"tracked file exceeds {MAX_TRACKED_BYTES} bytes: {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label} in {relative}")

    check_evidence_hashes(errors)
    check_local_links(files, errors)
    check_reachable_history(errors)

    if errors:
        print("public-repo check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"public-repo check passed ({len(files)} tracked files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

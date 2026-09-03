"""Fetch the documentation corpus for the RAG pattern into data/docs/.

Sources are public markdown files from the upstream projects (vLLM, LangGraph, RAGAS, …) —
fetched at setup time, never vendored into this repo (their licences stay theirs).

Two corpora:

*   `data/docs/` (default) — curated and small on purpose: a handful of READMEs. Small enough
    that a brute-force dot product over every chunk is the honest baseline, which is the point
    pattern 04 makes.
*   `data/docs-large/` (`--large`) — the full published docs of LangChain/LangGraph and Qdrant,
    tens of MB. At this size the brute-force baseline starts to hurt, which is what makes a
    retriever comparison (numpy vs Qdrant vs pgvector) worth measuring instead of asserting.

Run:  uv run patterns/04-rag-citations/fetch_docs.py [--large]
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data"

# Default corpus revisions pinned on 2026-09-03. Moving main/master branches make an old score
# impossible to reproduce even when the suite and model are unchanged.
SOURCES = {
    "vllm-readme.md": "https://raw.githubusercontent.com/vllm-project/vllm/bb363db9a5ec2edc7b39e99b00af363a89d1fb81/README.md",
    "langgraph-readme.md": "https://raw.githubusercontent.com/langchain-ai/langgraph/11738d83db4320bb191804342b5c76ae7eca54a0/README.md",
    "ragas-readme.md": "https://raw.githubusercontent.com/explodinggradients/ragas/298b68274234c060deacab3cf5fb52aa3a20e885/README.md",
    "uv-readme.md": "https://raw.githubusercontent.com/astral-sh/uv/0e886db78e891c0a148992f13190223f92537aaa/README.md",
    "ollama-readme.md": "https://raw.githubusercontent.com/ollama/ollama/b79067b0db7417f20108363bc22adb97f35c966a/README.md",
    "ollama-api.md": "https://raw.githubusercontent.com/ollama/ollama/b79067b0db7417f20108363bc22adb97f35c966a/docs/api.md",
    # storage layer — the vector contour the retriever comparison swaps between
    "qdrant-readme.md": "https://raw.githubusercontent.com/qdrant/qdrant/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/README.md",
    "qdrant-client-readme.md": "https://raw.githubusercontent.com/qdrant/qdrant-client/550484d767d319857d4f46e97d4551ba419ee670/README.md",
    "pgvector-readme.md": "https://raw.githubusercontent.com/pgvector/pgvector/e48241b4dcc045b18902914f668d03d1d399dfbe/README.md",
    # observability / evals
    "langsmith-sdk-readme.md": "https://raw.githubusercontent.com/langchain-ai/langsmith-sdk/abf10e88ee851a268d2cc801999272bbe2fb803f/README.md",
    "langfuse-readme.md": "https://raw.githubusercontent.com/langfuse/langfuse/a4ebd331861dd3a6ea550736b9e11fd13cc4d924/README.md",
}

# Whole published doc sites, served as one flat text file for machine consumption.
LARGE_SOURCES = {
    "langchain-langgraph-full.txt": "https://docs.langchain.com/llms-full.txt",
    "langchain-index.txt": "https://docs.langchain.com/llms.txt",
    "qdrant-index.txt": "https://qdrant.tech/llms.txt",
}


def fetch(sources: dict[str, str], dest: Path) -> None:
    downloaded, failed = {}, []
    for name, url in sources.items():
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                text = resp.read().decode("utf-8")
            print(f"  {name:30s} {len(text):>9d} chars")
            downloaded[name] = text
        except Exception as exc:
            failed.append((name, str(exc)))
    print(f"\nfetched {len(downloaded)}/{len(sources)}")
    for name, err in failed:
        print(f"  FAILED {name}: {err}")
    if failed:
        raise SystemExit("corpus fetch incomplete; existing files were left unchanged")

    dest.mkdir(parents=True, exist_ok=True)
    for name, text in downloaded.items():
        (dest / name).write_text(text, encoding="utf-8")
    provenance = {
        name: {
            "url": sources[name],
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "bytes": len(text.encode()),
        }
        for name, text in downloaded.items()
    }
    (dest / "_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote corpus and provenance -> {dest}")


def main() -> None:
    if "--large" in sys.argv:
        fetch(LARGE_SOURCES, ROOT / "docs-large")
    else:
        fetch(SOURCES, ROOT / "docs")


if __name__ == "__main__":
    main()

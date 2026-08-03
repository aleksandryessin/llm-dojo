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
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data"

SOURCES = {
    "vllm-readme.md": "https://raw.githubusercontent.com/vllm-project/vllm/main/README.md",
    "langgraph-readme.md": "https://raw.githubusercontent.com/langchain-ai/langgraph/main/README.md",
    "ragas-readme.md": "https://raw.githubusercontent.com/explodinggradients/ragas/main/README.md",
    "uv-readme.md": "https://raw.githubusercontent.com/astral-sh/uv/main/README.md",
    "ollama-readme.md": "https://raw.githubusercontent.com/ollama/ollama/main/README.md",
    "ollama-api.md": "https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md",
    # storage layer — the vector contour the retriever comparison swaps between
    "qdrant-readme.md": "https://raw.githubusercontent.com/qdrant/qdrant/master/README.md",
    "qdrant-client-readme.md": "https://raw.githubusercontent.com/qdrant/qdrant-client/master/README.md",
    "pgvector-readme.md": "https://raw.githubusercontent.com/pgvector/pgvector/master/README.md",
    # observability / evals
    "langsmith-sdk-readme.md": "https://raw.githubusercontent.com/langchain-ai/langsmith-sdk/main/README.md",
    "langfuse-readme.md": "https://raw.githubusercontent.com/langfuse/langfuse/main/README.md",
}

# Whole published doc sites, served as one flat text file for machine consumption.
LARGE_SOURCES = {
    "langchain-langgraph-full.txt": "https://docs.langchain.com/llms-full.txt",
    "langchain-index.txt": "https://docs.langchain.com/llms.txt",
    "qdrant-index.txt": "https://qdrant.tech/llms.txt",
}


def fetch(sources: dict[str, str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for name, url in sources.items():
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                text = resp.read().decode("utf-8")
            (dest / name).write_text(text, encoding="utf-8")
            print(f"  {name:30s} {len(text):>9d} chars")
            ok += 1
        except Exception as exc:
            failed.append((name, str(exc)))
    print(f"\nfetched {ok}/{len(sources)} into {dest}")
    for name, err in failed:
        print(f"  FAILED {name}: {err}")


def main() -> None:
    if "--large" in sys.argv:
        fetch(LARGE_SOURCES, ROOT / "docs-large")
    else:
        fetch(SOURCES, ROOT / "docs")


if __name__ == "__main__":
    main()

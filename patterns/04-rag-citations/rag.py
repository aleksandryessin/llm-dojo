"""RAG with citations and honest refusal, over the docs corpus in data/docs/.

The three decisions this pattern demonstrates:
1. Chunking follows document structure (markdown headings), not a fixed character count.
2. Every answer cites its sources as [1] [2]; every chunk knows its file and heading.
3. The model is explicitly allowed to refuse: if the context does not contain the answer,
   the correct behaviour is "not in the corpus" — refusal is scored later by the
   rag-grounding suite, it is not a failure mode.

No vector DB on purpose: ~100 chunks -> plain lists and a dot product. See the README
("when a numpy array beats a vector database").

Run:  uv run patterns/04-rag-citations/fetch_docs.py     # once, downloads corpus
      uv run patterns/04-rag-citations/rag.py "How does continuous batching work in vLLM?"
      uv run patterns/04-rag-citations/rag.py --rebuild   # after changing the corpus
"""
import json
import re
import sys
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "data" / "docs"
INDEX = ROOT / "data" / "index.json"

EMBED_MODEL = "nomic-embed-text"     # exercise: swap to bge-m3 and re-run the RU questions
CHAT_MODEL = "qwen2.5:7b"
TOP_K = 4

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


# ---------- indexing ----------------------------------------------------------------

def chunk_markdown(name: str, text: str, max_chars: int = 1800) -> list[dict]:
    """Split on headings first (structure-aware), then hard-wrap oversized sections."""
    chunks = []
    for section in re.split(r"\n(?=#{1,3} )", text):
        section = section.strip()
        if len(section) < 80:                      # skip stubs like a lone badge line
            continue
        heading = section.splitlines()[0].lstrip("# ").strip()
        for i in range(0, len(section), max_chars):
            chunks.append({"source": name, "heading": heading, "text": section[i : i + max_chars]})
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def build_index() -> list[dict]:
    files = sorted(DOCS.glob("*.md"))
    if not files:
        raise SystemExit(f"corpus is empty — run fetch_docs.py first (looked in {DOCS})")
    chunks = [c for f in files for c in chunk_markdown(f.name, f.read_text(encoding="utf-8"))]
    for batch_start in range(0, len(chunks), 32):
        batch = chunks[batch_start : batch_start + 32]
        for chunk, vector in zip(batch, embed([c["text"] for c in batch])):
            chunk["embedding"] = vector
    INDEX.write_text(json.dumps(chunks), encoding="utf-8")
    print(f"indexed {len(chunks)} chunks from {len(files)} files -> {INDEX.name}")
    return chunks


def load_index() -> list[dict]:
    if not INDEX.exists():
        return build_index()
    return json.loads(INDEX.read_text(encoding="utf-8"))


# ---------- retrieval + generation --------------------------------------------------

def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0

def retrieve(chunks: list[dict], question: str, k: int = TOP_K) -> list[tuple[float, dict]]:
    q = embed([question])[0]
    scored = sorted(((cosine(q, c["embedding"]), c) for c in chunks), key=lambda t: -t[0])
    return list(scored[:k])


# Machine-checkable refusal: the model must START a refusal with this exact token, then
# explain in the question's language. Scorers grep the token instead of guessing from prose.
REFUSAL_MARKER = "NOT_IN_CORPUS"

SYSTEM = (
    "Answer using ONLY the numbered context passages. Cite passages as [1], [2] after each "
    f"claim. If the context does not contain the answer, start your reply with {REFUSAL_MARKER} "
    "and then briefly say, in the language of the question, what is missing. "
    "Always answer in the same language as the question."
)


def ask(question: str, chunks: list[dict] | None = None, model: str = CHAT_MODEL) -> dict:
    """Full pipeline as a reusable function — the rag-grounding suite calls this directly."""
    chunks = chunks if chunks is not None else load_index()
    hits = retrieve(chunks, question)
    context = "\n\n".join(
        f"[{i+1}] ({c['source']} — {c['heading']})\n{c['text']}" for i, (_, c) in enumerate(hits)
    )
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return {
        "answer": resp.choices[0].message.content or "",
        "sources": [c["source"] for _, c in hits],
        "top_cos": hits[0][0] if hits else 0.0,
        "hits": hits,
    }


def answer(question: str) -> None:
    result = ask(question)
    print(f"Q: {question}\n")
    print(result["answer"])
    print("\nSources:")
    for i, (score, c) in enumerate(result["hits"]):
        print(f"  [{i+1}] {c['source']} — {c['heading']}  (cos {score:.3f})")


if __name__ == "__main__":
    if "--rebuild" in sys.argv:
        build_index()
        sys.exit(0)
    question = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or (
        "How does vLLM achieve high throughput?"
    )
    answer(question)

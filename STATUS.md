# Maintainer handoff

Updated: 2026-09-03

## Git state at audit start

- `main` was clean and matched freshly fetched `origin/main` at `607fb68` (`0` ahead, `0` behind).
- The audit work is isolated on `codex/public-showcase-audit`; it has no upstream and has not
  been pushed or merged.
- The only remote is `origin` at the public GitHub repository.
- Full reachable history contained no PDFs, office documents, oversized blobs, or high-confidence
  credential signatures. Local ignored `.env`, corpus, cache, and exploratory runs were not
  tracked.

## Security cleanup

- A deep object-database check found an encrypted OpenSSH private key and its public key as loose,
  unreachable blobs. They were never part of the reachable history and would not be included in a
  normal push, but both objects were pruned and a second `git fsck --full --no-reflogs` is clean.
- Treat the key as compromised anyway. Its public fingerprint is
  `SHA256:7U+y8Q8Aw1aCrS0zRN5zW1cW/bSTAAjQIEuDjkhRolI`; AY should remove that key from every
  `authorized_keys`, Git host, and service where it was registered, then replace it if still used.
- The only other unreachable object was an unfinished pattern 07 commit. Before pruning it, a
  recovery patch was saved as
  `/tmp/llm-dojo-recovery-600952b/0001-pattern-07-scaffold-karpathy-autoresearch-loop-on-a-.patch`
  (SHA-256 `524c30081a738bbd86e13a46546580835e5ea7a92a790b9472ac3d2111859e68`).

## Public state after this audit

- Five pattern directories exist. Patterns 01–04 are runnable examples; pattern 05 is an
  integration skeleton with unfinished semantic-cache code, not a production reference.
- Two suites exist: `tool-calling` (6 EN/RU pairs) and `rag-grounding` (9 EN/RU pairs).
- Reviewed evidence is allow-listed under `runs/`; all other runs remain ignored.
- CI exercises Python 3.11/3.12, compilation, unit/suite contracts, public-artifact checks,
  report regeneration, and Docker Compose validation without calling a live model.
- `AGENTS.md` and `docs/PUBLICATION_BOUNDARY.md` define the public/private boundary.

## Verification completed

- `uv sync --frozen --offline`: passed against the root lock.
- Python 3.11 and 3.12: 8 offline tests passed on each version.
- Compilation of `harness`, `patterns`, `suites`, `tests`, and `scripts`: passed.
- Public artifact/history scan: passed for 52 publishable files; evidence hashes and local links
  verified.
- Both reviewed capability reports regenerate byte-for-byte from the allow-listed JSONL.
- Docker Compose renders both without interpolation and with CI-only secret values.
- All 11 pinned default-corpus URLs resolved; the fetcher wrote a complete provenance manifest in
  a temporary validation directory.
- `git fsck --full --no-reflogs`: clean after the security cleanup.

## Important result correction

The RAG scorer previously calculated citation presence but did not require it for `passed`.
After enforcing the documented contract, `gemma3:1b` English RAG changes from `0.89` to `0.33`;
the other aggregate rows are unchanged. This is a scorer correction over immutable observations,
not a new model run.

## Known limits

- Live Ollama/vLLM execution is not part of CI. Published sample sizes are smoke tests, not a
  leaderboard or a statistical performance study.
- The default RAG fetch now pins upstream commit revisions and writes a local provenance file.
  The older reviewed run predates that rule and identifies its historical corpus by SHA-256 only;
  byte-for-byte recovery of that older corpus is not guaranteed by this repository.
- The application base image and Python dependencies are digest/hash-pinned. Compose service
  images are still tag-pinned rather than digest-pinned.
- Pattern 05 intentionally leaves semantic cache lookup/storage as TODO; its Compose wiring and
  health path can be validated, but the cache behavior cannot be claimed complete.

## AY next steps

1. Review the branch diff, especially the corrected RAG interpretation and publication policy.
2. Run the checks from `AGENTS.md` in a clean environment.
3. If accepted, commit and push this topic branch, then open a PR. Do not merge directly to
   `main` from the audit session.
4. For the next RAG run, copy the generated corpus hashes into evidence metadata and record the
   Ollama/model versions as well as the tags.

The sibling learning repository had pre-existing modified and untracked files. This audit read
its structure for classification only and made no changes there.

Local Docker image assembly could not run because the Docker daemon was stopped. The base-image
manifest and pinned RAG URLs were verified remotely; Compose rendering passed, and CI now performs
the full image build.

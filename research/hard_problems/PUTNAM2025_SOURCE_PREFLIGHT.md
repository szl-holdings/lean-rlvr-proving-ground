# Putnam 2025 exact-source preflight

The companion [offline preflight](putnam25_preflight.py) **does more than count filenames**.
It reads all 12 original Lean source files from an **owner-private** folder,
checks byte lengths and Git blob identities against the frozen
[challenge catalog](catalog.v1.json), ignores comments/string literals in
lexical diagnostics, and requires each expected theorem identity. It records
per-file SHA-256 and theorem-header fingerprints without publishing copyrighted
question text or solutions.

**November 17, 2026 private readback:** all 12 source blobs matched
the public immutable PutnamBench revision
a635813f5edf297d928f9bd5ef8324a26bdde09c.
The original templates contain **18 sorry tokens**, including **six separate
solution-abbreviation declarations**. These are placeholders defining a
benchmark task, **not solutions or verified proofs**.

The preflight also flags a theorem target trivially equivalent to True as a
TRIVIAL_TARGET_HOLD. This static scan is diagnostic only; it cannot detect
all semantically weakened statements, macros, imported axioms or malicious
Lean tactics. Genuine proof qualification requires an owner-controlled
statement registry, formal/informal equivalence review, a separately
approved **OS-isolated credential-free Lean checker**, and source binding.

Use locally, with source files already captured under the owner-private directory:

    python research/hard_problems/putnam25_preflight.py --catalog research/hard_problems/catalog.v1.json --source-dir <OWNER_PRIVATE_EVIDENCE>\putnam25-source-preflight-20261117 --output <OWNER_PRIVATE_EVIDENCE>\new-putnam25-receipt.json

The output is an **exclusive-create** JSON receipt containing only IDs,
digests, counts, structural warnings and honest NOT_RUN / UNAVAILABLE states.
It is not model evaluation, a proof admission receipt or a training launch.
This adds no competing controller, worker, receipt writer, or public problem
copy.

**Next experimental gate:** after Flagship55 has genuinely trained and
immutable YACHAY teacher, WILLAY guide and KHIPU skeptic specialist
adapters, pre-register a heldout Putnam task protocol and compare each
component against source-pinned Flagship54 and original-base baselines.
Bind prompts, tokenizer, adapter/model bytes, sources, compute and trusted
formal theorem statements. Do not insert public benchmark answers into
training gradients or claim improvement from a source preflight.

## Evidence boundaries

- **12/12** means byte-identical source-file integrity, not model accuracy.
- **18 placeholders** are upstream benchmark holes, not 18 solutions.
- **0 model attempts and 0 independent proof replays** in this pass.
- **Flagship55 math success is UNAVAILABLE** pending real model weights,
  source-bound outputs and independent proof checking.

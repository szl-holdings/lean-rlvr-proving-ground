# Source-bound local Putnam model diagnostic (experimental)

**Owner:** SZL proving ground. **State:** TESTED SOFTWARE CONTRACT,
NO QUALIFIED MODEL BENCHMARK.

The companion [local_model_probe.py](local_model_probe.py) accepts only an
original, exact-byte, source-verified Putnam 2025 Lean file and a **declared**
64-hex model manifest digest. It builds a target statement prompt without
reference solution comments, supports a network-free **plan-only** mode, and
can submit one bounded generation to an **already-running local Ollama server**
at http://127.0.0.1:11434. It does not start or restart a server, install a
model, download weights, launch a billable job, modify the original checkpoint,
execute model-produced Lean, or grant proof/training/merging authority.

## Frozen experimental controls

- Source repository: trishullab/PutnamBench
- Source revision: a635813f5edf297d928f9bd5ef8324a26bdde09c
- Source identity: existing challenge catalog + Git blob SHA-1, file length,
  theorem identity and per-file SHA-256 readback.
- Preapproved prompts: 2025 A1, A6, B1, B2, B4, B5 (six source files with
  no upstream solution-abbreviation placeholders in the prefix). All twelve
  problem identities remain in the immutable discovery catalog.
- Request: one response per invocation, temperature 0, seed 749, no streaming,
  maximum output 384 tokens, requested context 4096. The actual Ollama model
  alias and manifest digest are compared with the runtime's model listing
  **before and after** a live generation.
- Endpoint: only local loopback Ollama tags and generate, with redirects and
  proxies disabled. The runtime is existing infrastructure; it is not a
  separately created controller.
- Result: each private exclusive-created receipt records the exact prompt and
  model reply, input/output SHA-256, timing metrics where provided,
  model/catalog/source bindings and explicit evaluation holds.
- Classification: ABSTAIN_RECORDED / REJECTED_UNSAFE_OR_PLACEHOLDER /
  MANUAL_EXTRACTION_REQUIRED / UNVERIFIED_PROOF_TEXT / NO_RESPONSE.
  **None is a kernel-checked proof.**

## Current evidence / local access hold, November 17, 2026

- Existing Ollama API initially returned model aliases and digests, including
  Goedel-Prover-V2-8B Q4_K_M and Khipu 1.5B local manifests.
- At the first bounded **Goedel / Putnam 2025 A1** invocation, Ollama's
  metadata request timed out **before a model response was observed**.
  A later read-only GET also timed out. The runner returned a HOLD and
  **did not write a success receipt, claim a model result, restart Ollama,
  or switch to an unreviewed remote/paid inference provider**.
- Two offline plans for the *same* A1 source/statement were produced under
  private evidence: Goedel and Khipu both use prompt SHA-256
  bc113477401923827b59784dc815c31820a1f80d3d9c4a64f741652bf3a5d1b5.
  These are **not sent prompts or evaluation observations**. Neither model was
  trained/updated nor did this run check a Lean proof.
- Owner-local source proof files, full prompts and any later model responses
  must remain outside the Git checkout. Public source includes code/tests,
  method and digests only.

### How to prepare a private prompt without inference

Run from the proving-ground root, pointing to source files already
materialized in an owner-controlled private folder, with a new private output:

    python research/hard_problems/local_model_probe.py --plan-only --catalog research/hard_problems/catalog.v1.json --source <OWNER_PRIVATE_DIR>/putnam_2025_a1.lean --problem putnam_2025_a1 --model <LOCAL_MODEL_ALIAS> --digest <DECLARED_64_HEX_MODEL_DIGEST> --out <OWNER_PRIVATE_DIR>/new-plan.json

This validates source identity and deterministic prompt encoding but **does
not verify that the model exists or is serving**, and does not contact Ollama.

### One bounded real local attempt (only after the existing service is healthy)

The same command **without** --plan-only invokes the current loopback model.
It requires a genuinely live alias-to-digest match and writes a new,
source-pinned **unverified** response in the owner-private directory. An
unavailable API, changed weights, malformed response, timeout or prior output
path yields HOLD, not retry or fabricated success. The checker never executes
the returned tactics. A complete evaluation protocol must separately bind
runtime configuration, isolated Lean verification, formal/informal equivalence,
heldout contamination, rights, negative controls, denominators and failure
records before calculating a proof success rate.

**Flagship55 specialist status:** YACHAY, WILLAY and KHIPU three-adapter design
is still a source-bound proposal; no Flagship55 teacher/guide/skeptic
weights are verified by this probe. Real local Goedel or Khipu model
observations would be **separate baselines**, not Flagship55 or independent
scientific validation.

All limits, permissions, hashes and tests are scope claims, not a digital
signature. No new paid GPUs, controllers, privilege changes or publication.

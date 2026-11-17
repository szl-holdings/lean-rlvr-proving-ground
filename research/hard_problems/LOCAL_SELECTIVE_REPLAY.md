# Six-case local Putnam behavior replay — no mathematical score

**Observed:** November 17, 2026, 10:10–10:12 UTC. **Scope:** one already-running
on-host Ollama Qwen3 4B local service, not Flagship55 and not the Khipu or
Goedel models. Source-of-truth GitHub proving ground remains unchanged by
the run; no paid compute, model training, source downloads, Lean execution,
service restart or external provider use was initiated.

## Why this matters

The earlier [Putnam 2025 source preflight](PUTNAM2025_SOURCE_PREFLIGHT.md)
only establishes that twelve source files are pinned. The
[local model probe](LOCAL_MODEL_PROBE.md) creates independently
traceable one-shot inference attempts. **This replay** adds an offline,
fail-closed denominator and behavior breakdown that cannot mistake
abstention or unverified text for a proof.

A separate already-running Ollama instance, bound to a verified network
interface **on the owner laptop**, served model
`qwen3:4b-instruct` with manifest digest

`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.

The legacy loopback Ollama endpoint remained unresponsive; no process was
restarted or modified. This is a **separate local baseline**, not an
implied Khipu/Flagship55 model replacement. The one-shot executor used
source-verified original problem bytes and pinned settings: temperature 0,
seed 749, 384 maximum predicted tokens and 4096 requested context. It
reported tag/digest matches before and after each generation. The tag
reads were performed by the same executor and were **not independently
witnessed or signed**.

## Results — behavioral observations, not theorem correctness

| Slice | Observed |
| --- | ---: |
| Putnam 2025 A1, A6, B1, B2, B4, B5 | 6 cases |
| Local inference replies received | 6/6 |
| Replies recorded as explicit ABSTAIN | **6/6** |
| Candidate Lean proof texts proposed | **0** |
| Source-bound reply coverage | **100% of this six-case slice** |
| Answered coverage | **0%** |
| Selective risk | **UNAVAILABLE** (zero answered denominator) |
| Mathematical accuracy | **UNAVAILABLE** |
| Independently replayed / accepted proofs | **0 observed; no checker run** |

This is evidence of **complete abstention on this deliberately hard,
solved-competition slice**, under this prompt, model and exact sampling
configuration. It does *not* prove the model cannot solve any Putnam problem.
No quality claim, statistical generalization, scientific benchmark pass
rate or curriculum reward can be inferred.

**Important experimental implication:** a model can achieve flawless
instructional abstention while supplying zero mathematical utility.
Future teacher/guide/skeptic and GRPO ablations must include **answerable
positive controls** as well as unanswerable, contradictory and unresolved
examples, with predeclared coverage and risk targets. Do not reward
blanket abstention as mathematical progress. Specifically report empty
answer denominators as UNAVAILABLE, never zero-risk.

## Reproducible private readback

The offline `score_local_attempts.py` accepts six individual
owner-private receipts and the original source files under an explicitly
provided private source folder. It recomputes each file, source, prompt,
response and binding digest; rejects duplicate/missing problems, changed
inference identities, malformed timestamps, unsupported backends, false
qualification labels, changed sampling parameters and tampered responses.
Its output is a new exclusively created **private** aggregate with only
case IDs, byte hashes and measured behavior fields. It does not copy the
private raw responses into GitHub.

Illustrative command from the repository root:

    python research/hard_problems/score_local_attempts.py --catalog research/hard_problems/catalog.v1.json --source-dir <PRIVATE_PUTNAM_DIR> --model qwen3:4b-instruct --digest <PINNED_64_HEX_MODEL_DIGEST> --receipt <PRIVATE_A1_RECEIPT> --receipt <PRIVATE_A6_RECEIPT> --receipt <PRIVATE_B1_RECEIPT> --receipt <PRIVATE_B2_RECEIPT> --receipt <PRIVATE_B4_RECEIPT> --receipt <PRIVATE_B5_RECEIPT> --out <NEW_PRIVATE_AGGREGATE>

The six original receipt SHA-256 digests are available under owner-private
evidence. The private aggregate's initial readback hash was
`0c62fd2af176b2f3ae3b3b83cf04db3fecbb2bc0c11db6b89827803cd444affd`.
The revised scorer independently recomputed all six file/source/prompt/reply
bindings and wrote a **separate v2** private aggregate with SHA-256
`d69a7a2f4d78fe6676f96621f1f1d6e73b76a53e1fc6433a3a908d35e9205490`.
Neither historical aggregate was overwritten. This is still owner-device
readback, not independent model evaluation or a trusted signature.
These hashes are unkeyed integrity checks, not signatures or independent
proof validation.

## Nonnegotiable gates

- **No untrusted Lean execution here.** A generated text might contain
  malicious tactics or a weakened target; only an isolated authorized
  independent checker with exact trusted statement comparison can accept
  proofs.
- **Not a sealed test.** Upstream Putnam statements are public; training
  contamination has not been ruled out.
- **No model diagnosis beyond the observed slice.** Khipu, Goedel and
  Flagship55 were **not evaluated by this six-case run**.
- **No release authorization.** Source hashes, correct abstention counting
  and a green CI do not qualify mathematical correctness, training,
  production deployment, new revenue claims or publication of weights.

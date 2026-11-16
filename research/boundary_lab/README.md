# SZL Boundary Assurance v0.2

**Research library and diagnostics. No training, release, or provider-mutation authority.**
This extends the earlier private Boundary Lab without changing the locked-eight
formulas, existing `referee.py`, rewards, proof admission, or the private Brain.

## Components

* `boundary_lab.py`: original bounded graph/queue/shard/sequence witnesses and 28
  review-required synthetic records. Source and dataset identities: `sources.json`.
* `support_memory.py`: local SQLite event ledger and OR-of-AND support DAG. Revocation
  or expiry invalidates a support path; alternative valid support may preserve a
  conclusion. Superseding a source does not silently rebind old conclusions.
  Expected-head compare-and-set and transactions reject concurrent stale writers;
  history is not overwritten. Events contain identities/digests, not private text.
* `evaluation_contract.py`: frozen per-case/arm/seed coverage, model/task identities,
  token caps and denominators. Missing/failed attempts make rates unavailable, not
  zero. Correct supported answers and unsupported acceptance are distinct metrics.
* `verifier_search.py`: four static, trusted graph candidates compared against a
  frozen Kahn oracle on 4,101 explicit cases. Incorrect candidates are rejected
  before timing. Five serial same-process sweeps are diagnostics, not a general
  performance or energy claim. No arbitrary candidate code is loaded.
* `SupportBoundary.lean`: five elementary OR-of-AND support-algebra propositions,
  separate from the locked registry. Kernel execution and axiom disclosure are
  recorded separately; Python/SQLite refinement is not established.
* `assurance_demo.py`: offline replay, negative controls, and a handles-only
  review projection for proposed Brain/Anatomy/Hatun integration. No existing
  public API, autonomous controller or source publisher is modified.
* `local_diagnostic.py`: opt-in local-only integration smoke test against the
  already-installed, explicitly pinned local model alias. Verifies its local
  manifest/blob bytes before calls; no pull/install/paid endpoint. Four known
  synthetic tasks across four arms, two CPU threads, GPU disabled, 16 calls maximum,
  180-second loop budget, no retry. This is NOT the independent 200-case pilot.

## Reproduce offline

From this directory:

```sh
python -B -m unittest -v
python -B assurance_demo.py --out /a/new/private/output/directory
```

The target directory must be new. Demo measurements and databases must remain
outside source control. To check the research algebra, use an already installed
reviewed Lean toolchain to compile `SupportBoundary.lean`; record toolchain and
file hashes and inspect all five `#print axioms` results. Do not change the locked
count or admit the Python fixtures into the kernel-accepted corpus.

## Trust boundaries

A support state is consistency under supplied premises, NOT factual truth. Rights
and clock values are supplied by a trusted caller. A hash chain needs an externally
retained trusted head to detect wholesale rewriting; it is not a signature or
independent witness. The SQLite connection serializes this ledger's writes only;
external actions/hydration must recheck the observed head at their own commit/use
boundary. This prototype does not provide distributed fencing or BFT consensus.

The final evaluator must be pinned outside a candidate writer's authority. Running
trusted in-process candidates is not a sandbox for adversarial generated code.
The local inference path checks alias metadata before and after; Ollama does not
attest a per-request model digest. Tokenizer identity is bounded by the full GGUF
blob containing it, not a separately hashed tokenizer file. Prompt arms share caps,
not necessarily realized token counts. Real model outcomes do not establish a
causal improvement on four developer-authored cases.

The new CI workflow is read-only, path-scoped, and runs offline tests only. It does
not invoke the local inference runner or modify the existing proof/referee CI.

## Remaining acceptance gates

Independent 200-case task authoring/sealing, dataset rights/lineage admission,
revision-bound matched-budget model evaluation, live Brain/Anatomy/Hatun integration,
untrusted-code isolation, refinement proof, independent witness and production
qualification remain separate. No efficacy, novelty or universal theorem about a
production runtime is asserted by these software checks.

Source license: repository Apache-2.0. First-party, AI-assisted research code. No
third-party source or raw training dataset rows are copied into this package.

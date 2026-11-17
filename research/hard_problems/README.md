# SZL Hard-Math Proving-Ground Challenge Board

**Stage:** SOURCE-BOUND METADATA INDEX + SYNTHETIC CONTROL TESTS. This is not a trained Flagship55, model evaluation, new mathematical proof, or automatic RLVR data admission.

## Research-source inventory, pinned November 17, 2026

Source | Immutable source revision | Indexed Lean file pointers
--- | --- | ---:
[PutnamBench](https://github.com/trishullab/PutnamBench) | a635813f5edf297d928f9bd5ef8324a26bdde09c | **672**
[Formal Conjectures](https://github.com/google-deepmind/formal-conjectures) | 6751c0f043985ac6647db28a45a63afdf21acffe | **1,861**
[OpenQED](https://openqed.org/) | Mutable website; no immutable source pin | **10 topic references**

**Total: 2,533 Git-file references plus 10 topic labels.** This is neither 2,533 unsolved problems nor exhaustive coverage of world mathematics. Git-tree reads were complete and not truncated; the archive records exact returned tree SHA, raw source-response SHA-256, each Git blob SHA-1, byte size, path, and immutable source commit. No problem statement, solution, proof body, training dataset, or executable third-party code is copied into the index.

PutnamBench includes 672 Lean formalizations across 1962–2025, with all **12 identifiers from 2025 A1–B6**. These are solved competition tasks, **not open mathematical conjectures**. 2025 A5 and B6 are prioritized as challenging *benchmark* tests, but no original problem proof or independent solving claim was generated. [The MAA archive](https://maa.org/maa-putnam-archive/) has official problems and solutions. [Numina's Putnam 2025](https://github.com/project-numina/Numina-Putnam2025) documents existing Lean-checked solutions. The 2026 Putnam competition has not yet occurred as of this snapshot. PutnamBench's research paper reports Apache-2.0 Lean formalizations and separate MAA permission for informal statements. This catalog republishes *neither* the informal statements nor benchmark answers.

Formal Conjectures contains **1,861 source files** in the selected FormalConjectures tree. Some may encode open, solved, conditionally resolved, refuted, or superseded claims. **No open/unsolved status is automatically inferred from the repo name or filename.** A source file is also not proof that the formal statement matches the informal problem.

The curated 10-name board points to Riemann hypothesis, P versus NP, Navier–Stokes existence/smoothness, Birch–Swinnerton-Dyer, Yang–Mills mass gap, Hodge conjecture, Collatz, Goldbach, twin primes, and Legendre's conjecture. It is a **research reading queue**, not a contemporaneous authoritative unsolved-status attestation.

## Exact-source Putnam 2025 preflight

The [source-byte integrity harness](PUTNAM2025_SOURCE_PREFLIGHT.md) verifies the
12 pinned 2025 Lean source files locally without executing them. Its readback
found 18 upstream sorry placeholders, six solution abbreviations and zero
model evaluations. The real files and detailed readback remain private;
GitHub contains only the auditable validator, tests and scope documentation.

## Bound local model evaluation path

The [one-shot local model probe](LOCAL_MODEL_PROBE.md) now supports an offline
source-bound prompt plan and an optional, bounded localhost-only inference
attempt with exact model digest checks. Its raw prompts/responses are private
and its classifications are **not mathematical proof scores**. In the initial
2026-11-17 Goedel A1 attempt, the existing Ollama metadata endpoint timed
out; **no generated model response was observed**. No restart, remote fallback,
paid job, model modification or production qualification occurred.

## Existing first-party Putnam semantic gap

The owner-controlled [Lutar Putnam 2025 A1 file](https://github.com/szl-holdings/lutar-lean/blob/bcfc25badcd73d6b6f013853c1fb8bf384b2e460/Lutar/Putnam/P_A1.lean)
contains valuable partial mathematical lemmas, **but** the tracked theorem
named putnam_A1_correct concludes only True under elementary assumptions;
that is not the original eventual-coprimality statement. This is a
**formal-to-informal equivalence gap**, not evidence the competition problem
has been proved by that theorem. The first-party Putnam sources therefore
enter this board as statement/lemma **review references**, never as
automatic correct benchmark answers. Each claimed result needs its exact
formal target, hypotheses and independent kernel replay compared with the
original problem by a qualified reviewer.

## Existing SZL authority and Flagship55

The Khipu [Flagship55 architecture](https://github.com/szl-holdings/szl-khipu/blob/511a1b69b31c26567fa757838e97f16acf3dc3d1/docs/FLAGSHIP55_KHIPU_FABRIC.md) proposes YACHAY teacher, WILLAY guide and KHIPU skeptic specialist adapters. **No such adapters have been trained/embedded here**, and no model inference occurs in this catalog. Preserve the eight locked Lutar theorem IDs, specific hypotheses and conditional scopes. Unconditional Lambda uniqueness under bare A1–A5 is false as stated; learned confidence cannot upgrade it to PROVEN.

This repository's existing Lean referee, source-controller registry and admission gate retain ownership. Its accepted-looking elaboration reports are NOT independent hostile-code verification. This new catalog never invokes that referee for externally sourced Lean and does not send index entries to admission, GRPO, Forge training or Salad.

## Fully offline commands

Validate the checked-in catalog and run targeted tests:

    python research/hard_problems/challenge_index.py validate --catalog research/hard_problems/catalog.v1.json
    python -B -m unittest discover -s tests -p test_hard_problem_catalog.py -v

For a future refresh, re-pin both external Git commits in reviewed source, export complete source-specific Git-tree responses to private local JSON files, and invoke the offline builder with a fresh output path. The builder has **no GitHub API client, network access, dependency installation, model or Lean execution**. A source tree whose pagination/truncation is incomplete is a HOLD. All readbacks and rights checks must be repeated before distributing or using additional content.

    python research/hard_problems/challenge_index.py build --putnam-tree C:\PRIVATE\putnam-tree.json --conjectures-tree C:\PRIVATE\conjectures-tree.json --output C:\PRIVATE\new-catalog.json

The synthetic fixture contains exactly three *non-model* controls: ABSTAIN on 2025 A5; an intentionally fake proof containing a sorry placeholder on 2025 B6; and an unsupported proof claim on a source-bound conjecture reference. It verifies that a fake proof is rejected, a claimed proof remains UNVERIFIED, and an abstention does not count as a theorem solved. Write results only to an unused, owner-controlled private path:

    python research/hard_problems/challenge_index.py observe --catalog research/hard_problems/catalog.v1.json --submissions research/hard_problems/synthetic-submissions.v1.json --output C:\PRIVATE\control-observation.json

A later REAL MODEL_RESPONSE batch must bind an immutable model revision and preserve the full private responses separately. This indexer records hashes and honest categorization only; actual proof candidates require *independently replayed* source/predicate-checked Lean proofs in an OS-isolated, credential-free worker. No result from this offline classifier earns a successful mathematical score, model-qualification badge, or new training right. The synthetic run has **zero independent proof checks and model quality UNAVAILABLE**.

## Rules and limits

- Public source metadata is not copyright, privacy, licensing or training-data approval. No third-party source statements/solutions were imported into gradients.
- Separate **competition benchmarks with known solutions** from **research conjectures whose status requires independent verification**; avoid using a purported open problem as an answerable labeled training target.
- The source pin and Git blob identity establish referential integrity only: Git SHA-1 and SHA-256 are not signatures or an independent attestation.
- Never reward blanket abstention as correctness; on an empty verified denominator, quality is **UNAVAILABLE**, not 0% or 100%.
- Do not fabricate open-problem breakthroughs based on valid JSON, an output filename, unsupported code, a Lean sorry, a printed report, or a model's confidence.
- No new paid compute, training, replication, publication, license override, controller, watcher, provider mutations or protected-branch bypass is authorized here.

# Lutar A1–A5 curriculum — first-party synthetic, review required

This directory puts **Lutar's actual A1–A5 mathematics into the SZL model training
intake** without pretending that a synthetic example is a Lean proof, or that
passing CI is permission to spend GPU capacity or publish model weights.

## Exact canonical source

* GitHub: szl-holdings/lutar-lean @ `c2ca813fca00ecf58bcc5f505f2aa4237fbf2481`
  (protected-main snapshot, not a moving branch).
* `Lutar/Axioms.lean` blob `fc922178ca30d588dbb330dc834428bcfca36367`
* `Lutar/Invariant.lean` blob `4a418c631d9556d418e6aaa47611014855050d2c`
* Lean 4 / Mathlib toolchain version: `leanprover/lean4:v4.35.0`

These values are explicit source pins, not remotely verified signatures.
If canonical definitions change, review the mathematics, generator,
counterexamples, training impact and dataset admission separately. **Do not
automatically roll forward source SHA or reuse a previous admission receipt.**

## Included mathematical lessons

The generator covers the standard equal-weight geometric mean
`Lambda_2(a,b) = sqrt(a*b)` on exact integer-square products. Its exercises
are deliberately finite arithmetic fixtures; this is not a general verified
real-arithmetic oracle or a machine-checked Lean proof.

Ten families contain A1 monotonicity, A2 degree-one homogeneity, A3 diagonal
normalization, A4 upper boundedness, A5 axis-permutation invariance, a
counterexample to unconditional uniqueness (the max aggregator satisfies A1–A5
but differs from the geometric mean), fixed-unequal-weight permutation
counterexamples, fail-closed mandatory release evidence, strictly conditional
admission, and the zero-input boundary.

**A1–A5 do not imply unconditional uniqueness of Lambda.** A fixed unequal
weight vector also does NOT support arbitrary input-axis permutations by
itself. These negative examples are essential: their false alternatives
must never be taught as facts. The Lutar PR #369 gated-Lambda bridge is a
separate experimental proof surface; this corpus does not promote it or alter
the locked-eight formula register.

## Artifacts and training boundary

* `train.jsonl`: 160 distinct first-party synthetic SFT chat records.
* `holdout.jsonl`: 80 distinct developer-held diagnostic cases, drawn from
  disjoint numerical instances. It is **not an independent external holdout**.
* `manifest.json`: exact file SHA-256 digests, count, source pins and
  `training_authority: NONE`.
* `lutar_axioms.py`: stdlib-only deterministic generator and an optional
  exact-JSON numerical reward (`exact_numeric_reward`). This reward is NOT
  a Lean kernel referee or permission to add its outputs to proof admission.

Each row carries its family, source commit, numerical witness, synthetic
maturity and explicit `CANDIDATE_ONLY` status. Models may learn the format;
a numeric test cannot establish original mathematical discovery or general
proof competence. No raw private Brain, lab, patient, or third-party dataset
is included. The generator makes no API requests and never reads credentials.

## Reproduction and cross-repo SFT validation

From the repository root:

```sh
python3 -B curriculum/lutar_axioms.py --check
python3 -B -m unittest discover -s tests -p 'test_lutar_curriculum.py' -v
# In a separate checkout of szl-forge, use its EXISTING validator:
python3 /path/to/szl-forge/tools/validate_sft_dataset.py \
  curriculum/train.jsonl --min-examples 32 \
  --disjoint-from curriculum/holdout.jsonl --json
```

The Forge dataset validator accepts structurally sound, disjoint chat inputs.
This alone **does not satisfy** `szl-forge/training/launch_contract.py`:
an operator-controlled admission receipt, immutable dataset and student model
revisions, independently reviewed rights/licensing, a held-out evaluation
contract, budget, and an authorized training window are still required.
The training launcher MUST NOT be modified to skip these holds.

## Future governed training

After independent review, publish a new immutable, explicitly licensed dataset
revision via its approved publisher. Create a matching operator-controlled
`szl.forge.training-admission/v1` receipt. Run the existing Forge SFT
preflight against that revision and a separately sealed evaluation set,
then execute a bounded local-only QLoRA/LoRA run on an approved GPU. Retain
the exact model, dataset, teacher (if any), sampler seed, toolchain, receipts,
optimizer details, energy measurement when available, and a no-publication
marker. Promote to HF **only** through the model release gate after
independent evaluation, signature verification, and live revision readback.

This PR is **curriculum integration**, not a training launch and not a
production deployment.

# lean-rlvr-proving-ground domain leader study r1 (propose-only)

Date: 2026-11-25. Method: web-verified leader landscape + governing-seat ratification (Kimi nonce T13-RULING-20261124-K1). Study pinned to lean-rlvr-proving-ground HEAD c0b3af2ea6b92b6c7d7707401efbedaf8d4a2058, fetched 2026-11-25. This card is documentation only; it changes no code, CI, config, or existing PR status. All absorb actions are FUTURE PROPOSALS (non-authorizing); implementation and merges remain separately reviewed and gated. L Conjecture 1: OPEN (advisory, never a closed theorem). No speedup, energy, or proven-trust claims; upstream performance claims are labeled as upstream claims only. No unverified signing, attestation, or provenance-level claims; this study verifies nothing about this repo's artifacts.

## Domain: Lean-kernel-checked proof search as an RLVR environment, where the kernel referees candidate proofs, honesty-shaped rewards preserve abstention on conjecture-class targets, and corpus-v2 admission remains fail-closed.

## Leaders studied (web-verified 2026-11-25)
1. Lean 4 (https://github.com/leanprover/lean4) - moat: Its elaborator and trusted kernel provide the authoritative proof-checking boundary that makes Lean compilation meaningful as a verification signal.
2. TRL (https://github.com/huggingface/trl) - moat: It provides a widely used Hugging Face training library for supervised fine-tuning and preference or reward-based post-training workflows.
3. verifiers (https://github.com/willccbb/verifiers) - moat: It focuses on environments and rubric-based verification for evaluating and training language models on checkable tasks.

## Absorb actions (FUTURE PROPOSALS, non-authorizing)
1. (Lean 4) Propose a documentation-only design note reviewing how kernel acceptance, elaboration failure, timeout, and abstention should remain distinct evidence labels in the proof-referee loop. Cost: doc-only, approximately 0.5-1 maintainer day; limit: note only, no code, no infra changes.
2. (TRL) Propose a documentation-only review mapping TRL-style reward-training concepts to this repo's honesty-shaped reward doctrine, explicitly separating verified proof success, partial ABSTAIN credit, and unsupported reward or proof-yield claims. Cost: doc-only, approximately 0.5-1 maintainer day; limit: note only, no code, no infra changes.
3. (verifiers) Propose a documentation-only design note comparing verifier environment and rubric interfaces with the repo's referee outputs and corpus-v2 fail-closed admission evidence, without proposing a measured benefit. Cost: doc-only, approximately 0.5-1 maintainer day; limit: note only, no code, no infra changes.
4. Baseline preserve honestly: preserve the Lean kernel as the proof referee, keep L Conjecture 1 open and advisory, retain partial ABSTAIN labeling only for its defined conjecture-class case, keep corpus-v2 admission fail-closed, and require evidence for every reward-shaping or proof-yield claim.

## Do not do (per governing seat)

Do not merge, bypass the signature wall, or claim implementation beyond this card.

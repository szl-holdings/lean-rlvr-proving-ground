/-
SZL proving-ground RLVR — kernel-referee sandbox probes, v0 (core-only).

Fail-closed doctrine: every probe here is sorry-free, axiom-free and
kernel-checked by lake build in CI. Statements are honest concrete
fragments of the atlas entries they cite (cleared of denominators where
noted); the natural-language atlas lives in probes/atlas/. This file is
the seed set; corpus v2 grows ONLY from lake-build-accepted attempts
(kernel-referee admission rule, szl-forge PR #746).
-/

/-- TH_V18_04 (Egyptian Horus-Eye weight sum), cleared x64:
1/2 + 1/4 + 1/8 + 1/16 + 1/32 + 1/64 = 63/64. -/
theorem horus_cleared : 32 + 16 + 8 + 4 + 2 + 1 = 63 := by decide

/-- TH_V18_03 (Kraft inequality, code lengths {1,2,3,3}), cleared x8:
complete binary prefix code: sum 2^{-l_i} = 1. -/
theorem kraft_cleared : 4 + 2 + 1 + 1 = 8 := by decide

/-- F18 (Reed-Solomon Singleton bound), concrete RS(10,6) fragment:
d <= n - k + 1 = 5. Arithmetic fragment only, labeled honestly. -/
theorem rs_singleton_concrete : (10 - 6) + 1 = 5 := by decide

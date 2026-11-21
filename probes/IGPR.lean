/-! Research seed: conditional Nat-millipoint arithmetic, not a live scorer.
`referee.py` observes verdicts, not tactic positions or invariant margins.
`rewards.py` gives every rejected proof zero; none of the definitions below
run in classification, curriculum selection, GRPO, or admission. -/

namespace SZL.RLVR.IGPR

/-- Credited/off-target abstentions split the one ABSTAIN verdict by probe class.
`failed j` is an imagined first-error annotation, not a new referee verdict. -/
inductive Outcome where
  | accepted
  | abstainCredited
  | abstainOffTarget
  | rejected
  | failed (firstError : Nat)

/-- Today's reward levels ×1000: PROOF_ACCEPTED; ABSTAIN on/off conjecture;
all SORRY_PRESENT, BUILD_ERROR, AXIOM_SMUGGLED and NATIVE_DECIDE rejections. -/
def incumbent : Outcome → Nat
  | .accepted => 1000
  | .abstainCredited => 500
  | .abstainOffTarget => 100
  | .rejected | .failed _ => 0

/-- In the hypothetical model only, a failing trace gets dense process credit.
This definition does not enforce a cap; the theorems state the needed bounds. -/
def researchBase : Outcome → Nat
  | .failed j => 100 + 10 * j
  | o => incumbent o

def score (margin : Outcome → Nat) (o : Outcome) : Nat := researchBase o + margin o

theorem accepted_strictly_dominates_failed (margin : Outcome → Nat) (j : Nat)
    (hj : j ≤ 89) (hm : margin (.failed j) ≤ margin .accepted) :
    score margin (.failed j) < score margin .accepted := by
  simp only [score, researchBase, incumbent]
  omega

theorem first_error_monotone (margin : Outcome → Nat) {j k : Nat} (hjk : j < k)
    (hm : margin (.failed j) = margin (.failed k)) :
    score margin (.failed j) < score margin (.failed k) := by
  simp only [score, researchBase]
  omega

theorem score_bounded (margin : Outcome → Nat) (M : Nat) (hM : ∀ o, margin o ≤ M)
    (o : Outcome) (hj : ∀ j, o = .failed j → j ≤ 89) : score margin o ≤ 1000 + M := by
  have hm := hM o
  cases o with
  | failed j =>
    have h := hj j rfl
    simp only [score, researchBase]
    omega
  | accepted | abstainCredited | abstainOffTarget | rejected =>
    simp only [score, researchBase, incumbent]
    omega

theorem score_nonnegative (margin : Outcome → Nat) (o : Outcome) :
    0 ≤ score margin o := Nat.zero_le _

/-- Tight boundary: at equal zero margins, `j=90` ties acceptance and `j=91`
outscores it; neither observation earns any partial credit from the incumbent. -/
theorem ceiling_counterexample :
    score (fun _ => 0) (.failed 89) < score (fun _ => 0) .accepted ∧
    score (fun _ => 0) (.failed 90) = score (fun _ => 0) .accepted ∧
    score (fun _ => 0) .accepted < score (fun _ => 0) (.failed 91) ∧
    incumbent (.failed 90) = 0 ∧ incumbent (.failed 91) = 0 := by decide

/-- Even with `j≤89`, arbitrary margins can reverse both orderings. -/
theorem margin_counterexample :
    let margin : Outcome → Nat := fun | .failed 88 => 100 | _ => 0
    score margin .accepted < score margin (.failed 88) ∧
    score margin (.failed 89) < score margin (.failed 88) := by decide

end SZL.RLVR.IGPR

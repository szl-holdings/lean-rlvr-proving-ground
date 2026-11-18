/-
SZL 54-hour proving ground: core-only ancient-math *cleared arithmetic*
witnesses. These are NOT formalizations of the original papyri, Euclid's
complete geometric proofs or any unsolved scientific problem.
No Mathlib, sorry, new axioms, native_decide or unsafe evaluation.
-/
namespace SZLProving54

/-- Horus-Eye 63/64 sum after clearing the x64 denominator. -/
theorem horus_sum_cleared :
    (32 + 16 + 8 + 4 + 2 + 1 : Nat) = 63 := by decide

/-- Toy 2/5=1/3+1/15 after clearing denominator 15. -/
theorem rhind_two_fifths_cleared :
    (2 * 3 : Nat) = 5 + 1 := by decide

/-- Toy 2/7=1/4+1/28 after clearing denominator 28. -/
theorem rhind_two_sevenths_cleared :
    (2 * 4 : Nat) = 7 + 1 := by decide

/-- Toy 2/13=1/8+1/52+1/104 after clearing denominator 104. -/
theorem rhind_two_thirteenths_cleared :
    (2 * 8 : Nat) = 13 + 2 + 1 := by decide

/-- Finite 3/4/5 integer-square check, not general geometry. -/
theorem euclid_three_four_five :
    (3 * 3 + 4 * 4 : Nat) = 5 * 5 := by decide

/-- Finite 5/12/13 integer-square check, not general geometry. -/
theorem euclid_five_twelve_thirteen :
    (5 * 5 + 12 * 12 : Nat) = 13 * 13 := by decide

/-- Equality transitivity; no new project assumptions. -/
theorem equality_transitive {a b c : Nat}
    (ab : a = b) (bc : b = c) : a = c :=
  ab.trans bc

/-- Fixed x=(1,4) equal-weight geometric-mean toy arithmetic. -/
theorem lambda_two_axes_example : (2 * 2 : Nat) = 1 * 4 := by decide

/-- Distinct max witness, not the full Lutar axiom-system proof. -/
theorem lambda_not_max_instance : (2 : Nat) ≠ 4 := by decide

/-- An incomplete known denominator cannot equal a complete one. -/
theorem incomplete_count_ne_total {observed total : Nat}
    (h : observed < total) : observed ≠ total :=
  Nat.ne_of_lt h

end SZLProving54

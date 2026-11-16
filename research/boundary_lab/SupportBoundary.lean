/- Research-only support algebra. No change to locked formulas or corpus admission.
   This formalizes OR-of-AND support, NOT Python/SQLite refinement, source truth,
   clock authenticity, transaction durability, authorization, or deployed behavior. -/
namespace SZL.BoundaryResearch

def ClauseValid {α : Type} (active : α → Prop) (clause : List α) : Prop :=
  ∀ x, x ∈ clause → active x

def Supported {α : Type} (active : α → Prop) (clauses : List (List α)) : Prop :=
  ∃ clause, clause ∈ clauses ∧ ClauseValid active clause

def AfterWithdrawal {α : Type} (active : α → Prop) (removed : α) : α → Prop :=
  fun x => active x ∧ x ≠ removed

theorem support_monotone {α : Type} {before after : α → Prop}
    {clauses : List (List α)} (h : ∀ x, before x → after x)
    (hs : Supported before clauses) : Supported after clauses := by
  obtain ⟨clause, hc, ha⟩ := hs
  exact ⟨clause, hc, fun x hx => h x (ha x hx)⟩

theorem alternative_survives {α : Type} {active : α → Prop} {removed : α}
    {clauses : List (List α)} {clause : List α}
    (hc : clause ∈ clauses) (ha : ClauseValid active clause)
    (hn : ∀ x, x ∈ clause → x ≠ removed) :
    Supported (AfterWithdrawal active removed) clauses := by
  exact ⟨clause, hc, fun x hx => ⟨ha x hx, hn x hx⟩⟩

theorem withdrawal_cannot_create_support {α : Type} {active : α → Prop}
    {removed : α} {clauses : List (List α)}
    (hs : Supported (AfterWithdrawal active removed) clauses) : Supported active clauses := by
  exact support_monotone (fun _ hx => hx.1) hs

theorem all_paths_hit_removed_blocks {α : Type} {active : α → Prop}
    {removed : α} {clauses : List (List α)}
    (hit : ∀ clause, clause ∈ clauses → removed ∈ clause) :
    ¬ Supported (AfterWithdrawal active removed) clauses := by
  intro hs
  obtain ⟨clause, hc, ha⟩ := hs
  exact (ha removed (hit clause hc)).2 rfl

theorem no_alternatives_no_support {α : Type} (active : α → Prop) :
    ¬ Supported active [] := by
  intro hs
  obtain ⟨clause, hc, _⟩ := hs
  cases hc

end SZL.BoundaryResearch

#print axioms SZL.BoundaryResearch.support_monotone
#print axioms SZL.BoundaryResearch.alternative_survives
#print axioms SZL.BoundaryResearch.withdrawal_cannot_create_support
#print axioms SZL.BoundaryResearch.all_paths_hit_removed_blocks
#print axioms SZL.BoundaryResearch.no_alternatives_no_support
